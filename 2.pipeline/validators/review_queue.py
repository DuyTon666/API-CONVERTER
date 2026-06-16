import json
from pathlib import Path

from import_flow.config import REPORT_DIR

REVIEW_QUEUE_PATH = REPORT_DIR / "human_review_queue.json"

def load_queue() -> list:
    if not REVIEW_QUEUE_PATH.exists():
        return []
    raw = REVIEW_QUEUE_PATH.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else []

def save_queue(queue: list) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_QUEUE_PATH.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def already_in_queue(queue: list, entry_type: str, module: str, filename: str) -> bool:
    for entry in queue:
        if (
            entry.get("type") == entry_type
            and entry.get("module") == module
            and entry.get("file") == filename
        ):
            return True
    return False