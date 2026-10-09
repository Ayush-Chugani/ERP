"""Authenticated upload and download of private files (certificates, student documents, evidence, attachments)."""
import hashlib
import io
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import active_principal, client_ip
from app.config import get_settings
from app.core.errors import Forbidden, Invalid, NotFound
from app.core.ratelimit import local_limiter
from app.db.session import get_db
from app.models.documents_exit import FileObject
from app.rbac.engine import Principal
from app.resources import crud
from app.resources.registry import build_registry
from app.services import audit
from app.storage import get_storage

router = APIRouter(prefix="/files", tags=["Files"])
ALLOWED = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
LEVELS = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "HIGHLY_RESTRICTED")


def sniff(data: bytes, ext: str) -> str:
    """Validate that the bytes really are what the extension claims; returns the canonical MIME type."""
    if ext == "pdf":
        if not data.startswith(b"%PDF-"):
            raise Invalid("The file is not a valid PDF.")
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise Invalid("Encrypted PDFs are not accepted.")
            len(reader.pages)
        except Invalid:
            raise
        except Exception:  # noqa: BLE001 - any parser failure means the file is unusable
            raise Invalid("The PDF is damaged or unreadable.") from None
    elif ext == "png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise Invalid("The file is not a valid PNG image.")
    elif ext in ("jpg", "jpeg") and not data.startswith(b"\xff\xd8\xff"):
        raise Invalid("The file is not a valid JPEG image.")
    if ext in ("png", "jpg", "jpeg"):
        from PIL import Image, UnidentifiedImageError

        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise Invalid("The image is damaged or unreadable.") from None
    return ALLOWED[ext]


@router.post("", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), confidentiality: str = Form(default="CONFIDENTIAL"),
                 principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    s = get_settings()
    local_limiter.hit(f"upload:{principal.user_id}", "30/60")
    if confidentiality not in LEVELS:
        raise Invalid("Unknown confidentiality level.")
    name = (file.filename or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
    parts = name.lower().rsplit(".", 1)
    ext = parts[1] if len(parts) == 2 else ""
    if ext not in ALLOWED or not name or len(name) > 200:
        raise Invalid("Only PDF, PNG and JPEG files are accepted.", details={"file": ["Unsupported file type."]})
    data = await file.read(s.upload_max_bytes + 1)
    if len(data) > s.upload_max_bytes:
        raise Invalid(f"Files may be at most {s.upload_max_bytes // (1024 * 1024)} MB.", details={"file": ["Too large."]})
    if not data:
        raise Invalid("The file is empty.")
    mime = sniff(data, ext)
    now = datetime.now(UTC)
    key = f"{now:%Y/%m}/{uuid.uuid4().hex}.{ext}"
    get_storage().put(key, data, mime)
    row = FileObject(storage_provider=s.storage_backend, storage_key=key, original_file_name=name[:255], mime_type=mime,
                     file_size_bytes=len(data), checksum_sha256=hashlib.sha256(data).hexdigest(), stored_file_name=key.rsplit("/", 1)[-1],
                     file_extension=ext, confidentiality_level=confidentiality, uploaded_by_user_id=principal.user_id)
    db.add(row)
    db.flush()
    audit.record(db, principal, action="upload", module="DOCUMENT", resource="file_object", record_id=row.file_object_id,
                 after={"name": row.original_file_name, "size": row.file_size_bytes}, request_id=request.state.request_id,
                 ip=client_ip(request))
    db.commit()
    return {"file_object_id": row.file_object_id, "name": row.original_file_name, "size": row.file_size_bytes,
            "mime_type": row.mime_type, "sha256": row.checksum_sha256}


def _referencing_specs():
    """(spec, fk column) for every exposed table holding a foreign key to file_object."""
    out = []
    for spec in build_registry().values():
        for c in spec.columns.values():
            if c.fk_table == "file_object":
                out.append((spec, c.name))
    return out


def can_read_file(db: Session, principal: Principal, file_id: int, uploader: int | None) -> bool:
    if principal.is_superuser or uploader == principal.user_id:
        return True
    for spec, col in _referencing_specs():
        try:
            q, _ = crud.scoped(spec, principal, "READ")
        except Forbidden:
            continue
        hit = db.scalar(select(func.count()).select_from(q.where(spec.col(col) == file_id).order_by(None).subquery()))
        if hit:
            return True
    return False


@router.get("/{file_id}")
def download(file_id: int, request: Request, principal: Principal = Depends(active_principal),
             db: Session = Depends(get_db)):
    row = db.get(FileObject, file_id)
    if row is None or row.deleted_at is not None or not can_read_file(db, principal, file_id, row.uploaded_by_user_id):
        raise NotFound()   # same answer for "missing" and "not yours": no information leak
    try:
        data = get_storage().get(row.storage_key)
    except (FileNotFoundError, OSError):
        raise NotFound("The stored file is missing.") from None
    if hashlib.sha256(data).hexdigest() != row.checksum_sha256:
        raise Invalid("The stored file failed its integrity check.", code="integrity_failure", status=500)
    audit.record(db, principal, action="download", module="DOCUMENT", resource="file_object", record_id=file_id,
                 request_id=request.state.request_id, ip=client_ip(request))
    db.commit()
    safe = row.original_file_name.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(data, media_type=row.mime_type, headers={
        "Content-Disposition": f'attachment; filename="{safe}"', "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})

