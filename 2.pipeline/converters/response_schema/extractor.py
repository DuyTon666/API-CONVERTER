import json
import re
from typing import Any


def parse_success_response_json_sample(text: str) -> dict[str, list[dict]]:
    """
    Fallback generic:
    - Tìm block Success Response / Response thành công
    - Lấy JSON object đầu tiên trong block
    - Đọc payload["data"]
    - Convert keys trong data thành response_schemas
    """
    block = _find_success_response_block(text)
    if not block:
        return {}

    raw_json = _extract_first_json_object(block)
    if not raw_json:
        return {}

    try:
        payload = json.loads(raw_json)
    except Exception:
        return {}

    data = payload.get("data")
    if not isinstance(data, dict):
        return {}

    schemas: dict[str, list[dict]] = {}
    _collect_schema_from_object(data, "data", schemas)
    return schemas


def _find_success_response_block(text: str) -> str:
    marker_pattern = r"(Response thành công|Success Response)"

    for match in re.finditer(marker_pattern, text, re.IGNORECASE):
        block = text[match.start():match.start() + 8000]

        block = re.split(
            r"\n\s*(?:\d+(?:\.\d+)*\s+Response lỗi|Response lỗi|Error Codes|Danh sách mã lỗi|[IVX]+\.\s+)",
            block,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        if "{" in block and "data" in block:
            return block

    return ""


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