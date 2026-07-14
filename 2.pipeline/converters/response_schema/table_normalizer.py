import re
import unicodedata
import yaml

from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH  = PROJECT_ROOT / "4.config" / "response_schema_profiles.yaml"

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@lru_cache(maxsize=1)
def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}

    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _strip_accents(value: str) -> str:
    text = str(value or "").replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)

    return "".join(
        character
        for character in text
        if unicodedata.category(character) != "Mn"
    )


def _normalize_text(value: str) -> str:
    text = _strip_accents(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _get_aliases(section: str, name: str) -> set[str]:
    values = (
        _load_config()
        .get(section, {})
        .get(name, [])
        or []
    )

    return {
        _normalize_text(value)
        for value in values
        if str(value).strip()
    }


def _type_alias_map() -> dict[str, str]:
    result = {}

    for canonical_type, aliases in (
        _load_config().get("type_aliases", {}) or {}
    ).items():
        result[_normalize_text(canonical_type)] = canonical_type

        for alias in aliases or []:
            normalized_alias = _normalize_text(alias)
            if normalized_alias:
                result[normalized_alias] = canonical_type

    return result


def _is_identifier(value: str) -> bool:
    return bool(_IDENTIFIER_PATTERN.fullmatch(str(value or "").strip()))


def _is_placeholder_name(value: str) -> bool:
    text = str(value or "").strip()

    if not text or text in {"-", "—"}:
        return True

    if _normalize_text(text) in _get_aliases("column_aliases", "field_name"):
        return True

    wrapper_pairs = (
        ("(", ")"),
        ("[", "]"),
        ("<", ">"),
    )

    for opening, closing in wrapper_pairs:
        if text.startswith(opening) and text.endswith(closing):
            return True

    return False


def _expand_combind_names(value: str) -> list[str]:
    """
    Tách trường dạng:

        created_at / updated_at

    thành hai field riêng.

    Chỉ tách khi mọi vế đều là JSON identifier hợp lệ.
    Không tách URL hoặc chuỗi mô tả có dấu slash.
    """
    text = str(value or "").strip()

    if "/" not in text:
        return [text]

    parts = [
        part.strip()
        for part in re.split(r"\s*/\s*", text)
        if part.strip()
    ]

    if len(parts) >= 2 and all(_is_identifier(part) for part in parts):
        return parts

    return [text]


def _parse_field_path(value: str) -> list[tuple, [str, bool]]:
    """
    Parse:

        pagination.total_items
        certificates[].cert_pem
        san_list[]

    thành list (field_name, is_array).
    """
    text = str(value or "").strip()

    if not text:
        return []

    raw_parts = [
        part.strip()
        for part in text.split(".")
        if part.strip()
    ]

    if not raw_parts:
        return []

    result = []

    for raw_part in raw_parts:
        is_array = raw_part.endswith("[]")
        name = raw_part[:-2].strip() if is_array else raw_part

        if not _is_identifier(name):
            return []

        result.append((name, is_array))

    return result


def _scalar_type_from_text(value: str) -> str:
    normalized = _normalize_text(value)
    alias_map = _type_alias_map()
    canonical = alias_map.get(normalized)

    if canonical in {
        "string",
        "integer",
        "number",
        "boolean",
        "null",
    }:
        return canonical

    return "object"


def _description_implies_array(description: str) -> bool:
    normalized_description = _normalize_text(description)

    prefixes = (
        _load_config()
        .get("array_description_prefixes", [])
        or []
    )

    for prefix in prefixes:
        normalized_prefix = _normalize_text(prefix)

        if (
            normalized_prefix
            and (
                normalized_description == normalized_prefix
                or normalized_description.startswith(normalized_prefix + " ")
            )
        ):
            return True

    return False


def _normalize_type(
    raw_type: str,
    field_name: str,
    description: str,
) -> dict:
    raw = str(raw_type or "").strip()
    normalized = _normalize_text(raw)
    compact = re.sub(r"\s+", "", normalized)
    alias_map = _type_alias_map()

    canonical = alias_map.get(normalized)

    if canonical == "array_object":
        return {
            "type": 'array'
        }