from __future__ import annotations
import re


def detect_status_codes(text: str, config: dict) -> list[dict]:
    status_cfg = config.get("status_response_refs", {})
    response_refs = status_cfg.get("responses", {})
    error_code_map = config.get("error_code_map", {}).get("error_codes", {})
    found = []
    found_statuses = set()
    full_text = text or ""

    for status_code, info in response_refs.items():
        pattern = rf"\b{re.escape(str(status_code))}\b"
        if not re.search(pattern, full_text):
            continue

        found.append({
            "status": str(status_code),
            "ref": info.get("ref"),
        })
        found_statuses.add(str(status_code))

    for error_code, info in error_code_map.items():
        pattern = rf"\b{re.escape(str(error_code))}\b"
        if not re.search(pattern, full_text):
            continue
        http_status = str(info.get("http_status", "422"))
        found.append({
            "status": http_status,
            "error_code": str(error_code),
            "message": info.get("message", ""),
            "ref": response_refs.get(http_status, {}).get("ref")
        })

    return found