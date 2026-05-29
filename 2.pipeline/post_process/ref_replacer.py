# ref_replacer.py — replace common fields thành $ref theo schema_registry.yaml
# Chạy SAU readonly_tagger

from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as Q
from validators.yaml_validator import validate_yaml_file

def load_registry(registry_path: Path) -> dict:
    yaml = YAML()
    with open(registry_path, encoding="utf-8") as f:
        return yaml.load(f).get("fields", {})

def _is_request_schema(file_path: Path) -> bool:
    return file_path.stem.endswith("Request")

def _matches_field(field_data: dict, rule: dict) -> bool:
    match_type = rule.get("match_type")
    if match_type == "object":
        if field_data.get("type") != "object":
            return False
        props = set(field_data.get("properties", {}).keys())
        required_props = set(rule.get("match_properties", []))
        return required_props.issubset(props)
    if match_type == "array":
        if field_data.get("type") != "array":
            return False
        items = field_data.get("items", {})
        if rule.get("match_item_format"):
            return items.get("format") == rule["match_item_format"]
        return True
    return False

def process_file(file_path: Path, registry: dict, yaml: YAML) -> bool:
    with open(file_path, encoding="utf-8") as f:
        data = yaml.load(f)

    if not data or "properties" not in data:
        return False

    is_request = _is_request_schema(file_path)
    changed = False

    for field_name, rule in registry.items():
        if field_name not in data["properties"]:
            continue

        schema_kind = rule.get("schema_kind", "any")
        if schema_kind == "response" and is_request:
            continue
        if schema_kind == "request" and not is_request:
            continue

        field_data = data["properties"][field_name]
        if _matches_field(field_data, rule):
            if rule.get("ref_type") == "array_of":
                new_prop = {"type": "array", "items": {"$ref": Q(rule["ref"])}}
                if field_data.get("maxItems"):
                    new_prop["maxItems"] = field_data["maxItems"]
                data["properties"][field_name] = new_prop
            else:
                data["properties"][field_name] = {"$ref": Q(rule["ref"])}
            print(f"    [{file_path.name}] {field_name} → $ref: {rule['ref']}")
            changed = True

    if changed:
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)
        validate_yaml_file(file_path)
    return changed

def replace_common_refs(schemas_dir: Path, registry_path: Path) -> int:
    """
    Scan tất cả schema trong schemas_dir, replace field khớp rule thành $ref.
    Trả về số file đã thay đổi.
    """
    registry = load_registry(registry_path)
    if not registry:
        print("  [WARN] Registry rỗng, bỏ qua ref_replacer")
        return 0

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.representer.add_representer(
        type(None),
        lambda dumper, _: dumper.represent_scalar('tag:yaml.org,2002:null', 'null')
    )

    changed_count = 0
    for file_path in sorted(schemas_dir.glob("*.yaml")):
        if process_file(file_path, registry, yaml):
            changed_count += 1

    return changed_count

def replace_common_refs_from_registry(schemas_dir: Path, registry: dict) -> int:
    """
    Dùng registry dict từ _CONFIG thay vì đọc file.
    Gọi từ post_process/run.py.
    """
    if not registry:
        print(" [WARN] Registry rỗng")
        return 0

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.representer.add_representer(
        type(None),
        lambda dumper, _: dumper.represent_scalar('tag:yaml.org,2002:null', 'null')
    )

    changed_count = 0
    for file_path in sorted(schemas_dir.glob("*.taml")):
        if process_file(file_path, registry, yaml):
            changed_count +=1

    return changed_count