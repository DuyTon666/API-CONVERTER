# 2.pipeline/enrichers/side_effects/report_writer.py
"""
Ghi report tổng hợp sau khi chạy side_effects_enricher trên 1 batch.

Report dùng để audit: endpoint nào được enrich, effect_id nào được tạo,
endpoint nào bị skip và vì sao.
"""

import json
from datetime import datetime
from pathlib import Path


def build_result(
    entry: dict,
    status: str,
    effect_ids: list[str] | None = None,
    merge_report: dict | None = None,
    reason: str | None = None,
) -> dict:
    """
    Build 1 result record cho 1 entry đã xử lý.

    Args:
        entry: entry gốc từ human_review_queue.json
        status: "success" | "skipped" | "error"
        effect_ids: list effect_id đã inject (nếu success)
        merge_report: dict từ precedence.resolve_effects (nếu success)
        reason: lý do skip/error (nếu có)
    """
    return {
        "module": entry.get("module"),
        "file": entry.get("file"),
        "output": entry.get("output"),
        "matched_keyword": entry.get("detail", {}).get("matched_keyword"),
        "status": status,
        "effect_ids": effect_ids or [],
        "merge_report": merge_report,
        "reason": reason,
    }


def write_report(results: list[dict], output_path: str) -> dict:
    """
    Ghi report ra file JSON, trả về summary dict.

    Args:
        results: list[dict] từ build_result()
        output_path: đường dẫn file report (vd ../3.build/reports/side_effects_enrich_report.json)

    Returns:
        summary dict: {"total": N, "success": N, "skipped": N, "error": N}
    """
    summary = {"total": len(results), "success": 0, "skipped": 0, "error": 0}
    for r in results:
        status = r["status"]
        if status in summary:
            summary[status] += 1

    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "results": results,
    }

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return summary