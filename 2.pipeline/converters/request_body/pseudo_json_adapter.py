# 2.pipeline/converters/request_body/pseudo_json_adapter.py

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "4.config/request_schema_profiles.yaml"

RequiredState = Literal["required", "optional", "unknown"]


# Comment patterns 

# Xóa comment // nhưng không phá https:// hay http://
# Strategy: chỉ xóa // khi không có chữ trước dấu /
_COMMENT_RE = re.compile(r'(?<![:/])//.*')

# Nhận diện required/optional từ comment text
_REQUIRED_HINT_RE = re.compile(
    r'\b(bắt buộc|required|mandatory)\b',
    re.IGNORECASE | re.UNICODE,
)
_OPTIONAL_HINT_RE = re.compile(
    r'\b(tùy chọn|optional|không bắt buộc)\b',
    re.IGNORECASE | re.UNICODE,
)

# Nhận diện default từ comment: "Mặc định: X" hoặc "default: X"
_DEFAULT_HINT_RE = re.compile(
    r'(?:mặc định|default)\s*[:\=]\s*["\']?([^"\',\n\]]+?)["\']?\s*(?:[,\n]|$)',
    re.IGNORECASE | re.UNICODE,
)


# Data models 

@dataclass
class StructureEvidenceNode:
    """
    Một node trong cây cấu trúc suy luận từ pseudo-JSON.
    Không chứa constraint, enum, format — đó là việc của validation_adapter.
    """
    name: str | None = None
    path: tuple[str, ...] = field(default_factory=tuple)
    inferred_type: str | None = None        # None nếu không chắc (null value)
    properties: dict[str, StructureEvidenceNode] = field(default_factory=dict)
    items: StructureEvidenceNode | None = None
    has_example: bool = False
    example: Any = None
    required_state: RequiredState = "unknown"
    has_default: bool = False
    default_raw: str | None = None
    review_required: bool = False           # True khi null value hoặc type không rõ


@dataclass
class PseudoJsonAdapterOutput:
    root: StructureEvidenceNode | None = None
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    review_flags: list[dict] = field(default_factory=list)


# Config loader 

def _load_config(config_path: str | Path | None = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config không tồn tại: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# Comment stripping 

def _extract_comment(line: str) -> str | None:
    """
    Trả nội dung comment (phần sau //) nếu có.
    Không lấy comment trong chuỗi JSON.
    """
    # Tìm // không nằm trong string và không phải ://
    in_string = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"' and (i == 0 or line[i-1] != '\\'):
            in_string = not in_string
        if not in_string and ch == '/' and i + 1 < len(line) and line[i+1] == '/':
            # Kiểm tra ký tự trước không phải ':'
            if i == 0 or line[i-1] != ':':
                return line[i+2:].strip()
        i += 1
    return None


def _strip_comments(raw: str) -> tuple[str, dict[str, str]]:
    """
    Trả (json_text_không_có_comment, map line_key→comment_text).
    line_key = tên field ở dòng đó nếu xác định được.
    """
    lines = raw.splitlines()
    clean_lines = []
    comments: dict[str, str] = {}

    for line in lines:
        comment = _extract_comment(line)

        # Lấy tên field từ dòng nếu có: "field_name": value
        field_match = re.match(r'\s*"([^"]+)"\s*:', line)
        field_name = field_match.group(1) if field_match else None

        if comment and field_name:
            comments[field_name] = comment

        # Xóa comment khỏi dòng
        clean_line = _strip_inline_comments(line)
        # Xóa trailing comma trước } hoặc ] (JSON không cho phép)
        clean_lines.append(clean_line)

    return '\n'.join(clean_lines), comments


def _fix_trailing_commas(text: str) -> str:
    """Xóa trailing comma trước } hoặc ] để JSON hợp lệ."""
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


# Type inference 

def _infer_type(value: Any) -> str | None:
    """
    Suy luận OpenAPI type từ Python value.
    Trả None nếu value là None (null trong JSON) — không đoán.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return None


# Comment hint parsing 

def _parse_required_from_comment(comment: str) -> RequiredState:
    if _REQUIRED_HINT_RE.search(comment):
        return "required"
    if _OPTIONAL_HINT_RE.search(comment):
        return "optional"
    return "unknown"


def _parse_default_from_comment(comment: str) -> tuple[bool, str | None]:
    m = _DEFAULT_HINT_RE.search(comment)
    if m:
        raw = m.group(1).strip()
        if raw:
            return True, raw
    return False, None


# Recursive builder 

def _build_node(
    name: str | None,
    value: Any,
    path: tuple[str, ...],
    comments: dict[str, str],
    warnings: list[str],
    review_flags: list[dict],
    max_depth: int,
) -> StructureEvidenceNode:
    node = StructureEvidenceNode(name=name, path=path)

    if len(path) > max_depth:
        warnings.append(f"Vượt max_depth={max_depth} tại path {path}")
        review_flags.append({
            "path": list(path),
            "reason": f"Nesting vượt giới hạn max_depth={max_depth}",
            "adapter": "pseudo_json_adapter",
            "severity": "warning",
        })
        return node

    # Lấy comment của field này (chỉ tìm theo tên, không theo path)
    comment = comments.get(name, "") if name else ""

    # Required/default từ comment
    if comment:
        node.required_state = _parse_required_from_comment(comment)
        node.has_default, node.default_raw = _parse_default_from_comment(comment)
    else:
        node.required_state = "unknown"

    # Infer type
    inferred = _infer_type(value)
    node.inferred_type = inferred

    if value is None:
        # null value — không kết luận type hay nullable
        node.review_required = True
        review_flags.append({
            "path": list(path),
            "reason": "Giá trị null — không thể suy luận type, cần xem xét thủ công",
            "adapter": "pseudo_json_adapter",
            "severity": "blocking",
        })
        return node

    # Lưu example (value mẫu, không phải default)
    node.has_example = True
    node.example = value

    if isinstance(value, dict):
        node.inferred_type = "object"
        for k, v in value.items():
            child_path = path + (k,)
            child = _build_node(k, v, child_path, comments, warnings, review_flags, max_depth)
            node.properties[k] = child

    elif isinstance(value, list):
        node.inferred_type = "array"
        if value:
            # Dùng phần tử đầu làm items schema
            first = value[0]
            items_path = path + ("[0]",)
            node.items = _build_node(None, first, items_path, comments, warnings, review_flags, max_depth)
        else:
            # Array rỗng — không biết items type
            warnings.append(f"Array rỗng tại {path} — không suy luận được items type")
            review_flags.append({
                "path": list(path),
                "reason": "Array rỗng — không suy luận được items type",
                "adapter": "pseudo_json_adapter",
                "severity": "warning",
            })

    return node


def _extract_first_json_like_block(raw: str) -> str:
    starts = [
        idx for idx in [raw.find("{"), raw.find("[")]
        if idx >= 0
    ]
    if not starts:
        return ""

    start = min(starts)
    stack = []
    in_string = False
    escaped = False

    for idx in range(start, len(raw)):
        ch = raw[idx]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch in "{[":
            stack.append(ch)
            continue

        if ch in "}]":
            if not stack:
                return raw[start:idx + 1]

            opener = stack.pop()
            if (opener == "{" and ch != "}") or (opener == "[" and ch != "]"):
                return raw[start:idx + 1]

            if not stack:
                return raw[start:idx + 1]

    return raw[start:]


def _strip_inline_comments(line: str) -> str:
    """
    Xóa // comment trong JSON-like text.

    Hỗ trợ case DOCX reader làm JSON sample thành 1 dòng:
      "a": 1, // comment "b": 2
    """
    result = []
    i = 0
    in_string = False
    escaped = False

    while i < len(line):
        ch = line[i]

        if in_string:
            result.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            if i == 0 or line[i - 1] != ":":
                j = i + 2

                while j < len(line):
                    if line[j] == "\n":
                        break

                    if line[j] == '"' and re.match(r'"[^"]+"\s*:', line[j:]):
                        break

                    if line[j] in "}]":
                        break

                    j += 1

                i = j
                continue

        result.append(ch)
        i += 1

    return "".join(result)


# Public API 
def parse_pseudo_json(
    raw_block: str,
    section_path: list[str] | None = None,
    config_path: str | Path | None = None,
) -> PseudoJsonAdapterOutput:
    """
    Parse một block pseudo-JSON thành StructureEvidenceNode đệ quy.

    Chỉ xử lý: nesting, inferred type, example, required/default từ comment.
    Không xử lý: constraint, enum, format, merge với bảng.
    """
    config = _load_config(config_path)
    policy = config.get("parser_policy", {})
    max_depth = int(policy.get("max_depth", 10))

    output = PseudoJsonAdapterOutput()

    raw_json_block = _extract_first_json_like_block(raw_block)
    if not raw_json_block:
        output.warnings.append("Không tìm thấy block JSON ({...} hoặc [...]) trong input")
        output.review_flags.append({
            "path": section_path or [],
            "reason": "Input không chứa pseudo-JSON block",
            "adapter": "pseudo_json_adapter",
            "severity": "blocking",
        })
        return output

    # Strip comments và fix trailing commas
    clean_text, comments = _strip_comments(raw_json_block)
    clean_text = _fix_trailing_commas(clean_text)

    # Parse JSON
    try:
        parsed = json.loads(clean_text)
    except json.JSONDecodeError as exc:
        output.warnings.append(f"Không parse được pseudo-JSON sau khi strip comment: {exc}")
        output.review_flags.append({
            "path": section_path or [],
            "reason": f"JSON parse error: {exc.msg} tại line {exc.lineno}:{exc.colno}",
            "adapter": "pseudo_json_adapter",
            "severity": "blocking",
        })
        return output

    # Build node tree
    root_path: tuple[str, ...] = tuple(section_path) if section_path else ()
    warnings: list[str] = []
    review_flags: list[dict] = []

    root_node = _build_node(
        name=None,
        value=parsed,
        path=root_path,
        comments=comments,
        warnings=warnings,
        review_flags=review_flags,
        max_depth=max_depth,
    )

    output.root = root_node
    output.warnings = warnings
    output.review_flags = review_flags

    # Confidence: giảm theo số blocking flag
    blocking = sum(1 for f in review_flags if f.get("severity") == "blocking")
    total_fields = _count_fields(root_node)
    if total_fields > 0:
        output.confidence = max(0.0, 1.0 - blocking / total_fields)
    else:
        output.confidence = 0.0

    return output


def _count_fields(node: StructureEvidenceNode) -> int:
    """Đếm tổng số leaf node trong cây."""
    if not node.properties and node.items is None:
        return 1
    count = 0
    for child in node.properties.values():
        count += _count_fields(child)
    if node.items:
        count += _count_fields(node.items)
    return count