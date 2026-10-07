import csv
import io
from django.db import transaction
from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from .serializers import SERIALIZERS


def safe_cell(value):
    value='' if value is None else str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r','\n')) or value.startswith(('\t','\r','\n')) else value


class BulkOperations:
    @extend_schema(responses={200:str},description='CSV template. Parent identifiers are authorized API IDs; is_active and audit fields are excluded.')
    @action(detail=False,methods=['get'],url_path='import-template')
    def import_template(self,request):
        from .catalogue import writable
        stream=io.StringIO();csv.writer(stream).writerow([self.model._meta.pk.name,*[f.attname for f in writable(self.model) if f.name!='is_active']])
        response=HttpResponse(stream.getvalue(),content_type='text/csv; charset=utf-8')
        response['Content-Disposition']='attachment; filename="organization-template.csv"'
        response['Cache-Control']='no-store'
        return response

    @extend_schema(responses={200:str},description='Scoped CSV export, maximum 5000 rows. Formula-leading cells are escaped.')
    @action(detail=False,methods=['get'],url_path='export')
    def export_csv(self,request):
        rows=self.filter_queryset(self.get_queryset())
        if rows.count()>5000:raise ValidationError('Narrow filters to at most 5000 rows.')
        fields=[f.attname for f in self.model._meta.fields]
        stream=io.StringIO();writer=csv.writer(stream);writer.writerow(fields)
        for row in rows.iterator():writer.writerow([safe_cell(getattr(row,f)) for f in fields])
        response=HttpResponse(stream.getvalue(),content_type='text/csv; charset=utf-8')
        response['Content-Disposition']='attachment; filename="organization.csv"'
        response['Cache-Control']='no-store'
        return response

    @extend_schema(request=dict,responses={200:dict,400:dict},description='JSON {csv: string, dry_run: boolean}. At most 200 rows/256 KB; entire batch atomic. Parent ID inputs use scoped API IDs. Existing records require their primary-key column; code collisions are errors, never implicit upserts.')
    @action(detail=False,methods=['post'],url_path='import')
    def import_csv(self,request):
        if not isinstance(request.data,dict) or set(request.data)-{'csv','dry_run'}:raise ValidationError('Use csv and dry_run fields.')
        content=request.data.get('csv');dry=request.data.get('dry_run',True)
        if not isinstance(content,str) or len(content.encode('utf-8'))>262144 or type(dry) is not bool:raise ValidationError('Invalid CSV or dry_run flag; maximum 256 KB.')
        reader=csv.DictReader(io.StringIO(content))
        if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)):raise ValidationError('Missing or repeated columns.')
        rows=[]
        try:
            for row in reader:
                rows.append(row)
                if len(rows)>200:raise ValidationError('Maximum 200 rows.')
        except csv.Error:
            raise ValidationError('Malformed CSV.')
        if not rows:raise ValidationError('No records found.')
        errors=[];created=[]
        with transaction.atomic():
            for number,row in enumerate(rows,2):
                try:
                    if None in row or any(v is None for v in row.values()):raise ValidationError('Column count does not match header.')
                    pk=row.pop(self.model._meta.pk.name,None)
                    obj=None
                    if pk:
                        if not pk.isascii() or not pk.isdigit() or len(pk)>10 or not 1<=int(pk)<2**self.model._meta.pk.bits:
                            raise ValidationError('Invalid record ID.')
                        from .selectors import scoped
                        obj=scoped(self.model,request.user,write=True).filter(pk=pk).first()
                        if obj is None:raise ValidationError('Record is not in your management scope.')
                    for field in self.model._meta.fields:
                        key=field.attname
                        if key not in row:continue
                        if row[key]=='' and field.null:row[key]=None
                        elif field.is_relation:
                            try:row[key]=int(row[key])
                            except (ValueError,TypeError):raise ValidationError({key:'Use a parent ID from your authorized catalogue.'})
                    serializer=SERIALIZERS[self.model]['update' if obj else 'create'](obj,data=row,partial=bool(obj),context=self.get_serializer_context())
                    serializer.is_valid(raise_exception=True)
                    saved=serializer.save();created.append(saved.pk)
                except Exception as error:
                    from rest_framework.exceptions import APIException
                    if not isinstance(error,APIException):raise
                    errors.append({'row':number,'errors':error.detail})
            if errors or dry:transaction.set_rollback(True)
        report=io.StringIO();writer=csv.writer(report);writer.writerow(['row','errors'])
        for item in errors:writer.writerow([item['row'],safe_cell(str(item['errors']))])
        return Response({'dry_run':dry,'committed':not dry and not errors,'rows':len(rows),'errors':errors,'error_report_csv':report.getvalue()},status=400 if errors else 200)
