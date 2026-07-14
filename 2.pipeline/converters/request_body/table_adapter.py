# 2.pipeline/converters/request_body/table_adapter.py
import re
from pathlib import Path
from typing import Any, Literal

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "4.config/schema_table_profiles.yaml"

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
    required_columns: set[str]
) -> dict[str, int]:
    """
    Map tên cột thực tế về canonical column name.

    required_columns lấy từ config, không cố định theo request/response.
    """
    mapping = {}
    for index, column in enumerate(columns):
        canonical_name = alias_lookup.get(_normalize(column))

        if canonical_name and canonical_name not in mapping:
            mapping[canonical_name] = index

    if len(mapping) < minimum_matches:
        return {}

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


def _parse_type(
    raw_value: str,
    config: dict,
) -> tuple[str | None, bool]:
    """
    Parse type hoàn toàn theo config.

    Không nhận diện được thì trả None để review,
    không tự biến thành string.
    """
    raw = str(raw_value or "").strip()

    nullable_config = config.get("nullable_markers", {}) or {}
    separator = str(nullable_config.get("separator") or "|")

    nullable_values = {
        _normalize(value)
        for value in nullable_config.get("values", [])
        if str(value).strip()
    }

    if separator:
        parts = [
            part.strip()
            for part in raw.split(separator)
            if part.strip()
        ]
    else:
        parts = [raw] if raw else []

    nullable = any(
        _normalize(part) in nullable_values
        for part in parts
    )

    parts = [
        part
        for part in parts
        if _normalize(part) not in nullable_values
    ]

    if not parts:
        return None, nullable

    type_raw = _normalize(parts[0])

    type_aliases = config.get("type_aliases", {}) or {}

    for canonical_type, aliases in type_aliases.items():
        candidates = {
            _normalize(canonical_type),
            *{
                _normalize(alias)
                for alias in aliases or []
                if str(alias).strip()
            },
        }

        if type_raw in candidates:
            return str(canonical_type), nullable

    # Fallback tổng quát cho "Array<X>"/"List<X>" mà tổ hợp X chưa được
    # khai báo sẵn thành 1 canonical type riêng trong config (config chỉ
    # có sẵn "array<object>"/"array<file>" cho 2 case hay gặp). Thay vì
    # phải liệt kê thủ công từng tổ hợp (Array<Int>, Array<Enum>,
    # Array<String>, ...), tự tách phần tử X ra rồi tra alias của chính
    # X — dùng lại đúng type_aliases đã có, không hard-code danh sách tổ
    # hợp nào cả.
    array_match = re.match(r'^(?:array|list)<(.+)>$', type_raw)
    if array_match:
        inner_canonical, _ = _parse_type(array_match.group(1).strip(), config)
        if inner_canonical and not inner_canonical.startswith("array<"):
            return f"array<{inner_canonical}>", nullable

    return None, nullable


def parse_table(
    headers: list[str],
    rows: list[list[str]],
    section_path: list[str],
    source_file: str,
    config: dict | None = None,
) -> dict:
    """
    Nhận headers + rows thô từ section collector.

    Mọi alias, syntax field path và policy review đều lấy từ config.
    """
    if config is None:
        config = _load_config()

    alias_lookup = _build_alias_lookup(
        config.get("column_aliases", {}) or {}
    )

    policy = config.get("parser_policy")
    if not isinstance(policy, dict):
        raise ValueError(
            "Thiếu parser_policy trong 4.config/schema_table_profiles.yaml"
        )

    minimum_matches = policy.get("minimum_header_matches")
    if not isinstance(minimum_matches, int) or minimum_matches <= 0:
        raise ValueError(
            "parser_policy.minimum_header_matches phải là số nguyên dương"
        )

    configured_required_columns = policy.get("required_columns")
    if not isinstance(configured_required_columns, list):
        raise ValueError(
            "parser_policy.required_columns phải là list"
        )

    required_columns = {
        str(name).strip()
        for name in configured_required_columns
        if str(name).strip()
    }

    if not required_columns:
        raise ValueError(
            "parser_policy.required_columns không được rỗng"
        )

    col_map = _map_header(
        headers,
        alias_lookup,
        minimum_matches,
        required_columns,
    )

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
        raw_name = _get_column(
            row,
            col_map,
            "field_name",
        ).strip()

        if not raw_name:
            continue

        if _is_wrapped_placeholder(raw_name, config):
            review_flags.append({
                "path": section_path,
                "reason": (
                    "Row là group/placeholder, không phải field: "
                    f"{raw_name!r}"
                ),
                "adapter": "table_adapter",
                "severity": _policy_severity(
                    config,
                    "placeholder_row",
                ),
            })
            continue

        expanded_names = _expand_field_names(
            raw_name,
            config,
        )

        type_raw = _get_column(
            row,
            col_map,
            "type",
        )

        normalized_type, nullable = _parse_type(
            type_raw,
            config,
        )

        required_raw = _get_column(
            row,
            col_map,
            "required",
        )

        required_state: RequiredState = _parse_required(
            required_raw,
            config,
        )

        default_raw = _get_column(
            row,
            col_map,
            "default",
        )

        has_default = (
            bool(default_raw)
            and default_raw not in {"-", "—"}
        )

        description = _get_column(
            row,
            col_map,
            "description",
        )

        for expanded_name in expanded_names:
            field_path = _parse_field_path(
                expanded_name,
                config,
            )

            if field_path is None:
                review_flags.append({
                    "path": section_path + [expanded_name],
                    "reason": (
                        "Field name/path không hợp lệ: "
                        f"{expanded_name!r}"
                    ),
                    "adapter": "table_adapter",
                    "severity": _policy_severity(
                        config,
                        "invalid_field_name",
                    ),
                })
                continue

            evidence_path = section_path + [
                segment["name"]
                for segment in field_path
            ]

            if normalized_type is None:
                review_flags.append({
                    "path": evidence_path,
                    "reason": (
                        f"Không nhận diện được type: {type_raw!r}"
                    ),
                    "adapter": "table_adapter",
                    "severity": _policy_severity(
                        config,
                        "unknown_type",
                    ),
                })

            if required_state == "unknown":
                review_flags.append({
                    "path": evidence_path,
                    "reason": (
                        "Không nhận diện được required marker: "
                        f"{required_raw!r}"
                    ),
                    "adapter": "table_adapter",
                    "severity": _policy_severity(
                        config,
                        "unknown_required_marker",
                    ),
                })

            fields.append({
                "name": field_path[-1]["name"],
                "raw_name": raw_name,
                "field_path": field_path,
                "parent_hint": (
                    section_path[-1]
                    if len(section_path) > 1
                    else None
                ),
                "type_raw": type_raw,
                "normalized_type": normalized_type,
                "nullable": nullable,
                "required_raw": required_raw,
                "required_state": required_state,
                "has_default": has_default,
                "default_raw": (
                    default_raw
                    if has_default
                    else None
                ),
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


def _field_path_policy(config: dict) -> dict:
    policy = config.get("field_path_policy")

    if not isinstance(policy, dict):
        raise ValueError(
            "Thiếu field_path_policy trong "
            "4.config/schema_table_profiles.yaml"
        )

    return policy


def _field_path_setting(
    config: dict,
    setting_name: str,
) -> str:
    policy = _field_path_policy(config)
    value = policy.get(setting_name)

    if value is None or str(value) == "":
        raise ValueError(
            f"Thiếu field_path_policy.{setting_name} "
            "trong 4.config/schema_table_profiles.yaml"
        )

    return str(value)


def _policy_severity(
    config: dict,
    policy_name: str,
) -> str:
    parser_policy = config.get("parser_policy")

    if not isinstance(parser_policy, dict):
        raise ValueError(
            "Thiếu parser_policy trong "
            "4.config/schema_table_profiles.yaml"
        )

    item_policy = parser_policy.get(policy_name)

    if not isinstance(item_policy, dict):
        raise ValueError(
            f"Thiếu parser_policy.{policy_name}"
        )

    severity = str(
        item_policy.get("severity") or ""
    ).strip()

    if not severity:
        raise ValueError(
            f"Thiếu parser_policy.{policy_name}.severity"
        )

    return severity


def _is_valid_identifier(
    value: str,
    config: dict,
) -> bool:
    pattern = _field_path_setting(
        config,
        "identifier_pattern",
    )

    return (
        re.fullmatch(
            pattern,
            str(value or "").strip(),
        )
        is not None
    )


def _is_wrapped_placeholder(
    value: str,
    config: dict,
) -> bool:
    text = str(value or "").strip()

    wrappers = (
        _field_path_policy(config)
        .get("placeholder_wrappers")
    )

    if not isinstance(wrappers, list):
        raise ValueError(
            "field_path_policy.placeholder_wrappers "
            "phải là list"
        )

    for wrapper in wrappers:
        if (
            not isinstance(wrapper, (list, tuple))
            or len(wrapper) != 2
        ):
            raise ValueError(
                "Mỗi placeholder wrapper phải có "
                "đúng opening và closing"
            )

        opening = str(wrapper[0])
        closing = str(wrapper[1])

        if (
            opening
            and closing
            and text.startswith(opening)
            and text.endswith(closing)
        ):
            return True

    return False


def _expand_field_names(
    raw_name: str,
    config: dict,
) -> list[str]:
    """
    Tách field kết hợp chỉ khi tất cả các phần đều là
    identifier hợp lệ.

    Separator được lấy từ config.
    """
    text = str(raw_name or "").strip()

    if not text:
        return []

    separator = _field_path_setting(
        config,
        "combined_name_separator",
    )

    if separator not in text:
        return [text]

    parts = [
        part.strip()
        for part in text.split(separator)
        if part.strip()
    ]

    if (
        len(parts) >= 2
        and all(
            _is_valid_identifier(part, config)
            for part in parts
        )
    ):
        return parts

    return [text]


def _parse_field_path(
    raw_name: str,
    config: dict,
) -> list[dict] | None:
    """
    Parse field path theo syntax trong config.

    Ví dụ với separator "." và array_suffix "[]":

      pagination.total_items
      certificates[].cert_pem
    """
    separator = _field_path_setting(
        config,
        "separator",
    )

    array_suffix = _field_path_setting(
        config,
        "array_suffix",
    )

    raw_parts = [
        part.strip()
        for part in str(raw_name or "").split(separator)
        if part.strip()
    ]

    if not raw_parts:
        return None

    result = []

    for index, raw_part in enumerate(raw_parts):
        is_array = raw_part.endswith(array_suffix)

        if is_array:
            name = raw_part[:-len(array_suffix)].strip()
        else:
            name = raw_part

        if not _is_valid_identifier(name, config):
            return None

        is_leaf = index == len(raw_parts) - 1

        if is_array:
            container = "array"
        elif is_leaf:
            container = "leaf"
        else:
            container = "object"

        result.append({
            "name": name,
            "container": container,
        })

    return result