from . import models as m
from . import permissions as p


def summary(obj):
    if isinstance(obj, m.StudentDocument):
        return {
            "id": str(obj.pk),
            "document_type_id": str(obj.document_type_id),
            "document_number": obj.document_number,
            "issue_date": obj.issue_date,
            "expiry_date": obj.expiry_date,
            "status": obj.verification_status,
            "verified_at": obj.verified_at,
        }
    if isinstance(obj, m.CertificateRequest):
        return {
            "id": str(obj.pk),
            "request_number": obj.request_number,
            "certificate_type_id": str(obj.certificate_type_id),
            "requested_at": obj.requested_at,
            "status": obj.request_status,
            "issued_at": obj.issued_at,
            "certificate_number": obj.certificate_number,
        }
    if isinstance(obj, m.StudentExit):
        return {
            "id": str(obj.pk),
            "enrolment_id": str(obj.enrolment_id),
            "exit_type": obj.exit_type,
            "exit_date": obj.exit_date,
        }
    if isinstance(obj, m.CertificateType):
        return {
            "id": str(obj.pk),
            "label": obj.certificate_name,
            "certificate_code": obj.certificate_code,
            "certificate_name": obj.certificate_name,
            "is_active": obj.is_active,
        }
    if isinstance(obj, m.FileObject):
        return {"id": str(obj.pk), "deleted": obj.deleted_at is not None}
    raise ValueError("Unsupported presentation model")


def documents(actor):
    return p.scoped(m.StudentDocument, actor, "view_documents", "view_own_document")


def certificates(actor):
    qs = p.scoped(m.CertificateRequest, actor, "view_certificates", "view_own_document")
    for cap in ["review_certificate", "approve_certificate", "issue_certificate"]:
        qs = qs | p.scoped(m.CertificateRequest, actor, cap)
    return qs.distinct()


def exits(actor):
    return p.scoped(m.StudentExit, actor, "view_exit", "view_own_document")
