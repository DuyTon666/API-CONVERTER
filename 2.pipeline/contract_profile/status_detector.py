from __future__ import annotations
import re


def detect_status_codes(text: str, config: dict) -> list[dict]:
    status_cfg = config.get("status_response_refs", {})
    response_refs = status_cfg.get("responses", {})

    found = []
    full_text = text or ""

    for status_code, info in response_refs.items():
        pattern = rf"\b{re.escape(str(status_code))}\b"
        if not re.search(pattern, full_text):
            continue

        found.append({
            "status": str(status_code),
            "ref": info.get("ref"),
        })

    return found
