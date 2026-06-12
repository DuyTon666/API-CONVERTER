# validators/rule_engine.py
# Load và apply rules từ YAML config.
# Mỗi validator tạo 1 instance RuleEngine với file rules tương ứng.

from pathlib import Path
import yaml

from import_flow.config import CONFIG_DIR


class RuleEngine:
    """Load rules từ 1 file YAML và cung cấp API tra cứu."""

    def __init__(self, rule_file: str) -> None:
        """
        Args:
            rule_file: tên file trong 4.config/, vd: "content_type_rules.yaml"
        """
        self._path: Path = CONFIG_DIR / rule_file
        self._rules: dict = {}
        self._loaded: bool = False

    #Load 

    def _ensure_loaded(self) -> None:
        """Lazy load — chỉ đọc disk lần đầu tiên."""
        if self._loaded:
            return
        if not self._path.exists():
            print(f"[WARN] rule_engine: không tìm thấy {self._path}")
            self._rules = {}
        else:
            self._rules = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
            print(f"[rule_engine] Đã load {self._path.name} — {len(self._rules)} nhóm rule")
        self._loaded = True

    #API tra cứu 

    def get(self, key: str) -> list:
        """Trả về list các giá trị trong nhóm rule `key`. Trả về [] nếu không có."""
        self._ensure_loaded()
        return list(self._rules.get(key, []))

    def get_set(self, key: str) -> set:
        """Như get() nhưng trả về set — tiện cho lookup O(1)."""
        return set(self.get(key))

    def match_any(self, value: str, key: str) -> bool:
        """Kiểm tra value có nằm trong nhóm rule `key` không (so sánh lowercase)."""
        return value.lower() in self.get_set(key)

    def all_keys(self) -> list[str]:
        """Danh sách tất cả nhóm rule trong file — dùng để debug."""
        self._ensure_loaded()
        return list(self._rules.keys())

    def get_dict(self, key: str) -> dict:
        self._ensure_loaded()
        value = self._rules.get(key, {})
        return value if isinstance(value, dict) else {}

    def get_value(self, key: str, default=None):
        """Trả về scalar value (int, str, float) cho key. Dùng cho max_nesting_depth và các config đơn lẻ."""
        self._ensure_loaded()
        return self._rules.get(key, default)