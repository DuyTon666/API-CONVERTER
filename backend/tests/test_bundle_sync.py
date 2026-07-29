import pytest
from ruamel.yaml import YAML

import services.bundle_sync as bundle_sync_module
from services.bundle_sync import (
    diff_bundle,
    sync_operation_fields,
    sync_schema_fields,
    _apply_operation_update,
    _merge_marker,
)

_yaml = YAML()
_yaml.default_flow_style = False


def _write_fragment(dir_path, filename, content: dict):
    dir_path.mkdir(parents=True, exist_ok=True)
    with (dir_path / filename).open("w", encoding="utf-8") as f:
        _yaml.dump(content, f)


def _read_fragment(path):
    return _yaml.load(path.read_text(encoding="utf-8"))


def _operation(**overrides):
    op = {
        "operationId": "getTicket",
        "summary": "old summary",
        "description": "old description",
        "parameters": [
            {"name": "user_id", "in": "query", "description": "old param desc"},
        ],
        "responses": {"200": {"description": "old response desc"}},
    }
    op.update(overrides)
    return op


def _bundle_with_operation(operation: dict) -> dict:
    return {"paths": {"/tickets/{id}": {"get": dict(operation)}}}


# OUTPUT_DIR được import ở đầu bundle_sync.py (module-level), nên patch thẳng
# tên trong module đó (bundle_sync_module.OUTPUT_DIR) là đúng chỗ.
@pytest.fixture
def output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle_sync_module, "OUTPUT_DIR", tmp_path)
    return tmp_path


# TC-FE-01: sửa summary qua diff+sync phải ghi đúng cả tầng 2 (file fragment)
# và tầng 3 (node bundle), marker x-manual-edit-fields đúng ở cả 2 nơi.
def test_sync_operation_fields_writes_both_layers(output_dir):
    _write_fragment(output_dir / "paths", "get_ticket.yaml", {"get": _operation()})

    old_bundle = _bundle_with_operation(_operation())
    new_bundle = _bundle_with_operation(_operation(summary="new summary"))

    changes = diff_bundle(old_bundle, new_bundle)
    missing = sync_operation_fields(new_bundle, changes)

    assert missing == set()
    op = new_bundle["paths"]["/tickets/{id}"]["get"]
    assert op["summary"] == "new summary"
    assert op["x-manual-edit-fields"] == ["summary"]

    fragment = _read_fragment(output_dir / "paths" / "get_ticket.yaml")
    assert fragment["get"]["summary"] == "new summary"
    assert fragment["get"]["x-manual-edit-fields"] == ["summary"]


# TC-FE-02: PATCH nhiều operation cùng lúc, mỗi operation cập nhật đúng riêng.
def test_sync_operation_fields_updates_multiple_operations(output_dir):
    _write_fragment(output_dir / "paths", "get_ticket.yaml", {"get": _operation()})
    _write_fragment(
        output_dir / "paths",
        "create_tickets.yaml",
        {"post": _operation(operationId="createTickets", summary="old create summary")},
    )

    old_bundle = {
        "paths": {
            "/tickets/{id}": {"get": _operation()},
            "/tickets": {"post": _operation(operationId="createTickets", summary="old create summary")},
        }
    }
    new_bundle = {
        "paths": {
            "/tickets/{id}": {"get": _operation(summary="new get summary")},
            "/tickets": {
                "post": _operation(operationId="createTickets", summary="new create summary")
            },
        }
    }

    changes = diff_bundle(old_bundle, new_bundle)
    missing = sync_operation_fields(new_bundle, changes)

    assert missing == set()
    assert new_bundle["paths"]["/tickets/{id}"]["get"]["summary"] == "new get summary"
    assert new_bundle["paths"]["/tickets"]["post"]["summary"] == "new create summary"


# TC-FE-03: operationId không tồn tại trong bundle hiện tại (bên "new") thì không
# thể diff (diff_bundle chỉ so những operationId có ở CẢ HAI bên) -> không có
# thay đổi, không lỗi. Mô phỏng đúng tinh thần "PATCH operationId lạ -> no-op".
def test_diff_bundle_ignores_operation_id_not_present_in_either_bundle():
    old_bundle = _bundle_with_operation(_operation())
    new_bundle = _bundle_with_operation(_operation())  # không đổi gì + operationId khác không tồn tại

    changes = diff_bundle(old_bundle, new_bundle)
    assert changes == []


# TC-FE-04: sync_operation_fields trả "missing" khi operationId có trong changes
# nhưng KHÔNG có trong bundle đang đồng bộ vào (vd đã bị đổi tên/xoá) -> no-op an toàn.
def test_sync_operation_fields_reports_missing_when_operation_id_gone(output_dir):
    from services.bundle_sync import Change

    new_bundle = _bundle_with_operation(_operation())  # bundle chỉ có "getTicket"
    changes = [Change(kind="operation", key="khongTonTai123", path="summary", new_value="x")]

    missing = sync_operation_fields(new_bundle, changes)
    assert missing == {"khongTonTai123"}


# TC-FE-04 (parameter không khớp): _apply_operation_update không đụng gì khi
# parameters[].name trong update không khớp tên tham số thật của operation.
def test_apply_operation_update_is_noop_for_unmatched_parameter_name():
    operation = _operation()
    touched = _apply_operation_update(
        operation, {"parameters": [{"name": "khong_ton_tai", "description": "abc"}]}
    )
    assert touched == {}
    assert operation["parameters"][0]["description"] == "old param desc"


# TC-FE-05: giá trị đặc biệt (\n, dấu ", emoji, dấu :) phải ghi + đọc lại y nguyên
# qua vòng ruamel.yaml (dump rồi load lại).
def test_sync_operation_fields_roundtrips_special_characters(output_dir):
    _write_fragment(output_dir / "paths", "get_ticket.yaml", {"get": _operation()})

    special_value = 'Dòng 1\nDòng 2 có dấu " và emoji 🎉, kèm dấu: hai chấm'
    old_bundle = _bundle_with_operation(_operation())
    new_bundle = _bundle_with_operation(_operation(description=special_value))

    changes = diff_bundle(old_bundle, new_bundle)
    sync_operation_fields(new_bundle, changes)

    fragment = _read_fragment(output_dir / "paths" / "get_ticket.yaml")
    assert fragment["get"]["description"] == special_value


# TC-FE-06: file tầng 2 hỏng cú pháp YAML trước khi sync tới -> tầng 3 vẫn ghi
# thành công, tầng 2 hỏng bị bỏ qua an toàn (không crash, không throw).
def test_sync_operation_fields_skips_corrupted_layer2_file_safely(output_dir):
    paths_dir = output_dir / "paths"
    paths_dir.mkdir(parents=True)
    (paths_dir / "get_ticket.yaml").write_text(
        "get:\n  operationId: getTicket\n  summary: [unclosed bracket {\n", encoding="utf-8"
    )

    old_bundle = _bundle_with_operation(_operation())
    new_bundle = _bundle_with_operation(_operation(summary="new summary"))

    changes = diff_bundle(old_bundle, new_bundle)
    missing = sync_operation_fields(new_bundle, changes)  # không được raise

    assert missing == set()
    assert new_bundle["paths"]["/tickets/{id}"]["get"]["summary"] == "new summary"


# TC-FE-07: marker cộng dồn qua nhiều lần sửa khác nhau (sửa summary trước,
# description sau) -> marker giữ cả 2 field, không mất field cũ.
def test_sync_operation_fields_accumulates_marker_across_calls(output_dir):
    import copy

    _write_fragment(output_dir / "paths", "get_ticket.yaml", {"get": _operation()})

    old_bundle = _bundle_with_operation(_operation())
    bundle_after_first = _bundle_with_operation(_operation(summary="new summary"))
    sync_operation_fields(bundle_after_first, diff_bundle(old_bundle, bundle_after_first))
    # bundle_after_first giờ đã bị sync_operation_fields mutate thêm
    # x-manual-edit-fields: ["summary"] ngay trên node -- dùng làm "old" cho lần
    # sửa thứ 2, đúng thực tế: PATCH lần 2 luôn đọc lại bundle đã lưu từ lần 1
    # (đã có marker), không phải dựng bundle mới từ đầu.
    bundle_after_second = copy.deepcopy(bundle_after_first)
    bundle_after_second["paths"]["/tickets/{id}"]["get"]["description"] = "new description"
    sync_operation_fields(
        bundle_after_second, diff_bundle(bundle_after_first, bundle_after_second)
    )

    op = bundle_after_second["paths"]["/tickets/{id}"]["get"]
    assert op["x-manual-edit-fields"] == ["description", "summary"]

    fragment = _read_fragment(output_dir / "paths" / "get_ticket.yaml")
    assert fragment["get"]["x-manual-edit-fields"] == ["description", "summary"]


# DEF-03 (đã fix): marker x-manual-edit-fields không được tự liệt kê chính nó
# khi so 2 bundle, dù 1 bên đã có marker và bên kia chưa (bundle content cũ còn
# trong state khi diff, tình huống mô tả trong TC-YAML-04).
def test_diff_bundle_excludes_manual_edit_marker_from_diff():
    old_bundle = _bundle_with_operation(
        _operation(**{"x-manual-edit-fields": ["summary"]})
    )
    new_bundle = _bundle_with_operation(_operation(description="edited elsewhere"))

    changes = diff_bundle(old_bundle, new_bundle)
    assert all(c.path != "x-manual-edit-fields" for c in changes)


# TC-AIFIX-02: field trong components/schemas/ (không phải operation) phải
# đồng bộ qua sync_schema_fields, marker dạng dot-path (khác operation ở chỗ
# schema file không có wrapper method như "get:"/"post:").
def test_sync_schema_fields_writes_schema_layer_with_marker(output_dir):
    schema_file = output_dir / "components" / "schemas" / "UserInfo.yaml"
    schema_file.parent.mkdir(parents=True)
    _write_fragment(
        schema_file.parent,
        "UserInfo.yaml",
        {"type": "object", "properties": {"id": {"type": "string"}}},
    )
    schema_index = {"UserInfo": schema_file}

    old_bundle = {"components": {"schemas": {"UserInfo": {"properties": {"id": {"type": "string"}}}}}}
    new_bundle = {
        "components": {
            "schemas": {
                "UserInfo": {"properties": {"id": {"type": "string", "description": "Mã người dùng"}}}
            }
        }
    }

    changes = diff_bundle(old_bundle, new_bundle)
    missing = sync_schema_fields(new_bundle, changes, schema_index)

    assert missing == set()
    schema_node = new_bundle["components"]["schemas"]["UserInfo"]
    assert schema_node["properties"]["id"]["description"] == "Mã người dùng"
    assert schema_node["x-manual-edit-fields"] == ["properties.id.description"]

    fragment = _read_fragment(schema_file)
    assert fragment["properties"]["id"]["description"] == "Mã người dùng"
    assert fragment["x-manual-edit-fields"] == ["properties.id.description"]


def test_merge_marker_accumulates_without_duplicates():
    assert _merge_marker(["summary"], ["description"]) == ["description", "summary"]
    assert _merge_marker(["summary"], ["summary"]) == ["summary"]
    assert _merge_marker(None, ["summary"]) == ["summary"]
