import re
import yaml

from functools import lru_cache
from pathlib import Path
from typing import Optional

from converters.request_body.table_adapter import parse_table
from converters.request_body.schema_merger import merge
from converters.request_body.pseudo_json_adapter import parse_pseudo_json
from converters.request_body.validation_adapter import parse_validation_text

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "4.config/request_schema_profiles.yaml"


@lru_cache(maxsize=1)
def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_section_aliases(name: str) -> list[str]:
    aliases = (
        _load_config()
        .get("section_aliases", {})
        .get(name, [])
        or []
    )

    return [
        str(alias).strip()
        for alias in aliases
        if str(alias).strip()
    ]


def _get_section_stop_markers(name: str) -> list[str]:
    markers = (
        _load_config()
        .get("section_stop_markers", {})
        .get(name, [])
        or []
    )

    return [
        str(marker).strip()
        for marker in markers
        if str(marker).strip()
    ]


def build_request_schema_result(text: str):
    """
    Build canonical request schema từ DOCX text.

    Config-driven:
    - section alias đọc từ 4.config/request_schema_profiles.yaml
    - nếu Request Body chính không parse ra field thì fallback sang field_description
    """
    request_body_aliases = _get_section_aliases("request_body")
    field_desc_aliases = _get_section_aliases("field_description")

    body_section = (
        _find_section(text, *request_body_aliases)
        if request_body_aliases
        else None
    )

    field_desc_section = (
        _find_section(text, *field_desc_aliases)
        if field_desc_aliases
        else None
    )

    if not body_section and not field_desc_section:
        return None

    pseudo_json_output = None
    if body_section and ("{" in body_section or "[" in body_section):
        candidate = parse_pseudo_json(
            body_section,
            section_path=["request_body"],
        )

        if getattr(candidate, "root", None) is not None:
            pseudo_json_output = candidate

    table_output = _collect_table_output(
        body_section,
        field_desc_section,
    )

    validation_aliases = _get_section_aliases("validation_rules")
    validation_section = (
        _find_section(text, *validation_aliases)
        if validation_aliases
        else None
    )

    validation_output = (
        parse_validation_text(validation_section)
        if validation_section
        else None
    )

    # Request Body thường có CẢ VÍ DỤ JSON (cấu trúc/nesting) LẪN bảng mô
    # tả field (required/default/kiểu) ngay trong cùng section — như CSR:
    # ví dụ JSON kèm comment `// BẮT BUỘC` ở trên, bảng
    # "Trường | Bắt buộc | Kiểu | Mặc định | Mô tả" ở dưới. Trước đây nếu
    # có ví dụ JSON thì hàm return ngay, không bao giờ đọc bảng field —
    # làm mất required/default dù bảng có sẵn đầy đủ thông tin. Giờ luôn
    # thử lấy cả hai và merge — pseudo_json cho cấu trúc/nesting/example,
    # table cho required/default/description (ưu tiên khai báo tường minh),
    # giống cách response schema đã merge JSON-sample với table.
    if pseudo_json_output is not None or table_output is not None:
        return merge(
            table_output=table_output,
            pseudo_json_output=pseudo_json_output,
            validation_output=validation_output,
        )

    return None


def _collect_table_output(
    body_section: str | None,
    field_desc_section: str | None,
) -> dict | None:
    """
    Trích bảng mô tả field (required/kiểu/mặc định/mô tả) từ body_section
    và/hoặc field_desc_section, trả về table_output dict để merge cùng
    pseudo_json_output (nếu có). Dùng chung cho mọi trường hợp — không
    phụ thuộc module/endpoint cụ thể.
    """
    table_sources = []

    def add_table_source(source: str | None) -> None:
        if not source:
            return

        source = source.strip()
        if not source:
            return

        if source not in table_sources:
            table_sources.append(source)

    if body_section:
        add_table_source(_strip_entity_description_tail(body_section))
        add_table_source(body_section)

    add_table_source(field_desc_section)

    for table_source in table_sources:
        tables = _extract_text_tables_with_paths(
            table_source,
            default_path=["request_body"],
        )

        if not tables:
            continue

        merged_fields = []
        merged_warnings = []
        merged_review_flags = []

        for section_path, headers, rows in tables:
            parsed = parse_table(
                headers=headers,
                rows=rows,
                section_path=section_path,
                source_file="schema_extractor",
            )

            merged_fields.extend(parsed.get("fields", []))
            merged_warnings.extend(parsed.get("warnings", []))
            merged_review_flags.extend(parsed.get("review_flags", []))

        if not merged_fields:
            continue

        return {
            "fields": merged_fields,
            "warnings": merged_warnings,
            "review_flags": merged_review_flags,
        }

    return None


def _normalize_heading(value: str) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _strip_heading_numbering(line: str) -> str:
    return re.sub(
        r"^\s*\d+(?:\.\d+)*\.?\s+",
        "",
        str(line or "").strip(),
    )


def _is_heading_match(line: str, signal: str) -> bool:
    line_text = _normalize_heading(_strip_heading_numbering(line))
    signal_text = _normalize_heading(signal)

    if not line_text or not signal_text:
        return False

    if line_text == signal_text:
        return True

    allowed_suffixes = (
        signal_text + " -",
        signal_text + " —",
        signal_text + ":",
        signal_text + " (",
    )

    return line_text.startswith(allowed_suffixes)


def _extract_heading_number(line: str) -> Optional[str]:
    stripped = str(line or "").strip()
    match = re.match(r"^(\d+(?:\.\d+)*)\.?\s+\S", stripped)
    return match.group(1) if match else None


def _is_section_boundary(
    line: str,
    current_number: Optional[str] = None,
) -> bool:
    stripped = str(line or "").strip()

    if not stripped or "\t" in stripped:
        return False

    if re.match(r"^[IVX]+\.?\s+\S", stripped, re.IGNORECASE):
        return True

    number = _extract_heading_number(stripped)
    if number is None:
        return False

    if current_number and (
        number == current_number
        or number.startswith(current_number + ".")
    ):
        # Heading con của section hiện tại (vd "4.3.1 ..." dưới "4.3 ...")
        # — vẫn thuộc section này, không phải ranh giới kết thúc. Không
        # làm vậy thì bảng phụ mô tả nested object (vd "4.3.1 Request
        # body.ratings[]") sẽ bị cắt mất khỏi body_section.
        return False

    return True


def _find_section(text: str, *heading_signals: str) -> Optional[str]:
    """
    Tìm section theo heading alias từ config.

    Không match bừa dòng change history chỉ vì có chữ Request Body.
    Chỉ nhận các dòng heading thật như:
      4.3 Request Body
      Request Body
      Request Body - Schema
    """
    candidates = []
    lines = text.splitlines()

    for index, line in enumerate(lines):
        if not any(_is_heading_match(line, signal) for signal in heading_signals):
            continue

        current_number = _extract_heading_number(line)

        body_lines = []
        cursor = index + 1

        while cursor < len(lines):
            current_line = lines[cursor]

            if _is_section_boundary(current_line, current_number):
                break

            body_lines.append(current_line)
            cursor += 1

        body = "\n".join(body_lines).strip()
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
        score -= 1000        

    return score


def _strip_entity_description_tail(section_text: str | None) -> str | None:
    if not section_text:
        return section_text

    stop_markers = _get_section_stop_markers("request_body")

    if not stop_markers:
        return section_text.strip()

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
      b. contact_admin (...)              -> contact_admin
      c. contact_org (...)                -> contact_org
      4.3.1 Request body.ratings[]        -> ratings
    """

    # Ưu tiên tên field ngay trước "[]" — heading kiểu
    # "Request body.ratings[]" đánh dấu bảng mô tả field con của 1
    # array field, tên field không nhất thiết có underscore (vd
    # "ratings" — khác với "contact_admin" ở case dưới).
    array_match = re.search(r"([a-z][a-z0-9_]*)\[\]", heading)
    if array_match:
        return array_match.group(1)

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