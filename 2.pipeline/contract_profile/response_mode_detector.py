from __future__ import annotations
import re


def find_content_types(text: str) -> list[str]:
    pattern = r"application/[a-zA-Z0-9.+_-]+"
    found = re.findall(pattern, text or "")

    cleaned = []
    for item in found:
        item = item.strip().rstrip(".,;:)")
        cleaned.append(item)

    return sorted(set(cleaned))


def detect_response_headers(text: str, config: dict) -> list[str]:
    """
    Chỉ nên truyền response_headers section text vào đây.
    Không truyền full document text để tránh false positive.
    """
    response_cfg = config.get("response_contract_rules", {})
    headers_cfg = response_cfg.get("response_headers", {})

    known_headers = set()

    content_type_header = headers_cfg.get("content_type_header", {})
    if content_type_header.get("name"):
        known_headers.add(content_type_header["name"])

    emit_headers = headers_cfg.get("emit_headers", {})
    for h in emit_headers.keys():
        known_headers.add(h)

    found = []
    text_lower = (text or "").lower()

    for header in known_headers:
        pattern = rf"\b{re.escape(header.lower())}\b"
        if re.search(pattern, text_lower):
            found.append(header)

    return sorted(found)


def detect_response_modes(text: str, config: dict) -> list[dict]:
    response_cfg = config.get("response_contract_rules", {})
    modes = response_cfg.get("response_modes", {})

    text_lower = (text or "").lower()
    content_types = find_content_types(text)

    results = []

    for mode_name, mode_rule in modes.items():
        indicators = mode_rule.get("indicators", {})
        reasons = []

        for ct in indicators.get("content_types", []):
            if ct in content_types:
                reasons.append(f"content_type:{ct}")

        for kw in indicators.get("text_keywords", []):
            if kw.lower() in text_lower:
                reasons.append(f"keyword:{kw}")

        for qp in indicators.get("query_params", []):
            name = qp.get("name")
            if name and re.search(rf"\b{re.escape(name.lower())}\b", text_lower):
                reasons.append(f"query_param:{name}")

        if reasons:
            results.append({
                "mode": mode_name,
                "schema_ref": mode_rule.get("schema_ref"),
                "reasons": reasons,
            })

    return results
