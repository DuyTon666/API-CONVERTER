from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

REPORT_DIR = Path(__file__).resolve().parent.parent.parent / "3.build" / "reports"


def _load_json(path: Path) -> dict:
    """
    Đọc JSON file và trả về dict.
    Nếu file chưa tồn tại thì trả về dict rỗng.
    """
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    return {}


def _save_json(path: Path, data: dict) -> None:
    """
    Ghi dict ra JSON file.
    Tự tạo parent folder nếu chưa có.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_versions() -> dict:
    """
    Đọc file_versions.json.

    Đây là current state:
    - dùng để biết version mới nhất của từng file
    - dùng để skip nếu version không đổi
    """
    return _load_json(REPORT_DIR / "file_versions.json")


def save_versions(versions: dict) -> None:
    """
    Ghi đè toàn bộ file_versions.json bằng dict versions mới nhất.
    """
    _save_json(REPORT_DIR / "file_versions.json", versions)


def append_version_history(entry: dict) -> None:
    """
    Append một dòng vào version_run_history.jsonl.

    Đây là audit log:
    - mỗi lần chạy ghi thêm 1 dòng
    - không overwrite lịch sử cũ
    """
    path = REPORT_DIR / "version_run_history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def load_review_queue() -> list:
    data = _load_json(REPORT_DIR / "human_review_queue.json")

    if isinstance(data, list):
        return data

    return[]

def save_review_queue(items: list) -> None:
    """
    Ghi đè toàn bộ human_review_queue.json.

    Ghi thẳng list để tương thích với pipeline hiện tại.
    """
    path = REPORT_DIR / "human_review_queue.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def write_batch_log(module: str, source_format: str, stats: dict) -> Path:
    path = REPORT_DIR / "batch_log_by_module.json"

    log = _load_json(path)
    log.setdefault("modules", {})

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")    

    needs_review = stats.get("needs_review", [])
    review_actions = stats.get("review_actions", {})

    error_groups = {
        flag: [
            item.get("file", "")
            for item in needs_review
            if flag in item.get("flags", [])
        ]
        for flag in review_actions
    }

    entry = {
        "module": module,
        "source_type": "api_contract",
        "source_format": source_format,
        "timestamp": now,
        "total": stats.get("total", 0),
        "success": stats.get("success", 0),
        "failed": stats.get("failed", 0),
        "skipped": stats.get("skipped", 0),
        "success_files": stats.get("success_files", []),
        "skipped_files": stats.get("skipped_files", []),
        "errors": stats.get("errors", []),
        "needs_review": needs_review,
        "needs_review_count": len(needs_review),
        "error_groups": error_groups,
    }

    log["modules"].setdefault(module, {})
    log["modules"][module][source_format] = entry

    total_files = 0
    success = 0
    failed = 0
    skipped = 0

    for module_data in log["modules"].values():
        for format_data in module_data.values():
            total_files += format_data.get("total", 0)
            success += format_data.get("success", 0)
            failed += format_data.get("failed", 0)
            skipped += format_data.get("skipped", 0)

    log["timestamp"] = now
    log["summary"] = {
        "total_modules": len(log["modules"]),
        "total_files": total_files,
        "success": success,
        "failed": failed,
        "skipped": skipped,
    }

    _save_json(path, log)

    return path