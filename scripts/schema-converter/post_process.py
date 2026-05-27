# post_process.py — scan output schemas, replace matched fields với $ref theo registry

import sys
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as Q
from schema_converter.io_utils import validate_yaml_file

def load_registry(registry_path: str) -> dict:
    yaml = YAML()
    with open(registry_path, encoding="utf-8") as f:
        return yaml.load(f).get("fields", {})

def _matches_field(field_data: dict, rule: dict) -> bool:
    """Check xem field có khớp với rule không"""
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
    """Xử lý 1 file — trả về True nếu có thay đổi"""
    with open(file_path, encoding="utf-8") as f:
        data = yaml.load(f)

    if not data or "properties" not in data:
        return False

    changed = False
    for field_name, rule in registry.items():
        if field_name not in data["properties"]:
            continue
        field_data = data["properties"][field_name]
        if _matches_field(field_data, rule):
            if rule.get("ref_type") == "array_of":
                # Giữ lại maxItems nếu có
                new_prop = {
                    "type": "array",
                    "items": {"$ref": Q(rule["ref"])}
                }
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

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 post_process.py <schemas_dir>")
        sys.exit(1)

    schemas_dir = Path(sys.argv[1])
    registry_path = Path(__file__).parent / "schema_registry.yaml"

    if not registry_path.exists():
        print(f"[ERROR] Không tìm thấy registry: {registry_path}")
        sys.exit(1)

    registry = load_registry(str(registry_path))
    print(f"Registry: {list(registry.keys())}\n")

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.representer.add_representer(
        type(None),
        lambda dumper, _: dumper.represent_scalar('tag:yaml.org,2002:null', 'null')
    )

    files = list(schemas_dir.glob("*.yaml"))
    print(f"Scan {len(files)} files trong {schemas_dir}\n")

    total_changed = 0
    for f in files:
        if process_file(f, registry, yaml):
            total_changed += 1

    print(f"\nHoàn thành: {total_changed} file được update")

if __name__ == "__main__":
    main()