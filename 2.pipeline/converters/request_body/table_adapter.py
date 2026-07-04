# 2.pipeline/converters/request_body/table_adapter.py
import re
from pathlib import Path
from typing import Any, Literal

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "4.config/request_schema_profiles.yaml"

RequiredState = Literal["required", "optional", "unknown"]


def _normalize(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _normalize_required_marker(value: Any) -> str:
    """
    Normalize riêng cho required marker.
    Ví dụ:
      Có*       -> có
      Yes*      -> yes
      Required* -> required

    Dấu * trong contract thường nghĩa là required có điều kiện.
    Ở OpenAPI, nếu object cha optional thì field con required vẫn biểu diễn đúng:
    object optional, nhưng khi object xuất hiện thì field con bắt buộc.
    """
    text = _normalize(value)
    text = re.sub(r"\s*\*+$", "", text).strip()
    return text


def _load_config(config_path: str | Path | None = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_alias_lookup(alias_group: dict) -> dict[str, str]:
    """canonical_name → list[alias] thành alias_normalized → canonical_name"""
    lookup = {}
    for canonical_name, aliases in alias_group.items():
        for alias in (aliases or []):
            lookup[_normalize(alias)] = canonical_name
    return lookup


def _map_header(
    columns: list[str],
    alias_lookup: dict[str, str],
    minimum_matches: int,
) -> dict[str, int]:
    """
    Map tên cột thực tế → index.
    Trả {} nếu không đủ minimum_matches hoặc thiếu cột bắt buộc.
    """
    mapping = {}
    for index, column in enumerate(columns):
        canonical_name = alias_lookup.get(_normalize(column))
        if canonical_name and canonical_name not in mapping:
            mapping[canonical_name] = index

    if len(mapping) < minimum_matches:
        return {}

    required_columns = {"field_name", "type"}
    if not required_columns.issubset(mapping):
        return {}

    return mapping


def _get_column(columns: list[str], mapping: dict[str, int], canonical_name: str) -> str:
    """Lấy giá trị cột theo tên canonical. Trả chuỗi rỗng nếu không có."""
    index = mapping.get(canonical_name)
    if index is None or index >= len(columns):
        return ""
    return columns[index].strip()


def _parse_required(raw_value: str, config: dict) -> RequiredState:
    """
    Trả "required" | "optional" | "unknown".
    "unknown" khi marker không khớp bất kỳ nhóm nào — cần review flag.
    """
    value = _normalize_required_marker(raw_value)
    markers = config.get("required_markers", {})

    required_values = {_normalize_required_marker(item) for item in markers.get("required", [])}
    optional_values = {_normalize_required_marker(item) for item in markers.get("optional", [])}

    if value in required_values:
        return "required"
    if value in optional_values or not value:
        return "optional"
    return "unknown"


def _parse_type(raw_value: str, config: dict) -> tuple[str | None, bool]:
    """
    Trả (normalized_type, nullable).
    normalized_type=None nếu không nhận diện được → cần review flag.
    Xử lý dạng "Object|Null" → ("object", True).
    """
    raw = raw_value.strip()

    # Tách nullable: "String|Null", "integer | null"
    nullable = False
    parts = [p.strip().lower() for p in re.split(r"\|", raw)]
    if "null" in parts:
        nullable = True
        parts = [p for p in parts if p != "null"]

    if not parts:
        return None, nullable

    type_raw = parts[0]

    # Tra alias config: canonical_type → list[alias]
    type_aliases = config.get("type_aliases", {})
    for canonical_type, aliases in type_aliases.items():
        for alias in (aliases or []):
            if _normalize(alias) == _normalize(type_raw):
                return canonical_type, nullable

    # Không tìm thấy trong config
    return None, nullable


def parse_table(
    headers: list[str],
    rows: list[list[str]],
    section_path: list[str],
    source_file: str,
    config: dict | None = None,
) -> dict:
    """
    Nhận headers + rows thô từ Section Collector.
    Trả dict:
      {
        "fields": list[dict],   ← FieldEvidence dạng dict
        "warnings": list[str],
        "review_flags": list[dict],
      }
    """
    if config is None:
        config = _load_config()

    alias_lookup = _build_alias_lookup(config.get("column_aliases", {}))
    policy = config.get("parser_policy", {})
    minimum_matches = policy.get("minimum_header_matches", 2)

    col_map = _map_header(headers, alias_lookup, minimum_matches)
    if not col_map:
        return {
            "fields": [],
            "warnings": [
                f"Bảng tại {section_path} không đủ cột nhận diện "
                f"(headers={headers})"
            ],
            "review_flags": [],
        }

    fields = []
    warnings = []
    review_flags = []

    for row in rows:
        name = _get_column(row, col_map, "field_name").strip()
        if not name:
            continue

        type_raw = _get_column(row, col_map, "type")
        normalized_type, nullable = _parse_type(type_raw, config)
        if normalized_type is None:
            review_flags.append({
                "path": section_path + [name],
                "reason": f"Không nhận diện được type: '{type_raw}'",
                "adapter": "table_adapter",
                "severity": "blocking",
            })

        required_raw = _get_column(row, col_map, "required")
        required_state: RequiredState = _parse_required(required_raw, config)
        if required_state == "unknown":
            review_flags.append({
                "path": section_path + [name],
                "reason": f"Không nhận diện được required marker: '{required_raw}'",
                "adapter": "table_adapter",
                "severity": "blocking",
            })

        default_raw = _get_column(row, col_map, "default")
        has_default = bool(default_raw) and default_raw not in {"-", "—"}

        description = _get_column(row, col_map, "description")

        fields.append({
            "name": name,
            "parent_hint": section_path[-1] if len(section_path) > 1 else None,
            "type_raw": type_raw,
            "normalized_type": normalized_type,
            "nullable": nullable,
            "required_raw": required_raw,
            "required_state": required_state,
            "has_default": has_default,
            "default_raw": default_raw if has_default else None,
            "description": description or None,
            "provenance": [{
                "adapter": "table_adapter",
                "section": " > ".join(section_path),
                "source_file": source_file,
            }],
        })

    return {
        "fields": fields,
        "warnings": warnings,
        "review_flags": review_flags,
    }