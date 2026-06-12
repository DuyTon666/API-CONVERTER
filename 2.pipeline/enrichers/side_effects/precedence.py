# 2.pipeline/enrichers/side_effects/precedence.py
"""
Xử lý precedence khi YAML đã có x-side-effects từ trước.

Rule:
  - confirmed: true        -> KHÔNG BAO GIỜ overwrite
  - source: manual_override -> KHÔNG BAO GIỜ overwrite
  - source: rule_based + confirmed: false -> được replace nếu:
        cùng effect_id, HOẶC
        cùng (type, target, trigger)

Module này KHÔNG quyết định confidence/threshold -- chỉ merge effects[].
"""


def _effect_signature(effect: dict) -> tuple:
    """
    Signature dùng để so sánh 2 effect có "cùng ý nghĩa" không,
    khi effect_id khác nhau (vd: resource suy luận khác giữa 2 lần chạy).
    """
    target = effect.get("target", {})
    return (
        effect.get("type"),
        target.get("entity"),
        target.get("field"),
        effect.get("trigger"),
    )


def _is_protected(effect: dict) -> bool:
    """True nếu effect này KHÔNG được phép overwrite."""
    if effect.get("confirmed") is True:
        return True
    if effect.get("source") == "manual_override":
        return True
    if effect.get("source") == "human_review":
        return True
    return False


def resolve_effects(existing: dict | None, new_effects: list[dict]) -> tuple[list[dict], dict]:
    """
    Merge new_effects vào existing["effects"] (nếu có), theo precedence rule.

    Args:
        existing: dict x-side-effects hiện tại trong YAML, hoặc None
        new_effects: list[dict] effects[] mới build từ effect_builder

    Returns:
        (merged_effects, merge_report)
        merge_report: dict thống kê -- {"kept": int, "replaced": int, "added": int}
    """
    report = {"kept": 0, "replaced": 0, "added": 0}

    if existing is None or not existing.get("effects"):
        report["added"] = len(new_effects)
        return new_effects, report

    old_effects = existing["effects"]

    # Index old effects: theo effect_id và theo signature
    old_by_id = {e.get("effect_id"): e for e in old_effects}
    old_by_sig = {}
    for e in old_effects:
        old_by_sig.setdefault(_effect_signature(e), e)

    merged = []
    consumed_old_ids = set()

    for new_effect in new_effects:
        old_match = old_by_id.get(new_effect.get("effect_id")) or old_by_sig.get(
            _effect_signature(new_effect)
        )

        if old_match is not None and _is_protected(old_match):
            # Giữ effect cũ (protected), bỏ effect mới
            merged.append(old_match)
            consumed_old_ids.add(old_match.get("effect_id"))
            report["kept"] += 1
        elif old_match is not None:
            # Old effect là rule_based + confirmed=false -> replace bằng new
            merged.append(new_effect)
            consumed_old_ids.add(old_match.get("effect_id"))
            report["replaced"] += 1
        else:
            # Không có effect cũ tương ứng -> effect hoàn toàn mới
            merged.append(new_effect)
            report["added"] += 1

    # Giữ lại các old effect KHÔNG bị consume (vd: protected effect mà
    # new_effects không có signature tương ứng -- vẫn phải giữ)
    for old_effect in old_effects:
        if old_effect.get("effect_id") not in consumed_old_ids and _is_protected(old_effect):
            merged.append(old_effect)
            report["kept"] += 1

    return merged, report