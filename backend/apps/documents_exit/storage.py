import hashlib
import io
import re
import unicodedata
import warnings
from pathlib import Path

from django.conf import settings
from django.utils.module_loading import import_string
from rest_framework.exceptions import ValidationError

from .integrations import ProviderUnavailable, invoke


class LocalPrivateStorage:
    provider = "LOCAL_PRIVATE"
    encrypted = False

    def path(self, key):
        root = Path(settings.DOCUMENTS_STORAGE_ROOT).resolve()
        path = (root / key).resolve()
        if not re.fullmatch(
            r"[a-f0-9]{32}\.(pdf|png|jpg|jpeg)", key
        ) or not path.is_relative_to(root):
            raise ProviderUnavailable()
        return path

    def put(self, key, data):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        created = False
        try:
            with path.open("xb") as stream:
                created = True
                stream.write(data)
            path.chmod(0o600)
        except BaseException:
            # Remove partial writes from this unique key only.
            if created and path.exists():
                path.unlink()
            raise

    def open(self, key):
        return self.path(key).open("rb")

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)

    def exists(self, key):
        return self.path(key).is_file()

    def keys(self):
        root = Path(settings.DOCUMENTS_STORAGE_ROOT).resolve()
        if not root.exists():
            return
        for path in root.iterdir():
            if path.is_file() and re.fullmatch(
                r"[a-f0-9]{32}\.(pdf|png|jpg|jpeg)", path.name
            ):
                yield path.name


def backend():
    return import_string(settings.DOCUMENTS_STORAGE_FACTORY)()


def validate_name(name):
    if not isinstance(name, str):
        raise ValidationError("Invalid file name.")
    name = unicodedata.normalize("NFKC", name)
    if (
        not 1 <= len(name) <= 255
        or any(ord(c) < 32 for c in name)
        or any(c in name for c in "/\\:")
        or name.startswith(".")
        or name.count(".") != 1
    ):
        raise ValidationError(
            "Use a plain file name with a single permitted extension."
        )
    ext = name.rsplit(".", 1)[-1].lower()
    if ext not in settings.DOCUMENTS_ALLOWED_EXTENSIONS or ext not in (
        "pdf",
        "png",
        "jpg",
        "jpeg",
    ):
        raise ValidationError("File type is not permitted.")
    return name, ext


def validate_upload(upload):
    name, ext = validate_name(upload.name)
    limit = settings.DOCUMENTS_MAX_BYTES
    if getattr(upload, "size", 0) > limit:
        raise ValidationError("File exceeds the upload limit.")
    data = upload.read(limit + 1)
    if not data or len(data) > limit:
        raise ValidationError("A nonempty file within the upload limit is required.")
    # Provider is required even for generated files; unknown/error states never pass.
    if invoke("DOCUMENTS_MALWARE_SCANNER", data=data) is not True:
        raise ValidationError("File failed security scanning.")
    try:
        if ext == "pdf":
            from pypdf import PdfReader

            if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
                raise ValueError()
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 500:
                raise ValueError()
            forbidden = [
                b"/JavaScript",
                b"/JS",
                b"/Launch",
                b"/EmbeddedFile",
                b"/OpenAction",
                b"/AA",
                b"/RichMedia",
                b"/XFA",
            ]
            if any(token in data for token in forbidden):
                raise ValueError()
            from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

            visited = set()
            budget = [0]

            def inspect(value):
                if isinstance(value, IndirectObject):
                    value = value.get_object()
                marker = id(value)
                if marker in visited:
                    return
                visited.add(marker)
                budget[0] += 1
                if budget[0] > 20000:
                    raise ValueError()
                if isinstance(value, DictionaryObject):
                    if any(
                        str(key)
                        in [
                            "/JavaScript",
                            "/JS",
                            "/Launch",
                            "/EmbeddedFile",
                            "/EmbeddedFiles",
                            "/OpenAction",
                            "/AA",
                            "/RichMedia",
                            "/XFA",
                        ]
                        for key in value
                    ):
                        raise ValueError()
                    if str(value.get("/S", "")) in ["/JavaScript", "/Launch"]:
                        raise ValueError()
                    for child in value.values():
                        inspect(child)
                elif isinstance(value, ArrayObject):
                    for child in value:
                        inspect(child)

            inspect(reader.trailer)
            mime = "application/pdf"
        else:
            from PIL import Image

            with warnings.catch_warnings():
                warnings.simplefilter("error")
                with Image.open(io.BytesIO(data)) as image:
                    if image.width * image.height > 25_000_000 or image.format != (
                        "PNG" if ext == "png" else "JPEG"
                    ):
                        raise ValueError()
                    image.verify()
            mime = "image/png" if ext == "png" else "image/jpeg"
    except Exception:  # noqa: BLE001 - redact provider/parser exceptions at the security boundary.
        raise ValidationError(
            "File content does not match a supported safe document type."
        ) from None
    if mime not in settings.DOCUMENTS_ALLOWED_MIMES:
        raise ValidationError("File type is not permitted.")
    claimed = getattr(upload, "content_type", None)
    if claimed and claimed not in [mime, "application/octet-stream"]:
        raise ValidationError("File content and declared type do not match.")
    return {
        "name": name,
        "extension": ext,
        "mime": mime,
        "data": data,
        "checksum": hashlib.sha256(data).hexdigest(),
    }
