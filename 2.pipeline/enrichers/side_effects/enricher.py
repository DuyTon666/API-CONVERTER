# 2.pipeline/enrichers/side_effects/enricher.py
"""
Orchestrator chính cho x-side-effects enrichment.

Flow:
  human_review_queue.json (type=side_effect_endpoint)
      -> config_loader (effect_templates)
      -> resource_inferer ({resource})
      -> effect_builder (effects[] + effect_id)
      -> precedence (merge với x-side-effects cũ nếu có)
      -> schema_validator (validate trước khi ghi)
      -> yaml_injector (ghi vào file YAML)
      -> report_writer (audit report)

Usage:
    python3 -m enrichers.side_effects.enricher [--module ticket] [--dry-run]
"""

import json
import argparse
from datetime import date
from pathlib import Path

import yaml

from .config_loader import get_effect_template
from .resource_inferer import infer_resource
from .effect_builder import build_effects
from .precedence import resolve_effects
from .schema_validator import validate
from .yaml_injector import inject_x_side_effects
from .report_writer import build_result, write_report


# Paths tính từ vị trí file này: 2.pipeline/enrichers/side_effects/enricher.py
_PIPELINE_DIR = Path(__file__).resolve().parents[2]  # 2.pipeline/
_QUEUE_PATH = _PIPELINE_DIR.parent / "3.build" / "reports" / "human_review_queue.json"
_REPORT_PATH = _PIPELINE_DIR.parent / "3.build" / "reports" / "side_effects_enrich_report.json"

_SCHEMA_VERSION = "1.1"


def _load_queue() -> list[dict]:
    with open(_QUEUE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("items") or data.get("entries") or data.get("results") or data.get("queue") or []


def _read_existing_x_side_effects(filepath: str, method: str) -> dict | None:
    """Đọc x-side-effects hiện có trong YAML (nếu có), không mutate file."""
    path = Path(filepath)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    method = method.lower()
    if method not in data:
        return None
    return data[method].get("x-side-effects")


def enrich_side_effects(module: str | None = None, dry_run: bool = False) -> dict:
    """
    Chạy enrichment cho toàn bộ (hoặc 1 module) entries type=side_effect_endpoint.

    Args:
        module: nếu set, chỉ xử lý entries của module này (vd "ticket")
        dry_run: nếu True, không ghi file YAML, chỉ tính toán + report

    Returns:
        summary dict từ report_writer.write_report
    """
    entries = _load_queue()

    target_entries = [
        e for e in entries
        if e.get("type") == "side_effect_endpoint"
        and (module is None or e.get("module") == module)
    ]

    results = []

    for entry in target_entries:
        detail = entry.get("detail", {})
        matched_rule = detail.get("matched_rule")
        matched_keyword = detail.get("matched_keyword")
        method = detail.get("method")
        output_path = entry.get("output")

        # Bước b: lookup template
        template = get_effect_template(matched_rule, matched_keyword)
        if template is None:
            results.append(build_result(
                entry, "skipped",
                reason=f"Không có effect_template cho {matched_rule}.{matched_keyword}",
            ))
            continue

        # Bước c: infer resource
        resource, resource_evidence = infer_resource(entry)
        if resource is None:
            results.append(build_result(
                entry, "skipped",
                reason="Không suy luận được {resource} từ path/filename/module",
            ))
            continue

        # Bước d: build effects
        effects = build_effects(resource, resource_evidence, template, matched_rule, matched_keyword)

        # Bước e: precedence merge
        try:
            existing = _read_existing_x_side_effects(output_path, method)
        except Exception as ex:
            results.append(build_result(entry, "error", reason=f"Lỗi đọc YAML: {ex}"))
            continue

        merged, merge_report = resolve_effects(existing, effects)

        # Bước f: build x-side-effects + validate
        x_side_effects = {
            "schema_version": _SCHEMA_VERSION,
            "meta": {
                "detected_by": entry.get("source", "rule_based"),
                "confidence": template["confidence"],
                "review_status": "pending",
                "last_updated": date.today().isoformat(),
            },
            "effects": merged,
            "review": {
                "required": True,
                "reason": "Side effects được suy luận từ action endpoint, chưa được xác nhận từ source document.",
                "note": None,
            },
        }

        is_valid, error = validate(x_side_effects)
        if not is_valid:
            results.append(build_result(entry, "error", reason=f"Schema invalid: {error}"))
            continue

        # Bước g: inject
        try:
            inject_x_side_effects(output_path, method, x_side_effects, dry_run=dry_run)
        except Exception as ex:
            results.append(build_result(entry, "error", reason=f"Lỗi inject YAML: {ex}"))
            continue

        # Bước h: record success
        effect_ids = [e["effect_id"] for e in merged]
        results.append(build_result(entry, "success", effect_ids=effect_ids, merge_report=merge_report))

    summary = write_report(results, str(_REPORT_PATH))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Enrich x-side-effects vào OpenAPI YAML")
    parser.add_argument("--module", default=None, help="Chỉ xử lý 1 module (vd: ticket)")
    parser.add_argument("--dry-run", action="store_true", help="Không ghi file, chỉ tính toán + report")
    args = parser.parse_args()

    summary = enrich_side_effects(module=args.module, dry_run=args.dry_run)

    print(f"Report: {_REPORT_PATH}")
    print(f"total={summary['total']} success={summary['success']} "
          f"skipped={summary['skipped']} error={summary['error']}")


if __name__ == "__main__":
    main()