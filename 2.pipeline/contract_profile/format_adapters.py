# format_adapters.py
# Đọc bảng error code từ DOCX/PDF, normalize ra list row chuẩn.
# Mọi config đọc từ table_format_profiles.yaml.

import os
import re
import yaml
import pdfplumber
import unicodedata

from docx import Document

def load_profiles(yaml_path: str) -> list[dict]:
    """Đọc table_format_profiles.yaml, trả về list profile."""
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("profiles", [])


def _strip_accents(value: str) -> str:
    text = str(value or "").replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _normalize_key(value: str) -> str:
    text = _strip_accents(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def match_profile(header_cells: list[str], profiles: list[dict]) -> dict | None:
    """
    So header thật với profile.

    Hỗ trợ:
    - header_match_keywords: tất cả keyword phải có
    - header_match_any: nếu khai báo thì chỉ cần một keyword xuất hiện
    - header_exclude_keywords: nếu có keyword này thì loại profile
    """
    header_text = _normalize_key(" ".join(header_cells))

    for profile in profiles:
        required_keywords = [
            _normalize_key(kw)
            for kw in profile.get("header_match_keywords", [])
            if str(kw).strip()
        ]

        if not all(kw in header_text for kw in required_keywords):
            continue

        any_keywords = [
            _normalize_key(kw)
            for kw in profile.get("header_match_any", [])
            if str(kw).strip()
        ]

        if any_keywords and not any(kw in header_text for kw in any_keywords):
            continue

        excluded_keywords = [
            _normalize_key(kw)
            for kw in profile.get("header_exclude_keywords", [])
            if str(kw).strip()
        ]

        if excluded_keywords and any(kw in header_text for kw in excluded_keywords):
            continue

        return profile

    return None


def _clean_text(value) -> str:
    text = str(value or "").replace("\u200b", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_valid_http_status(value) -> bool:
    text = _clean_text(value)
    
    if not text.isdigit():
        return False

    number = int(text)
    return 400 <= number <= 599


def _looks_like_error_code(value) -> bool:
    text = _clean_text(value)

    if not text.isdigit():
        return False

    return len(text) >= 4


def _is_suspect_message_value(value) -> bool:
    text = _clean_text(value)
    lower = text.lower()

    if lower in {"", "null", "none", "nan", "-"}:
        return True

    if (text.startswith("{") and text.endswith("}")) or (
        text.startswith("[") and text.endswith("]")
    ):
        return True

    return False


def _looks_like_descriptive_text(value) -> bool:
    text = _clean_text(value)

    if _is_suspect_message_value(text):
        return False

    return len(text) >= 12


def _normalize_row(cells: list[str], header_cells: list[str], profile: dict, source_file: str, table_index: int) -> dict | None:
    """
    Map cells theo tên cột thật (header_cells) dùng column_aliases trong profile.
    Không map theo vị trí cứng — tránh lệch cột khi bảng có thêm/thiếu cột.
    Trả về None nếu row rỗng hoặc code không hợp lệ.
    """
    aliases = profile.get("column_aliases", {}) or {}
    defaults = profile.get("defaults", {})
    header_lower = [_normalize_key(h) for h in header_cells]

    def find_value(field: str) -> str | None:
        "Tìm alias nào khớp với header, lấy giá trị đó"
        for alias in alias.get(field, []):
            alias_key = _normalize_key(alias)
            for i, h in enumerate(header_lower):
                if alias_key and (alias_key == h or alias_key in h or h in alias_key):
                    if i < len(cells):
                        return _clean_text(cells[i])
        return None

    code = _clean_text(find_value("code"))
    http_status = _clean_text(find_value("http_status"))
    category = _clean_text(find_value("category"))
    message = _clean_text(find_value("message"))
    field_name = _clean_text(find_value("field"))
    suggested_action = _clean_text(find_value("suggested_action"))
    source_type = _clean_text(defaults.get("source_type"))
    source_profile = _clean_text(profile.get("name"))

    if not category:
        category = _clean_text(defaults.get("category"))

    # Repair generic case:
    # Header ghi Error Code | HTTP, nhưng row thực tế lại là HTTP | Error Code.
    # Ví dụ: code=422, http_status=4622 => code=4622, http_status=422.
    if (
        _is_valid_http_status(code)
        and not _is_valid_http_status(http_status)
        and _looks_like_error_code(http_status)
    ):
        code, http_status = http_status, code

    if not code or not code.isdigit():
        return None

    # Repair generic case:
    # Một số bảng dùng cột "Ngữ cảnh" làm message thật,
    # còn cột "Mô tả" chứa null/JSON data.
    if _is_suspect_message_value(message) and _looks_like_descriptive_text(category):
        message = category
        category = ""

    normalized = {
        "code": code,
        "http_status": http_status,
        "category": category,
        "message": message,
        "source_file": os.path.basename(source_file),
        "table_index": table_index,
        "source_profile": source_profile,
    }

    if field_name:
        normalized["field"] = field_name

    if suggested_action:
        normalized["suggested_action"] = suggested_action

    if source_type:
        normalized["source_type"] = source_type

    return normalized


def _extract_from_docx(file_path: str, profiles: list[dict]) -> list[dict]:
    """ Đọc tất cả bảng trong docx, match profile, normalize."""
    doc = Document(file_path)
    result = []

    for table_index, table in enumerate(doc.tables):
        if not table.rows:
            continue

        header_cells = [c.text.strip() for c in table.rows[0].cells]
        profile = match_profile(header_cells, profiles)
        if profile is None:
            continue

        for row in table.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            normalized = _normalize_row(cells, header_cells, profile, file_path, table_index)
            if normalized is not None:
                result.append(normalized)

    return result


def _extract_from_pdf(file_path: str, profiles: list[dict]) -> list[dict]:
    # Gom bảng cross-page: header và data có thể bị cắt ngang sang trang khác.
    # active_profile: profile đang active sau khi match được header.
    # active_rows: rows đang gom, chưa normalize.
    # Khi gặp header mới → lưu luồng cũ, bắt đầu luồng mới.
    # Khi gặp bảng không match header + đang có active_profile → gom tiếp vào luồng hiện tại.

    active_profile = None
    active_rows = []
    table_index = 0
    final_tables = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                if not table or not table[0]:
                    continue

                first_row = [str(c).strip() if c else "" for c in table[0]]
                profile = match_profile(first_row, profiles)

                if profile is not None:
                    # Gặp header mới → lưu luồng cũ nếu có
                    if active_profile is not None and active_rows:
                        final_tables.append((active_profile, active_rows, table_index, active_header))
                        table_index += 1
                    active_profile = profile
                    active_header = first_row
                    active_rows = list(table[1:])
                else:
                    # Không match header → có thể là phần tiếp của bảng bị cắt trang
                    if active_profile is not None:
                        active_rows.extend(table)

        # Lưu luồng cuối cùng
        if active_profile is not None and active_rows:
            final_tables.append((active_profile, active_rows, table_index, active_header))

    results = []
    for profile, rows, t_idx, header_cells in final_tables:
        for raw_row in rows:
            cells = [str(c).strip() if c else "" for c in raw_row]
            normalized = _normalize_row(cells, header_cells, profile, file_path, t_idx)
            if normalized is not None:
                results.append(normalized)

    return results


def extract_tables(file_path: str, profiles: list[dict]) -> list[dict]:
    """
    Entrypoint chính. Detect DOCX hay PDF theo extension, gọi đúng hàm.
    Trả về list row đã normalize.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return _extract_from_docx(file_path, profiles)
    elif ext == ".pdf":
        return _extract_from_pdf(file_path, profiles)
    else: 
        raise ValueError(f"Định dạng không hỗ trợ: {ext} (Hiện tại sử dụng cho .docx và .pdf)")