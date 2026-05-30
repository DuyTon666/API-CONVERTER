# Đọc và ghi module_registry.yaml.
# Không ai được ghi trực tiếp vào registry ngoài class này.

from pathlib import Path
from datetime import date
import yaml

class ModuleRegistry:
    def __init__(self, config_dir: str):
        self._path = Path(config_dir) / "module_registry.yaml"
        self._data = self._load()

    def _load(self) -> dict:
        if not self._path.exists():
            raise FileNotFoundError(f"Thiếu registry: {self._path}")
        return yaml.safe_load(self._path.read_text(encoding="utf-8")) or {"modules": {}}

    def _save(self) -> None:
        self._path.write_text(
            yaml.dump(self._data, allow_unicode=True, sort_keys=False),
            encoding="utf-8"
        )

    def exists(self, module: str) -> bool:
        """Module đã được đăng ký rồi hay chưa"""
        return module in self._data.get("modules", {})

    def get_status(self, module: str) -> str | None:
        """Trả về status của module, None nếu chưa đăng ký."""
        return self._data.get("modules", {}).get(module, {}).get("status")

    def get_info(self, module: str) -> dict:
        """Trả về toàn bộ thông tin của module."""
        return self._data.get("modules", {}).get(module, {})

    def register(self, module: str, source_dir: str,
                 output_dir: str, schemas_dir: str) -> None:
        """
        Thêm module mới vào registry với status: draft.
        Gọi khi bootstrap - không gọi trong strict mod.
        """
        if self.exists(module):
            raise ValueError(f"Module '{module}' đã tồn tại trong registry.")

        self._data.setdefault("modules", {}) [module] = {
            "status": "draft",
            "registered_at": str(date.today()),
            "source_dir":   source_dir,
            "output_dir":   output_dir,
            "schemas_dir":  schemas_dir,
        }
        self._save()

    def approve(self, module: str, approved_by: str = "") -> None:
        """
        Đổi status từ draft → active.
        Gọi khi người dùng đã review output và xác nhận đúng.
        """
        if not self.exists(module):
            raise ValueError(f"Module '{module}' chưa có trong registry")
        
        entry = self._data["modules"][module]

        if entry["status"] == "active":
            print(f"   Module '{module}' đã active rồi.")
            return

        entry["status"]     = "active"
        entry["approved_at"] = str(date.today())
        if approved_by:
            entry["approved_by"] = approved_by
        self._save()