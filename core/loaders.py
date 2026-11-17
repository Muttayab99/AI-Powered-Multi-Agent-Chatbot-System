"""Text extraction for uploaded and fetched files."""
import io
import re
from pathlib import Path

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".html", ".htm")


class UnsupportedFileError(ValueError):
    pass


def decode_text(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as e:
            raise UnsupportedFileError("This PDF is password-protected.") from e
    pages = []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[Page {number}]\n{text.strip()}")
    return "\n\n".join(pages)


def docx_text(data: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(data))
    blocks = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                blocks.append(" | ".join(cells))
    return "\n".join(blocks)


def html_text(data: bytes) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        text = pdf_text(data)
    elif suffix == ".docx":
        text = docx_text(data)
    elif suffix in (".html", ".htm"):
        text = html_text(data)
    elif suffix in (".txt", ".md", ".csv", ".json"):
        text = decode_text(data)
    else:
        raise UnsupportedFileError(
            f"Unsupported file type '{suffix or filename}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    return re.sub(r"\n{3,}", "\n\n", text).strip()
