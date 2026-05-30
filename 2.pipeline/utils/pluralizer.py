# Đọc rule từ config, đoán tên folder plural cho module.

from pathlib import Path
import yaml

def _load_rules(config_dir: str) -> list:
    """
    Đọc plural rules từ config
    Và trả về list rules theo ưu tiên
    """

    rule_path = Path(config_dir) / "global" / "pluralization_rules.yaml"
    if not rule_path.exists():
        raise FileNotFoundError(f"Thiếu config: {rule_path}")

    data = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
    return data.get("rules", [])

def pluralize(name: str, config_dir: str) -> str:
    
    """
    Nhận tên module, trả về tên plural theo rule trong config.
    
    Ví dụ:
        pluralize("ticket")   → "tickets"
        pluralize("activity") → "activities"
        pluralize("status")   → "statuses"
    """
    rules = _load_rules(config_dir)

    for rule in rules:
        if "default" in rule:
            return name + rule["default"]

        suffix = rule.get("suffix", "")
        if name.endswith(suffix):
            return name[:-len(suffix)] + rule["replace"]

    return name + "s"