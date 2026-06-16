# 2.pipeline/enrichers/path_classifier.py

import json
import re
import datetime
from pathlib import Path

import yaml
import anthropic

from import_flow.config import CONFIG_DIR

PATH_SEGMENTS_CONFIG = CONFIG_DIR / "path_segments.yaml"

_client = anthropic.Anthropic()

def _load_segments_config() -> dict:
    if not PATH_SEGMENTS_CONFIG.exists():
        return {"modules": {}}
    return yaml.safe_load(PATH_SEGMENTS_CONFIG.read_text(encoding="utf-8")) or {"modules": {}}

def _save_segments_config(data: dict) -> None:
    PATH_SEGMENTS_CONFIG.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

def _extract_segments(path: str) -> list[str]:
    return [
        s for s in path.split("/")
        if s and s != "v1" and not s.startswith("{")
    ]

def _get_last_meaningful_segment(path: str) -> str | None:
    segments = [s for s in path.split("/") if s and not s.startswith("{")]
    return segments[-1] if segments else None

def _is_cached(module_data: dict, segment: str) -> dict | None:
    for entry in module_data.get("action_segments", []):
        if entry["segment"] == segment:
            return {**entry, "type": "action"}
    for entry in module_data.get("resource_segments", []):
        if entry["segment"] == segment:
            return {**entry, "type": "resource"}
    return None

def _call_claude(segment: str, method: str, path: str, summary: str) -> dict:
    prompt = (
        "You are a REST API design expert.\n"
        f"HTTP method: {method}\n"
        f"Full path: {path}\n"
        f"Path segment to classify: '{segment}'\n"
        f"API summary: {summary}\n\n"
        "Classify this path segment as 'action' or 'resource'.\n"
        "- action: a verb or verb phrase indicating an operation (close, reopen, approve, change-password)\n"
        "- resource: a noun indicating a collection or entity (tickets, users, conversations, ratings)\n\n"
        "Return JSON only:\n"
        '{"type": "action", "confidence": 0.92, "reason": "verb indicating state change"}\n'
        "confidence must be a float between 0.0 and 1.0.\n"
        "Do not include any text before or after the JSON object."
    )

    try:
        response = _client.messages.create(
            model="cc/claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        return _parse_json(raw)
    except Exception as e:
        print(f"    [WARN] path_classifier LLM call failed: {e}")
        return {}

def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}

def _append_to_cache(config: dict, module: str, segment: str, result: dict) -> None:
    if module not in config["modules"]:
        config["modules"][module] = {
            "action_segments": [],
            "resource_segments": [],
        }    

    module_data = config["modules"][module]
    entry = {
        "segment": segment,
        "confidence": result.get("confidence", 0.0),
        "reason":     result.get("reason", ""),
        "classified_by":    "claude",
        "classified_at":    datetime.datetime.now().strftime("%Y-%m-%d"),
    }

    seg_type = result.get("type", "resource")
    if seg_type == "action":
        module_data["action_segments"].append(entry)
    else:
        module_data["resource_segments"].append(entry)

def classify_path(
    module: str,
    method: str,
    path: str,
    summary: str = "",
) -> dict | None:
    """
    Classify segment cuối của path.
    Trả về dict {"type", "segment", "confidence", "reason"} hoặc None nếu fail.
    Tự động cache vào path_segments.yaml.
    """
    segment = _get_last_meaningful_segment(path)
    if not segment:
        return None

    config      = _load_segments_config()
    module_data = config.get("modules", {}).get(module, {})

    cached = _is_cached(module_data, segment)
    if cached:
        print(f"    [path_classifier] cache hit: '{segment}' -> {cached['type']} (conf={cached['confidence']})")
        return cached

    print(f"    [path_classifier] classifying '{segment}' via Claude...")
    result = _call_claude(segment=segment, method=method, path=path, summary=summary)

    if not result or "type" not in result:
        print(f"    [WARN] path_classifier: Không classify được segment '{segment}'")
        return None

    print(
        f"  [path_classifier] '{segment}' -> {result['type']}"
        f"conf={result.get('confidence', 0.0):.2f})"
    )

    _append_to_cache(config, module, segment, result)
    _save_segments_config(config)

    return {**result, "segment": segment}