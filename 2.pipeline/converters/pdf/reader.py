import re
import yaml
import pdfplumber
from pathlib import Path

def _load_config(config_path: str) -> dict:
    return yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    
def _should_skip(line: str, skip_patterns: list[str]) -> bool:
    for pattern in skip_patterns:
        if line.strip().startswith(pattern):
            return True
    return False

def _extract_table_lines(table: list) -> list[str]:
    """Chuyển table pdfplumber → list[str] dạng cell1\tcell2 — giống DOCX reader."""
    lines = []
    for row in table:
        cells = [str(c).strip() if c else "" for c in row]
        lines.append("\t".join(cells))
    lines.append("")
    return lines

def _extract_page(page, skip_patterns: list[str]) -> list[str]:
    lines = []

    tables = page.extract_tables()
    table_bboxes = [t.bbox for t in page.find_tables()]

    def _outside_tables(obj):
        for bbox in table_bboxes:
            x0, top, x1, bottom = bbox
            if (obj["x0"] >= x0 and obj["x1"] <= x1
                    and obj["top"] >= top and obj ["bottom"] <= bottom):
                return False
        return True

    words = page.extract_words()
    filtered = [w for w in words if _outside_tables(w)]

    line_map: dict[int, list] = {}
    for w in filtered:
        y = round(w["top"])
        line_map.setdefault(y, []).append(w)

    text_lines = []
    for y in sorted(line_map.keys()):
        words_in_line = sorted(line_map[y], key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in words_in_line)
        if text.strip() and not _should_skip(text, skip_patterns):
            text_lines.append((y, text))

    table_lines = []
    for i, table in enumerate(tables):
        if i < len(table_bboxes):
            y = round(table_bboxes[i][1])
        else:
            y = 9999
        for line in _extract_table_lines(table):
            table_lines.append((y, line))
            y += 1

    all_lines = sorted(text_lines + table_lines, key=lambda x: x[0])
    lines = [text for _, text in all_lines]

    return lines

def read_pdf(file_path: str, config_path: str) -> str:
    """
    Đọc PDF API Contract → string giống output read_docx().
    Parser DOCX tái dùng trực tiếp không cần sửa.
    """
    cfg = _load_config(config_path).get("reader", {})
    skip_patterns = cfg.get("skip_patterns", [])
    skip_pages = cfg.get("skip_first_pages", 0)

    all_lines = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages[skip_pages:]:
            all_lines.extend(_extract_page(page, skip_patterns))
            all_lines.append("")
    
    return "\n".join(all_lines)