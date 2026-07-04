# 2.pipeline/converters/request_body/validation_adapter.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any 

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "4.config/request_schema_profiles.yaml"

# Data Models

@dataclass
class ConstraintEvidence:
    """
    Một constraint trích xuất được từ validation text.
    target_path: canonical path tuple — ghép với adapter khác bằng path.
    """
    target_path: tuple[str, ...]
    constraint_type: str
    value_raw: str
    value_parsed: Any
    parse_confidence: float
    source_text: str


@dataclass
class ValidationAdapterOutput:
    constraints: list[ConstraintEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    review_flags: list[dict] = field(default_factory=list)


# Config

def _load_config(config_path: str | Path | None = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config không tồn tại: {path} ")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# Pattern extractors 

# Tối đa N ký tự / max N chars / maxLength N
_MAX_LENGTH_RE = re.compile(
    r'(?:tối đa|toi da|max(?:imum)?(?:\s+length)?)\s+(\d+)\s*(?:ký tự|ki tu|char|character)?',
    re.IGNORECASE | re.UNICODE,
)

# Tối thiểu N ký tự / min N chars / minLength N
_MIN_LENGTH_RE = re.compile(
    r'(?:tối thiểu|toi thieu|min(?:imum)?(?:\s+length)?)\s+(\d+)\s*(?:ký tự|ki tu|char|character)?',
    re.IGNORECASE | re.UNICODE,
)

# Đúng N ký tự / exactly N chars
_EXACT_LENGTH_RE = re.compile(
    r'(?:đúng|dung|exactly)\s+(\d+)\s*(?:ký tự|ki tu|char|character)',
    re.IGNORECASE | re.UNICODE,
)

# ≥ N hoặc >= N
_MINIMUM_RE = re.compile(
    r'[≥>]=?\s*(\d+(?:\.\d+)?)',
    re.UNICODE,
)

# ≤ N hoặc <= N
_MAXIMUM_RE = re.compile(
    r'[≤<]=?\s*(\d+(?:\.\d+)?)',
    re.UNICODE,
)

# regex ^...$
_PATTERN_RE = re.compile(
    r'regex\s+(\S+)',
    re.IGNORECASE,
)

# enum dạng ∈ {A, B, C} hoặc ∈ {2048, 4096}
_ENUM_SET_RE = re.compile(
    r'[∈∋]\s*\{([^}]+)\}',
    re.UNICODE,
)


# Format hints 

# Đọc từ config nếu có, fallback về map cứng tối thiểu này
_BUILTIN_FORMAT_HINTS: dict[str, str] = {
    "rfc 5322": "email",
    "rfc5322": "email",
    "e.164": "phone",        # không phải OpenAPI format chuẩn — sẽ thêm warning
    "iso 3166-1 alpha-2": "iso3166-alpha2",
    "fqdn": "hostname",
    "rfc 1035": "hostname",
    "uuid": "uuid",
    "uri": "uri",
    "date": "date",
    "date-time": "date-time",
}


def _build_format_hints(config: dict) -> dict[str, str]:
    hints = dict(_BUILTIN_FORMAT_HINTS)
    for keyword, fmt in config.get("format_hints", {}).items():
        hints[keyword.lower()] = fmt
    return hints


# Field name / path extraction

def _parse_field_path(raw_name: str) -> tuple[str, ...]:
    """
    "contact.contact_tech" → ("contact", "contact_tech")
    "common_name"          → ("common_name",)
    """
    parts = [p.strip() for p in raw_name.strip().split(".") if p.strip()]
    return tuple(parts)


def _is_section_number_path(field_path: tuple[str, ...]) -> bool:
    """
    Bỏ qua heading dạng 4.4 / 5.1.2.
    Đây là section number, không phải field path.
    """
    return bool(field_path) and all(part.isdigit() for part in field_path)


# Single segment parser

def _extract_constraints_from_segment(
    field_path: tuple[str, ...],
    segment: str,
    format_hints: dict[str, str],
    review_flags: list[dict],
    warnings: list[str],
) -> list[ConstraintEvidence]:
    """
    Từ một đoạn text mô tả constraint của một field,
    trích xuất danh sách ConstraintEvidence.
    """
    results: list[ConstraintEvidence] = []
    seg_lower = segment.lower()

    # maxLength
    m = _MAX_LENGTH_RE.search(segment)
    if m:
        results.append(ConstraintEvidence(
            target_path=field_path,
            constraint_type="maxLength",
            value_raw=m.group(1),
            value_parsed=int(m.group(1)),
            parse_confidence=1.0,
            source_text=segment.strip(),
        ))

    # minLength
    m = _MIN_LENGTH_RE.search(segment)
    if m:
        results.append(ConstraintEvidence(
            target_path=field_path,
            constraint_type="minLength",
            value_raw=m.group(1),
            value_parsed=int(m.group(1)),
            parse_confidence=1.0,
            source_text=segment.strip(),
        ))

    # exactLength → minLength + maxLength
    m = _EXACT_LENGTH_RE.search(segment)
    if m:
        n = int(m.group(1))
        for ct in ("minLength", "maxLength"):
            results.append(ConstraintEvidence(
                target_path=field_path,
                constraint_type=ct,
                value_raw=m.group(1),
                value_parsed=n,
                parse_confidence=1.0,
                source_text=segment.strip(),
            ))

    # minimum (≥)
    m = _MINIMUM_RE.search(segment)
    if m:
        raw = m.group(1)
        parsed = float(raw) if "." in raw else int(raw)
        results.append(ConstraintEvidence(
            target_path=field_path,
            constraint_type="minimum",
            value_raw=raw,
            value_parsed=parsed,
            parse_confidence=1.0,
            source_text=segment.strip(),
        ))

    # maximum (≤)
    m = _MAXIMUM_RE.search(segment)
    if m:
        raw = m.group(1)
        parsed = float(raw) if "." in raw else int(raw)
        results.append(ConstraintEvidence(
            target_path=field_path,
            constraint_type="maximum",
            value_raw=raw,
            value_parsed=parsed,
            parse_confidence=1.0,
            source_text=segment.strip(),
        ))

    # pattern (regex ^...$)
    m = _PATTERN_RE.search(segment)
    if m:
        results.append(ConstraintEvidence(
            target_path=field_path,
            constraint_type="pattern",
            value_raw=m.group(1),
            value_parsed=m.group(1),
            parse_confidence=1.0,
            source_text=segment.strip(),
        ))

    # enum ∈ {A, B, C}
    m = _ENUM_SET_RE.search(segment)
    if m:
        raw_items = m.group(1)
        items = [item.strip() for item in raw_items.split(",") if item.strip()]
        try:
            parsed_items = [int(x) for x in items]
        except ValueError:
            try:
                parsed_items = [float(x) for x in items]
            except ValueError:
                parsed_items = items
        results.append(ConstraintEvidence(
            target_path=field_path,
            constraint_type="enum_values",
            value_raw=raw_items,
            value_parsed=parsed_items,
            parse_confidence=1.0,
            source_text=segment.strip(),
        ))

    # format hints
    for keyword, fmt in format_hints.items():
        if keyword in seg_lower:
            confidence = 1.0
            non_standard = {"phone", "iso3166-alpha2"}
            if fmt in non_standard:
                confidence = 0.7
                warnings.append(
                    f"{'.'.join(field_path)}: format '{fmt}' không phải OpenAPI standard — "
                    f"sẽ lưu vào x-format hoặc description"
                )
            results.append(ConstraintEvidence(
                target_path=field_path,
                constraint_type="format",
                value_raw=keyword,
                value_parsed=fmt,
                parse_confidence=confidence,
                source_text=segment.strip(),
            ))
            break

    return results


# Line parser 

# Nhận diện đầu dòng dạng "field_name: ..." hoặc "field.path: ..."
_FIELD_LINE_RE = re.compile(
    r'^([\w.]+)\s*(?:\([^)]*\))?\s*[:\-–]\s*(.+)$',
    re.UNICODE,
)

# Nhận diện dạng "field_name constraint. other_field constraint."
# Tách theo pattern: <word_or_path> <text>.
_MULTI_FIELD_RE = re.compile(
    r'([\w.]+)\s+([^.]+\.)',
    re.UNICODE,
)


def _parse_line(
    line: str,
    format_hints: dict[str, str],
    review_flags: list[dict],
    warnings: list[str],
) -> list[ConstraintEvidence]:
    """
    Parse một dòng validation text.
    Xử lý cả dạng:
      - "field: constraint text"
      - "field1 constraint1. field2 constraint2."
    """
    line = line.strip()
    if not line:
        return []

    results: list[ConstraintEvidence] = []

    # Thử dạng "field: text"
    m = _FIELD_LINE_RE.match(line)
    if m:
        raw_name = m.group(1)
        constraint_text = m.group(2)
        field_path = _parse_field_path(raw_name)
        if _is_section_number_path(field_path):
            return []
        results.extend(_extract_constraints_from_segment(
            field_path, constraint_text, format_hints, review_flags, warnings,
        ))
        return results

    # Thử dạng "field1 text. field2 text." — nhiều field trên 1 dòng
    # Ví dụ: "org_name tối đa 64 ký tự. locality tối đa 128 ký tự."
    matches = list(_MULTI_FIELD_RE.finditer(line))
    if len(matches) >= 2:
        for match in matches:
            raw_name = match.group(1)
            constraint_text = match.group(2)
            field_path = _parse_field_path(raw_name)
            if _is_section_number_path(field_path):
                continue
            results.extend(_extract_constraints_from_segment(
                field_path, constraint_text, format_hints, review_flags, warnings,
            ))
        return results

    # Thử dạng "field_name text" — field name là word/path đầu tiên, không có dấu :
    m = re.match(r'^(?:\d+(?:\.\d+)*[\.)]\s+)?([\w.]+)\s+(.+)$', line, re.UNICODE)
    if m:
        raw_name = m.group(1)
        constraint_text = m.group(2)
        field_path = _parse_field_path(raw_name)
        if _is_section_number_path(field_path):
            return []
        results.extend(_extract_constraints_from_segment(
            field_path, constraint_text, format_hints, review_flags, warnings,
        ))
        return results

    # Không nhận diện được cấu trúc field
    review_flags.append({
        "path": [],
        "reason": f"Không nhận diện được field name trong dòng: {line[:80]!r}",
        "adapter": "validation_adapter",
        "severity": "warning",
    })
    return results


# Public entry point 

def parse_validation_text(
    raw_block: str,
    section_path: list[str] | None = None,
    config_path: str | Path | None = None,
) -> ValidationAdapterOutput:
    """
    Parse block text validation rules thành danh sách ConstraintEvidence.

    Không biết module, tên file, hay field nghiệp vụ.
    Chỉ nhận diện pattern constraint từ text và gắn vào field path.
    """
    config = _load_config(config_path)
    format_hints = _build_format_hints(config)

    output = ValidationAdapterOutput()

    for line in raw_block.splitlines():
        line = line.strip().lstrip("-•·–—").strip()
        if not line:
            continue
        # Bỏ qua dòng chỉ là heading
        if line.endswith(":") and len(line) < 60 and " " not in line.rstrip(":"):
            continue

        constraints = _parse_line(
            line,
            format_hints,
            output.review_flags,
            output.warnings,
        )
        output.constraints.extend(constraints)

    return output
