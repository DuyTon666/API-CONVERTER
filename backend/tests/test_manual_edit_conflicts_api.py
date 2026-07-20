from fastapi.testclient import TestClient

from main import app
import import_flow.config as import_flow_config

# TestClient bọc quanh app FastAPI thật (main.app) -> gọi được y hệt HTTP request
# (client.get/post) mà không cần "uvicorn main:app" chạy thật ở port nào cả.
client = TestClient(app)


# REPORT_DIR được import cục bộ bên trong từng hàm của manual_edit_conflicts.py
# (import_flow.config import REPORT_DIR) -> patch thẳng ở import_flow.config là
# đủ, vì lần import kế tiếp (mỗi lần hàm chạy) sẽ đọc lại giá trị mới này.
def _use_tmp_report_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(import_flow_config, "REPORT_DIR", tmp_path)


# TC-CONFLICT-01: chưa có file manual_edit_conflicts.json -> queue rỗng (card
# tương ứng bên frontend sẽ không render).
def test_get_conflicts_returns_empty_list_when_no_file(tmp_path, monkeypatch):
    _use_tmp_report_dir(tmp_path, monkeypatch)
    response = client.get("/modules/manual-edit-conflicts")
    assert response.status_code == 200
    assert response.json() == []


# TC-CONFLICT-06: thiếu "field" trong payload -> 400 INVALID_CONFLICT_RESOLVE.
def test_resolve_conflict_rejects_payload_missing_field(tmp_path, monkeypatch):
    _use_tmp_report_dir(tmp_path, monkeypatch)
    response = client.post(
        "/modules/manual-edit-conflicts/resolve",
        json={"entityId": "getTicket", "choice": "keep_old"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_CONFLICT_RESOLVE"


# TC-CONFLICT-06: "choice" không phải keep_old/accept_new -> 400 INVALID_CONFLICT_RESOLVE.
def test_resolve_conflict_rejects_invalid_choice_value(tmp_path, monkeypatch):
    _use_tmp_report_dir(tmp_path, monkeypatch)
    response = client.post(
        "/modules/manual-edit-conflicts/resolve",
        json={"entityId": "getTicket", "field": "summary", "choice": "yolo"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_CONFLICT_RESOLVE"


# Payload hợp lệ nhưng chưa có conflict nào đang chờ (file chưa tồn tại)
# -> 404 CONFLICT_NOT_FOUND, không phải 400 (khác lỗi validate ở 2 test trên).
def test_resolve_conflict_returns_404_when_nothing_pending(tmp_path, monkeypatch):
    _use_tmp_report_dir(tmp_path, monkeypatch)
    response = client.post(
        "/modules/manual-edit-conflicts/resolve",
        json={"entityId": "getTicket", "field": "summary", "choice": "keep_old"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "CONFLICT_NOT_FOUND"
