import re

from typing import Optional

from converters.request_body.table_adapter import parse_table
from converters.request_body.schema_merger import merge
from converters.request_body.pseudo_json_adapter import parse_pseudo_json


def build_request_schema_result(text: str):
    """
    Build canonical request schema từ DOCX text.

    Bản đầu chỉ dùng field description tables.
    Không parse pseudo-json / validation ở đây để tránh làm rối parser.
    """
    body_section = _find_section(text, "Request Body", "Request body")
    field_desc_section = _find_section(
        text,
        "Mô tả các trường",
        "Mô tả trường",
        "Field description",
    )

    if not body_section and not field_desc_section:
        return None

    if body_section and ("{" in body_section or "[" in body_section):
        pseudo_json_output = parse_pseudo_json(
            body_section,
            section_path=["request_body"],
        )

        if getattr(pseudo_json_output, "root", None) is not None:
            return merge(
                table_output=None,
                pseudo_json_output=pseudo_json_output,
                validation_output=None,
            )

    table_source = (
        _strip_entity_description_tail(body_section)
        if body_section
        else field_desc_section
    )
    if not table_source:
        return None

    tables = _extract_text_tables_with_paths(
        table_source,
        default_path=["request_body"],
    )

    if not tables:
        return None

    merged_fields = []
    merged_warnings = []
    merged_review_flags = []

    for section_path, headers, rows in tables:
        table_output = parse_table(
            headers=headers,
            rows=rows,
            section_path=section_path,
            source_file="schema_extractor",
        )

        merged_fields.extend(table_output.get("fields", []))
        merged_warnings.extend(table_output.get("warnings", []))
        merged_review_flags.extend(table_output.get("review_flags", []))

    if not merged_fields:
        return None

    return merge(
        table_output={
            "fields": merged_fields,
            "warnings": merged_warnings,
            "review_flags": merged_review_flags,
        },
        pseudo_json_output=None,
        validation_output=None,
    )


def _find_section(text: str, *heading_signals: str) -> Optional[str]:
    """
    Tìm section theo heading signal.
    Không lấy match đầu tiên vì DOCX có thể có mục lục / change history.
    """
    candidates = []

    for signal in heading_signals:
        pattern = re.compile(
            rf"(?:^|\n)[^\n]*{re.escape(signal)}[^\n]*\n(.+?)(?=\n\s*\d+\.\d+[\s\n]|\Z)",
            re.DOTALL | re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            body = match.group(1).strip()
            if body:
                candidates.append(body)

    if not candidates:
        return None
    
    return max(candidates, key=_score_section)


def _score_section(body: str) -> int:
    lowered = body.lower()
    score = len(body)

    if "\t" in body and ("trường" in lowered or "field" in lowered):
        score += 5000

    if "{" in body and ":" in body:
        score += 3000

    if "không có" in lowered:
        score += 1000        

    return score


def _strip_entity_description_tail(section_text: str | None) -> str | None:
    if not section_text:
        return section_text

    stop_markers = [
        "Mô tả chi tiết các thuộc tính",
        "Mô tả chi tiết thuộc tính",
        "Mô tả thuộc tính",
        "Attribute description",
        "Field description",
    ]

    cut_at = len(section_text)
    for marker in stop_markers:
        idx = section_text.find(marker)
        if idx >= 0:
            cut_at = min(cut_at, idx)

    return section_text[:cut_at].strip()


def _is_table_heading(line: str) -> bool:
    stripped = line.strip()

    if not stripped or "\t" in stripped:
        return False

    return bool(
        re.match(r"^\d+(\.\d+)+\s+\S", stripped)
        or re.match(r"^[a-zA-Z]\.\s+\S", stripped)
    )


def _extract_object_name_from_heading(heading: str) -> Optional[str]:
    """
    Ví dụ:
      b. contact_admin (...) -> contact_admin
      c. contact_org (...)   -> contact_org
    """
    
    match = re.search(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b", heading)
    if match:
        return match.group(1)

    return None


def _extract_text_tables_with_paths(
    section_text: str,
    default_path: list[str],
) -> list[tuple[list[str], list[str], list[list[str]]]]:
    """
    Tách bảng tab-separated.
    Trả về list of (section_path, headers, rows).
    """

    result = []
    lines = section_text.splitlines()
    current_heading = ""

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if _is_table_heading(stripped):
            current_heading = stripped
            i += 1
            continue

        cols = [col.strip() for col in line.split("\t")]

        if len(cols) >= 3 and cols [0] and any(cols[1:]):
            headers = cols
            rows = []
            i += 1

            while i < len(lines):
                row_line = lines[i]
                row_stripped = row_line.strip()
                row_cols = [col.strip() for col in row_line.split("\t")]

                if not any(row_cols):
                    break

                if _is_table_heading(row_stripped):
                    break

                if len(row_cols) >= 2 and row_cols[0]:
                    rows.append(row_cols)

                i += 1

            if rows:
                object_name = _extract_object_name_from_heading(current_heading)
                if object_name:
                    section_path = default_path + [object_name]
                else:
                    section_path = default_path

                result.append((section_path, headers, rows))

            continue

        i += 1

    return result