import re
import unicodedata
import json

from dataclasses import dataclass, field
from typing import Optional
from converters.models import ParsedOperation
from converters.request_body.schema_extractor import build_request_schema_result
from converters.response_schema.extractor import parse_success_response_json_sample


def parse_text(text: str) -> ParsedOperation:
    text = unicodedata.normalize('NFC', text)
    op = ParsedOperation()
    op.method = _parse_method(text)
    op.path = _parse_path(text)
    op.service = _parse_service(text)
    op.content_type = _parse_content_type(text)
    op.permission = _parse_permission(text)
    op.parameters = _parse_path_parameters(text)
    op.has_request_body, op.request_body_required = _parse_request_body(text)
    op.error_codes = _parse_error_codes(text)
    op.request_body_fields = _parse_request_body_fields(text)
    op.request_body_children = _parse_request_body_children(text, op.request_body_fields)
    op.response_schemas = _parse_response_schemas(text)
    op.success_status = _parse_success_status(text)
    op.review_flags = _get_review_flags(op, text)
    op.change_history = _parse_change_history(text)
    if op.change_history:
        op.version = op.change_history[-1]["version"]
    else:
        op.version = _parse_version(text)
    op.query_parameters = _parse_query_parameters(text)
    op.request_schema_result = build_request_schema_result(text)

    if op.request_schema_result and getattr(op.request_schema_result, "root", None):
        op.has_request_body = True

        if getattr(op.request_schema_result.root, "required", []):
            op.request_body_required = True

    return op


def _parse_method(text: str) -> str:
    # Đọc method từ các label rõ ràng đã chuẩn hóa trong tài liệu,
    # Tránh bắt nhầm chữ GET/POST/... xuất hiện ở phần khác (vd: Lịch sử thay đổi,
    # ví dụ request, mô tả nghiệp vụ). Alias field tham khảo từ
    # 4.config/global/table_type_rules.yaml (method / HTTP Method).
    labeled_patterns = [
        r'(?im)^method\s*[:\t]?\s+(GET|POST|PUT|DELETE|PATCH)\b',
        r'(?i)HTTP Method\s*[:\t]?\s*(GET|POST|PUT|DELETE|PATCH)\b',
    ]

    candidates = []
    for pattern in labeled_patterns:
        for match in re.finditer(pattern, text):
            candidates.append(match.group(1).upper())

    unique = set(candidates)

    if len(unique) == 1:
        return unique.pop()

    if len(unique) > 1:
        # Method mâu thuẫn giữa các label rõ ràng trong cùng file.
        print(f"WARNING: method mâu thuẫn giữa các label trong file: {sorted(unique)}")
        return ""

    # Không tìm được method ở vùng label chuẩn -> fallback quét toàn text (giữ tương thích cũ)
    match = re.search(r'\b(GET|POST|PUT|DELETE|PATCH)\b', text)
    return match.group(1) if match else ""


def _parse_path(text: str) -> str:
    match = re.search(r'(/v\d+/[^\s]+)', text)
    return match.group(1) if match else ""


def _parse_service(text: str) -> str:
    # Case 1 — dòng "Service\t<value>" (format bảng có tab)
    match = re.search(r'Service\t(\S+)', text)
    if match:
        return match.group(1).strip()
    
    # Case 2 — dòng "Service <value>" (format PDF không có tab)
    match = re.search(r'^Service\s+(\S+)$', text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    return ""


def _parse_content_type(text: str) -> str:
    # Đọc section 4.3 Request Body
    section = re.search(r'4\.3 Request Body(.+?)4\.4', text, re.DOTALL)
    if section:
        body_text = section.group(1).lower()
        # Nếu có field type file → multipart
        if any(t in body_text for t in ['array<file>', 'file', 'binary']):
            return "multipart/form-data"
    
    # Fallback: đọc metadata
    if 'multipart/form-data' in text:
        return "multipart/form-data"
    
    return "application/json"


def _parse_permission(text: str) -> str:
    # Tìm CHECK_ trước vì đây là giá trị thật
    match = re.search(r'CHECK_\w+', text)
    if match:
        return match.group(0)
    
    # Fallback nếu không có CHECK_
    match = re.search(r'Middleware[:\s]+permission[:\s]+(\S+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    match = re.search(r'permission[:\s]+(\S+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return ""


def _parse_path_parameters(text: str) -> list:
    # Bước 1 — lấy tên param từ URL (luôn có, luôn đúng)
    path_match = re.search(r'/v\d+/[^\s]+', text)
    if not path_match:
        return []

    param_names = re.findall(r'\{(\w+)\}', path_match.group(0))
    if not param_names:
        return []

    # Bước 2 — thử đọc type từ bảng nếu có
    type_map = {}
    section = re.search(r'Path Parameters.*?(?=b\.\s|4\.3|Query)', text, re.DOTALL | re.IGNORECASE)
    if section:
        # Hướng A — bảng dùng tab (format docx thực tế)
        for line in section.group(0).split('\n'):
            cols = line.split('\t')
            # Bảng có 4 cột: Tên | Bắt buộc | Kiểu | Mô tả
            if len(cols) >= 3:
                name = cols[0].strip()
                dtype = cols[2].strip()
                # Bỏ header row và dòng trống
                if name and name != 'Tên' and dtype in ('Integer', 'String', 'Array', 'Boolean'):
                    type_map[name] = dtype.lower()

        # Hướng B — fallback nếu bảng không dùng tab (format cũ)
        if not type_map:
            rows = re.findall(r'(\w+)\s+(✔️|✖️)\s+(Integer|String|Array|Boolean)', section.group(0))
            for name, _, dtype in rows:
                type_map[name] = dtype.lower()

    # Bước 3 — ghép lại
    # required luôn True vì OpenAPI 3.1 bắt buộc
    # type lấy từ bảng nếu có, fallback về string nếu không
    params = []
    for name in param_names:
        params.append({
            "name": name,
            "required": True,
            "type": type_map.get(name, "string")  # có bảng → dùng bảng, không có → string
        })
    return params


def _parse_query_parameters(text: str) -> list:
    lines = text.splitlines()

    def _is_section_heading(line: str) -> bool:
        stripped = line.strip()
        if not stripped or "\t" in stripped:
            return False
        return bool(
            re.match(r"^(?:[IVX]+\.\s+|\d+(?:\.\d+)*\.?\s+)", stripped, re.IGNORECASE)
        )

    def _normalize_header(value: str) -> str:
        return value.strip().lower()

    def _find_column(headers: list[str], candidates: set[str]) -> int | None:
        normalized = [_normalize_header(h) for h in headers]
        for idx, header in enumerate(normalized):
            if header in candidates:
                return idx
        return None

    def _looks_like_query_header(cols: list[str]) -> bool:
        name_idx = _find_column(cols, {"tên", "field", "name"})
        type_idx = _find_column(cols, {"kiểu", "type"})
        return name_idx is not None and type_idx is not None

    start_idx = None
    query_heading_signals = (
        "query parameters",
        "query params",
        "query parameter",
        "tham số query",
    )

    for idx, line in enumerate(lines):
        lowered = line.lower()
        if "\t" not in line and any(signal in lowered for signal in query_heading_signals):
            start_idx = idx
            break

    if start_idx is None:
        return []

    params = []
    seen_names = set()
    headers = None

    for line in lines[start_idx + 1:]:
        stripped = line.strip()

        if not stripped:
            if headers is not None:
                break
            continue

        if _is_section_heading(stripped):
            break

        if "\t" not in line:
            if headers is not None:
                break
            continue

        cols = [c.strip() for c in line.split("\t")]

        if headers is None:
            if _looks_like_query_header(cols):
                headers = cols
            continue

        if _looks_like_query_header(cols):
            break

        name_idx = _find_column(headers, {"tên", "field", "name"})
        type_idx = _find_column(headers, {"kiểu", "type"})
        default_idx = _find_column(headers, {"mặc định", "default"})
        description_idx = _find_column(headers, {"mô tả", "description", "desc"})

        if name_idx is None or type_idx is None:
            continue

        if name_idx >= len(cols) or type_idx >= len(cols):
            continue

        name = cols[name_idx].strip()
        dtype = cols[type_idx].strip()

        if not name:
            continue

        name_lower = name.lower()
        if name_lower in seen_names:
            continue

        dtype_clean = re.sub(r"\(.*?\)", "", dtype).strip().lower()
        dtype_key = re.sub(r"\s+", "", dtype_clean)

        if dtype_key in ("integer", "int", "bigint", "long"):
            openapi_type = "integer"
            fmt = None
        elif dtype_key in ("number", "float", "double", "decimal"):
            openapi_type = "number"
            fmt = None
        elif dtype_key in ("boolean", "bool"):
            openapi_type = "boolean"
            fmt = None
        elif dtype_key in ("date", "datetime", "date-time"):
            openapi_type = "string"
            fmt = "date-time"
        elif dtype_key == "enum":
            openapi_type = "string"
            fmt = None
        elif dtype_key == "string":
            openapi_type = "string"
            fmt = None
        else:
            continue

        default = None
        if default_idx is not None and default_idx < len(cols):
            default = cols[default_idx] or None

        description = ""
        if description_idx is not None and description_idx < len(cols):
            description = cols[description_idx]

        enum_values = []
        if dtype_key == "enum":
            enum_values = re.findall(r"`([^`]+)`", description)
            if not enum_values:
                enum_values = re.findall(
                    r"\b([A-Za-z0-9_]+)\s*(?=\(|—|-)",
                    description,
                )
            enum_values = list(dict.fromkeys(enum_values))

        seen_names.add(name_lower)

        params.append({
            "name": name,
            "type": openapi_type,
            "is_enum": dtype_key == "enum",
            "enum_values": enum_values,
            "default": int(default) if default and default.isdigit() else (default if default else None),
            "description": description,
            "format": fmt,
        })

    return params


def _parse_request_body_required(text: str) -> bool:
    section = re.search(r'4\.3 Request Body(.+?)4\.4', text, re.DOTALL)
    if not section:
        return False
    # Nếu có ✔️ trong section thì required: true, không thì false
    return '✔️' in section.group(1) or '✔' in section.group(1)
    

def _parse_error_codes(text: str) -> list:
    # Tìm section "5.2.3 Danh sách mã lỗi" — heading thật trong file docx
    section = re.search(
        r'5\.2\.3.*?Danh sách mã lỗi(.+?)(?=\n\d+\.|6\.|B\d|\Z)',
        text, re.DOTALL | re.IGNORECASE
    )

    if section:
        # Codes đứng đầu dòng hoặc sau tab, format: 4102\tAuth\t...
        codes = re.findall(r'(?:^|\t)(4\d{3}|5\d{3})\b', section.group(1), re.MULTILINE)
    else:
        # Fallback — scan toàn bộ text, loại trừ "4000 ký tự"
        codes = re.findall(r'\b(4\d{3}|5\d{3})\b(?!\s*ký\s*tự)', text)

    return list(dict.fromkeys(codes))


def _parse_request_body(text: str) -> tuple:
    """Trả về (has_body, required)"""
    section = re.search(
        r'(?:4\.3|4\.)\s+Request Body(.+?)(?=\n\s*(?:4\.4|5\.|IV\.|V\.)|\Z)',
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not section:
        return False, True

    body_text = section.group(1).strip()
    if "Không có" in body_text or len(body_text) <= 5:
        return False, True

    required = (
        '\u2714' in body_text
        or 'Có' in body_text
        or re.search(r'\brequired\b', body_text, re.IGNORECASE) is not None
    )
    return True, required


def _parse_request_body_fields(text: str) -> list:
    """Extract từng field trong bảng 4.3 Request Body"""
    section = re.search(
        r'(?:4\.3|4\.)\s+Request Body(.+?)(?=\n\s*(?:4\.1|4\.4|5\.|IV\.|V\.)|\Z)',
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not section:
        return []
    
    fields = []
    for line in section.group(1).split('\n'):
        cols = [c.strip() for c in line.split('\t')]
        # Cần ít nhất 3 cột: Tên, Bắt buộc, Kiểu
        if len(cols) < 3:
            continue
        name = cols[0]
        # Bỏ header row và dòng trống
        if not name or name.lower() in {"tên", "field", "name"}:
            continue
        if len(cols) >= 4 and cols[1].strip().lower() in {"string", "integer", "int", "boolean", "bool", "number", "decimal", "array", "object", "enum"}:
            dtype = cols[1]
            required = '✔' in cols[2] or cols[2].strip().lower() in {"có", "yes", "true", "required"}
            description = cols[3].replace('-', ' - ')
        else:
            required = '✔' in cols[1] or cols[1].strip().lower() in {"có", "yes", "true", "required"}
            dtype = cols[2] if len(cols) > 2 else 'string'
            description = cols[3].replace('-', ' - ') if len(cols) > 3 else ''
        enum_values = []
        if dtype.lower() == 'enum':
            enum_values = re.findall(r'[•·]\s*(\w+):', description)
            if not enum_values:
                enum_values = re.findall(r'\b([A-Z_]{2,})\b', description)
        max_length = re.search(r"Tối đa (\d+) ký tự", description)
        max_items = re.search(r"Tối đa (\d+) files", description)
        fields.append({
            "name": name,
            "required": required,
            "type": dtype,
            "description": description,
            "enum_values": enum_values,
            "max_length": int(max_length.group(1)) if max_length else None,
            "max_items": int(max_items.group(1)) if max_items else None,
        })

    return fields


def _parse_success_status(text: str) -> str:
    """
    Lấy HTTP status của response thành công.
    Ví dụ:
    - Response thành công (201 Created)
    - Response thành công — 201 Created
    - Success Response — HTTP 201
    - HTTP Status / 202 Accepted
    """
    marker_pattern = r"(Response thành công|Success Response)"

    for match in re.finditer(marker_pattern, text, re.IGNORECASE):
        block = text[match.start():match.start() + 1200]

        block = re.split(
            r"\n\s*(?:5\.2|12\.2|Response lỗi|Error Codes|Danh sách mã lỗi)",
            block,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        status_match = re.search(
            r"\b(20[0-9])\s*(?:OK|Created|Accepted|No\s+Content)?\b",
            block,
            re.IGNORECASE,
        )

        if status_match:
            return status_match.group(1)

    for match in re.finditer(r"HTTP Status(?!es)", text, re.IGNORECASE):
        block = text[match.start():match.start() + 300]

        status_match = re.search(
            r"\b(20[0-9])\s*(?:OK|Created|Accepted|No\s+Content)?\b",
            block,
            re.IGNORECASE,
        )

        if status_match:
            return status_match.group(1)

    return ""


def _parse_response_schemas(text: str) -> dict:
    schemas = {}
    section_pattern = re.finditer(
        r'5\.1\.\d+ Mô tả chi tiết Response (data[^\n]*)\n(.+?)(?=5\.1\.\d+|5\.2|\Z)',
        text,
        re.DOTALL
    )

    for match in section_pattern:
        schema_path = match.group(1).strip()
        block = match.group(2)
        fields = []

        for line in block.split('\n'):
            cols = [c.strip() for c in line.split('\t')]
            if len(cols) < 2:
                continue

            name = cols[0].strip()
            dtype = cols[1].strip()
            desc = cols[2].strip() if len(cols) > 2 else ''

            name_key = name.lower()
            dtype_key = dtype.lower()

            is_header_row = (
                name_key in {"field", "trường", "ten", "tên", "name"}
                and dtype_key in {"type", "kiểu", "kieu"}
            )
            if not name or is_header_row:
                continue

            dtype_lower = dtype.lower()
            if 'array<object>' in dtype_lower:
                openapi_type = 'array'
            elif 'object' in dtype_lower:
                openapi_type = 'object'
            elif 'integer' in dtype_lower:
                openapi_type = 'integer'
            elif 'boolean' in dtype_lower:
                openapi_type = 'boolean'
            elif 'number' in dtype_lower or 'float' in dtype_lower or 'decimal' in dtype_lower:
                openapi_type = 'number'
            else:
                openapi_type = 'string'

            fields.append({
                "name": name,
                "type": openapi_type,
                "description": desc,
                "original_type": dtype
            })

        if fields:
            schemas[schema_path] = fields

    if not schemas:
        fallback_section = re.search(
            r'(?:^|\n)\s*\d+\.\s*Mô tả Response Fields\s*\n(.+?)(?=\n\s*(?:\d+\.\s+|[IVX]+\.\s+|5\.2|Response lỗi|Error Codes|Danh sách mã lỗi)|\Z)',
            text,
            re.DOTALL | re.IGNORECASE,
        )

        if fallback_section:
            fields = []

            for line in fallback_section.group(1).split('\n'):
                cols = [c.strip() for c in line.split('\t')]
                if len(cols) < 2:
                    continue

                name = cols[0].strip()
                dtype = cols[1].strip()
                desc = cols[2] .strip() if len(cols) > 2 else ''

                name_key = name.lower()
                dtype_key = dtype.lower()

                is_header_row = (
                    name_key in {"field", "trường", "ten", "tên", "name"}
                    and dtype_key in {"type", "kiểu", "kieu"}
                )
                if not name or is_header_row:
                    continue

                dtype_lower = dtype.lower().replace("?", "")
                if 'array<object>' in dtype_lower:
                    openapi_type = 'array'
                elif 'object' in dtype_lower:
                    openapi_type = 'object'
                elif 'integer' in dtype_lower or dtype_lower == 'int':
                    openapi_type = 'integer'
                elif 'boolean' in dtype_lower or dtype_lower == 'bool':
                    openapi_type = 'boolean'
                elif 'number' in dtype_lower or 'float' in dtype_lower or 'decimal' in dtype_lower:
                    openapi_type = 'number'
                else:
                    openapi_type = 'string'

                fields.append({
                    "name": name,
                    "type": openapi_type,
                    "description": desc,
                    "orginal_type": dtype
                })

            if fields:
                schemas["data"] = fields

    if not schemas:
        schemas = parse_success_response_json_sample(text)

    return schemas


def _get_review_flags(op: ParsedOperation, text: str) -> list:
    flags = []
    if not op.method:
        flags.append("method_missing")
    if not op.path:
        flags.append("path_missing")
    if not op.permission:
        flags.append("permission_missing")
    if not op.error_codes and '5.2' in text:
        flags.append("error_codes_not_parsed")
    if op.has_request_body and not op.request_body_fields:
        flags.append("request_body_fields_empty")
    return flags


def _parse_version(text: str) -> str:
    match = re.search(r'Phiên bản \(version\):\t(\d+\.\d+)', text)
    if match:
        return match.group(1)
    match = re.search(r'Phiên bản.*?(\d+\.\d+)', text)
    if match:
        return match.group(1)
    return ""


def _parse_request_body_children(text: str, parent_fields: list) -> dict:
    """
    Parse sub-fields của Array<Object> trong request body.

    Docx có sub-section dạng:
        4.3.1 Request body.ratings[]
        Tên | Bắt buộc | Kiểu | Mô tả
        supporter_id | ✔️ | Integer | ...

    Trả về: { "ratings": [{"name": "supporter_id", ...}, ...] }
    """
    # Chỉ quan tâm field cha có type Array<Object>
    array_parents = {
        f["name"] for f in parent_fields
        if f["type"].lower().replace(" ", "") == "array<object>"
    }
    if not array_parents:
        return {}

    children = {}
    sub_sections = re.finditer(
        r'4\.3\.\d+\s+Request\s+body\.(\w+)\[\](.+?)(?=4\.3\.\d+|4\.4|\Z)',
        text, re.DOTALL | re.IGNORECASE
    )

    for match in sub_sections:
        parent_name = match.group(1)
        if parent_name not in array_parents:
            continue

        sub_fields = []
        for line in match.group(2).split('\n'):
            cols = [c.strip() for c in line.split('\t')]
            if len(cols) < 3:
                continue
            name = cols[0]
            if not name or name == 'Tên':
                continue
            required = '✔' in cols[1]
            dtype = cols[2]
            description = cols[3].replace('-', ' - ') if len(cols) > 3 else ''
            max_length = re.search(r"Tối đa (\d+) ký tự", description)
            max_items = re.search(r"Tối đa (\d+) files", description)
            sub_fields.append({
                "name": name,
                "required": required,
                "type": dtype,
                "description": description,
                "max_length": int(max_length.group(1)) if max_length else None,
                "max_items": int(max_items.group(1)) if max_items else None,
            })

        if sub_fields:
            children[parent_name] = sub_fields

    return children


def _parse_change_history(text: str) -> list:
    """
    Parse bảng Lịch sử thay đổi.

    Format thường gặp:
    Phiên bản | Ngày | Người thực hiện | Phần thay đổi | Ghi chú

    Hỗ trợ:
    - Bảng dùng tab từ docx
    - Phần thay đổi bị xuống dòng
    - Dừng khi gặp section mới như Nhân sự tham gia, Mục lục, I. Tổng quan
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    start_idx = None
    for i, line in enumerate(lines):
        if "Lịch sử thay đổi" in line or "change history" in line.lower():
            start_idx = i
            break

    if start_idx is None:
        return []

    def _clean_change(value: str) -> str:
        value = value.strip()

        # Cắt phần bị parser nuốt nhầm sau bảng change history
        stop_markers = [
            "Nhân sự tham gia",
            "Mục lục",
            "I. Tổng quan",
            "II.",
            "III.",
        ]

        for marker in stop_markers:
            if marker in value:
                value = value.split(marker)[0].strip()

        return value

    def _is_next_section(line: str) -> bool:
        section_markers = [
            "Nhân sự tham gia",
            "Mục lục",
            "I. Tổng quan",
            "II.",
            "III.",
            "API ",
        ]
        return any(marker in line for marker in section_markers)

    history = []
    current = None

    # Dạng fallback nếu line bị mất tab
    row_pattern = re.compile(r"^(\d+(?:\.\d+)*)\s+(\d{2}/\d{2}/\d{4})\s+(.*)$")

    for line in lines[start_idx + 1:]:
        # Bỏ header
        if "Phiên bản" in line and "Ngày" in line:
            continue

        # Nếu đã có data rồi mà gặp section mới thì dừng
        if history or current:
            if _is_next_section(line):
                if current:
                    current["change"] = _clean_change(current["change"])
                    history.append(current)
                    current = None
                break

        cols = [c.strip() for c in line.split("\t") if c.strip()]

        # Case chuẩn từ docx table:
        # version | date | actor | change | note
        if len(cols) >= 4 and re.match(r"^\d+(?:\.\d+)*$", cols[0]) and re.match(r"^\d{2}/\d{2}/\d{4}$", cols[1]):
            if current:
                current["change"] = _clean_change(current["change"])
                history.append(current)

            current = {
                "version": cols[0],
                "date": cols[1],
                "actor": cols[2],
                "change": _clean_change(cols[3]),
            }

            if len(cols) >= 5:
                current["note"] = _clean_change(cols[4])

            continue

        # Fallback: line dạng "1.0 03/04/2026 Tạo mẫu tài liệu"
        match = row_pattern.match(line)
        if match:
            if current:
                current["change"] = _clean_change(current["change"])
                history.append(current)

            version, date, rest = match.groups()

            current = {
                "version": version.strip(),
                "date": date.strip(),
                "actor": "",
                "change": _clean_change(rest.strip()),
            }
            continue

        # Dòng tiếp theo của phần thay đổi bị xuống dòng
        # Ví dụ:
        # 1.1 07/04/2026 Thay đổi HTTP method từ
        # GET thành POST
        if current:
            # Nếu line có tab nhưng không phải row version mới, khả năng cao là section khác bị dính vào
            if "\t" in line:
                current["change"] = _clean_change(current["change"])
                history.append(current)
                current = None
                break

            current["change"] = _clean_change(current["change"] + " " + line)

    if current:
        current["change"] = _clean_change(current["change"])
        history.append(current)

    return history