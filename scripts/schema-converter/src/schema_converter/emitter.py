# emitter.py — nhận ParsedOperation và xuất ra file YAML chuẩn OpenAPI 3.1

from ruamel.yaml import YAML
# DoubleQuotedScalarString: buộc ruamel.yaml in chuỗi có dấu ngoặc kép
# Cần thiết cho $ref vì OpenAPI yêu cầu $ref phải có quotes
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as Q
from pathlib import Path
import yaml
from .parser import ParsedOperation  # import class dữ liệu từ parser
from .io_utils import validate_yaml_file

def emit_yaml(op: ParsedOperation, output_path: str):
    """
    Hàm chính: nhận ParsedOperation, ghi ra file YAML.
    op          — object chứa toàn bộ thông tin đã parse được
    output_path — đường dẫn file YAML sẽ được tạo ra
    """

    #1: chuyển ParsedOperation thành dict Python
    data = _build_structure(op)

    #2: khởi tạo YAML writer
    yaml = YAML()
    yaml.default_flow_style = False  # luôn dùng block style, không dùng inline {a: b}
    yaml.indent(mapping=2, sequence=4, offset=2)  # căn indent giống file viết tay

    #3: dạy YAML writer cách in giá trị None
    # Mặc định ruamel.yaml in None thành rỗng "", ta muốn in thành "null"
    yaml.representer.add_representer(
        type(None),
        lambda dumper, _: dumper.represent_scalar('tag:yaml.org,2002:null', 'null')
    )

    #4: tạo thư mục output nếu chưa có, rồi ghi file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)  # dump = chuyển dict Python → text YAML và ghi vào file
    validate_yaml_file(output_path)

def _ref(path: str) -> dict:
    """
    Helper tạo $ref đúng chuẩn OpenAPI 3.1.
    OpenAPI yêu cầu $ref phải là chuỗi có dấu ngoặc kép.
    Q() (DoubleQuotedScalarString) báo cho ruamel.yaml biết phải in quotes.

    Ví dụ: _ref("../../components/responses/Unauthorized.yaml")
    Output YAML: $ref: "../../components/responses/Unauthorized.yaml"
    """
    return {"$ref": Q(path)}

_SCHEMA_REGISTRY = _load_schema_registry()
REQUEST_AUTO_REMOVE_FIELDS = set(_SCHEMA_REGISTRY.get("request_auto_remove_fields", []))
RESPONSE_READONLY_FIELDS   = set(_SCHEMA_REGISTRY.get("response_readonly_fields", []))

def _apply_server_managed_rules(field_name: str, prop: dict, schema_kind: str) -> dict | None:
    """
    schema_kind = "request"  -> bỏ id/created_at/updated_at khỏi request
    schema_kind = "response" -> thêm readOnly: true vào id/created_at/updated_at
    """
    if schema_kind == "request":
        if field_name in REQUEST_AUTO_REMOVE_FIELDS:
            return None
        return prop

    if schema_kind == "response":
        if field_name in RESPONSE_READONLY_FIELDS:
            prop["readOnly"] = True
        return prop

    return prop

def _resolve_response_schema(op: ParsedOperation) -> dict:
    """..."""
    standard_ref = _ref("../../components/schemas/core/StandardSuccess.yaml")
    if not op.response_schemas or not op.operation_id:
        return standard_ref
    prefix = op.operation_id[0].upper() + op.operation_id[1:]
    service = op.service or "ticket"
    schema_keys = set(op.response_schemas.keys())
    if any(k.startswith("data.data") for k in schema_keys):
        data_schema = _ref(f"../../components/schemas/{service}/{prefix}Data.yaml")
    elif "data[]" in schema_keys:
        array_schema_name = f"{prefix}DataList"
        data_schema = {"type": "array", "items": _ref(f"../../components/schemas/{service}/{array_schema_name}.yaml")}
    elif "data" in schema_keys:
        data_schema = _ref(f"../../components/schemas/{service}/{prefix}Data.yaml")
    else:
        return standard_ref
    return {"allOf": [standard_ref, {"type": "object", "properties": {"data": data_schema}}]}

def _load_schema_registry() -> dict:
    """
    Load schema_registry.yaml ở thư mục scripts/schema-converter.
    """
    converter_dir = Path(__file__).resolve().parents[2]
    registry_path = converter_dir / "schema_registry.yaml"

    if not registry_path.exists():
        return {}

    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}

    # Normalize key về string để tránh lỗi YAML parse key số thành int.
    if "error_codes" in data:
        data["error_codes"] = {
            str(k): v for k, v in (data.get("error_codes") or {}).items()
        }

    if "response_refs" in data:
        data["response_refs"] = {
            str(k): v for k, v in (data.get("response_refs") or {}).items()
        }

    return data


_SCHEMA_REGISTRY = _load_schema_registry()


def _group_error_codes_by_status(error_codes):
    """
    Input: op.error_codes từ parser.
    Output: {"422": ["4200", "4468"], "404": ["4004"], ...}
    """
    grouped = {}
    registry = _SCHEMA_REGISTRY.get("error_codes", {})

    for code in error_codes or []:
        code = str(code).strip()
        meta = registry.get(code)

        # Không biết code này thì bỏ qua để không làm fail toàn pipeline.
        # Nếu muốn strict hơn thì đổi thành raise ValueError.
        if not meta:
            continue

        status = str(meta.get("http_status", "")).strip()
        if not status:
            continue

        grouped.setdefault(status, []).append(code)

    return grouped


def _make_422_response(codes):
    registry = _SCHEMA_REGISTRY.get("error_codes", {})
    lines = []

    for code in codes:
        meta = registry.get(str(code), {})
        message = meta.get("message", "Lỗi nghiệp vụ")
        lines.append(f"{code} — {message}")

    return {
        "description": "\n".join(lines),
        "content": {
            "application/json": {
                "schema": _ref("../../components/schemas/core/StandardError.yaml")
            }
        }
    }

def _build_structure(op: ParsedOperation) -> dict:
    """
    Xây dựng toàn bộ cấu trúc OpenAPI từ ParsedOperation.
    Trả về 1 dict Python — ruamel.yaml sẽ convert dict này thành YAML.
    """

    # --- PHẦN 1: XÂY PARAMETERS ---
    parameters = []
    for p in op.parameters:
        # Mỗi path parameter cần: name, in, required, schema
        parameters.append({
            "name": p["name"],
            "in": "path",            # path parameter vì nằm trong URL
            "required": p["required"],
            "schema": {"type": p["type"].lower()}  # lower() vì OpenAPI dùng "integer" không phải "Integer"
        })
    for p in op.query_parameters:
        schema = {"type": p["type"]}
        if p.get("is_enum") and p.get("enum_values"):
            schema["enum"] = p["enum_values"]
        if p.get("format"):
            schema["format"] = p["format"]
        param = {
            "name": p["name"],
            "in": "query",
            "required": False,
            "schema": schema,
        }
        if p.get("default"):
            param["schema"]["default"] = p["default"]
        if p.get("description"):
            param["description"] = p["description"]
        parameters.append(param)

    # --- PHẦN 2: GROUP ERROR CODES THEO HTTP STATUS ---
    grouped_errors = _group_error_codes_by_status(op.error_codes)
    business_codes = grouped_errors.get("422", [])

    # --- PHẦN 3: XÂY RESPONSES ---
    response_schema = _resolve_response_schema(op)   # gọi hàm bên ngoài
    has_real_data = bool(op.response_schemas and op.operation_id)
    response_200_content = {"schema": response_schema}
    if not has_real_data:
        response_200_content["example"] = {"success": True, "data": None, "error": None}

    responses = {   # responses luôn được tạo, không nằm trong if
        "200": {
            "description": "Thành công",
            "content": {"application/json": response_200_content}
        },
        "401": _ref("../../components/responses/Unauthorized.yaml"),
        "403": _ref("../../components/responses/Forbidden.yaml"),
        "404": _ref("../../components/responses/NotFound.yaml"),
        "500": _ref("../../components/responses/InternalError.yaml"),
    }

    response_refs = _SCHEMA_REGISTRY.get("response_refs", {})

    for status, ref_path in response_refs.items():
        if status not in responses:   # không ghi đè 200/401/403/404/500 đã có
            responses[status] = _ref(ref_path)

    if business_codes:
        responses["422"] = _make_422_response(business_codes)

    # --- PHẦN 4: GHÉP LẠI THÀNH CẤU TRÚC OPENAPI ---
    method_key = op.method.lower()  # "PUT" → "put" vì OpenAPI dùng chữ thường
    structure = {
        method_key: {
            "summary": op.summary,       
            "operationId": op.operation_id,   
            "description": op.description,
            "tags": [op.service.capitalize() if op.service else "API"],
            "security": [{"bearerAuth": []}],
            "x-permission": op.permission,
            "parameters": parameters,
            "responses": responses,
        }
    }

    # --- PHẦN 5: THÊM REQUEST BODY NẾU CÓ ---
    # Không phải endpoint nào cũng có request body
    # Ví dụ: close ticket không có, nhưng create ticket có
    has_body = op.has_request_body or bool(op.request_body_fields)

    if has_body and op.method.upper() not in ("GET", "DELETE"):
        schema_name = op.operation_id[0].upper() + op.operation_id[1:] + "Request" if op.operation_id else ""
        schema_ref  = f"../../components/schemas/{op.service}/{schema_name}.yaml" if schema_name else ""
        structure[method_key]["requestBody"] = {
            "required": op.request_body_required,
            "content": {
                op.content_type: {
                    "schema": _ref(schema_ref)
                }
            }
        }
    return structure

def emit_request_schema(op: ParsedOperation, schemas_dir: str):
    """Tạo file RequestSchema.yaml từ request body fields"""
    if not op.request_body_fields or not op.operation_id:
        return

    # reopenUserTicket → ReopenUserTicketRequest.yaml
    schema_name = op.operation_id[0].upper() + op.operation_id[1:] + "Request"
    output_path = Path(schemas_dir) / f"{schema_name}.yaml"

    if output_path.exists():
        print(f"    Schema đã tồn tại, bỏ qua: {output_path}")
        return schema_name

    properties = {}
    required_fields = []

    for f in op.request_body_fields:
        dtype = f["type"].lower().replace(" ", "")
        if dtype == "enum":
            prop = {"type": "string"}
            if f.get("enum_values"):
                prop["enum"] = f["enum_values"]
        elif dtype == "array<object>":
            sub_fields = op.request_body_children.get(f["name"], [])
            if sub_fields:
                sub_props = {}
                sub_required = []
                for sf in sub_fields:
                    s_dtype = sf["type"].lower().replace(" ", "")
                    if s_dtype == "integer":
                        sp = {"type": "integer"}
                    else:
                        sp = {"type": "string"}
                        if sf.get("max_length"):
                            sp["maxLength"] = sf["max_length"]
                    if sf.get("description"):
                        sp["description"] = sf["description"]
                    sub_props[sf["name"]] = sp
                    if sf["required"]:
                        sub_required.append(sf["name"])
                items = {"type": "object", "properties": sub_props}
                if sub_required:
                    items["required"] = sub_required
                prop = {"type": "array", "items": items}
            else:
                # Không có sub-section trong docx → giữ generic, cần review thủ công
                prop = {"type": "array", "items": {"type": "object"}}
        elif dtype == "array<file>":
            prop = {"type": "array", "items": {"type": "string", "format": "binary"}}
            if f.get("max_items"):
                prop["maxItems"] = f["max_items"]  
        elif dtype == "integer":
            prop = {"type": "integer"}
        else:
            prop = {"type": "string"}
            if f.get("max_length"):
                prop["maxLength"] = f["max_length"]

        if f.get("description"):
            prop["description"] = f["description"]

        field_name = f["name"]
        prop = _apply_server_managed_rules(field_name, prop, schema_kind="request")

        # id/created_at/updated_at không được nằm trong request schema
        if prop is None:
            continue

        properties[field_name] = prop
        if f["required"]:
            required_fields.append(field_name)

    data = {"type": "object", "properties": properties}
    if required_fields:
        data["required"] = required_fields

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    validate_yaml_file(output_path)

    print(f"      Schema: {output_path}")
    return schema_name

def _build_properties(fields: list, parent_path: str = "", all_schemas: dict = None, prefix: str = "") -> dict:
    properties = {}
    for f in fields:
        dtype = f["type"]
        child_path = f"{parent_path}.{f['name']}" if parent_path else f['name']
        has_child = all_schemas and child_path in all_schemas

        def _schema_name(path):
            return prefix + "".join(p.capitalize() for p in path.split("."))

        # Check xem child có nested thêm không
        def _child_has_nested(path):
            if not all_schemas:
                return False
            return any(k.startswith(path + ".") for k in all_schemas)

        if dtype == "array":
            if has_child:
                if _child_has_nested(child_path):
                    # Phức tạp → $ref file riêng
                    prop = {"type": "array", "items": _ref(f"./{_schema_name(child_path)}.yaml")}
                else:
                    # Đơn giản → inline
                    child_fields = all_schemas[child_path]
                    prop = {"type": "array", "items": {
                        "type": "object",
                        "properties": _build_properties(child_fields, child_path, all_schemas, prefix)
                    }}
            else:
                prop = {"type": "array", "items": {"type": "object"}}
        elif dtype == "object":
            if has_child:
                if _child_has_nested(child_path):
                    # Phức tạp → $ref file riêng
                    prop = _ref(f"./{_schema_name(child_path)}.yaml")
                else:
                    # Đơn giản → inline
                    child_fields = all_schemas[child_path]
                    prop = {"type": "object", "properties": _build_properties(child_fields, child_path, all_schemas, prefix)}
            else:
                prop = {"type": "object"}
        elif dtype == "integer":
            prop = {"type": "integer"}
        else:
            prop = {"type": "string"}

        if f.get("description"):
            prop["description"] = f["description"]
        field_name = f["name"]
        prop = _apply_server_managed_rules(field_name, prop, schema_kind="response")

        if prop is None:
            continue

        properties[field_name] = prop

    return properties

def emit_response_schemas(op: ParsedOperation, schemas_dir: str):
    if not op.response_schemas or not op.operation_id:
        return
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)

    prefix = op.operation_id[0].upper() + op.operation_id[1:]

    for path, fields in op.response_schemas.items():
        parts = path.split(".")
        sub_name = prefix + "".join(p.capitalize() for p in parts)
        sub_name = sub_name.replace("[]", "List") 
        sub_path = Path(schemas_dir) / f"{sub_name}.yaml"
        sub_data = {
            "type": "object",
            "properties": _build_properties(fields, parent_path=path, all_schemas=op.response_schemas, prefix=prefix)
        }
        sub_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sub_path, "w", encoding="utf-8") as f:
            yaml.dump(sub_data, f)
        validate_yaml_file(sub_path)
        print(f"      Response schema: {sub_path}")