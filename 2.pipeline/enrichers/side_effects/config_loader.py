# 2.pipeline/enrichers/side_effects/config_loader.py
"""
Đọc side_effects_rules.yaml và cung cấp helper lookup effect_templates.

File này chỉ là lớp truy xuất (accessor), không chứa logic suy luận.
"""
from pathlib import Path
from functools import lru_cache
import yaml

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "4.config" / "side_effects_rules.yaml"

@lru_cache(maxsize=1)
def load_rules() -> dict:
    """
    Đọc và parse side_effects_rules.yaml.
    Cache lại (lru_cache) vì file không đổi trong 1 lần chạy enricher.
    """
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy config: {_CONFIG_PATH}")

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if "effect_templates" not in data:
        raise ValueError(
            f"{_CONFIG_PATH} thiếu section 'effect_templates' - "
            "enricher không có gì để  build effects []"
        )
    return data

def get_effect_template(matched_rule: str, matched_keyword: str) -> dict | None:
    """
    Lookup template theo matched_rule (vd: 'action_verbs') và
    matched_keyword (vd: 'change') từ human_review_queue entry.

    Trả về dict dạng:
        {
            "confidence": 0.75,
            "effects": [ {...}, {...} ]
        }
    hoặc None nếu không có template tương ứng.
    """
    rules = load_rules()
    group = rules["effect_templates"].get(matched_rule)
    if group is None:
        return None
    return group.get(matched_keyword)


def find_effect_template_any_group(keyword: str) -> tuple[str, str] | None:
    """
    Tìm template cho `keyword` trên TẤT CẢ group trong effect_templates,
    không giới hạn ở action_verbs/notification_keywords/async_keywords.

    Dùng cho endpoint được path_classifier (LLM) gắn cờ 'action' — segment
    LLM trả về không nằm trong rule keyword list nào (đó là lý do rule
    match không bắt được), nhưng nếu ai đó đã khai báo sẵn template cho
    đúng keyword đó dưới 1 group thì vẫn nên dùng được, thay vì luôn skip.

    Trả (matched_rule, matched_keyword) nếu tìm thấy, None nếu không.
    """
    rules = load_rules()
    templates = rules.get("effect_templates", {})
    keyword_norm = keyword.lower()

    for group, group_templates in templates.items():
        if not isinstance(group_templates, dict):
            continue
        if keyword_norm in group_templates:
            return group, keyword_norm

    return None


def get_confidence_thresholds() -> dict:
    """
    Trả về confidence_thresholds từ config.
    vd: {"emit_yaml": 0.75, "human_review": 0.40}
    """
    rules = load_rules()
    return rules.get("confidence_thresholds", {})

def clear_cache() -> None:
    """Xoá cache — dùng trong test khi cần reload config sau khi sửa file."""
    load_rules.cache_clear()

def get_resource_vocabulary() -> dict:
    """
    Trả về resource_vocabulary từ config.
    vd: {"ticket": ["tickets", "ticket"], "service": [...], ...}
    """
    rules = load_rules()
    return rules.get("resource_vocabulary", {})