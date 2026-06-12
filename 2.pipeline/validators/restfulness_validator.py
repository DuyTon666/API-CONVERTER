# validators/restfulness_validator.py
# Detect vi phạm REST convention: CRUD verb trong operationId,
# sai HTTP method, path nested quá sâu.
# Tái dùng RuleEngine + ReviewEngine — không chứa logic detect trực tiếp.

import re
import json
import yaml
from pathlib import Path

from import_flow.config import OPENAPI_DIR, REPORT_DIR
from validators.validation_model import (
    ValidationResult,
    SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW,
    SOURCE_RULE_BASED,
    FIX_MANUAL,
)
from validators.rule_engine import RuleEngine
from validators.review_engine import ReviewEngine

_RULES_FILE = "restfulness_rules.yaml"

#Helpers

def _load_file_versions() -> dict:
    """Đọc file_versions.json, trả về dict rỗng nếu chưa có."""
    path = REPORT_DIR / "file_versions.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def _get_actual_path(yaml_abs_path: str, versions: dict) -> str | None:
    """Tìm http_path thật từ file_versions.json theo output path."""
    for entry in versions.values():
        if entry.get("output") == yaml_abs_path:
            return entry.get("http_path")
    return None

def _derive_path_hint(filename: str) -> str:
    """Fallback: derive path hint từ tên file."""
    stem = Path(filename).stem
    return "/" + stem.replace("_", "-")

def _split_camel(operation_id: str) -> list[str]:

    """
    Tách camelCase thành list word lowercase.
    createUserTicket → ['create', 'user', 'ticket']
    """

    words = re.sub(r"([A-Z])", r" \1", operation_id).split()
    return [w.lower() for w in words]

def _count_resource_depth(path: str) -> int:

    """
    Đếm số cấp resource thật trong path.
    Bỏ qua: v1/v2/v3, {} param, chuỗi rỗng.
    /v1/users/{}/tickets/{}/comments → 3
    """

    segments = path.strip("/").split("/")
    resource = [
        s for s in segments
        if s 
        and not re.match(r"^v\d+$", s)          # bỏ v1, v2
        and not re.match(r"^\{.*\}$", s)         # bỏ {param}
        and not re.match(r"^\{\}$", s)
    ]
    return len(resource)

def _check_crud_verb(
    operation_id:   str,
    rules:          RuleEngine,
) -> dict | None:

    """
    Kiểm tra operationId có chứa CRUD verb không.
    Trả về dict {matched_verb} hoặc None.
    """
    
    if not operation_id:
        return None
    words       = _split_camel(operation_id)
    crud_set    = rules.get_set("crud_verbs_in_operation_id")
    for word in words:
        if word in crud_set:
            return {"matched_verb": word}
    return None

def _check_wrong_method(
    method: str,
    operation_id: str,
    rules:  RuleEngine,
) -> dict | None:

    """
    Kiểm tra HTTP method có phù hợp với operationId không.
    Trả về dict {method, forbidden_verb} hoặc None.
    """

    if not operation_id:
        return None
    wrong_map   = rules.get_dict("wrong_method_rules")
    forbidden   = set(wrong_map.get(method.lower(), []))
    if not forbidden:
        return None
    words = _split_camel(operation_id)
    for word in words:
        if word in forbidden:
            return {"method": method, "forbidden_verb": word}
    return None

def _check_nesting(path: str, max_depth: int) -> dict | None:

    """
    Kiểm tra path có nested quá sâu không.
    Trả về dict {depth, max_depth} hoặc None.
    """
    depth = _count_resource_depth(path)
    if depth > max_depth:
        return {"depth": depth, "max_depth": max_depth}
    return None

def _build_result(
    issue_type:     str,
    severity:       str,
    module:         str,
    filename:       str,
    output:         str,
    detail:         dict,
) -> ValidationResult:
    return ValidationResult(
        type            = issue_type,
        severity        = severity,
        confidence      = 0.85,
        source          = SOURCE_RULE_BASED,
        fix_strategy    = FIX_MANUAL,
        review_required = True,
        module          = module,
        file            = filename,
        output          = output,
        detail          = detail,        
    )

#Public API

def validate_restfulness(module: str | None = None) -> None:
    """
    Scan toàn bộ YAML output, detect vi phạm REST convention.
    Args:
        module: tên module cụ thể, hoặc None để scan tất cả.
    """
    rules   = RuleEngine(_RULES_FILE)
    severity_map = rules.get_dict("severity_map")
    max_depth = rules.get_value("max_nesting_depth", default=3)
    reviewer  = ReviewEngine()
    reviewer.load()
    versions  = _load_file_versions()

    base      = Path(OPENAPI_DIR) / "paths"
    scan_dirs  = [base / module] if module else [d for d in base.iterdir() if d.is_dir()]

    found = 0

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            print(f"[WARN] restfulness_validator: Không tìm thấy {scan_dir}")
            continue

        mod_name = scan_dir.name
        print(f"[restfulness_validator] Scan module: {mod_name}")

        for yaml_file in sorted(scan_dir.glob("*.yaml")):
            filename = yaml_file.name
            abs_path = str(yaml_file.resolve())

            try:
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            except Exception as e:
                print(f"    [WARN] Không đọc được {filename}: {e}")
                continue

            method      = next(iter(raw.keys()), "get").lower()
            operation   = raw.get(method, {})
            operation_id = operation.get("operationId", "")

            actual_path = _get_actual_path(abs_path, versions)
            path_used   = actual_path if actual_path else _derive_path_hint(filename)

            print(f"  [{filename}] method={method} operationId={operation_id} path={path_used}")


            crud_match = _check_crud_verb(operation_id, rules)

            if crud_match:
                sev    = severity_map.get("crud_verbs_in_operation_id", SEVERITY_MEDIUM)
                result = _build_result(
                    issue_type = "crud_verb_in_operation_id",
                    severity   = sev,
                    module     = mod_name,
                    filename   = filename,
                    output     = abs_path,
                    detail     = {
                        "operation_id":  operation_id,
                        "matched_verb":  crud_match["matched_verb"],
                        "path":          path_used,
                        "method":        method,
                        "suggestion":    f"Dùng {method.upper()} {path_used} thay vì verb trong operationId",
                    },
                )
                if reviewer.add(result):
                    print(f"    → crud_verb [{crud_match['matched_verb']}] severity={sev}")
                    found += 1

            method_match = _check_wrong_method(method, operation_id, rules)
            if method_match:
                sev    = severity_map.get("wrong_method_for_state_change", SEVERITY_HIGH)
                result = _build_result(
                    issue_type = "wrong_method_for_state_change",
                    severity   = sev,
                    module     = mod_name,
                    filename   = filename,
                    output     = abs_path,
                    detail     = {
                        "operation_id":   operation_id,
                        "method":         method,
                        "forbidden_verb": method_match["forbidden_verb"],
                        "path":           path_used,
                        "suggestion":     f"Dùng POST hoặc PATCH thay vì {method.upper()} cho action thay đổi state",
                    },
                )
                if reviewer.add(result):
                    print(f"    → wrong_method [{method}/{method_match['forbidden_verb']}] severity={sev}")
                    found += 1

            # Check 3 — Over-nested path
            nesting_match = _check_nesting(path_used, max_depth)
            if nesting_match:
                sev    = severity_map.get("over_nested_path", SEVERITY_LOW)
                result = _build_result(
                    issue_type = "over_nested_path",
                    severity   = sev,
                    module     = mod_name,
                    filename   = filename,
                    output     = abs_path,
                    detail     = {
                        "path":      path_used,
                        "depth":     nesting_match["depth"],
                        "max_depth": nesting_match["max_depth"],
                        "method":    method,
                    },
                )
                if reviewer.add(result):
                    print(f"    → over_nested depth={nesting_match['depth']} max={max_depth} severity={sev}")
                    found += 1

    reviewer.save()
    print(f"[restfulness_validator] Hoàn tất — {found} vi phạm REST được flag.")