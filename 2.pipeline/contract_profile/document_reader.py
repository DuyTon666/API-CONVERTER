from pathlib import Path


def _table_to_lines(table) -> list[str]:
    lines = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            value = " ".join((cell.text or "").split())
            cells.append(value)
        if any(cells):
            lines.append(" | ".join(cells))
    return lines


def read_docx(path: Path) -> str:
    try:
        from docx import Document
        from docx.text.paragraph import Paragraph
        from docx.table import Table
    except ImportError as e:
        raise RuntimeError(
            "Missing dependency: python-docx. Install with: pip install python-docx"
        ) from e

    doc = Document(str(path))
    parts: list[str] = []

    # Quan trọng: đọc paragraph và table theo đúng thứ tự trong Word body
    for child in doc.element.body.iterchildren():
        tag = child.tag.lower()

        if tag.endswith("}p"):
            paragraph = Paragraph(child, doc)
            text = (paragraph.text or "").strip()
            if text:
                parts.append(text)

        elif tag.endswith("}tbl"):
            table = Table(child, doc)
            parts.extend(_table_to_lines(table))

    return "\n".join(parts)


def read_pdf(path: Path) -> str:
    # Try pypdf first, then PyPDF2
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError as e:
            raise RuntimeError(
                "Missing dependency: pypdf or PyPDF2. Install with: pip install pypdf"
            ) from e

    reader = PdfReader(str(path))
    parts: list[str] = []

    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text.strip())

    return "\n".join(parts)


def read_document(path: str | Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".docx":
        return read_docx(path)

    if suffix == ".pdf":
        return read_pdf(path)

    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    raise ValueError(f"Unsupported file type: {suffix}")
