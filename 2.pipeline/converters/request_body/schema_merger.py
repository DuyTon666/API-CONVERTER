# 2.pipeline/converters/request_body/schema_merger.py

from __future__ import annotations

from typing import Any

from converters.request_body.schema_models import SchemaNode, SchemaParseResult


ARRAY_OBJECT_TYPE = "array<object>"
ARRAY_FILE_TYPE = "array<file>"


def _make_node_from_type(normalized_type: str | None, nullable: bool = False) -> SchemaNode:
    """
    Convert normalized_type từ adapter về SchemaNode.
    Không xử lý enum/constraints ở đây.
    """
    if normalized_type == ARRAY_OBJECT_TYPE:
        return SchemaNode(
            type="array",
            nullable=nullable,
            items=SchemaNode(type="object"),
        )

    if normalized_type == ARRAY_FILE_TYPE:
        return SchemaNode(
            type="array",
            nullable=nullable,
            items=SchemaNode(type="string", format="binary"),
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
            node = node.properties.get(part)

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
    if field_name not in parent.required:
        parent.required.append(field_name)


def _apply_table_field(
    root: SchemaNode,
    field: dict,
    warnings: list[str],
    unknown_paths: set[tuple[str, ...]],
) -> None:
    name = field.get("name")
    if not name:
        return

    parent_hint = field.get("parent_hint")
    matches = _find_field_paths(root, name, parent_hint)

    if not matches:
        # CSR hoặc bảng mô tả field không có pseudo_json tree.
        parent_path = _resolve_table_parent_path(root, parent_hint)
        parent = _ensure_object_path(root, parent_path)
        parent.properties[name] = _make_node_from_type(
            field.get("normalized_type"),
            bool(field.get("nullable")),
        )
        path = parent_path + (name,)
    elif len(matches) == 1:
        path = matches[0]
        current = _get_node(root, path)
        if current is None:
            warnings.append(f"Không tìm thấy node tại path {path}")
            return

        replacement = _make_node_from_type(
            field.get("normalized_type"),
            bool(field.get("nullable")),
        )

        # Giữ lại cấu trúc/example từ pseudo_json nếu có.
        replacement.properties = current.properties
        replacement.items = current.items
        replacement.has_example = current.has_example
        replacement.example = current.example
        replacement.required = current.required

        parent = _get_node(root, path[:-1])
        if parent is None:
            warnings.append(f"Không tìm thấy parent node tại path {path[:-1]}")
            return
        parent.properties[path[-1]] = replacement
    else:
        warnings.append(
            f"Field {name!r} bị ambiguous với parent_hint={parent_hint!r}: {matches}"
        )
        return

    node = _get_node(root, path)
    if node is None:
        return

    if field.get("description"):
        node.description = field["description"]

    if field.get("has_default"):
        node.has_default = True
        node.default = _cast_default(field.get("default_raw"), node)

    if field.get("required_state") == "required":
        parent = _get_node(root, path[:-1])
        if parent is not None:
            _add_required(parent, path[-1])

    # Nếu pseudo_json trước đó không biết type vì value null, table đã resolve được.
    if field.get("normalized_type"):
        unknown_paths.discard(path)


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
        _apply_table_field(root, field, warnings, unknown_paths)

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

    result = SchemaParseResult(root=root, warnings=warnings)
    # schema_models.py có thể đã hoặc chưa khai báo field này;
    # set attr để tương thích giai đoạn chuyển đổi.
    result.review_required = review_required

    return result