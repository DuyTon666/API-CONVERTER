from core.config import DIST_DIR
from core.errors import ErrorCode, http_error
from services.bundle_sync import (
    _HTTP_METHODS,
    diff_bundle,
    sync_schema_fields,
    _index_schema_files
)
from api_utils.field_paths import set_value_at_path

# 2 scheme wrapper chung, không phải dữ liệu nghiệp vụ riêng của operation nào,
# loại khỏi kết quả resolve response (StandardSuccess.data mới là cái cần quan tâm).
_STANDARD_WRAPPER_SCHEMAS = {"StandardSuccess", "StandardError"}

def _resolve_ref_name(node: object) -> str | None:
    """node == {'$ref': '#/components/schemas/X'} -> 'X', else None."""
    if isinstance(node, dict) and isinstance(node.get("$ref"), str):
       ref = node["$ref"]
       prefix = "#/components/schemas/"
       if ref.startswith(prefix):
           return ref[len(prefix):]
    return None
    
def _resolve_data_schema_name(node: object) -> tuple[str | None, bool]:
    """Trả (schema_name, is_list). Hỗ trợ node là $ref trực tiếp, hoặc
        {type: array, items: $ref} (case getSupportStaffsByTicket)."""
    if not isinstance(node, dict):
        return None, False
    direct = _resolve_ref_name(node)
    if direct:
        return direct, False
    if node.get("type") == "array":
        name = _resolve_ref_name(node.get("items"))
        if name:
            return name, True
    return None, False

def _resolve_request_schema(operation: dict) -> tuple[str | None, bool]:
    """requestBody.content['application/json'].schema -> (name, is_list).
    Trả (None, False) nếu không có requestBody hoặc content-type khác
    application/json (vd multipart/form-data — các endpoint upload file ticket)."""
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None, False
    content = request_body.get("content") or {}
    schema = (content.get("application/json") or {}).get("schema")
    return _resolve_data_schema_name(schema)

def _resolve_response_schema(operation: dict) -> tuple[str | None, bool]:
    """Tìm response 2xx đầu tiên có content; nếu schema là allOf, tìm member có
    'properties.data' rồi giải qua đó. Trả (None, False) nếu operation không có
    schema response riêng (chỉ trả StandardSuccess/StandardError trần — hợp lệ,
    không phải lỗi)."""
    for code, resp in (operation.get("responses") or {}).items():
        if not code.startswith("2") or not isinstance(resp, dict):
            continue
        content = resp.get("content") or {}
        schema = (content.get("application/json") or {}).get("schema")
        if not isinstance(schema, dict):
            continue

        all_of = schema.get("allOf")
        if isinstance(all_of, list):
            for member in all_of:
                if isinstance(member, dict) and "data" in (member.get("properties") or {}):
                    name, is_list = _resolve_data_schema_name(member["properties"]["data"])
                    if name and name not in _STANDARD_WRAPPER_SCHEMAS:
                        return name, is_list
            return None, False    

        name, is_list = _resolve_data_schema_name(schema)
        if name and name not in _STANDARD_WRAPPER_SCHEMAS:
            return name, is_list
        return None, False
    return None, False

def _walk_schema_properties(
    schema: dict, path_prefix: list[str], label_prefix: list[str], depth: int
) -> tuple[list[dict], list[tuple[str, bool]]]:
    """Đệ quy qua properties của 1 schema. Trả (fields, nested_refs).
    fields: list {path, label, depth, type, description, readOnly} — path theo
    đúng field-path grammar (api_utils/field_paths.py), vd
    "properties.contact.properties.contact_admin.properties.email.description".
    nested_refs: list (schema_name, is_list) cho property là $ref (trực tiếp
    hoặc qua items) sang schema khác — caller tự dựng thành group riêng."""
    fields: list[dict] = []
    nested_refs: list[tuple[str, bool]] = []

    for name, prop in (schema.get("properties") or {}).items():
        if not isinstance(prop, dict):
            continue

        this_path = path_prefix + ["properties", name]
        this_label = label_prefix + [name]

        ref_name, is_list = _resolve_data_schema_name(prop)
        if ref_name:
            nested_refs.append((ref_name, is_list))
            continue

        fields.append(
            {
                "path": ".".join(this_path + ["description"]),
                "label": " › ".join(this_label),
                "depth": depth,
                "type": prop.get("type") or "object",
                "description": prop.get("description") or "",
                "readOnly": bool(prop.get("readOnly")),
            }
        )

        if prop.get("type") == "object" and prop.get("properties"):
            sub_fields, sub_refs = _walk_schema_properties(prop, this_path, this_label, depth + 1)
            fields.extend(sub_fields)
            nested_refs.extend(sub_refs)
        elif prop.get("type") == "array":
            items = prop.get("items")
            if isinstance(items, dict) and items.get("type") == "object" and items.get("properties"):
                sub_fields, sub_refs = _walk_schema_properties(
                    items, this_path + ["items"], this_label, depth + 1
                )
                fields.extend(sub_fields)
                nested_refs.extend(sub_refs)
        # array/object rỗng (không properties/items.properties) -> chỉ giữ field
        # vừa thêm ở trên (mô tả chính property đó), không đệ quy tiếp — theo
        # đúng quyết định đã chốt cho 5 property kiểu này (vd mappings_summary).

    return fields, nested_refs

def _compute_schema_fan_in(
    schemas: dict, top_level: list[tuple[str, str]]
) -> dict[str, set[str]]:
    """BFS từ mỗi (schema_name, operationId) ở top_level qua mọi $ref lồng bên
    trong, build reverse-index schema_name -> set(operationId). Dùng để đánh dấu
    schema nào thực sự dùng chung (fan-in > 1), kể cả khi bản thân schema top-level
    của operation không hề bị share (vd UserInfo lồng trong GetTicketDetailData)."""
    fan_in: dict[str, set[str]] = {}

    def visit(schema_name: str, op_id: str, seen: frozenset[str]) -> None:
        if schema_name in seen:
            return
        seen = seen | {schema_name}
        fan_in.setdefault(schema_name, set()).add(op_id)
        schema = schemas.get(schema_name)
        if not isinstance(schema, dict):
            return
        _, nested_refs = _walk_schema_properties(schema, [], [], 0)
        for ref_name, _is_list in nested_refs:
            visit(ref_name, op_id, seen)

    for schema_name, op_id in top_level:
        visit(schema_name, op_id, frozenset())

    return fan_in


def _build_schema_group(schema_name: str, schemas: dict, fan_in: dict[str, set[str]]) -> dict:
    schema = schemas.get(schema_name) or {}
    fields, nested_refs = _walk_schema_properties(schema, [], [], 0)
    return {
        "schemaName": schema_name,
        "shared": len(fan_in.get(schema_name, set())) > 1,
        "fields": fields,
        "nested": [
            _build_schema_group(ref_name, schemas, fan_in) for ref_name, _is_list in nested_refs
        ],
    }


# Logic cho route GET /docs/schema-fields — trả 1 entry/operation, request/response
# có thể null (operation không có requestBody, hoặc chỉ trả StandardSuccess trần).
def list_operation_data_schemas() -> list[dict]:
    import yaml as _yaml

    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise http_error(
            404, ErrorCode.BUNDLE_NOT_FOUND, "Bundle chưa được tạo, hãy build tài liệu trước"
        )
    bundle = _yaml.safe_load(bundle_path.read_text(encoding="utf-8")) or {}
    schemas = (bundle.get("components") or {}).get("schemas") or {}

    resolved: dict[str, dict[str, str | None]] = {}
    top_level: list[tuple[str, str]] = []

    for path_item in (bundle.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            op_id = operation.get("operationId") or ""
            if not op_id:
                continue
            req_name, _ = _resolve_request_schema(operation)
            resp_name, _ = _resolve_response_schema(operation)
            resolved[op_id] = {"request": req_name, "response": resp_name}
            if req_name:
                top_level.append((req_name, op_id))
            if resp_name:
                top_level.append((resp_name, op_id))

    fan_in = _compute_schema_fan_in(schemas, top_level)

    return [
        {
            "operationId": op_id,
            "request": _build_schema_group(names["request"], schemas, fan_in)
            if names["request"]
            else None,
            "response": _build_schema_group(names["response"], schemas, fan_in)
            if names["response"]
            else None,
        }
        for op_id, names in resolved.items()
    ]


# Logic cho route PATCH /docs/schema-fields — mỗi update {schemaName, path,
# description}. Tái dùng nguyên xi diff_bundle()/sync_schema_fields() đã có sẵn
# trong bundle_sync.py (đã chạy đúng trong production qua tab YAML thô) — không
# viết engine ghi mới.
def update_schema_fields(updates: list) -> dict:
    import copy
    import yaml as _yaml

    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise http_error(
            404, ErrorCode.BUNDLE_NOT_FOUND, "Bundle chưa được tạo, hãy build tài liệu trước"
        )

    old_bundle = _yaml.safe_load(bundle_path.read_text(encoding="utf-8")) or {}
    new_bundle = copy.deepcopy(old_bundle)
    schemas = (new_bundle.get("components") or {}).get("schemas") or {}

    updated = 0
    for upd in updates:
        schema_name = upd.get("schemaName")
        path = upd.get("path")
        node = schemas.get(schema_name)
        if not schema_name or not path or not isinstance(node, dict):
            continue
        if set_value_at_path(node, path, upd.get("description", "")):
            updated += 1

    changes = diff_bundle(old_bundle, new_bundle)
    sync_schema_fields(new_bundle, changes, _index_schema_files())

    bundle_path.write_text(
        _yaml.dump(new_bundle, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return {"ok": True, "updated": updated}

# Làm phẳng 1 SchemaGroup (kể cả nested không shared) thành list field kèm
# schemaName riêng — dùng cho AI suggest (liệt kê field trống + ghép kết quả trả
# về đúng chỗ). Bỏ qua toàn bộ nhánh group nào shared=True (không bao giờ gợi ý
# AI vào schema dùng chung như UserInfo).
def flatten_schema_group(group: dict | None) -> list[dict]:
    if group is None:
        return []
    flat = [{**f, "schemaName": group["schemaName"]} for f in group["fields"]]
    for nested in group["nested"]:
        if not nested["shared"]:
            flat.extend(flatten_schema_group(nested))
    return flat