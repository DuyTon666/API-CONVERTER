# validators/side_effects_validator.py
# Detect endpoint có side effect: action verb, notification, async job.
# Kết hợp rule_based (YAML) + path_classifier (Claude LLM khi cần).

import yaml
from pathlib import Path

from import_flow.config import OPENAPI_DIR, REPORT_DIR
from validators.validation_model import (
    ValidationResult,
    SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW,
    SOURCE_RULE_BASED, SOURCE_CLAUDE,
    FIX_MANUAL,
)
from validators.rule_engine import RuleEngine
from validators.review_engine import ReviewEngine
from enrichers.path_classifier import classify_path

_CONFIDENCE_EMIT_DEFAULT = 0.75
_CONFIDENCE_RULE_DEFAULT = 0.85

_RULES_FILE = "side_effects_rules.yaml"

_RULE_GROUPS = [
    "action_verbs",
    "notification_keywords",
    "async_keywords",
]

def _load_file_versions() -> dict:
    versions_path = REPORT_DIR / "file_versions.json"
    if not versions_path.exists():
        return {}
    import json
    return json.loads(versions_path.read_text(encoding="utf-8"))

def _get_actual_path(yaml_abs_path: str, versions: dict) -> str | None:
    for entry in versions.values():
        if entry.get("output") == yaml_abs_path:
            return entry.get("http_path")
    return None

def _derive_path_hint(filename: str) -> str:
    stem = Path(filename).stem
    hint = stem.replace("_","-")
    return f"/{hint}"

def _rule_check(path: str, rules: RuleEngine) -> dict | None:
    segments = [s.lower() for s in path.replace("/", "-").split("-") if s]
    severity_map = rules.get_dict("severity_map")

    for group in _RULE_GROUPS:
        keywords = rules.get_set(group)
        for seg in segments:
            if seg in keywords:
                return {
                    "matched_rule": group,
                    "keyword":      seg,
                    "severity":     severity_map.get(group, SEVERITY_MEDIUM),
                }
    return None

def _build_result(
    module:     str,
    filename:   str,
    output:     str,
    path_used:  str,
    method:     str,
    source:     str,
    confidence: str,
    severity:   str,
    matched_rule: str | None = None,
    matched_keyword: str | None = None,
    classifier_reason:  str | None = None,
) -> ValidationResult:
    return ValidationResult(
        type            = "side_effect_endpoint",
        severity        = severity,
        confidence      = confidence,
        source          = source,
        fix_strategy    = FIX_MANUAL,
        review_required = True,
        module          = module,
        file            = filename,
        output          = output,
        detail          = {
            "path":         path_used,
            "method":       method,
            "matched_rule": matched_rule,
            "matched_keyword": matched_keyword,
            "classifier_reason": classifier_reason,
        },
    )

def validate_side_effects(module: str | None = None) -> None:
    rules       = RuleEngine(_RULES_FILE)
    thresholds       = rules.get_dict("confidence_thresholds")
    _CONFIDENCE_EMIT = thresholds.get("emit_yaml",    _CONFIDENCE_EMIT_DEFAULT)
    _CONFIDENCE_RULE = thresholds.get("emit_yaml", _CONFIDENCE_RULE_DEFAULT)
    reviewer    = ReviewEngine()
    reviewer.load()
    versions    = _load_file_versions()

    base = Path(OPENAPI_DIR) / "paths"
    scan_dirs = [base / module] if module else [d for d in base.iterdir() if d.is_dir()]

    found = 0

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            print(f"[WARN] side_effects_validator: Không tìm thấy {scan_dir}")
            continue

        mod_name = scan_dir.name
        print(f"[side_effects_validator] Scan module: {mod_name}")

        for yaml_file in sorted(scan_dir.glob("*.yaml")):
            filename = yaml_file.name
            abs_path = str(yaml_file.resolve())

            try:
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            except Exception as e:
                print(f"    [WARN] Không đọc được {filename}: {e}")
                continue

            method = next(iter(raw.keys()), "get").lower()
            summary = raw.get(method, {}).get("summary", "")

            actual_path = _get_actual_path(abs_path, versions)
            path_used   = actual_path if actual_path else _derive_path_hint(filename)
            path_source = "file_versions" if actual_path else "filename_hint"

            print(f"    [{filename}] path={path_used} ({path_source}), method={method}")

            rule_match = _rule_check(path_used, rules)

            if rule_match:
                result = _build_result(
                    module          = mod_name,
                    filename        = filename,
                    output          = abs_path,
                    path_used       = path_used,
                    method          = method,
                    source          = SOURCE_RULE_BASED,
                    confidence      = _CONFIDENCE_RULE,
                    severity        = rule_match["severity"],
                    matched_rule    = rule_match["matched_rule"],
                    matched_keyword = rule_match["keyword"],
                )
                if reviewer.add(result):
                    print(f"    -> rule_match [{rule_match['keyword']}] severity={rule_match['severity']}")
                    found += 1
                continue

            classification = classify_path(
                module  = mod_name,
                method  = method,
                path    = path_used,
                summary = summary,
            )

            if not classification or classification.get("type") != "action":
                continue

            conf = float(classification.get("confidence", 0.0))
            if conf < _CONFIDENCE_EMIT:
                print(f"    -> classifier: action nhưng confidence={conf:.2f} <  {_CONFIDENCE_EMIT}, bỏ qua")
                continue

            result = _build_result(
                module          = mod_name,
                filename        = filename,
                output          = abs_path,
                path_used       = path_used,
                method          = method,
                source          = SOURCE_CLAUDE,
                confidence      = conf,
                severity        = SEVERITY_MEDIUM,
                classifier_reason = classification.get("reason"),
            )
            if reviewer.add(result):
                print(f"    -< classifier: action conf={conf:.2f} reason={classification.get('reason')}")
                found += 1

    reviewer.save()
    print(f"[side_effect_validator] Hoàn tất - {found} side effect endpoint được flag.")