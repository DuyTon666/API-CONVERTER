from __future__ import annotations
import re


def infer_enums(text: str, config: dict) -> list[dict]:
    enum_cfg = config.get("enum_inference_rules", {})
    if not enum_cfg.get("enabled", False):
        return []

    results = []
    text_lower = text.lower()

    known_params = enum_cfg.get("known_param_enums", {})
    confidence_cfg = enum_cfg.get("confidence", {})

    for param_name, rule in known_params.items():
        param_lower = param_name.lower()
        values = rule.get("values", [])

        if param_lower not in text_lower:
            continue

        found_values = []
        for value in values:
            if re.search(rf"\b{re.escape(str(value).lower())}\b", text_lower):
                found_values.append(value)

        if found_values:
            results.append({
                "param": param_name,
                "values": found_values,
                "default": rule.get("default"),
                "source": "known_param_enums",
                "confidence": confidence_cfg.get("from_known_param", 0.95),
            })

    return results
