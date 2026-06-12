"""Convert uploaded source files into knowledge-base markdown.

Text files (.md/.txt/.markdown) pass through unchanged. PDFs are converted to
text via pypdf and saved as ``<name>.md``. The KB only stores text the agent can
read, so conversion happens here at ingest time — not at generation time.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

TEXT_EXTS = {".md", ".txt", ".markdown"}
PDF_EXTS = {".pdf"}
SUPPORTED_EXTS = TEXT_EXTS | PDF_EXTS


@dataclass
class Converted:
    name: str  # destination filename in _kb/ (always .md/.txt)
    content: str
    note: str = ""  # non-fatal warning, e.g. "no extractable text"


class ConvertError(Exception):
    pass


def _ext(name: str) -> str:
    i = name.rfind(".")
    return name[i:].lower() if i >= 0 else ""


def pdf_to_text(data: bytes) -> str:
    """Extract text from a PDF's text layer. Empty string if none (e.g. scans)."""

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n\n".join(p.strip() for p in parts if p.strip()).strip()


def convert(name: str, *, text: str | None = None, data: bytes | None = None) -> Converted:
    """Turn one uploaded file into KB markdown.

    Provide ``text`` for text files or ``data`` (raw bytes) for PDFs. Raises
    ``ConvertError`` for unsupported types or unreadable PDFs.
    """

    ext = _ext(name)
    if ext in TEXT_EXTS:
        if text is None and data is not None:
            text = data.decode("utf-8", errors="replace")
        return Converted(name=name, content=text or "")
    if ext in PDF_EXTS:
        if data is None:
            raise ConvertError(f"{name}: PDF requires binary content")
        try:
            extracted = pdf_to_text(data)
        except Exception as exc:  # malformed / corrupt PDF
            raise ConvertError(f"{name}: could not read PDF ({exc})") from exc
        dest = name[: -len(ext)] + ".md"
        if not extracted:
            # Likely a scanned/image PDF with no text layer.
            return Converted(
                name=dest,
                content=f"# {name}\n\n(No extractable text — the PDF may be scanned images.)\n",
                note="no extractable text (scanned?)",
            )
        return Converted(name=dest, content=f"# {name}\n\n{extracted}\n")
    raise ConvertError(f"{name}: unsupported type — convert to .md/.txt/.pdf")
