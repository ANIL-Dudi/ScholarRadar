
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


def cv_to_text(data: bytes, filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()

    if suffix not in {".pdf", ".txt"}:
        raise ValueError("Upload your CV as a PDF or TXT file.")

    if not data:
        raise ValueError("The uploaded CV is empty.")

    if suffix == ".pdf":
        try:
            reader = PdfReader(BytesIO(data))

            if reader.is_encrypted:
                raise ValueError(
                    "Password-protected PDFs are not supported."
                )

            text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(
                "Could not read the PDF. Please upload a valid PDF."
            ) from exc
    else:
        text = data.decode("utf-8", errors="replace")

    if not text.strip():
        raise ValueError(
            "No readable text found. If your PDF is scanned, "
            "you may need OCR."
        )

    return text.strip()
