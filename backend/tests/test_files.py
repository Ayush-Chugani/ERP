"""Uploads are validated by content, stored privately and only downloadable by people allowed to see the owning record."""
import io

import pytest
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import text


def pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(72, 72)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return buf.getvalue()


def upload(client, name, data, ctype="application/octet-stream"):
    return client.http.post("/api/v1/files", files={"file": (name, data, ctype)})


def test_valid_pdf_and_png_are_accepted(as_user):
    c = as_user("student")
    r = upload(c, "marksheet.pdf", pdf_bytes())
    assert r.status_code == 201, r.text
    assert r.json()["mime_type"] == "application/pdf" and len(r.json()["sha256"]) == 64
    assert upload(c, "photo.png", png_bytes()).status_code == 201


@pytest.mark.parametrize("name,data", [
    ("evil.exe", b"MZ\x90\x00"), ("fake.pdf", b"not a pdf at all"), ("fake.png", b"%PDF-1.4 hello"),
    ("empty.pdf", b""), ("noext", b"%PDF-1.4"), ("../../etc/passwd.pdf", b"nope"), ("script.html", b"<script>1</script>"),
])
def test_bad_uploads_are_rejected(as_user, name, data):
    assert upload(as_user("student"), name, data).status_code == 422


def test_oversized_upload_rejected(as_user, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "upload_max_bytes", 1024)
    assert upload(as_user("student"), "big.pdf", pdf_bytes() + b"0" * 5000).status_code == 422


def test_download_is_access_controlled(as_user, db):
    owner, stranger = as_user("student"), as_user("student2")
    fid = upload(owner, "doc.pdf", pdf_bytes()).json()["file_object_id"]
    got = owner.http.get(f"/api/v1/files/{fid}")
    assert got.status_code == 200 and got.content.startswith(b"%PDF-")
    assert got.headers["content-disposition"].startswith("attachment") and got.headers["x-content-type-options"] == "nosniff"
    assert stranger.http.get(f"/api/v1/files/{fid}").status_code == 404
    assert as_user("demoadmin").http.get(f"/api/v1/files/{fid}").status_code == 200
    assert owner.http.get("/api/v1/files/999999").status_code == 404


def test_linking_a_file_to_a_record_shares_it_with_record_readers(as_user, db):
    student = as_user("student")
    me = student.get("/auth/me").json()
    fid = upload(student, "id.pdf", pdf_bytes()).json()["file_object_id"]
    doc_type = db.execute(text("SELECT document_type_id FROM document_type LIMIT 1")).scalar()
    r = student.post("/documents/student-document", json={"document_type_id": doc_type, "file_object_id": fid,
                                                          "student_id": me["student_ids"][0]})
    assert r.status_code == 201, r.text
    assert as_user("student2").http.get(f"/api/v1/files/{fid}").status_code == 404
    assert as_user("registrar").http.get(f"/api/v1/files/{fid}").status_code == 200
