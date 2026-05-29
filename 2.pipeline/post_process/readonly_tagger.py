# readonly_tagger.py — đánh readOnly: true vào response schema fields
# Chạy TRƯỚC ref_replacer vì sau khi replace thành $ref thì không còn property để tag

from pathlib import Path
from ruamel.yaml import YAML

def _is_request_schema(file_path: Path) -> bool:
    return file_path.stem.endswith("Request")

def tag_readonly_fields(schemas_dir: Path, readonly_fields: set) -> int:
    """
    Scan tất cả response schema trong schemas_dir,
    đánh readOnly: true vào các field có trong readonly_fields.
    Bỏ qua *Request.yaml vì readOnly không áp dụng cho request.
    Trả về số file đã thay đổi.
    """
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)

    changed_count = 0
    for file_path in sorted(schemas_dir.glob("*.yaml")):
        if _is_request_schema(file_path):
            continue   # bỏ qua request schema

        with open(file_path, encoding="utf-8") as f:
            data = yaml.load(f)

        if not data or "properties" not in data:
            continue

        changed = False
        for field_name, prop in data["properties"].items():
            if field_name in readonly_fields:
                if isinstance(prop, dict) and not prop.get("readOnly"):
                    prop["readOnly"] = True
                    changed = True
                    print(f"    [{file_path.name}] {field_name} → readOnly: true")

        if changed:
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f)
            changed_count += 1

    return changed_count