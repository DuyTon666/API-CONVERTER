# 2.pipeline/enrichers/side_effects/effect_builder.py
"""
Build effects[] hoàn chỉnh từ effect_template + resource đã suy luận.

Resolve {resource} placeholder, gắn effect_id, source, confirmed, evidence.
Không hard-code mapping type -> effect_id segment trong Python -- dùng
chính field "type" có sẵn trong template.
"""

import copy


def _resolve_placeholder(value, resource: str | None):
    """
    Resolve "{resource}" trong string. Áp dụng đệ quy cho dict/list.

    Nếu resource là None và string có chứa "{resource}" -> giữ nguyên
    placeholder (không resolve được) -- enricher sẽ set confidence thấp /
    review_required=true cho case này ở bước sau.
    """
    if resource is None:
        return value

    if isinstance(value, str):
        return value.replace("{resource}", resource)

    if isinstance(value, dict):
        return {k: _resolve_placeholder(v, resource) for k, v in value.items()}

    if isinstance(value, list):
        return [_resolve_placeholder(v, resource) for v in value]

    return value


def _make_effect_id(resource: str | None, matched_keyword: str, effect_type: str, seq: int) -> str:
    """
    Format: {resource}_{keyword}_{type}_{seq:03d}
    vd: ticket_change_state_change_001

    Nếu resource là None, dùng "unknown" -- effect_id vẫn phải hợp lệ
    theo schema pattern ^[a-z0-9_]+$.
    """
    res = resource or "unknown"
    # effect_type có thể chứa "_" (vd "state_change", "async_job") -- giữ nguyên
    return f"{res}_{matched_keyword}_{effect_type}_{seq:03d}"


def build_effects(
    resource: str | None,
    resource_evidence: dict,
    template: dict,
    matched_rule: str,
    matched_keyword: str,
) -> list[dict]:
    """
    Build effects[] hoàn chỉnh, sẵn sàng để schema_validator kiểm tra.

    Args:
        resource: resource đã suy luận (có thể None)
        resource_evidence: dict từ resource_inferer.infer_resource()
        template: dict từ config_loader.get_effect_template()
                  -- {"confidence": float, "effects": [ {...}, ... ]}
        matched_rule: vd "action_verbs"
        matched_keyword: vd "change"

    Returns:
        list[dict] -- effects[] hoàn chỉnh
    """
    effects = []

    for i, effect_template in enumerate(template["effects"]):
        # Deep copy để không mutate config gốc (config bị cache bởi lru_cache)
        effect = copy.deepcopy(effect_template)

        # Resolve {resource} trong mọi field (description, target.entity, ...)
        effect = _resolve_placeholder(effect, resource)

        effect_type = effect["type"]

        # Gắn effect_id
        effect["effect_id"] = _make_effect_id(resource, matched_keyword, effect_type, i + 1)

        # Gắn source -- mọi effect do enricher build đều là rule_based ban đầu
        effect["source"] = "rule_based"

        # confirmed đã có sẵn = false trong template, giữ nguyên
        # (không set lại để không vô tình override nếu sau này template
        #  có effect đặc biệt confirmed=true)
        effect.setdefault("confirmed", False)

        # Gắn evidence
        effect["evidence"] = {
            "source": resource_evidence.get("resource_source"),
            "matched_keyword": matched_keyword,
            "rule_id": f"{matched_rule}.{matched_keyword}",
            "resource_source": resource_evidence.get("resource_source"),
            "template_index": i,
        }

        # channel field: nếu template không có (vd state_change), không thêm
        # -- schema cho phép field optional này absent

        effects.append(effect)

    return effects