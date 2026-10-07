import io

from pypdf import PdfWriter


def clean(*, data):
    return True


def infected(*, data):
    return False


def pdf(**kwargs):
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    writer.write(stream)
    return stream.getvalue()


def cleared(**kwargs):
    return {"allowed": True, "enrolment_status": "WITHDRAWN"}


def not_cleared(**kwargs):
    return {"allowed": False}
