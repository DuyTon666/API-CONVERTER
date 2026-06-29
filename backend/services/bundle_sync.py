from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from core.config import OUTPUT_DIR
from utils.field_paths import PathSegment, format_path, set_value_at_path


# Set các key hợp lệ trong 1 path item của OpenAPI — dùng để lọc bỏ key khác
# (summary, description, parameters cấp path...) khi loop qua operation thật.
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def _is_inline(node: object) -> bool:
    """True nếu node là dict và không phải $ref (loại trừ response/schema dùng chung)."""
    return isinstance(node, dict) and "$ref" not in node

# Tạo dictionary để ghi lại những field đã sửa.
def _apply_operation_update(operation: dict, upd: dict) -> dict:
    """Áp update (summary/description/parameters/responses) vào 1 operation dict, trả về field vừa đổi."""
    touched = {}
    if "summary" in upd:
        operation["summary"] = upd["summary"]
        touched["summary"] = True
    if "description" in upd:
        operation["description"] = upd["description"]
        touched["description"] = True
    for p_upd in upd.get("parameters") or []:
        for p in operation.get("parameters") or []:
            if _is_inline(p) and p.get("name") == p_upd.get("name"):
                p["description"] = p_upd.get("description", "")
                touched.setdefault("parameters", []).append(p_upd.get("name"))
    for r_upd in upd.get("responses") or []:
        resp = (operation.get("responses") or {}).get(r_upd.get("code"))
        if _is_inline(resp):
            resp["description"] = r_upd.get("description", "")
            touched.setdefault("responses", []).append(r_upd.get("code"))
    return touched


def _index_operation_files() -> dict[str, Path]:
    """Quét toàn bộ file tầng 2 (5.openapi/paths/**), build map operationId -> đường dẫn file."""
    import yaml as _yaml

    index: dict[str, Path] = {}
    for file in OUTPUT_DIR.glob("paths/**/*.yaml"):
        try:
            doc = _yaml.safe_load(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        for method, operation in doc.items():
            if method in _HTTP_METHODS and isinstance(operation, dict):
                op_id = operation.get("operationId")
                if op_id:
                    index[op_id] = file
    return index


def _index_schema_files() -> dict[str, Path]:
    """Quét 5.openapi/components/schemas/**, map tên schema -> file.
    File schema không có wrapper key (khác file path/) — tên file (không .yaml)
    chính là tên schema, đúng với key trong bundle['components']['schemas']."""
    return {f.stem: f for f in OUTPUT_DIR.glob("components/schemas/**/*.yaml")}

def _diff_recursive(old: dict, new: dict, prefix: list[PathSegment]) -> list[tuple[str, object]]:
    """So sánh 2 dict, trả list (path_str, giá_trị_mới) cho mọi field khác nhau ở bất kỳ độ sâu."""
    changes = []
    for key in set(old.keys()) | set(new.keys()):
        if key == "x-manual-edit-fields":
            continue  # marker là bookkeeping nội bộ, không phải field user sửa — không diff
        old_val = old.get(key)
        new_val = new.get(key)
        if key == "parameters":
            changes.extend(_diff_parameters(old_val, new_val, prefix))
        elif key == "responses":
            changes.extend(_diff_responses(old_val, new_val, prefix))
        elif isinstance(old_val, dict) and isinstance(new_val, dict):
            changes.extend(_diff_recursive(old_val, new_val, prefix + [PathSegment(key=key)]))
        elif old_val != new_val:
            path_str = format_path(prefix + [PathSegment(key=key)])
            changes.append((path_str, new_val))
    return changes


def _diff_responses(old_dict: dict, new_dict: dict, prefix: list[PathSegment]) -> list[tuple[str, object]]:
    """So sánh dict responses theo code, bỏ qua code nào đang $ref ở 1 trong 2 bên."""
    changes = []
    for code in set(old_dict or {}) | set(new_dict or {}):
        old_r = (old_dict or {}).get(code)
        new_r = (new_dict or {}).get(code)
        if (old_r is not None and not _is_inline(old_r)) or (new_r is not None and not _is_inline(new_r)):
            continue
        seg = PathSegment(key="responses", selector=code)
        changes.extend(_diff_recursive(old_r or {}, new_r or {}, prefix + [seg]))
    return changes

def _diff_parameters(old_list: list, new_list: list, prefix: list[PathSegment]) -> list[tuple[str, object]]:
    """So sánh list parameters, match theo 'name', bỏ qua phần tử $ref."""
    changes = []
    old_by_name = {p.get("name"): p for p in (old_list or []) if isinstance(p, dict)}
    new_by_name = {p.get("name"): p for p in (new_list or []) if isinstance(p, dict)}
    for name in set(old_by_name) | set(new_by_name):
        old_p = old_by_name.get(name)
        new_p = new_by_name.get(name)
        if (old_p is not None and not _is_inline(old_p)) or (new_p is not None and not _is_inline(new_p)):
            continue
        seg = PathSegment(key="parameters", selector=name, match_field="name")
        changes.extend(_diff_recursive(old_p or {}, new_p or {}, prefix + [seg]))
    return changes

def _merge_marker(existing: list[str] | None, touched_paths: list[str]) -> list[str] | None:
    """Union field-path vừa sửa vào marker x-manual-edit-fields hiện có (cộng dồn qua nhiều lần sửa)."""
    merged = set(existing or [])
    merged.update(touched_paths)
    return sorted(merged) or None


@dataclass(frozen=True)
class Change:
    kind: Literal["operation", "schema"]
    key: str  # operationId hoặc tên schema
    path: str  # field-path, vd "responses[200].description"
    new_value: object


def _index_operations_by_id(bundle: dict) -> dict[str, dict]:
    """Map operationId -> operation dict, đi qua bundle['paths']."""
    index: dict[str, dict] = {}
    for path_item in (bundle.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method in _HTTP_METHODS and isinstance(operation, dict):
                op_id = operation.get("operationId")
                if op_id:
                    index[op_id] = operation
    return index


def diff_bundle(old_bundle: dict, new_bundle: dict) -> list[Change]:
    """So sánh operation theo operationId, schema theo tên — chỉ giữa node tồn tại ở CẢ HAI bundle."""
    changes = []

    old_ops = _index_operations_by_id(old_bundle)
    new_ops = _index_operations_by_id(new_bundle)
    for op_id in set(old_ops) & set(new_ops):
        for path_str, new_value in _diff_recursive(old_ops[op_id], new_ops[op_id], []):
            changes.append(Change(kind="operation", key=op_id, path=path_str, new_value=new_value))

    old_schemas = (old_bundle.get("components") or {}).get("schemas") or {}
    new_schemas = (new_bundle.get("components") or {}).get("schemas") or {}
    for name in set(old_schemas) & set(new_schemas):
        for path_str, new_value in _diff_recursive(old_schemas[name], new_schemas[name], []):
            changes.append(Change(kind="schema", key=name, path=path_str, new_value=new_value))

    return changes


def _apply_changes_and_mark(node: dict, changes: list[Change]) -> None:
    """Áp list Change vào 1 node (operation hoặc schema), gắn marker cho field thật sự set được."""
    touched_paths = [c.path for c in changes if set_value_at_path(node, c.path, c.new_value)]
    if touched_paths:
        node["x-manual-edit-fields"] = _merge_marker(node.get("x-manual-edit-fields"), touched_paths)


def sync_operation_fields(bundle: dict, changes: list[Change], op_index: dict[str, Path]) -> None:
    """Áp field đổi (kind='operation') vào tầng 3 (node trong bundle) + tầng 2 (file tương ứng),
    gắn marker x-manual-edit-fields ở cả 2 nơi. Lỗi đọc/ghi 1 file thì bỏ qua, không fail cả request."""
    from ruamel.yaml import YAML

    by_op: dict[str, list[Change]] = {}
    for c in changes:
        if c.kind == "operation":
            by_op.setdefault(c.key, []).append(c)
    if not by_op:
        return

    bundle_ops = _index_operations_by_id(bundle)
    fragment_yaml = YAML()
    fragment_yaml.default_flow_style = False
    fragment_yaml.indent(mapping=2, sequence=4, offset=2)

    for op_id, op_changes in by_op.items():
        operation = bundle_ops.get(op_id)
        if operation is not None:
            _apply_changes_and_mark(operation, op_changes)

        file_path = op_index.get(op_id)
        if file_path is None:
            continue
        try:
            fragment = fragment_yaml.load(file_path.read_text(encoding="utf-8"))
            for method, f_operation in fragment.items():
                if (
                    method in _HTTP_METHODS
                    and isinstance(f_operation, dict)
                    and f_operation.get("operationId") == op_id
                ):
                    _apply_changes_and_mark(f_operation, op_changes)
            with file_path.open("w", encoding="utf-8") as f:
                fragment_yaml.dump(fragment, f)
        except Exception:
            pass


def sync_schema_fields(bundle: dict, changes: list[Change], schema_index: dict[str, Path]) -> None:
    """Áp field đổi (kind='schema') vào tầng 3 + tầng 2 (file schema, không có wrapper key),
    gắn marker x-manual-edit-fields ở cả 2 nơi. Lỗi đọc/ghi 1 file thì bỏ qua, không fail cả request."""
    from ruamel.yaml import YAML

    by_schema: dict[str, list[Change]] = {}
    for c in changes:
        if c.kind == "schema":
            by_schema.setdefault(c.key, []).append(c)
    if not by_schema:
        return

    bundle_schemas = (bundle.get("components") or {}).get("schemas") or {}
    fragment_yaml = YAML()
    fragment_yaml.default_flow_style = False
    fragment_yaml.indent(mapping=2, sequence=4, offset=2)

    for name, schema_changes in by_schema.items():
        schema_node = bundle_schemas.get(name)
        if schema_node is not None:
            _apply_changes_and_mark(schema_node, schema_changes)

        file_path = schema_index.get(name)
        if file_path is None:
            continue
        try:
            fragment = fragment_yaml.load(file_path.read_text(encoding="utf-8"))
            if isinstance(fragment, dict):
                _apply_changes_and_mark(fragment, schema_changes)
            with file_path.open("w", encoding="utf-8") as f:
                fragment_yaml.dump(fragment, f)
        except Exception:
            pass
