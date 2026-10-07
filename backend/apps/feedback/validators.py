from decimal import Decimal,InvalidOperation
from rest_framework.exceptions import ValidationError

def decimal(value):
    if isinstance(value,(bool,float)):raise ValidationError('Use an exact decimal string.')
    try:value=Decimal(value)
    except (InvalidOperation,TypeError,ValueError):raise ValidationError('Invalid decimal.')
    if not value.is_finite():raise ValidationError('Finite decimal required.')
    return value

def answer(item,data):
    if not isinstance(data,dict):raise ValidationError('Answer must be an object.')
    kind=item['response_type'];allowed={str(c['id']) for c in item['choices']}
    if kind=='SINGLE_CHOICE':
        if set(data)!={'choice_id'} or str(data['choice_id']) not in allowed:raise ValidationError('Select one permitted choice.')
        return {'feedback_choice_id':int(data['choice_id'])}
    if kind=='MULTIPLE_CHOICE':
        values=data.get('choice_ids')
        if set(data)!={'choice_ids'} or not isinstance(values,list) or not values or len(values)>100 or len({str(x) for x in values})!=len(values) or any(str(x) not in allowed for x in values):raise ValidationError('Select unique permitted choices.')
        return {'choices':[int(x) for x in values]}
    if kind=='RATING':
        if set(data)!={'numeric_score'}:raise ValidationError('Provide only a numeric score.')
        score=decimal(data['numeric_score']);low=decimal(item['rating_min']);high=decimal(item['rating_max']);step=decimal(item['rating_step'])
        if not low<=score<=high or (score-low)%step!=0:raise ValidationError('Rating is outside the configured range or step.')
        return {'numeric_score':score}
    if kind=='TEXT':
        text=data.get('text_response')
        if set(data)!={'text_response'} or not isinstance(text,str) or not text.strip() or len(text)>item['text_limit'] or any(ord(c)<32 and c not in '\n\r\t' for c in text):raise ValidationError('Text is blank, too long or contains control characters.')
        # Plain text only. Clients escape HTML; never mark this string as safe.
        return {'text_response':text.strip()}
    raise ValidationError('Unsupported response type.')
