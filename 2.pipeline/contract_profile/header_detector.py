from __future__ import annotations
import re


def detect_request_headers(section_text: str, config: dict) -> list[dict]:
    header_cfg = config.get("header_refs", {})
    request_headers = header_cfg.get("request_headers", {})

    text_lower = (section_text or "").lower()
    results = []

    for header_name, info in request_headers.items():
        pattern = rf"\b{re.escape(header_name.lower())}\b"
        if not re.search(pattern, text_lower):
            continue

        item = {
            "name": header_name,
            "emit": bool(info.get("emit", False)),
        }

        if info.get("ref"):
            item["ref"] = info["ref"]

        if info.get("handled_by"):
            item["handled_by"] = info["handled_by"]

        if info.get("reason"):
            item["reason"] = info["reason"]

        results.append(item)

    return results
