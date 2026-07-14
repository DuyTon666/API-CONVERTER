import re
import unicodedata
import json
import yaml

from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from converters.models import ParsedOperation
from converters.request_body.schema_extractor import build_request_schema_result
from converters.response_schema.extractor import (
    parse_success_response_json_sample,
    detect_data_root_is_array,
    find_table_block_after_json_sample,
)
from converters.request_body.table_adapter import (
    parse_table as parse_schema_table,
)
from converters.request_body.schema_merger import (
    merge as merge_schema_tables,
)


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
    op.change_history = _parse_change_history(text)
    if op.change_history:
        op.version = op.change_history[-1]["version"]
    else:
        op.version = _parse_version(text)
    op.query_parameters = _parse_query_parameters(text)
    op.request_schema_result = build_request_schema_result(text)

    if _request_schema_has_content(
        op.request_schema_result
    ):
        op.has_request_body = True

        if getattr(
            op.request_schema_result.root,
            "required",
            [],
        ):
            op.request_body_required = True

    op.review_flags = _get_review_flags(
        op,
        text,
    )

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
            if headers is not None and params:
                params[-1]["description"] = (
                    (params[-1]["description"] + "\n" + stripped).strip()
                )
                continue
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
        return False, False

    body_text = section.group(1).strip()
    if (
        re.search(r"\bkhông\s+có\b", body_text, re.IGNORECASE)
        or len(body_text) <= 5
    ):
        return False, False

    required = (
        '\u2714' in body_text
        or 'Có' in body_text
        or re.search(r'\brequired\b', body_text, re.IGNORECASE) is not None
    )
    return True, required

SCHEMA_TABLE_PROFILE_PATH = (
    Path(__file__).resolve().parents[3]
    / "4.config"
    / "schema_table_profiles.yaml"
)

REQUEST_SCHEMA_PROFILE_PATH = (
    Path(__file__).resolve().parents[3]
    / "4.config"
    / "request_schema_profiles.yaml"
)


def _request_schema_has_content(result) -> bool:
    """
    Chỉ coi canonical schema là bằng chứng có request body
    khi root chứa cấu trúc hoặc example có dữ liệu thật.
    """
    root = getattr(result, "root", None)

    if root is None:
        return False

    example = getattr(root, "example", None)

    if isinstance(
        example,
        (str, bytes, dict, list, tuple, set),
    ):
        has_meaningful_example = bool(example)
    else:
        # False và 0 vẫn là example hợp lệ.
        has_meaningful_example = example is not None

    return bool(
        getattr(root, "properties", None)
        or getattr(root, "items", None) is not None
        or getattr(root, "required", None)
        or (
            getattr(root, "has_example", False)
            and has_meaningful_example
        )
    )


def _normalize_header_alias(value: str) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


@lru_cache(maxsize=1)
def _load_request_schema_profile() -> dict:
    with open(REQUEST_SCHEMA_PROFILE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def _load_schema_table_profile() -> dict:
    with open(SCHEMA_TABLE_PROFILE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_column_aliases(canonical_name: str) -> set[str]:
    profile = _load_schema_table_profile()
    aliases = (
        profile
        .get("column_aliases", {})
        .get(canonical_name, [])
        or []
    )
    return {_normalize_header_alias(alias) for alias in aliases}


def _is_field_header_name(value: str) -> bool:
    return _normalize_header_alias(value) in _get_column_aliases("field_name")


def _is_type_header_name(value: str) -> bool:
    return _normalize_header_alias(value) in _get_column_aliases("type")


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
        if not name or _is_field_header_name(name):
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


def _response_node_to_legacy_schemas(
    root,
    schema_path: str,
) -> dict:
    """
    Chuyển canonical SchemaNode về format response_schemas
    mà emitter hiện tại đang sử dụng.

    Object:
      data.pagination.total_items

    Array object:
      data.certificates[].cert_pem

    sẽ thành:
      data
      data.pagination
      data.certificates
    """
    schemas = {}

    def visit(node, current_path: str) -> None:
        if getattr(node, "type", None) != "object":
            return

        properties = getattr(node, "properties", {}) or {}
        fields = []
        child_nodes = []

        for field_name, child in properties.items():
            child_type = (
                getattr(child, "type", None)
                or "string"
            )

            fields.append({
                "name": field_name,
                "type": child_type,
                "nullable": bool(
                    getattr(child, "nullable", False)
                ),
                "description": (
                    getattr(child, "description", None)
                    or ""
                ),
                "original_type": child_type,
            })

            child_path = (
                f"{current_path}.{field_name}"
            )

            if child_type == "object":
                child_nodes.append((
                    child_path,
                    child,
                ))

            elif child_type == "array":
                items = getattr(
                    child,
                    "items",
                    None,
                )

                if (
                    items is not None
                    and getattr(items, "type", None)
                    == "object"
                ):
                    child_nodes.append((
                        child_path,
                        items,
                    ))

        if fields:
            schemas[current_path] = fields

        for child_path, child_node in child_nodes:
            visit(
                child_node,
                child_path,
            )

    visit(root, schema_path)

    return schemas


def _apply_implicit_array_item_scope(
    table_output: dict,
) -> None:
    """
    Xử lý bảng response khai báo array theo dạng ngầm:

      items       Array
      id          UUID
      name        String
      pagination.total_items Integer

    Các field phẳng sau array được xem là field của array items,
    cho đến khi gặp:

    - một path tường minh như pagination.total_items;
    - một object/array root mới.

    Không phụ thuộc tên field, module hoặc endpoint.
    """
    fields = table_output.get("fields")

    if not isinstance(fields, list):
        return

    active_array_name: str | None = None

    for field in fields:
        if not isinstance(field, dict):
            active_array_name = None
            continue

        field_path = field.get("field_path")

        if not isinstance(field_path, list) or not field_path:
            active_array_name = None
            continue

        normalized_type = str(
            field.get("normalized_type") or ""
        ).strip()

        # Path tường minh như pagination.total_items hoặc
        # certificates[].cert_pem tự mô tả được cấu trúc.
        if len(field_path) > 1:
            active_array_name = None
            continue

        is_array_declaration = (
            normalized_type == "array"
            or normalized_type.startswith("array<")
        )

        if is_array_declaration:
            active_array_name = str(
                field.get("name") or ""
            ).strip() or None
            continue

        # Object root mới kết thúc scope của array trước đó.
        if normalized_type == "object":
            active_array_name = None
            continue

        if active_array_name is None:
            continue

        leaf = field_path[0]

        if (
            not isinstance(leaf, dict)
            or leaf.get("container") != "leaf"
        ):
            active_array_name = None
            continue

        leaf_name = str(
            leaf.get("name") or ""
        ).strip()

        if not leaf_name:
            active_array_name = None
            continue

        field["field_path"] = [
            {
                "name": active_array_name,
                "container": "array",
            },
            {
                "name": leaf_name,
                "container": "leaf",
            },
        ]


def _parse_response_table_block(
    block: str,
    schema_path: str,
) -> dict:
    """
    Parse một bảng response bằng shared table adapter
    và canonical schema merger.
    """
    table_rows = []

    for line in block.splitlines():
        columns = [
            column.strip()
            for column in line.split("\t")
        ]

        if len(columns) >= 2:
            table_rows.append(columns)

    if len(table_rows) < 2:
        return {}

    headers = table_rows[0]
    rows = table_rows[1:]

    table_output = parse_schema_table(
        headers=headers,
        rows=rows,
        section_path=[schema_path],
        source_file="",
    )

    _apply_implicit_array_item_scope(
        table_output,
    )

    result = merge_schema_tables(
        table_output=table_output,
    )

    if not result or not result.root:
        return {}

    return _response_node_to_legacy_schemas(
        result.root,
        schema_path,
    )


def _merge_response_schema_maps(
    base_schemas: dict,
    overlay_schemas: dict,
) -> dict:
    """
    Merge hai response schema map theo schema path và field name.

    base:
      thường lấy từ JSON response example, cung cấp cấu trúc đầy đủ.

    overlay:
      thường lấy từ response table, được ưu tiên cho type,
      description và metadata vì đây là khai báo tường minh.

    Không phụ thuộc module, endpoint hay tên field cụ thể.
    """
    merged: dict[str, list[dict]] = {}

    for schema_path, fields in (base_schemas or {}).items():
        if not isinstance(fields, list):
            continue

        merged[schema_path] = [
            dict(field)
            for field in fields
            if isinstance(field, dict)
        ]

    for schema_path, overlay_fields in (overlay_schemas or {}).items():
        if not isinstance(overlay_fields, list):
            continue

        current_fields = merged.setdefault(
            schema_path,
            [],
        )

        field_indexes = {
            str(field.get("name") or "").strip(): index
            for index, field in enumerate(current_fields)
            if str(field.get("name") or "").strip()
        }

        for overlay_field in overlay_fields:
            if not isinstance(overlay_field, dict):
                continue

            field_name = str(
                overlay_field.get("name") or ""
            ).strip()

            if not field_name:
                continue

            if field_name not in field_indexes:
                field_indexes[field_name] = len(current_fields)
                current_fields.append(
                    dict(overlay_field)
                )
                continue

            index = field_indexes[field_name]
            combined = dict(current_fields[index])

            base_type = str(
                combined.get("type") or ""
            ).strip().lower()

            overlay_type = str(
                overlay_field.get("type") or ""
            ).strip().lower()

            nullable = (
                bool(combined.get("nullable"))
                or bool(overlay_field.get("nullable"))
                or (
                    base_type == "null"
                    and bool(overlay_type)
                    and overlay_type != "null"
                )
                or (
                    overlay_type == "null"
                    and bool(base_type)
                    and base_type != "null"
                )
            )

            for key, value in overlay_field.items():
                if value is None:
                    continue

                if isinstance(value, str) and not value.strip():
                    continue

                # Concrete type có giá trị hơn null-only sample.
                # Khi overlay chỉ là null nhưng base đã có concrete
                # type thì giữ base type và đánh dấu nullable.
                if (
                    key == "type"
                    and overlay_type == "null"
                    and base_type
                    and base_type != "null"
                ):
                    continue

                combined[key] = value

            if nullable:
                combined["nullable"] = True

            current_fields[index] = combined

    return merged


def _parse_response_schemas(text: str) -> dict:
    schemas = {}

    section_pattern = re.finditer(
        (
            r"5\.1\.\d+\s+"
            r"Mô tả chi tiết Response "
            r"(data[^\n]*)\n"
            r"(.+?)"
            r"(?=5\.1\.\d+|5\.2|\Z)"
        ),
        text,
        re.DOTALL,
    )

    for match in section_pattern:
        schema_path = match.group(1).strip()
        block = match.group(2)

        parsed = _parse_response_table_block(
            block,
            schema_path,
        )

        schemas.update(parsed)

    if not schemas:
        fallback_section = re.search(
            (
                r"(?:^|\n)\s*\d+\.\s*"
                r"Mô tả Response Fields\s*\n"
                r"(.+?)"
                r"(?=\n\s*(?:"
                r"\d+\.\s+|"
                r"[IVX]+\.\s+|"
                r"5\.2|"
                r"Response lỗi|"
                r"Error Codes|"
                r"Danh sách mã lỗi"
                r")|\Z)"
            ),
            text,
            re.DOTALL | re.IGNORECASE,
        )

        if fallback_section:
            parsed = _parse_response_table_block(
                fallback_section.group(1),
                "data",
            )

            schemas.update(parsed)

        if not schemas:
            table_block = find_table_block_after_json_sample(text)
            if table_block:
                parsed = _parse_response_table_block(
                    table_block,
                    "data",
                )
                schemas.update(parsed)

    sample_schemas = parse_success_response_json_sample(
        text
    )
    merged = _merge_response_schema_maps(
        sample_schemas,
        schemas,
    )

    if (
        "data" in merged
        and "data[]" not in merged
        and detect_data_root_is_array(text)
    ):
        merged["data[]"] = merged.pop("data")
        for child_path in list(merged.keys()):
            if child_path.startswith("data."):
                merged[f"data[].{child_path[len('data.'):]}"] = merged.pop(child_path)

    return merged


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