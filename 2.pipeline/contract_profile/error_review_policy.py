# 2.pipeline/contract_profile/error_review_policy.py
from __future__ import annotations

import difflib
import re
import unicodedata
import os
import yaml

from pathlib import Path
from dataclasses import dataclass
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "4.config" / "errors" / "review_policy.yaml"
DEFAULT_GLOBAL_MAP_PATH = ROOT / "4.config" / "errors" / "error_code_map.yaml"

_GLOBAL_MAP_CACHE: dict | None = None
_POLICY_CACHE: dict | None = None


def load_review_policy() -> dict:
    global _POLICY_CACHE

    if _POLICY_CACHE is not None:
        return _POLICY_CACHE

    path = Path(os.environ.get("ERROR_REVIEW_POLICY_PATH", DEFAULT_POLICY_PATH))

    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy review policy config: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    _POLICY_CACHE = data
    return data


def load_global_error_map() -> dict:
    global _GLOBAL_MAP_CACHE

    if _GLOBAL_MAP_CACHE is not None:
        return _GLOBAL_MAP_CACHE

    path = Path(os.environ.get("ERROR_GLOBAL_MAP_PATH", DEFAULT_GLOBAL_MAP_PATH))

    if not path.exists():
        _GLOBAL_MAP_CACHE = {}
        return _GLOBAL_MAP_CACHE

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    error_codes = data.get("error_codes") or {}
    _GLOBAL_MAP_CACHE = error_codes if isinstance(error_codes, dict) else {}
    return _GLOBAL_MAP_CACHE


def get_global_error_code(code: str) -> dict:
    item = load_global_error_map().get(str(code)) or {}
    return item if isinstance(item, dict) else {}


def policy_get(path: list[str], default=None):
    cur = load_review_policy()

    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)

    return default if cur is None else cur


def get_similarity_threshold(name: str, default: float) -> float:
    value = policy_get(["similarity_thresholds", name], default)

    try:
        return float(value)
    except Exception:
        return default


def get_group_order() -> list[str]:
    return list(policy_get(["groups", "order"], []))


def get_group_title(group: str) -> str:
    titles = policy_get(["groups", "title"], {})
    if isinstance(titles, dict):
        return str(titles.get(group, group))
    return group


def is_hidden_by_default(group: str) -> bool:
    hidden = policy_get(["groups", "hidden_by_default"], [])
    return group in set(hidden or [])

@dataclass
class ReviewEntry:
    raw: dict
    code: str
    namespace: str
    source: str
    incoming_http: str
    incoming_message: str
    existing_http: str
    existing_message: str
    category: str
    missing_http_status: bool
    intra_batch_conflict: bool
    resolution: Any


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _pick(*values: Any) -> str:
    for value in values:
        text = _as_str(value)
        if text:
            return text
    return ""


def _normalize_http(value: Any) -> str:
    text = _as_str(value)
    if text.lower() in {"none", "null", "nan"}:
        return ""
    return text


def _remove_accents(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize_message(text: str) -> str:
    text = _remove_accents(text).lower()
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_suspect_message(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = normalize_message(raw)

    exact_values = policy_get(["message_quality", "suspect_exact"], [])
    if isinstance(exact_values, list):
        for item in exact_values:
            if normalize_message(str(item)) == normalized:
                return True

    regex_values = policy_get(["message_quality", "suspect_regex"], [])
    if isinstance(regex_values, list):
        for pattern in regex_values:
            try:
                if re.search(str(pattern), raw):
                    return True
            except re.error:
                continue
    
    return False


def message_similarity(a: str, b: str) -> float:
    na = normalize_message(a)
    nb = normalize_message(b)

    if not na or not nb:
        return 0.0

    seq_ratio = difflib.SequenceMatcher(None, na, nb).ratio()

    ta = set(na.split())
    tb = set(nb.split())

    if not ta or not tb:
        return seq_ratio

    jaccard = len(ta & tb) / len(ta | tb)
    return max(seq_ratio, jaccard)


def _get_nested(dct: dict, *keys: str) -> Any:
    cur: Any = dct
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def looks_like_review_entry(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False

    if "code" not in obj:
        return False

    return any(
        key in obj
        for key in (
            "incoming",
            "existing",
            "incoming_message",
            "existing_message",
            "matched_namespace",
            "namespace",
            "missing_http_status",
        )
    )


def flatten_review_entries(data: Any) -> list[dict]:
    result: list[dict] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if looks_like_review_entry(node):
                result.append(node)
                return

            for value in node.values():
                walk(value)

        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return result


def to_review_entry(raw: dict) -> ReviewEntry:
    incoming = raw.get("incoming") if isinstance(raw.get("incoming"), dict) else {}
    existing = raw.get("existing") if isinstance(raw.get("existing"), dict) else {}
    flags = raw.get("flags") if isinstance(raw.get("flags"), dict) else {}

    code = _pick(
        raw.get("code"),
        incoming.get("code"),
        existing.get("code"),
    )

    namespace = _pick(
        raw.get("namespace"),
        raw.get("matched_namespace"),
        raw.get("scope"),
        existing.get("namespace"),
        existing.get("scope"),
    )

    source = _pick(
        raw.get("source"),
        raw.get("source_file"),
        raw.get("file"),
        raw.get("filename"),
        raw.get("document"),
        incoming.get("source"),
        incoming.get("source_file"),
    )

    incoming_http = _normalize_http(
        _pick(
            incoming.get("http_status"),
            incoming.get("http"),
            raw.get("incoming_http_status"),
            raw.get("incoming_http"),
            raw.get("http_status"),
            raw.get("http"),
        )
    )

    existing_http = _normalize_http(
        _pick(
            existing.get("http_status"),
            existing.get("http"),
            raw.get("existing_http_status"),
            raw.get("existing_http"),
        )
    )

    incoming_message = _pick(
        incoming.get("message"),
        incoming.get("description"),
        raw.get("incoming_message"),
        raw.get("message"),
        raw.get("description"),
    )

    existing_message = _pick(
        existing.get("message"),
        existing.get("description"),
        raw.get("existing_message"),
    )

    namespaces = policy_get(["global_namespaces"], [])
    namespaces = {str(item).lower() for item in namespaces}

    if namespace.lower() in namespaces:
        global_def = get_global_error_code(code)

        if global_def:
            if not existing_http:
                existing_http = _normalize_http(
                    _pick(
                        global_def.get("http_status"),
                        global_def.get("http"),
                    )
                )

            if not existing_message:
                existing_message = _pick(
                    global_def.get("message"),
                    global_def.get("description"),
                )

    category = _pick(
        incoming.get("category"),
        raw.get("category"),
    )

    missing_http_status = bool(
        raw.get("missing_http_status")
        or flags.get("missing_http_status")
        or _get_nested(raw, "flags", "missing_http_status")
    )

    intra_batch_conflict = bool(
        raw.get("intra_batch_conflict")
        or flags.get("intra_batch_conflict")
        or _get_nested(raw, "flags", "intra_batch_conflict")
    )

    return ReviewEntry(
        raw=raw,
        code=code,
        namespace=namespace,
        source=source,
        incoming_http=incoming_http,
        incoming_message=incoming_message,
        existing_http=existing_http,
        existing_message=existing_message,
        category=category,
        missing_http_status=missing_http_status,
        intra_batch_conflict=intra_batch_conflict,
        resolution=raw.get("resolution"),
    )


def has_resolution(entry: ReviewEntry) -> bool:
    return entry.resolution not in (None, "", {}, [])


def is_global(entry: ReviewEntry) -> bool:
    namespaces = policy_get(["global_namespaces"], [])
    namespaces = {str(item).lower() for item in namespaces}
    return entry.namespace.lower() in namespaces


def suggest_http_status(entry: ReviewEntry) -> str:
    code = str(entry.code or "").strip()
    category = str(entry.category or "").strip()
    msg = normalize_message(entry.incoming_message)

    config = policy_get(["status_suggestion"], {})
    if not isinstance(config, dict):
        return "review"

    by_code = config.get("by_code") or {}
    if code in by_code:
        return str(by_code[code])

    for item in config.get("by_message_regex") or []:
        if not isinstance(item, dict):
            continue

        pattern = item.get("pattern")
        status = item.get("status")

        if not pattern or not status:
            continue

        try:
            if re.search(str(pattern), msg, flags=re.IGNORECASE):
                return str(status)
        except re.error:
            continue

    by_prefix = config.get("by_prefix") or {}
    for prefix, status in by_prefix.items():
        if code.startswith(str(prefix)):
            return str(status)

    by_category = config.get("by_category") or {}
    if category in by_category:
        return str(by_category[category])

    return str(config.get("default") or "review")


def classify_entry(entry: ReviewEntry) -> str:
    if has_resolution(entry):
        return "RESOLVED"

    if is_suspect_message(entry.incoming_message):
        return "PARSE_SUSPECT_MESSAGE"

    if entry.intra_batch_conflict and not is_global(entry):
        return "INTRA_MODULE_CODE_REVIEW"

    if entry.missing_http_status and not entry.incoming_http:
        return "MISSING_HTTP_STATUS"

    sim = message_similarity(entry.incoming_message, entry.existing_message)

    if is_global(entry):
        threshold = get_similarity_threshold("global_pass_candidate", 0.55)

        same_meaning = sim >= threshold or not entry.existing_message
        http_diff = (
            entry.incoming_http
            and entry.existing_http
            and entry.incoming_http != entry.existing_http
        )

        if http_diff:
            if same_meaning:
                return "GLOBAL_HTTP_VARIANT"
            return "GLOBAL_SEMANTIC_REVIEW"

        if same_meaning:
            return "GLOBAL_PASS_CANDIDATE"

        return "GLOBAL_SEMANTIC_REVIEW"

    if not entry.existing_message:
        if entry.intra_batch_conflict:
            return "INTRA_MODULE_CODE_REVIEW"
        return "NEW_CODE_OK_HIDE"

    threshold = get_similarity_threshold("safe_keep_existing", 0.72)

    if sim >= threshold:
        return "SAFE_KEEP_EXISTING"

    return "MODULE_HARD_CONFLICT"


def suggest_decision(entry: ReviewEntry, group: str) -> str:
    if group == "GLOBAL_HTTP_VARIANT":
        return "pass_global_variant"

    if group == "PARSE_SUSPECT_MESSAGE":
        return "fix_parser_or_source"

    if group in {"GLOBAL_PASS_CANDIDATE", "SAFE_KEEP_EXISTING"}:
        return "keep_existing"

    if group == "MISSING_HTTP_STATUS":
        return f"http_status={suggest_http_status(entry)}"

    if group in {"MODULE_HARD_CONFLICT", "INTRA_MODULE_CODE_REVIEW"}:
        return "reassign_or_reuse"

    return "needs_review"


def group_entries(
    entries: list[ReviewEntry],
    show_resolved: bool = False,
    show_new: bool = False,
) -> dict[str, list[ReviewEntry]]:
    grouped: dict[str, list[ReviewEntry]] = {}

    for entry in entries:
        group = classify_entry(entry)

        if group == "NEW_CODE_OK_HIDE" and not show_new:
            continue

        if group == "RESOLVED" and not show_resolved:
            continue

        if is_hidden_by_default(group):
            if group == "RESOLVED" and show_resolved:
                pass
            elif group == "NEW_CODE_OK_HIDE" and show_new:
                pass
            else:
                continue

        grouped.setdefault(group, []).append(entry)

    return grouped