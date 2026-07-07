# emitter.py — nhận ParsedOperation và xuất ra file YAML chuẩn OpenAPI 3.1

from ruamel.yaml import YAML
# DoubleQuotedScalarString: buộc ruamel.yaml in chuỗi có dấu ngoặc kép
# Cần thiết cho $ref vì OpenAPI yêu cầu $ref phải có quotes
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as Q
from pathlib import Path
import yaml
from converters.models import ParsedOperation
from validators.yaml_validator import validate_yaml_file

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
    """
    return {"$ref": Q(path)}


_OMIT_DEFAULT = object()


def _schema_type_set(schema: dict) -> set[str]:
    raw_type = schema.get("type")

    if isinstance(raw_type, list):
        return {str(item) for item in raw_type}

    if raw_type:
        return {str(raw_type)}

    return set()


def _normalize_schema_default(raw_default, schema: dict):
    """
    Normalize default trước khi emit OpenAPI.

    - Không emit default null/None/"null" cho primitive schema.
    - Cast default theo schema type để tránh lỗi kiểu:
      type: integer + default: "null"
      type: integer + default: "1"
    """
    if raw_default is None:
        return _OMIT_DEFAULT

    if isinstance(raw_default, str):
        value = raw_default.strip()

        if value.lower() in {"", "null", "none"}:
            return _OMIT_DEFAULT
    else:
        value = raw_default

    schema_types = _schema_type_set(schema)

    if "integer" in schema_types:
        try:
            return int(value)
        except (TypeError, ValueError):
            return _OMIT_DEFAULT

    if "number" in schema_types:
        try:
            return float(value)
        except (TypeError, ValueError):
            return _OMIT_DEFAULT

    if "boolean" in schema_types:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            lowered = value.lower()
            if lowered in {"true", "1", "yes", "y", "có"}:
                return True
            if lowered in {"false", "0", "no", "n", "không", "khong"}:
                return False

        return _OMIT_DEFAULT

    return value


def _has_canonical_request_schema(op: ParsedOperation) -> bool:
    result = getattr(op, "request_schema_result", None)
    return bool(result and getattr(result, "root", None))


def _can_emit_request_schema(op: ParsedOperation) -> bool:
    return bool(
        op.operation_id
        and (
            _has_canonical_request_schema(op)
            or op.request_body_fields
        )
    )


def _request_schema_name(operation_id: str) -> str:
    if not operation_id:
        return ""

    base = operation_id[0].upper() + operation_id[1:]

    if base.lower().endswith("request"):
        return base
    
    return base + "Request"


def _schema_node_to_openapi(node, schema_kind: str = "request") -> dict:
    node_type = getattr(node, "type", "string") or "string"

    if getattr(node, "nullable", False):
        schema = {"type": [node_type, "null"]}
    else:
        schema = {"type": node_type}

    if getattr(node, "description", None):
        schema["description"] = node.description

    if getattr(node, "format", None):
        schema["format"] = node.format

    if getattr(node, "enum", None):
        schema["enum"] = node.enum

    if getattr(node, "has_default", False):
        default_value = _normalize_schema_default(node.default, schema)
        if default_value is not _OMIT_DEFAULT:
            schema["default"] = default_value

    if getattr(node, "has_example", False):
        schema["example"] = node.example

    constraints = getattr(node, "constraints", {}) or {}
    for key, value in constraints.items():
        if value is not None:
            schema[key] = value

    if node.type == "object":
        properties = {}

        for field_name, child in node.properties.items():
            prop = _schema_node_to_openapi(child, schema_kind=schema_kind)
            prop = _apply_server_managed_rules(
                field_name,
                prop,
                schema_kind=schema_kind,
            )

            if prop is None:
                continue

            prop = _ensure_schema_description(prop, field_name)
            properties[field_name] = prop

        schema["properties"] = properties

        required = [
            field_name
            for field_name in getattr(node, "required", [])
            if field_name in properties
        ]

        if required:
            schema["required"] = required

    if node.type == "array":
        if getattr(node, "items", None) is not None:
            schema["items"] = _schema_node_to_openapi(
                node.items,
                schema_kind=schema_kind,
            )
        else:
            schema["items"] = {}

    return schema

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
    standard_ref = _ref(_CONFIG.get(
        "standard_success_ref",
        "../../components/schemas/common/StandardSuccess.yaml"
    ))
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
    

def _load_config(config_dir: str) -> dict:
    cfg = Path(config_dir)
    result = {}

    # --- global/review_actions.yaml ---
    review_path = cfg / "global" / "review_actions.yaml"
    if review_path.exists():
        raw = yaml.safe_load(review_path.read_text(encoding="utf-8")) or {}
        result["review_actions"] = raw.get("actions", {})
        result["post_enrich_checks"] = raw.get("post_enrich_checks", {})
    else:
        print(f"  [WARN] Không tìm thấy: {review_path}")
        result["review_actions"] = {}
        result["post_enrich_checks"] = {}

    # --- error_code_map.yaml ---
    error_map_path = cfg / "error_code_map.yaml"
    if error_map_path.exists():
        raw = yaml.safe_load(error_map_path.read_text(encoding="utf-8")) or {}
        result["error_codes"] = {
            str(k): v for k, v in raw.get("error_codes", {}).items()
        }
    else:
        print(f"  [WARN] Không tìm thấy: {error_map_path}")
        result["error_codes"] = {}

    # --- schema_registry.yaml ---
    registry_path = cfg / "schema_registry.yaml"
    if registry_path.exists():
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        result["schema_registry"] = raw.get("fields", {})
    else:
        print(f"    [WARN] Không tìm thấy: {registry_path}")
        result["schema_registry"] = {}

    # --- schema_description_policy.yaml ---
    desc_policy_path = cfg / "schema_description_policy.yaml"
    if desc_policy_path.exists():
        result["schema_description_policy"] = (
            yaml.safe_load(desc_policy_path.read_text(encoding="utf-8")) or {}
        )
    else:
        result["schema_description_policy"] = {"enabled": False}

    # --- global/response_refs.yaml ---
    refs_path = cfg / "global" / "response_refs.yaml"
    if refs_path.exists():
        raw = yaml.safe_load(refs_path.read_text(encoding="utf-8")) or {}
        result["response_refs"] = {
            str(k): v for k, v in raw.get("response_refs", {}).items()
        }
        result["standard_success_ref"] = raw.get(
            "standard_success_ref",
            "../../components/schemas/common/StandardSuccess.yaml"
        )
        result["standard_error_ref"] = raw.get(
            "standard_error_ref",
            "../../components/schemas/common/StandardError.yaml"
        )
    else:
        print(f"  [WARN] Không tìm thấy: {refs_path}")
        result["response_refs"] = {}
        result["standard_success_ref"] = "../../components/schemas/common/StandardSuccess.yaml"
        result["standard_error_ref"]   = "../../components/schemas/common/StandardError.yaml"

    # --- global/server_managed_fields.yaml ---
    smf_path = cfg / "global" / "server_managed_fields.yaml"
    if smf_path.exists():
        raw = yaml.safe_load(smf_path.read_text(encoding="utf-8")) or {}
        result["request_auto_remove_fields"] = raw.get("request_auto_remove_fields", [])
        result["response_readonly_fields"]   = raw.get("response_readonly_fields", [])
    else:
        print(f"  [WARN] Không tìm thấy: {smf_path}")
        result["request_auto_remove_fields"] = []
        result["response_readonly_fields"]   = []

    return result


_CONFIG: dict = {}
REQUEST_AUTO_REMOVE_FIELDS: set = set()
RESPONSE_READONLY_FIELDS: set   = set()


def init_config(config_dir: str) -> None:
    global _CONFIG, REQUEST_AUTO_REMOVE_FIELDS, RESPONSE_READONLY_FIELDS
    _CONFIG                    = _load_config(config_dir)
    REQUEST_AUTO_REMOVE_FIELDS = set(_CONFIG.get("request_auto_remove_fields", []))
    RESPONSE_READONLY_FIELDS   = set(_CONFIG.get("response_readonly_fields", []))


def _parameter_description(param: dict, location: str) -> str:
    existing = str(param.get("description") or "").strip()
    if existing:
        return existing

    name = str(param.get("name") or "").strip()
    if not name:
        return "Tham số API"

    if location == "path":
        return f"Tham số đường dẫn '{name}'."
    
    if location == "query":
        return f"Tham số truy vấn '{name}'."

    return f"Tham số  '{name}'."


def _normalize_parameter_default(value, schema_type: str):
    if value is None:
        return None

    schema_type = str(schema_type or "").lower()

    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"null", "none", "n/a"}:
            return None

        if schema_type == "integer":
            try:
                return int(text)
            except ValueError:
                return None

        if schema_type == "number":
            try:
                return float(text)
            except ValueError:
                return None

        if schema_type == "boolean":
            lowered = text.lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
            return None
        
        return text

    if schema_type == "integer":
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return None

    if schema_type == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        return None

    if schema_type == "boolean":
        if isinstance(value, bool):
            return value
        return None

    return value


def _format_description_template(template: str, **values) -> str:
    try:
        return str(template).format(**values)
    except (KeyError, IndexError, ValueError):
        return str(template)


def _schema_description_policy() -> dict:
    return _CONFIG.get("schema_description_policy", {}) or {}


def _generated_description_enabled() -> bool:
    policy = _schema_description_policy()
    return bool(policy.get("enabled", False))


def _schema_property_description(field_name: str, existing: str | None = None) -> str:
    existing = str(existing or "").strip()
    if existing:
        return existing

    if not _generated_description_enabled():
        return ""

    name =str(field_name or "").strip()
    if not name:
        return ""

    policy = _schema_description_policy()
    common_fields = policy.get("common_fields", {}) or {}

    configured = str(common_fields.get(name) or "").strip()
    if configured:
        return configured

    template = policy.get("property_fallback_template", "Trường '{field_name}'.")
    return _format_description_template(
        template,
        field_name=name,
        field_label=name.replace("_", " "),
    )


def _schema_component_description(schema_name: str, existing: str | None = None) -> str:
    existing =str(existing or "").strip()
    if existing:
        return existing

    if not  _generated_description_enabled():
        return ""

    name = str(schema_name or "").strip()
    if not name:
        return ""

    policy = _schema_description_policy()
    template = policy.get("component_fallback_template", "Schema '{schema_name}'.")
    return _format_description_template(template, schema_name=name)


def _ensure_schema_description(schema: dict, name: str, *, component: bool = False) -> dict:
    if not isinstance(schema, dict):
        return schema

    description = (
        _schema_component_description(name, schema.get("description"))
        if component
        else _schema_property_description(name, schema.get("description"))
    )

    if description:
        schema["description"] = description

    return schema


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
            "schema": {"type": p["type"].lower()} , # lower() vì OpenAPI dùng "integer" không phải "Integer"
            "description": _parameter_description(p, "path"),
        })

    for p in op.query_parameters:
        schema_type = str(p.get("type") or "string").strip().lower()
        description = _parameter_description(p, "query")

        schema = {"type": schema_type}

        if p.get("is_enum") and p.get("enum_values"):
            schema["enum"] = p["enum_values"]
            schema["description"] = description

        if p.get("format"):
            schema["format"] = p["format"]
        
        default_value = _normalize_parameter_default(p.get("default"), schema_type)
        if default_value is not None:
            schema["default"] = default_value

        param = {
            "name": p["name"],
            "in": "query",
            "required": False,
            "schema": schema,
            "description": description,
        }

        parameters.append(param)

    # --- PHẦN 2: GROUP ERROR CODES THEO HTTP STATUS ---

    # --- PHẦN 3: XÂY RESPONSES ---
    response_schema = _resolve_response_schema(op)   # gọi hàm bên ngoài
    has_real_data = bool(op.response_schemas and op.operation_id)
    success_response_content = {"schema": response_schema}
    if not has_real_data:
        success_response_content["example"] = {"success": True, "data": None, "error": None}

    success_status = str(getattr(op, "success_status", "") or "200").strip()
    if not (success_status.isdigit() and success_status.startswith("2")):
        success_status = "200"

    responses = {
        success_status: {
            "description": "Thành công",
            "content": {"application/json": success_response_content}
        },
    }

    response_refs = _CONFIG.get("response_refs", {})
    for status, ref_path in response_refs.items():
        if str(status) == success_status:
            continue
        responses[status] = _ref(ref_path)


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
    can_emit_request_schema = _can_emit_request_schema(op)
    method_upper = op.method.upper()

    # GET/HEAD không emit requestBody.
    # Các method khác, kể cả DELETE, vẫn emit nếu parser tìm thấy body/schema thật.
    if can_emit_request_schema and method_upper not in {"GET", "HEAD"}:
        schema_name = _request_schema_name(op.operation_id)

        schema_ref = (
            f"../../components/schemas/"
            f"{op.service}/{schema_name}.yaml"
        )
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
    """Tạo file RequestSchema.yaml từ request body schema"""
    if not op.operation_id:
        return None

    has_canonical_schema = _has_canonical_request_schema(op)

    if not has_canonical_schema and not op.request_body_fields:
        return None

    # reopenUserTicket → ReopenUserTicketRequest.yaml
    schema_name = _request_schema_name(op.operation_id)
    output_path = Path(schemas_dir) / f"{schema_name}.yaml"

    if output_path.exists():
        print(f"    Schema đã tồn tại, bỏ qua: {output_path}")
        return schema_name

    if has_canonical_schema:
        data = _schema_node_to_openapi(
            op.request_schema_result.root,
            schema_kind="request",
        )
        data = _ensure_schema_description(data, schema_name, component=True)

        yaml = YAML()
        yaml.default_flow_style = False
        yaml.indent(mapping=2, sequence=4, offset=2)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        validate_yaml_file(output_path)

        print(f"      Schema: {output_path}")
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
                    description = _schema_property_description(sf["name"], sf.get("description"))
                    if description:
                        sp["description"] = description
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

        field_name = f["name"]

        description = _schema_property_description(field_name, f.get("description"))
        if description:
            prop["description"] = description

        prop = _apply_server_managed_rules(field_name, prop, schema_kind="request")

        # id/created_at/updated_at không được nằm trong request schema
        if prop is None:
            continue
        prop = _ensure_schema_description(prop, field_name)

        properties[field_name] = prop
        if f["required"]:
            required_fields.append(field_name)

    data = {"type": "object", "properties": properties}
    data = _ensure_schema_description(data, schema_name, component=True)
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


def _scalar_schema(dtype: str) -> dict:
    dtype = (dtype or "string").lower()

    if dtype in {"string", "integer", "number", "boolean"}:
        return {"type": dtype}

    if dtype == "null":
        return {"type": ["string", "null"]}

    return {"type": "string"}


def _array_items_schema(field: dict) -> dict:
    item_type = (field.get("item_type") or "").lower()

    if item_type in {"string", "integer", "number", "boolean"}:
        return {"type": item_type}

    if item_type == "null":
        return {"type": ["string", "null"]}

    return {"type": "object"}


def _build_properties(fields: list, parent_path: str = "", all_schemas: dict = None, prefix: str = "") -> dict:
    properties = {}
    for f in fields:
        dtype = (f.get("type") or "string").lower()
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
                prop = {"type": "array", "items": _array_items_schema(f)}
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
        else:
            prop = _scalar_schema(dtype)

        field_name = f["name"]

        description = _schema_property_description(field_name, f.get("description"))
        if description:
            prop["description"] = description

        prop = _apply_server_managed_rules(field_name, prop, schema_kind="response")

        if prop is None:
            continue
        prop = _ensure_schema_description(prop, field_name)

        properties[field_name] = prop

    return properties

def _is_referenced_schema(path: str, all_schemas: dict) -> bool:
    """
    Trả về True nếu path này sẽ được $ref trong parent.
    Một path được $ref khi:
    1. Là top-level: "data", "data[]", "data.data", "data.data[]"
       → được $ref từ path YAML (resolve_response_schema)
    2. Có nested thêm: any(k.startswith(path + ".") for k in all_schemas)
       → _build_properties() sẽ dùng $ref đến file này
    """
    # Top-level paths luôn được tạo
    top_level = {"data", "data[]", "data.data", "data.data[]"}
    if path in top_level:
        return True

    # Có nested thêm → _build_properties dùng $ref
    return any(k.startswith(path + ".") or k.startswith(path + "[].")
               for k in all_schemas if k != path)


def emit_response_schemas(op: ParsedOperation, schemas_dir: str):
    if not op.response_schemas or not op.operation_id:
        return

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)

    prefix = op.operation_id[0].upper() + op.operation_id[1:]

    for path, fields in op.response_schemas.items():

        # ── Chỉ tạo file khi path này thực sự được $ref ──────────
        if not _is_referenced_schema(path, op.response_schemas):
            continue

        parts    = path.split(".")
        sub_name = prefix + "".join(p.capitalize() for p in parts)
        sub_name = sub_name.replace("[]", "List")
        sub_path = Path(schemas_dir) / f"{sub_name}.yaml"

        sub_data = {
            "type": "object",
            "properties": _build_properties(
                fields,
                parent_path=path,
                all_schemas=op.response_schemas,
                prefix=prefix,
            )
        }
        sub_data = _ensure_schema_description(sub_data, sub_name, component=True)

        sub_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sub_path, "w", encoding="utf-8") as f:
            yaml.dump(sub_data, f)

        validate_yaml_file(sub_path)
        print(f"      Response schema: {sub_path}")