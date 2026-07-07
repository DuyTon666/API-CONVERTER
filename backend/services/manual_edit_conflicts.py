import json
import traceback
from pathlib import Path

from core.config import DIST_DIR
from core.errors import ErrorCode, http_error
from api_utils.field_paths import get_value_at_path


# Set các key hợp lệ trong 1 path item của OpenAPI — bản riêng cho
# manual_edit_conflicts.py, không tái dùng từ bundle_sync.py (chấp nhận
# duplicate nhỏ, xem plan Phần 2).
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


# Quét toàn bộ file tầng 2 dưới paths_dir, build map operationId -> (file, operation
# dict) — dùng chung cho cả lúc capture (trước import) và compare (sau import).
def _index_operations(paths_dir: Path) -> dict[str, tuple[Path, dict]]:
    import yaml as _yaml

    index: dict[str, tuple[Path, dict]] = {}
    if not paths_dir.exists():
        return index
    for file in paths_dir.glob("**/*.yaml"):
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
                    index[op_id] = (file, operation)
    return index

# Quét toàn bộ file schema tầng 2 dưới schemas_dir (1 module), build map
# schema_name (file.stem) -> (file, schema dict) — mirror của _index_operations()
# nhưng file schema không có wrapper method-key, nội dung file chính là schema dict.
def _index_schemas(schemas_dir: Path) -> dict[str, tuple[Path, dict]]:
    import yaml as _yaml

    index: dict[str, tuple[Path, dict]] = {}
    if not schemas_dir.exists():
        return index
    for file in schemas_dir.glob("**/*.yaml"):
        try:
            doc = _yaml.safe_load(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(doc, dict):
            index[file.stem] = (file, doc)
    return index

# Lấy đúng giá trị hiện tại của các field được đánh dấu trong marker
# x-manual-edit-fields — dùng cả lúc capture (giá trị trước import) và lúc lấy
# giá trị sau import để so sánh. Field summary/description -> giá trị thẳng;
# parameters/responses -> ghép key dạng "parameters.<name>" / "responses.<code>"
# để biết chính xác field con nào (đồng nhất với key dùng trong conflict entry).
def _extract_marked_fields(operation: dict, marker: list[str]) -> dict:
    fields = {}
    for path_str in marker:
        found, value = get_value_at_path(operation, path_str)
        if found:
            fields[path_str] = value
    return fields


# Capture — trước khi run_batch() có thể ghi đè file, lưu lại giá trị hiện tại
# của mọi field đã từng được đánh dấu sửa tay, để so sánh sau khi import xong.
def _scan_manual_edits(paths_dir: Path) -> dict:
    captured: dict[str, dict] = {}
    for op_id, (file, operation) in _index_operations(paths_dir).items():
        marker = operation.get("x-manual-edit-fields")
        if not marker:
            continue
        fields = _extract_marked_fields(operation, marker)
        if fields:
            captured[op_id] = {"file": file, "fields": fields}
    return captured

# Mirror của _scan_manual_edits() cho schema — tái dùng nguyên _extract_marked_fields()
# (đã generic theo dict + field-path, không phân biệt operation hay schema).
def _scan_manual_schema_edits(schemas_dir: Path) -> dict:
    captured: dict[str, dict] = {}
    for name, (file, schema) in _index_schemas(schemas_dir).items():
        marker = schema.get("x-manual-edit-fields")
        if not marker:
            continue
        fields = _extract_marked_fields(schema, marker)
        if fields:
            captured[name] = {"file": file, "fields": fields}
    return captured


# Lấy giá trị hiện tại của 1 field theo field_key ("summary"/"description" hoặc
# "parameters.<name>"/"responses.<code>"). Trả None nếu field đó không còn tồn
# tại trong operation (tham số/response bị xoá khỏi doc) — phân biệt với "" (field
# còn tồn tại nhưng rỗng), để không tạo conflict giả cho thứ không còn tồn tại.
def _get_field_value(operation: dict, field_key: str) -> str | None:
    found, value = get_value_at_path(operation, field_key)
    return value if found else None


# Đổi list field_key (dạng dotted) ngược lại thành dict x-manual-edit-fields —
# chiều ngược của _extract_marked_fields, dùng khi ghi lại marker sau so sánh.
def _field_keys_to_marker(field_keys: list[str]) -> list[str] | None:
    return sorted(set(field_keys)) or None


# Append conflict entries vào 3.build/reports/manual_edit_conflicts.json — đọc
# toàn bộ, nối thêm, ghi lại (không khoá tiến trình, xem rủi ro đã ghi trong plan).
def _append_manual_edit_conflicts(conflicts: list[dict]) -> None:
    if not conflicts:
        return
    from import_flow.config import REPORT_DIR

    path = REPORT_DIR / "manual_edit_conflicts.json"
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.extend(conflicts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# Sau khi run_batch() chạy xong cho 1 module: so sánh giá trị field đã sửa tay
# (captured trước import) với giá trị hiện tại. Field không đổi (hoặc file bị
# pipeline skip do version không đổi) -> ghi lại marker, không bị mất qua nhiều
# lần import. Field đổi thật (version đổi + giá trị mới khác giá trị sửa tay)
# -> KHÔNG ghi đè, đẩy vào hàng đợi review (API Phần 3 sẽ đọc file này).
def _resolve_manual_edits_after_import(
    paths_dir: Path, captured: dict, module_name: str, detected_at: str
) -> None:
    from ruamel.yaml import YAML

    fragment_yaml = YAML()
    fragment_yaml.default_flow_style = False
    fragment_yaml.indent(mapping=2, sequence=4, offset=2)

    after_index = _index_operations(paths_dir)
    conflicts = []

    for op_id, cap in captured.items():
        after = after_index.get(op_id)
        if after is None:
            continue  # file bị skip (marker vẫn còn) hoặc operation biến mất khỏi doc

        after_file, after_operation = after
        kept_fields = []
        for field_key, old_value in cap["fields"].items():
            new_value = _get_field_value(after_operation, field_key)
            if new_value is None:
                continue  # field không còn tồn tại — bỏ qua, không tạo conflict giả
            if new_value == old_value:
                kept_fields.append(field_key)
            else:
                conflicts.append(
                    {
                        "kind": "operation",
                        "entityId": op_id,
                        "module": module_name,
                        "field": field_key,
                        "old_value": old_value,
                        "new_value": new_value,
                        "detected_at": detected_at,
                    }
                )

        new_marker = _field_keys_to_marker(kept_fields)
        try:
            fragment = fragment_yaml.load(after_file.read_text(encoding="utf-8"))
            for method, operation in fragment.items():
                if (
                    method in _HTTP_METHODS
                    and isinstance(operation, dict)
                    and operation.get("operationId") == op_id
                ):
                    if new_marker:
                        operation["x-manual-edit-fields"] = new_marker
                    else:
                        operation.pop("x-manual-edit-fields", None)
            with after_file.open("w", encoding="utf-8") as f:
                fragment_yaml.dump(fragment, f)
        except Exception:
            traceback.print_exc()

    _append_manual_edit_conflicts(conflicts)

# Mirror của _resolve_manual_edits_after_import() cho schema — tái dùng nguyên
# _get_field_value(). Khác biệt: file schema không có method/operationId loop khi
# ghi lại marker — set thẳng trên schema dict (toàn bộ nội dung file).
def _resolve_manual_schema_edits_after_import(
    schemas_dir: Path, captured: dict, module_name: str, detected_at: str
) -> None:
    from ruamel.yaml import YAML

    fragment_yaml = YAML()
    fragment_yaml.default_flow_style = False
    fragment_yaml.indent(mapping=2, sequence=4, offset=2)

    after_index = _index_schemas(schemas_dir)
    conflicts = []

    for name, cap in captured.items():
        after = after_index.get(name)
        if after is None:
            continue

        after_file, after_schema = after
        kept_fields = []
        for field_key, old_value in cap["fields"].items():
            new_value = _get_field_value(after_schema, field_key)
            if new_value is None:
                continue
            if new_value == old_value:
                kept_fields.append(field_key)
            else:
                conflicts.append(
                    {
                        "kind": "schema",
                        "entityId": name,
                        "module": module_name,
                        "field": field_key,
                        "old_value": old_value,
                        "new_value": new_value,
                        "detected_at": detected_at,
                    }
                )

        new_marker = _field_keys_to_marker(kept_fields)
        try:
            fragment = fragment_yaml.load(after_file.read_text(encoding="utf-8"))
            if isinstance(fragment, dict):
                if new_marker:
                    fragment["x-manual-edit-fields"] = new_marker
                else:
                    fragment.pop("x-manual-edit-fields", None)
            with after_file.open("w", encoding="utf-8") as f:
                fragment_yaml.dump(fragment, f)
        except Exception:
            traceback.print_exc()

    _append_manual_edit_conflicts(conflicts)

# Trả về danh sách xung đột đang chờ duyệt — đọc thẳng manual_edit_conflicts.json
# (ghi bởi _append_manual_edit_conflicts), dùng cho ManualEditConflictsCard.
# Logic rút từ route GET /modules/manual-edit-conflicts.
def list_conflicts() -> list[dict]:
    from import_flow.config import REPORT_DIR

    path = REPORT_DIR / "manual_edit_conflicts.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


# Duyệt 1 xung đột. "keep_old": ghi old_value trở lại tầng 2 + tầng 3 qua
# sync_operation_fields() (services/bundle_sync.py) — cùng cơ chế dual-write dùng
# chung với Form Editor/YAML thô. "accept_new": không đổi gì trong file (giá trị
# mới đã có sẵn từ lúc _resolve_manual_edits_after_import phát hiện conflict).
# Cả 2 case: xoá entry khỏi hàng đợi. Logic rút từ route
# POST /modules/manual-edit-conflicts/resolve.
def resolve_conflict(payload: dict) -> dict:
    import yaml as _yaml
    from import_flow.config import REPORT_DIR

    kind = payload.get("kind", "operation")
    entity_id = payload.get("entityId") or payload.get("operationId")
    field_key = payload.get("field")
    choice = payload.get("choice")
    if not entity_id or not field_key or choice not in ("keep_old", "accept_new"):
        raise http_error(
            400,
            ErrorCode.INVALID_CONFLICT_RESOLVE,
            "Thiếu entityId/field hoặc choice không hợp lệ (phải là 'keep_old'/'accept_new')",
        )

    path = REPORT_DIR / "manual_edit_conflicts.json"
    if not path.exists():
        raise http_error(
            404, ErrorCode.CONFLICT_NOT_FOUND, "Không có xung đột nào đang chờ duyệt"
        )
    conflicts = json.loads(path.read_text(encoding="utf-8"))

    # Fallback tương thích ngược: entry cũ trong file (ghi trước khi có
    # kind/entityId) chỉ có "operationId" — coi như kind="operation".
    def entry_id(c: dict) -> str:
        return c.get("entityId", c.get("operationId"))

    def entry_kind(c: dict) -> str:
        return c.get("kind", "operation")

    match = next(
        (
            c
            for c in conflicts
            if entry_kind(c) == kind and entry_id(c) == entity_id and c["field"] == field_key
        ),
        None,
    )
    if match is None:
        raise http_error(
            404,
            ErrorCode.CONFLICT_NOT_FOUND,
            "Không tìm thấy xung đột này (có thể đã được duyệt trước đó)",
        )

    if choice == "keep_old":
        bundle_path = DIST_DIR / "openapi-bundled.yaml"
        bundle = _yaml.safe_load(bundle_path.read_text(encoding="utf-8")) or {}
        if kind == "schema":
            from services.bundle_sync import Change, sync_schema_fields, _index_schema_files

            change = Change(kind="schema", key=entity_id, path=field_key, new_value=match["old_value"])
            sync_schema_fields(bundle, [change], _index_schema_files())
        else:
            from services.bundle_sync import Change, sync_operation_fields, _index_operation_files

            change = Change(kind="operation", key=entity_id, path=field_key, new_value=match["old_value"])
            sync_operation_fields(bundle, [change], _index_operation_files())
        bundle_path.write_text(
            _yaml.dump(bundle, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    remaining = [
        c
        for c in conflicts
        if not (entry_kind(c) == kind and entry_id(c) == entity_id and c["field"] == field_key)
    ]
    path.write_text(
        json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"ok": True, "remaining": len(remaining)}
