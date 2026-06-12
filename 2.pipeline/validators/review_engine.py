# validators/review_engine.py
# Quản lý human_review_queue.json: load, save, dedup, filter.
# Thay thế review_queue.py — nhận ValidationResult thay vì dict thô.

import json
from pathlib import Path

from import_flow.config import REPORT_DIR
from validators.validation_model import ValidationResult

REVIEW_QUEUE_PATH = REPORT_DIR / "human_review_queue.json"


class ReviewEngine:
    """Quản lý review queue trong suốt 1 pipeline run."""

    def __init__(self) -> None:
        self._queue: list[ValidationResult] = []
        self._dedup_keys: set[tuple] = set()
        self._loaded: bool = False

    #Load / Save 

    def load(self) -> None:
        """Đọc queue từ disk, deserialize về ValidationResult."""
        if not REVIEW_QUEUE_PATH.exists():
            print("[review_engine] Chưa có queue file, bắt đầu queue mới.")
            return

        raw = REVIEW_QUEUE_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return

        entries = json.loads(raw)
        for entry in entries:
            result = ValidationResult.from_dict(entry)
            self._queue.append(result)
            self._dedup_keys.add(result.dedup_key())

        print(f"[review_engine] Đã load {len(self._queue)} entry từ queue.")
        self._loaded = True

    def save(self) -> None:
        """Ghi queue hiện tại ra disk."""
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        data = [r.to_dict() for r in self._queue]
        REVIEW_QUEUE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[review_engine] Đã ghi {len(self._queue)} entry ra {REVIEW_QUEUE_PATH.name}.")

    #Thêm entry 

    def add(self, result: ValidationResult) -> bool:
        """
        Thêm 1 ValidationResult vào queue nếu chưa có duplicate.
        Trả về True nếu thêm được, False nếu bị dedup.
        """
        key = result.dedup_key()
        if key in self._dedup_keys:
            return False
        self._queue.append(result)
        self._dedup_keys.add(key)
        return True

    #Query 

    def filter(
        self,
        issue_type: str | None = None,
        module: str | None = None,
        severity: str | None = None,
    ) -> list[ValidationResult]:
        """Lọc queue theo type / module / severity."""
        result = self._queue
        if issue_type:
            result = [r for r in result if r.type == issue_type]
        if module:
            result = [r for r in result if r.module == module]
        if severity:
            result = [r for r in result if r.severity == severity]
        return result

    def count(self) -> int:
        return len(self._queue)

    def is_duplicate(self, result: ValidationResult) -> bool:
        return result.dedup_key() in self._dedup_keys
