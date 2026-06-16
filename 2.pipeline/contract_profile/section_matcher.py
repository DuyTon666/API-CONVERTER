from __future__ import annotations
import re


GENERIC_ALIASES = {
    "request",
    "response",
}


def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def _is_heading_like(line: str) -> bool:
    line = line.strip()
    if not line:
        return False

    patterns = [
        r"^\d+(\.\d+)*\s+.+",       # 4.1 Request Headers
        r"^[IVX]+\.\s+.+",          # I. Tổng quan
        r"^[a-zA-Z]\.\s+.+",        # a. Path Parameters
        r"^Response .+",
        r"^Request .+",
        r"^API .+",
    ]

    return any(re.match(p, line, flags=re.IGNORECASE) for p in patterns)


def _alias_matches_line(alias: str, line: str) -> bool:
    alias_norm = normalize_text(alias)
    line_norm = normalize_text(line)

    if not alias_norm or not line_norm:
        return False

    # Những alias quá chung như "Request"/"Response" chỉ match nếu exact heading.
    # Tránh match nhầm vào X-Request-Id hoặc "trả Response..."
    if alias_norm in GENERIC_ALIASES:
        return alias_norm == line_norm

    # Nếu là heading-like thì cho contains match.
    if _is_heading_like(line):
        return alias_norm == line_norm or alias_norm in line_norm

    # Với table row bình thường thì chỉ cho exact/starts-with nhẹ,
    # không contains bừa.
    return alias_norm == line_norm or line_norm.startswith(alias_norm + " ")


def detect_sections(text: str, config: dict) -> dict:
    aliases_cfg = config.get("section_aliases", {})
    sections = aliases_cfg.get("sections", {})

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    results = {}

    for section_name, section_info in sections.items():
        aliases = section_info.get("aliases", [])
        matched = []
        candidates = []
        
        # Extract keywords từ aliases để filter candidate headings
        alias_keywords = set()
        for alias in aliases:
            for word in normalize_text(alias).split():
                if len(word) > 3:  # bỏ từ ngắn như "the", "cho", "của"
                    alias_keywords.add(word)

        for line in lines:
            line_matched = False
            for alias in aliases:
                if _alias_matches_line(alias, line):
                    matched.append(alias)
                    line_matched = True
            if not line_matched and _is_heading_like(line):
                line_lower = normalize_text(line)
                if any(kw in line_lower for kw in alias_keywords):
                    candidates.append(line)
        results[section_name] = {
            "found":                bool(matched),
            "matched_aliases":      sorted(set(matched)),
            "candidate_headings":   candidates if not matched else [],
        }

    return results


def extract_section_texts(text: str, config: dict) -> dict[str, str]:
    aliases_cfg = config.get("section_aliases", {})
    sections = aliases_cfg.get("sections", {})

    lines = text.splitlines()
    starts: list[dict] = []

    for idx, line in enumerate(lines):
        clean = line.strip()
        if not clean:
            continue

        for section_name, section_info in sections.items():
            for alias in section_info.get("aliases", []):
                if _alias_matches_line(alias, clean):
                    starts.append({
                        "section": section_name,
                        "line_index": idx,
                        "line": clean,
                        "alias": alias,
                    })
                    break

    seen = set()
    unique_starts = []
    for item in sorted(starts, key=lambda x: x["line_index"]):
        key = (item["section"], item["line_index"])
        if key not in seen:
            unique_starts.append(item)
            seen.add(key)

    section_texts: dict[str, str] = {}

    for pos, item in enumerate(unique_starts):
        section = item["section"]
        start = item["line_index"]

        end = len(lines)
        for nxt in unique_starts[pos + 1:]:
            if nxt["line_index"] > start:
                end = nxt["line_index"]
                break

        chunk = "\n".join(lines[start:end]).strip()

        if section in section_texts:
            section_texts[section] += "\n" + chunk
        else:
            section_texts[section] = chunk

    return section_texts
