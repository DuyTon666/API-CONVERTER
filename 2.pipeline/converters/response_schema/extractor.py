import json
import re
from typing import Any


def _find_success_response_json(text: str) -> tuple[str, dict] | None:
    """
    Duyệt qua TỪNG chỗ khớp "Response thành công" / "Success Response",
    thử extract + parse JSON thật ở mỗi chỗ, trả về block+payload đầu
    tiên PARSE THÀNH CÔNG và có key "data".
    """
    marker_pattern = r"(Response thành công|Success Response)"

    for match in re.finditer(marker_pattern, text, re.IGNORECASE):
        block = text[match.start():match.start() + 8000]

        block = re.split(
            r"\n\s*(?:\d+(?:\.\d+)*\s+Response lỗi|Response lỗi|Error Codes|Danh sách mã lỗi|[IVX]+\.\s+)",
            block,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        raw_json = _extract_first_json_object(block)
        if not raw_json:
            continue

        try:
            payload = json.loads(raw_json)
        except Exception:
            continue

        if not isinstance(payload, dict) or "data" not in payload:
            continue

        return block, payload

    return None


def find_table_block_after_json_sample(text: str) -> str:
    """
    Fallback khi response table không có heading số thứ tự đứng trước
    (bảng nối thẳng ngay sau JSON mẫu trong Success Response).
    Trả về đoạn text ngay sau dấu đóng JSON để caller tự parse
    tab-separated table, hoặc "" nếu không tìm được JSON mẫu.
    """
    found = _find_success_response_json(text)
    if not found:
        return ""
    block, _payload = found
    raw_json = _extract_first_json_object(block)
    if not raw_json:
        return ""
    end_index = block.find(raw_json)
    if end_index < 0:
        return ""
    end_index += len(raw_json)
    return block[end_index:end_index + 2000]


def parse_success_response_json_sample(text: str) -> dict[str, list[dict]]:
    """
    Fallback generic:
    - Tìm block Success Response / Response thành công có JSON parse được thật
    - Đọc payload["data"]
    - Convert keys trong data thành response_schemas
    """
    found = _find_success_response_json(text)
    if not found:
        return {}

    _block, payload = found
    data = payload.get("data")
    schemas: dict[str, list[dict]] = {}

    if isinstance(data, dict):
        _collect_schema_from_object(data, "data", schemas)
        return schemas

    if isinstance(data, list) and data and isinstance(data[0], dict):
        _collect_schema_from_object(data[0], "data[]", schemas)
        return schemas

    return {}


def detect_data_root_is_array(text: str) -> bool:
    """
    Phát hiện "data" trong Response thành công có phải array hay không,
    dựa trên payload JSON đã parse thành công thật (dùng chung
    _find_success_response_json với parse_success_response_json_sample
    thay vì tự tìm lại bằng substring check riêng).
    """
    found = _find_success_response_json(text)
    if not found:
        return False

    _block, payload = found
    return isinstance(payload.get("data"), list)


def _extract_first_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return ""

    depth = 0
    in_string = False
    escaped = False

    for idx in range(start, len(text)):
        ch = text[idx]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]

    return ""


def _infer_openapi_type(value: Any) -> str:
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "boolean"

    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"

    if isinstance(value, float):
        return "number"

    if isinstance(value, list):
        return "array"

    if isinstance(value, dict):
        return "object"

    return "string"


def infer_array_item_type(value: str) -> str:
    for item in value:
        if item is not None:
            return _infer_openapi_type(item)

    if value:
        return "null"

    return ""


def _collect_schema_from_object(
    obj: dict,
    path: str,
    schemas: dict[str, list[dict]],
) -> None:
    fields = []

    for name, value in obj.items():
        field_type = _infer_openapi_type(value)

        field = {
            "name": name,
            "type": field_type,
            "description": "",
            "original_type": field_type,
        }

        if isinstance(value, list):
            item_type = infer_array_item_type(value)
            if item_type:
                field["item_type"] = item_type
                field["original_type"] = f"array<{item_type}>"

        fields.append(field)

        if isinstance(value, dict):
            _collect_schema_from_object(
                value,
                f"{path}.{name}",
                schemas,
            )

        if isinstance(value, list) and value and isinstance(value[0], dict):
            _collect_schema_from_object(
                value[0],
                f"{path}.{name}",
                schemas,
            )

    if fields:
        schemas[path] = fields
