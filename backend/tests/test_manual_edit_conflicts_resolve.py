import json

import pytest
from fastapi import HTTPException
from ruamel.yaml import YAML

import services.manual_edit_conflicts as conflicts_module
import services.bundle_sync as bundle_sync_module
import import_flow.config as import_flow_config
from services.manual_edit_conflicts import list_conflicts, resolve_conflict

_yaml = YAML()

BUNDLE_TEXT = """paths:
  /tickets/{id}:
    get:
      operationId: getTicket
      summary: giá trị MỚI từ import
"""


def _seed_conflicts(report_dir, entries: list[dict]):
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "manual_edit_conflicts.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _conflict_entry(**overrides):
    entry = {
        "kind": "operation",
        "entityId": "getTicket",
        "field": "summary",
        "old_value": "giá trị CŨ do user sửa tay",
        "new_value": "giá trị MỚI từ import",
        "module": "ticket",
        "detected_at": "2026-07-01T00:00:00",
    }
    entry.update(overrides)
    return entry


# DIST_DIR được import module-level trong manual_edit_conflicts.py -> patch
# thẳng tên đó. REPORT_DIR được import cục bộ trong từng hàm -> patch tại
# import_flow.config (nguồn), giống cách đã làm ở test_manual_edit_conflicts_api.py.
# OUTPUT_DIR (dùng bởi sync_operation_fields khi "keep_old") patch ở bundle_sync.
@pytest.fixture
def conflict_env(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    output_dir = tmp_path / "5.openapi"
    report_dir = tmp_path / "reports"
    dist_dir.mkdir()
    (dist_dir / "openapi-bundled.yaml").write_text(BUNDLE_TEXT, encoding="utf-8")

    monkeypatch.setattr(conflicts_module, "DIST_DIR", dist_dir)
    monkeypatch.setattr(bundle_sync_module, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(import_flow_config, "REPORT_DIR", report_dir)
    return dist_dir, output_dir, report_dir


# TC-CONFLICT-02: card hiện đúng dữ liệu — GET trả đúng entry vừa bơm.
def test_list_conflicts_returns_seeded_entries(conflict_env):
    _, _, report_dir = conflict_env
    _seed_conflicts(report_dir, [_conflict_entry()])

    result = list_conflicts()
    assert len(result) == 1
    assert result[0]["entityId"] == "getTicket"
    assert result[0]["field"] == "summary"


# TC-CONFLICT-03: "Giữ bản cũ" (keep_old) -- tầng 2 + tầng 3 đổi về đúng
# old_value, marker được set lại, entry biến mất khỏi queue.
def test_resolve_keep_old_restores_old_value_in_both_layers(conflict_env):
    dist_dir, output_dir, report_dir = conflict_env
    _seed_conflicts(report_dir, [_conflict_entry()])

    paths_dir = output_dir / "paths"
    paths_dir.mkdir(parents=True)
    with (paths_dir / "get_ticket.yaml").open("w", encoding="utf-8") as f:
        _yaml.dump({"get": {"operationId": "getTicket", "summary": "giá trị MỚI từ import"}}, f)

    result = resolve_conflict(
        {"entityId": "getTicket", "field": "summary", "choice": "keep_old"}
    )

    assert result == {"ok": True, "remaining": 0}
    assert list_conflicts() == []

    bundle = _yaml.load((dist_dir / "openapi-bundled.yaml").read_text(encoding="utf-8"))
    op = bundle["paths"]["/tickets/{id}"]["get"]
    assert op["summary"] == "giá trị CŨ do user sửa tay"
    assert op["x-manual-edit-fields"] == ["summary"]

    fragment = _yaml.load((paths_dir / "get_ticket.yaml").read_text(encoding="utf-8"))
    assert fragment["get"]["summary"] == "giá trị CŨ do user sửa tay"


# TC-CONFLICT-04: "Lấy bản mới" (accept_new) -- tầng 2 + tầng 3 KHÔNG đổi gì,
# entry biến mất khỏi queue.
def test_resolve_accept_new_leaves_content_untouched(conflict_env):
    dist_dir, output_dir, report_dir = conflict_env
    _seed_conflicts(report_dir, [_conflict_entry()])

    result = resolve_conflict(
        {"entityId": "getTicket", "field": "summary", "choice": "accept_new"}
    )

    assert result == {"ok": True, "remaining": 0}
    assert list_conflicts() == []
    # Bundle không bị ghi đè gì cả -- vẫn y hệt nội dung ban đầu.
    assert (dist_dir / "openapi-bundled.yaml").read_text(encoding="utf-8") == BUNDLE_TEXT


# TC-CONFLICT-05: resolve 2 lần liên tiếp cùng 1 entry -- lần 1 OK, lần 2
# 404 CONFLICT_NOT_FOUND (đã bị xoá khỏi queue từ lần 1).
def test_resolve_same_entry_twice_second_call_returns_404(conflict_env):
    _, _, report_dir = conflict_env
    _seed_conflicts(report_dir, [_conflict_entry()])

    payload = {"entityId": "getTicket", "field": "summary", "choice": "accept_new"}
    resolve_conflict(payload)

    with pytest.raises(HTTPException) as exc_info:
        resolve_conflict(payload)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "CONFLICT_NOT_FOUND"


# TC-CONFLICT-07 (DEF-02 đã fix): entityId không còn tồn tại ở bundle lẫn tầng 2
# -- resolve "keep_old" phải báo lỗi rõ ràng (409 CONFLICT_ENTITY_GONE), KHÔNG
# được trả 200 giả rồi âm thầm xoá entry mà không ghi được gì (mất dữ liệu im lặng).
def test_resolve_keep_old_for_gone_entity_returns_409_not_fake_200(conflict_env):
    _, _, report_dir = conflict_env
    _seed_conflicts(
        report_dir,
        [_conflict_entry(entityId="totallyFakeOpId999", field="summary")],
    )

    with pytest.raises(HTTPException) as exc_info:
        resolve_conflict(
            {"entityId": "totallyFakeOpId999", "field": "summary", "choice": "keep_old"}
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "CONFLICT_ENTITY_GONE"
    # Entry KHÔNG bị xoá khỏi queue khi resolve thất bại -- vẫn còn đó để thử lại.
    assert len(list_conflicts()) == 1


# TC-CONFLICT-08: file tầng 2 của operation đã bị xoá, nhưng operation vẫn còn
# trong bundle -- keep_old vẫn sửa đúng tầng 3, tầng 2 thiếu file bị bỏ qua an toàn.
def test_resolve_keep_old_skips_missing_layer2_file_safely(conflict_env):
    dist_dir, output_dir, report_dir = conflict_env
    _seed_conflicts(report_dir, [_conflict_entry()])
    # Cố tình KHÔNG tạo file tầng 2 nào (paths_dir rỗng/không tồn tại).

    result = resolve_conflict(
        {"entityId": "getTicket", "field": "summary", "choice": "keep_old"}
    )

    assert result == {"ok": True, "remaining": 0}
    bundle = _yaml.load((dist_dir / "openapi-bundled.yaml").read_text(encoding="utf-8"))
    assert bundle["paths"]["/tickets/{id}"]["get"]["summary"] == "giá trị CŨ do user sửa tay"


# TC-CONFLICT-11: 2 conflict khác entity cùng lúc, resolve 1 cái -- entry còn
# lại không bị ảnh hưởng.
def test_resolve_one_of_multiple_conflicts_leaves_other_untouched(conflict_env):
    _, _, report_dir = conflict_env
    _seed_conflicts(
        report_dir,
        [
            _conflict_entry(entityId="getTicket", field="summary"),
            _conflict_entry(entityId="createTickets", field="description", old_value="old", new_value="new"),
        ],
    )

    resolve_conflict({"entityId": "getTicket", "field": "summary", "choice": "accept_new"})

    remaining = list_conflicts()
    assert len(remaining) == 1
    assert remaining[0]["entityId"] == "createTickets"
    assert remaining[0]["field"] == "description"
