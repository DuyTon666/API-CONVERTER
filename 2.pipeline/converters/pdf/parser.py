import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ParsedOperation:
    summary: str = ""
    operation_id: str = ""
    description: str = ""
    method: str = ""
    path: str = ""
    service: str = ""
    content_type: str = "application/json"
    permission: str = ""
    parameters: list = field(default_factory=list)
    has_request_body: bool = False
    request_body_required: bool = True
    request_body_fields: list = field(default_factory=list)      
    error_codes: list = field(default_factory=list)
    response_schemas: dict = field(default_factory=dict)
    request_body_children: dict = field(default_factory=dict)
    review_flags: list = field(default_factory=list)
    version: str = ""
    query_parameters: list = field(default_factory=list)
    change_history: list = field(default_factory=list)

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
    op.review_flags = _get_review_flags(op, text)
    op.change_history = _parse_change_history(text)
    if op.change_history:
        op.version = op.change_history[-1]["version"]
    else:
        op.version = _parse_version(text)
    op.query_parameters = _parse_query_parameters(text)
    return op

def _parse_method(text: str) -> str:
    match = re.search(r'\b(GET|POST|PUT|DELETE|PATCH)\b', text)
    return match.group(1) if match else ""

def _parse_path(text: str) -> str:
    match = re.search(r'(/v\d+/[^\s]+)', text)
    return match.group(1) if match else ""

def _parse_service(text: str) -> str:
    match = re.search(r'Endpoint Service.*?\n.*?(/\S+)\s+(\S+)\s+(https?://\S+)\s+(\w+)', text, re.DOTALL)
    if match:
        return match.group(2)
    match2 = re.search(r'(account|ticket|user|payment)\s+apigateway', text, re.IGNORECASE)
    return match2.group(1) if match2 else ""

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
    section = re.search(r'Query Parameters(.+?)(?=4\.3|4\.4|\Z)', text, re.DOTALL | re.IGNORECASE)
    if not section:
        return []

    params = []
    for line in section.group(1).split('\n'):
        cols = [c.strip() for c in line.split('\t')]
        # Bảng query params: Tên | Kiểu | Mặc định | Mô tả (4 cột, không có cột Bắt buộc)
        if len(cols) < 2:
            continue
        name = cols[0]
        if not name or name in ('Tên', 'Field', ''):
            continue
        dtype = cols[1].lower()
        default = cols[2] if len(cols) > 2 else None
        description = cols[3] if len(cols) > 3 else ''

        # Map type sang OpenAPI type
        if dtype == 'integer':
            openapi_type = 'integer'
        elif dtype == 'date':
            openapi_type = 'string'
        else:
            openapi_type = 'string'

        # Enum values
        enum_values = []
        if dtype == 'enum':
            enum_values = re.findall(r'([A-Z][A-Z_]+):', description)

        params.append({
            "name": name,
            "type": openapi_type,
            "is_enum": dtype == 'enum',
            "enum_values": enum_values,
            "default": int(default) if default and default.isdigit() else (default if default else None),
            "description": description,
            "format": "date-time" if dtype == 'date' else None,
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
    section = re.search(r'4\.3 Request Body(.+?)4\.4', text, re.DOTALL)
    if not section:
        return False, True
    
    body_text = section.group(1).strip()
    if "Không có" in body_text or len(body_text) <= 5:
        return False, True
    
    # required: true nếu có ít nhất 1 field bắt buộc (có ✔️)
    # required: false nếu tất cả fields đều optional (không có ✔️)
    required = '\u2714' in body_text    
    return True, required

def _parse_request_body_fields(text: str) -> list:
    """Extract từng field trong bảng 4.3 Request Body"""
    section = re.search(r'4\.3 Request Body(.+?)4\.4', text, re.DOTALL)
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
        if not name or name == 'Tên':
            continue
        required = '✔' in cols[1]
        dtype = cols[2] if len(cols) > 2 else 'string'
        # Lấy constraints từ cột Mô tả nếu có
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
def _parse_response_schemas(text: str) -> dict:
    schemas = {}
    section_pattern = re.finditer(
        r'5\.1\.\d+ Mô tả chi tiết Response (data[^\n]*)\n(.+?)(?=5\.1\.\d+|5\.2|\Z)',
        text, re.DOTALL
    )
    for match in section_pattern:
        schema_path = match.group(1).strip()
        block = match.group(2)
        fields = []
        for line in block.split('\n'):
            cols = [c.strip() for c in line.split('\t')]
            if len(cols) < 2 or cols[0] in ('Field', ''):
                continue
            name = cols[0]
            dtype = cols[1]
            desc = cols[2] if len(cols) > 2 else ''
            dtype_lower = dtype.lower()
            if 'array<object>' in dtype_lower:
                openapi_type = 'array'
            elif 'object' in dtype_lower:
                openapi_type = 'object'
            elif 'integer' in dtype_lower:
                openapi_type = 'integer'
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