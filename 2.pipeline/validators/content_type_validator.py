# validators/content_type_validator.py
# Validator kiểm tra content-type mismatch giữa declared và inferred.
# Dùng RuleEngine để load rules, ReviewEngine để quản lý queue.

from pathlib import Path

import yaml

from import_flow.config import load_import_config, get_output_root
from validators.rule_engine import RuleEngine
from validators.review_engine import ReviewEngine
from validators.validation_model import (
    ValidationResult,
    SEVERITY_HIGH,
    SOURCE_RULE_BASED,
    FIX_MANUAL,
)

CHECK_OK = "ok"
CHECK_NO_BODY = "no_body"
CHECK_NO_SCHEMA = "no_schema"

#Helpers nội bộ 

def _collect_field_info(schema: dict) -> list[dict]:
    """Thu thập tên và format của từng field trong schema."""
    fields = []
    for name, spec in schema.get("properties", {}).items():
        fmt = spec.get("format", "")
        if spec.get("type") == "array":
            fmt = spec.get("items", {}).get("format", fmt)
        fields.append({"name": name, "format": fmt})
    return fields


def _infer_content_type(fields: list[dict], rules: RuleEngine) -> tuple[str, list[str]]:
    """Suy luận content-type từ danh sách field, dùng RuleEngine tra cứu."""
    evidence = []

    for f in fields:
        name = f["name"].lower()
        fmt  = f["format"].lower()

        if rules.match_any(fmt, "binary_formats"):
            evidence.append(f"format:{fmt} (field: {f['name']})")
        elif rules.match_any(name, "multipart_keywords"):
            evidence.append(f"field name: {f['name']}")

    if evidence:
        return "multipart/form-data", evidence
    return "application/json", []


def _resolve_schema_ref(ref: str, yaml_path: Path) -> dict:
    """Resolve $ref tương đối so với vị trí file YAML."""
    try:
        schema_path = (yaml_path.parent / ref).resolve()
        if not schema_path.exists():
            return {}
        return yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _check_file(
    yaml_path: Path,
    module: str,
    rules: RuleEngine,
) -> ValidationResult | str:
    """Kiểm tra 1 file YAML, trả về ValidationResult nếu phát hiện mismatch."""
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return CHECK_NO_SCHEMA

    # Tìm operation có requestBody
    operation = None
    for val in data.values():
        if isinstance(val, dict) and "requestBody" in val:
            operation = val
            break

    if operation is None:
        return CHECK_NO_BODY

    content = operation["requestBody"].get("content", {})
    if not content:
        return CHECK_NO_BODY

    declared   = list(content.keys())[0]
    schema_obj = content[declared].get("schema", {})

    if "$ref" in schema_obj:
        schema = _resolve_schema_ref(schema_obj["$ref"], yaml_path)
    else:
        schema = schema_obj

    if not schema:
        return CHECK_NO_SCHEMA

    fields             = _collect_field_info(schema)
    inferred, evidence = _infer_content_type(fields, rules)

    if declared == inferred:
        return CHECK_OK

    return ValidationResult(
        type            = "content_type_mismatch",
        severity        = SEVERITY_HIGH,
        confidence      = 0.95,
        source          = SOURCE_RULE_BASED,
        fix_strategy    = FIX_MANUAL,
        review_required = True,
        module          = module,
        file            = yaml_path.name,
        output          = str(yaml_path),
        detail          = {
            "declared": declared,
            "inferred": inferred,
            "evidence": evidence,
        },
    )


#Entry point 

def validate_content_types(module: str | None = None) -> None:
    """Quét toàn bộ output YAML, phát hiện content-type mismatch."""
    cfg         = load_import_config()
    output_root = get_output_root(cfg)
    rules       = RuleEngine("content_type_rules.yaml")

    if module:
        module_dirs = [output_root / module]
    else:
        module_dirs = sorted(d for d in output_root.iterdir() if d.is_dir())

    engine          = ReviewEngine()
    engine.load()
    total_new       = 0
    total_duplicate = 0

    for module_dir in module_dirs:
        if not module_dir.exists():
            continue

        mod_name     = module_dir.name
        yaml_files   = sorted(module_dir.glob("*.yaml"))
        mod_checked  = 0
        mod_mismatch = 0
        mod_skipped  = 0

        for yf in yaml_files:
            result = _check_file(yf, mod_name, rules)

            if result == CHECK_NO_BODY:
                mod_skipped += 1
                continue

            mod_checked += 1

            if result in {CHECK_OK, CHECK_NO_SCHEMA}:
                continue

            if engine.is_duplicate(result):
                total_duplicate += 1
                continue

            engine.add(result)
            mod_mismatch += 1
            total_new    += 1

            print(
                f"[WARN] content_type_mismatch: {yf.name}\n"
                f"       declared={result.detail['declared']}"
                f" inferred={result.detail['inferred']}\n"
                f"       evidence: {', '.join(result.detail['evidence'])}"
            )

        checked = mod_checked
        print(
            f"[content_type] module={mod_name} "
            f"checked={checked} "
            f"mismatch={mod_mismatch} "
            f"skipped(no-body)={mod_skipped}"
        )

    if total_new > 0:
        engine.save()
        print(f"[INFO] {total_new} mục mới đã được ghi vào human review.")
    elif total_duplicate > 0:
        print(f"[INFO] {total_duplicate} mục đã tồn tại trong queue, bỏ qua.")
    else:
        print("[OK] Không phát hiện content-type mismatch.")
