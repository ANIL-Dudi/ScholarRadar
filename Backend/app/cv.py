from io import BytesIO
from pypdf import PdfReader


def cv_to_text(data: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        return "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(data)).pages)
    return data.decode("utf-8", errors="ignore")