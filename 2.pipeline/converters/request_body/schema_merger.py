# 2.pipeline/converters/request_body/schema_merger.py

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from converters.request_body.schema_models import SchemaNode, SchemaParseResult

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "4.config/schema_table_profiles.yaml"


@lru_cache(maxsize=1)
def _load_config(config_path: str | Path | None = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def _load_format_example_validators() -> dict[str, re.Pattern]:
    raw = _load_config().get("format_example_validators", {}) or {}
    return {
        fmt: re.compile(pattern)
        for fmt, pattern in raw.items()
    }


ARRAY_TYPE_PREFIX = "array<"
ARRAY_TYPE_SUFFIX = ">"


def _is_array_type(normalized_type: str | None) -> bool:
    return bool(
        normalized_type
        and normalized_type.startswith(ARRAY_TYPE_PREFIX)
        and normalized_type.endswith(ARRAY_TYPE_SUFFIX)
    )


def _make_node_from_type(normalized_type: str | None, nullable: bool = False) -> SchemaNode:
    """
    Convert normalized_type từ adapter về SchemaNode.
    Không xử lý enum/constraints ở đây.

    "array<X>" được xử lý tổng quát bằng đệ quy — KHÔNG hard-code danh
    sách item type được phép (object/file/string/integer/...). X là gì
    thì item node theo đúng type đó (kể cả X lồng thêm array khác).
    """
    if _is_array_type(normalized_type):
        item_type = normalized_type[len(ARRAY_TYPE_PREFIX):-len(ARRAY_TYPE_SUFFIX)]
        return SchemaNode(
            type="array",
            nullable=nullable,
            items=_make_node_from_type(item_type, nullable=False),
        )

    if normalized_type == "enum":
        return SchemaNode(type="string", nullable=nullable)

    if normalized_type == "file":
        return SchemaNode(type="string", nullable=nullable, format="binary")

    if normalized_type in {"object", "array", "string", "integer", "number", "boolean"}:
        return SchemaNode(type=normalized_type, nullable=nullable)

    # Placeholder nội bộ. Nếu còn node này sau merge thì review_required=True.
    return SchemaNode(type="string", nullable=nullable)


def _cast_default(raw_value: Any, node: SchemaNode) -> Any:
    """
    Cast default theo type cuối cùng của node.
    Không tự đổi semantic contract: N/A vẫn là "N/A", SHA-2 vẫn là "SHA-2".
    """
    if raw_value is None:
        return None

    value = str(raw_value).strip()

    if node.type == "integer":
        try:
            return int(value)
        except ValueError:
            return raw_value

    if node.type == "number":
        try:
            return float(value)
        except ValueError:
            return raw_value

    if node.type == "boolean":
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        return raw_value

    return raw_value


def _relative_path(
    path: tuple[str, ...],
    root_prefix: tuple[str, ...],
) -> tuple[str, ...]:
    """
    pseudo_json_adapter có thể gắn section_path như ("request_body",)
    vào path evidence. SchemaNode root thì bắt đầu ngay từ field thật.
    """
    if root_prefix and path[:len(root_prefix)] == root_prefix:
        return path[len(root_prefix):]
    return path


def _copy_basic_node(
    src,
    root_prefix: tuple[str, ...] | None = None,
) -> tuple[SchemaNode, set[tuple[str, ...]]]:
    """
    Convert StructureEvidenceNode từ pseudo_json_adapter sang SchemaNode.
    Trả thêm unknown_paths cho các field có value null hoặc không suy luận được type.
    """
    if root_prefix is None:
        root_prefix = tuple(getattr(src, "path", ()))

    unknown_paths: set[tuple[str, ...]] = set()

    inferred_type = getattr(src, "inferred_type", None)
    nullable = False

    if inferred_type is None or str(inferred_type).lower() in {"null", "none"}:
        node = SchemaNode(type="string", nullable=True)
        unknown_paths.add(_relative_path(tuple(getattr(src, "path", ())), root_prefix))
    else:
        node = _make_node_from_type(str(inferred_type), nullable=False)

    if getattr(src, "has_example", False):
        node.has_example = True
        node.example = getattr(src, "example", None)

    for child_name, child_src in getattr(src, "properties", {}).items():
        child_node, child_unknowns = _copy_basic_node(child_src, root_prefix)
        node.properties[child_name] = child_node
        unknown_paths.update(child_unknowns)

    src_items = getattr(src, "items", None)
    if src_items is not None:
        item_node, item_unknowns = _copy_basic_node(src_items, root_prefix)
        node.items = item_node
        unknown_paths.update(item_unknowns)

    return node, unknown_paths


def _iter_paths(node: SchemaNode, path: tuple[str, ...] = ()):
    yield path, node

    for name, child in node.properties.items():
        yield from _iter_paths(child, path + (name,))

    if node.items is not None:
        yield from _iter_paths(node.items, path + ("[]",))


def _get_node(root: SchemaNode, path: tuple[str, ...]) -> SchemaNode | None:
    node = root

    for part in path:
        if part == "[]":
            node = node.items
        else:
            # Field cha là array (vd "ratings[]") — field con nằm trong
            # .items chứ không phải .properties của chính node array.
            # Tự descend qua .items trước khi tra field_name, khớp với
            # cách _ensure_object_path() đã đặt field vào đó.
            if node is not None and node.type == "array":
                node = node.items
            node = node.properties.get(part) if node is not None else None

        if node is None:
            return None

    return node


def _ensure_object_path(root: SchemaNode, path: tuple[str, ...]) -> SchemaNode:
    """
    Tạo object path nếu table-only schema như CSR không có pseudo_json tree.
    """
    node = root

    for part in path:
        if part not in node.properties:
            node.properties[part] = SchemaNode(type="object")
        node = node.properties[part]

        if node.type == "array":
            # Field cha là array (vd bảng con "ratings[]") — field con
            # thuộc về item BÊN TRONG array đó, không phải chính node
            # array này. Không được ép type="object" lên thẳng node
            # array (sẽ làm mất type="array" đã suy đúng từ trước).
            if node.items is None:
                node.items = SchemaNode(type="object")
            node = node.items

        if node.type != "object":
            node.type = "object"

    return node


def _find_field_paths(
    root: SchemaNode,
    field_name: str,
    parent_hint: str | None,
) -> list[tuple[str, ...]]:
    matches: list[tuple[str, ...]] = []

    for path, _node in _iter_paths(root):
        if not path:
            continue

        if path[-1] != field_name:
            continue

        if parent_hint:
            if len(path) >= 2 and path[-2] == parent_hint:
                matches.append(path)
        else:
            matches.append(path)

    return matches


def _resolve_table_parent_path(
    root: SchemaNode,
    parent_hint: str | None,
) -> tuple[str, ...]:
    """
    Resolve parent path cho table-only schema.

    Case flat:
      parent_hint=None
      -> ()

    Case object trực tiếp:
      parent_hint="metadata"
      root.metadata exists
      -> ("metadata",)

    Case object con theo prefix:
      parent_hint="contact_org"
      root.contact exists
      -> ("contact", "contact_org")

    Không đoán nếu không có root object tương ứng.
    """
    if not parent_hint:
        return ()

    if _get_node(root, (parent_hint,)) is not None:
        return (parent_hint,)

    if "_" in parent_hint:
        prefix = parent_hint.split("_", 1)[0]
        prefix_node = _get_node(root, (prefix,))
        if prefix_node is not None and prefix_node.type == "object":
            return (prefix, parent_hint)

    return (parent_hint,)


def _add_required(parent: SchemaNode, field_name: str) -> None:
    # "required" chỉ có ý nghĩa trên schema type=object. Nếu parent
    # resolve ra là 1 node type=array (field cha là mảng object, vd
    # "ratings[]"), field con thực sự thuộc về .items — không phải
    # chính node array đó.
    if parent.type == "array" and parent.items is not None:
        parent = parent.items

    if field_name not in parent.required:
        parent.required.append(field_name)


def _seed_required_from_pseudo_json(node: SchemaNode, src) -> None:
    """
    pseudo_json_adapter suy ra required_state từ comment `// bắt buộc`
    ngay trong JSON mẫu — đây là nguồn duy nhất khi bảng field đi kèm
    không có cột "Bắt buộc" (case phổ biến ở tài liệu admin: JSON mẫu +
    bảng phụ 3 cột Tên/Kiểu/Mô tả). _copy_basic_node() không copy
    required_state nên nếu không seed ở đây, required từ comment sẽ
    bị mất hoàn toàn. Gọi trước khi áp table_output — _add_required()
    chỉ thêm chứ không bao giờ xoá, nên table vẫn có thể bổ sung thêm
    required mà không mất tính "table ưu tiên khi có khai báo tường minh".
    """
    for child_name, child_src in getattr(src, "properties", {}).items():
        child_node = node.properties.get(child_name)
        if child_node is None:
            continue

        if getattr(child_src, "required_state", None) == "required":
            _add_required(node, child_name)

        _seed_required_from_pseudo_json(child_node, child_src)


def _has_explicit_field_path(field: dict) -> bool:
    """
    Field path cần xử lý cấu trúc khi:

    - có nhiều segment: pagination.total_items
    - hoặc segment duy nhất là array: tags[]
    """
    field_path = field.get("field_path")

    if not isinstance(field_path, list) or not field_path:
        return False

    if len(field_path) > 1:
        return True

    first = field_path[0]

    return (
        isinstance(first, dict)
        and first.get("container") == "array"
    )


def _make_explicit_field_node(
    field: dict,
    leaf_container: str,
) -> SchemaNode:
    """
    Tạo leaf node từ field evidence.

    Ví dụ:
      cert_pem + String → string
      tags[] + String   → array<string>
      files[] + File    → array<binary>
    """
    normalized_type = field.get("normalized_type")
    nullable = bool(field.get("nullable"))

    if leaf_container != "array":
        return _make_node_from_type(
            normalized_type,
            nullable,
        )

    if normalized_type == "array" or _is_array_type(normalized_type):
        return _make_node_from_type(
            normalized_type,
            nullable,
        )

    item_node = None

    if normalized_type:
        item_node = _make_node_from_type(
            normalized_type,
            nullable=False,
        )

    return SchemaNode(
        type="array",
        nullable=nullable,
        items=item_node,
    )


def _resolve_explicit_field_target(
    root: SchemaNode,
    field: dict,
    warnings: list[str],
) -> tuple[SchemaNode, str, tuple[str, ...], str] | None:
    """
    Chuyển field_path thành vị trí thật trong SchemaNode.

    certificates[].cert_pem
      → certificates.items.properties.cert_pem

    pagination.total_items
      → pagination.properties.total_items
    """
    field_path = field.get("field_path")

    if not isinstance(field_path, list) or not field_path:
        return None

    parent_hint = field.get("parent_hint")
    base_path = _resolve_table_parent_path(
        root,
        parent_hint,
    )

    parent = _ensure_object_path(
        root,
        base_path,
    )

    canonical_path = list(base_path)

    for segment in field_path[:-1]:
        if not isinstance(segment, dict):
            warnings.append(
                f"Field path segment không hợp lệ: {segment!r}"
            )
            return None

        name = str(segment.get("name") or "").strip()
        container = str(
            segment.get("container") or ""
        ).strip()

        if not name or container not in {"object", "array"}:
            warnings.append(
                "Field path container không hợp lệ: "
                f"name={name!r}, container={container!r}"
            )
            return None

        child = parent.properties.get(name)

        if child is None:
            if container == "array":
                child = SchemaNode(
                    type="array",
                    items=SchemaNode(type="object"),
                )
            else:
                child = SchemaNode(type="object")

            parent.properties[name] = child

        if child.type != container:
            warnings.append(
                f"Conflict container tại path "
                f"{tuple(canonical_path + [name])}: "
                f"đang là {child.type!r}, "
                f"field path yêu cầu {container!r}"
            )
            return None

        canonical_path.append(name)

        if container == "array":
            if child.items is None:
                child.items = SchemaNode(type="object")

            if child.items.type != "object":
                warnings.append(
                    "Array có field con nhưng items không phải object "
                    f"tại path {tuple(canonical_path)}"
                )
                return None

            parent = child.items
            canonical_path.append("[]")
        else:
            parent = child

    leaf = field_path[-1]

    if not isinstance(leaf, dict):
        warnings.append(
            f"Leaf field path không hợp lệ: {leaf!r}"
        )
        return None

    leaf_name = str(leaf.get("name") or "").strip()
    leaf_container = str(
        leaf.get("container") or "leaf"
    ).strip()

    if (
        not leaf_name
        or leaf_container not in {"leaf", "array"}
    ):
        warnings.append(
            "Leaf field path không hợp lệ: "
            f"name={leaf_name!r}, "
            f"container={leaf_container!r}"
        )
        return None

    path = tuple(
        canonical_path + [leaf_name]
    )

    return (
        parent,
        leaf_name,
        path,
        leaf_container,
    )


def _apply_table_field(
    root: SchemaNode,
    field: dict,
    warnings: list[str],
    unknown_paths: set[tuple[str, ...]],
) -> bool:
    """
    Apply field table vào SchemaNode.

    Có field_path rõ ràng:
      dựng object/array theo field_path.

    Không có field_path:
      giữ nguyên flow parent_hint cũ.
    """
    name = str(field.get("name") or "").strip()

    if not name:
        return False

    if _has_explicit_field_path(field):
        resolved = _resolve_explicit_field_target(
            root,
            field,
            warnings,
        )

        if resolved is None:
            return True

        parent, name, path, leaf_container = resolved

        replacement = _make_explicit_field_node(
            field,
            leaf_container,
        )

        current = parent.properties.get(name)

        if current is not None:
            current_has_structure = (
                bool(current.properties)
                or current.items is not None
            )

            if (
                current.type != replacement.type
                and current_has_structure
            ):
                warnings.append(
                    f"Conflict type tại path {path}: "
                    f"đang là {current.type!r}, "
                    f"table khai báo {replacement.type!r}"
                )
                return True

            replacement.properties = current.properties

            if current.items is not None:
                replacement.items = current.items

            replacement.required = current.required
            replacement.has_example = current.has_example
            replacement.example = current.example

            # pseudo_json suy ra nullable=True khi value mẫu là null
            # (vd "duns": null) — bảng field thường chỉ ghi "String" (không
            # có marker "|null") nên _make_explicit_field_node() ở trên tạo
            # replacement với nullable=False, đè mất suy luận đúng đó. OR
            # lại để giữ nullable nếu MỘT trong hai nguồn xác nhận nullable.
            if current.nullable:
                replacement.nullable = True

        parent.properties[name] = replacement

    else:
        parent_hint = field.get("parent_hint")
        matches = _find_field_paths(
            root,
            name,
            parent_hint,
        )

        if not matches:
            parent_path = _resolve_table_parent_path(
                root,
                parent_hint,
            )

            parent = _ensure_object_path(
                root,
                parent_path,
            )

            parent.properties[name] = _make_node_from_type(
                field.get("normalized_type"),
                bool(field.get("nullable")),
            )

            path = parent_path + (name,)

        elif len(matches) == 1:
            path = matches[0]
            current = _get_node(root, path)

            if current is None:
                warnings.append(
                    f"Không tìm thấy node tại path {path}"
                )
                return True

            replacement = _make_node_from_type(
                field.get("normalized_type"),
                bool(field.get("nullable")),
            )

            replacement.properties = current.properties
            replacement.items = current.items
            replacement.has_example = current.has_example
            replacement.example = current.example
            replacement.required = current.required

            # Xem giải thích ở nhánh explicit-field-path phía trên: giữ
            # nullable nếu pseudo_json đã suy ra True (JSON mẫu có value
            # null) dù bảng field không ghi marker "|null".
            if current.nullable:
                replacement.nullable = True

            parent = _get_node(
                root,
                path[:-1],
            )

            if parent is None:
                warnings.append(
                    "Không tìm thấy parent node tại path "
                    f"{path[:-1]}"
                )
                return True

            parent.properties[path[-1]] = replacement

        else:
            warnings.append(
                f"Field {name!r} bị ambiguous với "
                f"parent_hint={parent_hint!r}: {matches}"
            )
            return True

    node = _get_node(root, path)

    if node is None:
        warnings.append(
            f"Không tìm thấy node sau khi merge tại path {path}"
        )
        return True

    if field.get("description"):
        node.description = field["description"]

    if field.get("has_default"):
        node.has_default = True
        node.default = _cast_default(
            field.get("default_raw"),
            node,
        )

    if field.get("required_state") == "required":
        required_parent = _get_node(
            root,
            path[:-1],
        )

        if required_parent is not None:
            _add_required(
                required_parent,
                path[-1],
            )

    if field.get("normalized_type"):
        unknown_paths.discard(path)

    return False


def _apply_table_output(
    root: SchemaNode,
    table_output: dict | None,
    warnings: list[str],
    unknown_paths: set[tuple[str, ...]],
) -> bool:
    has_blocking = False

    if not table_output:
        return has_blocking

    warnings.extend(table_output.get("warnings", []))

    for flag in table_output.get("review_flags", []):
        warnings.append(flag.get("reason", str(flag)))
        if flag.get("severity") == "blocking":
            has_blocking = True

    for field in table_output.get("fields", []):
        if _apply_table_field(
            root,
            field,
            warnings,
            unknown_paths,
        ):
            has_blocking = True

    return has_blocking


def _apply_constraint(
    root: SchemaNode,
    constraint,
    warnings: list[str],
) -> None:
    path = tuple(getattr(constraint, "target_path", ()))
    node = _get_node(root, path)

    if node is None:
        warnings.append(f"Không tìm thấy field cho constraint tại path {path}")
        return

    ctype = getattr(constraint, "constraint_type", "")
    value = getattr(constraint, "value_parsed", None)

    if value is None:
        warnings.append(f"Constraint {ctype!r} tại path {path} không có value_parsed")
        return

    if ctype == "enum_values":
        node.enum = value if isinstance(value, list) else [value]
        return

    if ctype == "format":
        node.format = str(value)
        return

    allowed_constraints = {
        "minLength",
        "maxLength",
        "pattern",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "uniqueItems",
    }

    if ctype in allowed_constraints:
        node.constraints[ctype] = value
        return

    warnings.append(f"Constraint type chưa hỗ trợ: {ctype!r} tại path {path}")


def _apply_validation_output(
    root: SchemaNode,
    validation_output,
    warnings: list[str],
) -> bool:
    has_blocking = False

    if not validation_output:
        return has_blocking

    warnings.extend(getattr(validation_output, "warnings", []))

    for flag in getattr(validation_output, "review_flags", []):
        warnings.append(flag.get("reason", str(flag)))
        if flag.get("severity") == "blocking":
            has_blocking = True

    for constraint in getattr(validation_output, "constraints", []):
        _apply_constraint(root, constraint, warnings)

    return has_blocking


def _sanitize_examples(
    node: SchemaNode,
    warnings: list[str],
    path: tuple[str, ...] = (),
) -> None:
    """
    Bỏ example không hợp lệ so với chính schema của nó — thà không có
    example còn hơn phát hành example sai. Không đoán/bịa giá trị thay
    thế. Đệ quy cho mọi node trong cây, không riêng root.

    3 case:
    - object thiếu field bắt buộc trong chính example của nó (docx đôi
      khi chỉ nhắc field trong text mô tả/comment, không đưa vào JSON
      mẫu).
    - object CÓ đủ field bắt buộc nhưng 1 giá trị bên trong không khớp
      format của field con đó (vd field con "provider_product_id" có
      format uuid, nhưng dict example của object cha lại giữ nguyên
      placeholder "uuid-v4" — tách biệt với example riêng của field
      con, nên phải kiểm cả ở đây).
    - leaf có format chuẩn OpenAPI (uuid, email, date, ...) nhưng
      example không khớp regex của format đó (docx viết placeholder mô
      tả, vd "uuid-v4", thay vì giá trị mẫu thật).
    """
    format_validators = _load_format_example_validators()

    def _is_missing_or_invalid(required_field: str) -> bool:
        if required_field not in node.example:
            return True
        child = node.properties.get(required_field)
        value = node.example[required_field]
        if child is None or not child.format or not isinstance(value, str):
            return False
        validator = format_validators.get(child.format)
        return validator is not None and not validator.match(value)

    if (
        node.type == "object"
        and node.has_example
        and isinstance(node.example, dict)
        and any(
            _is_missing_or_invalid(required_field)
            for required_field in node.required
        )
    ):
        missing = [
            f for f in node.required
            if _is_missing_or_invalid(f)
        ]
        warnings.append(
            f"Bỏ example tại path {path or ('root',)}: field bắt buộc "
            f"{missing} thiếu hoặc sai format trong ví dụ JSON nguồn"
        )
        node.has_example = False
        node.example = None

    if (
        node.has_example
        and node.format
        and isinstance(node.example, str)
    ):
        validator = _load_format_example_validators().get(node.format)
        if validator is not None and not validator.match(node.example):
            warnings.append(
                f"Bỏ example tại path {path or ('root',)}: {node.example!r} "
                f"không khớp format {node.format!r} trong ví dụ JSON nguồn"
            )
            node.has_example = False
            node.example = None

    for field_name, child in node.properties.items():
        _sanitize_examples(
            child, warnings, path + (field_name,),
        )

    if node.items is not None:
        _sanitize_examples(
            node.items, warnings, path + ("[]",),
        )


def merge(
    table_output: dict | None = None,
    pseudo_json_output=None,
    validation_output=None,
) -> SchemaParseResult:
    """
    Merge output từ 3 adapter thành SchemaParseResult.

    Precedence:
    - nesting/example: pseudo_json
    - type/required/default/description: table
    - enum/format/constraints: validation
    """
    warnings: list[str] = []
    review_required = False
    unknown_paths: set[tuple[str, ...]] = set()

    if pseudo_json_output and getattr(pseudo_json_output, "root", None) is not None:
        root, unknown_paths = _copy_basic_node(pseudo_json_output.root)
        _seed_required_from_pseudo_json(root, pseudo_json_output.root)
        warnings.extend(getattr(pseudo_json_output, "warnings", []))
    else:
        root = SchemaNode(type="object")

    if _apply_table_output(root, table_output, warnings, unknown_paths):
        review_required = True

    if _apply_validation_output(root, validation_output, warnings):
        review_required = True

    # Sau khi table đã có cơ hội resolve null/type unknown,
    # path nào vẫn unknown thì cần review.
    for path in sorted(unknown_paths):
        if path:
            warnings.append(
                f"Không suy luận được type cuối cùng cho path {path}"
            )
            review_required = True

    _sanitize_examples(root, warnings)

    result = SchemaParseResult(root=root, warnings=warnings)
    # schema_models.py có thể đã hoặc chưa khai báo field này;
    # set attr để tương thích giai đoạn chuyển đổi.
    result.review_required = review_required

    return result