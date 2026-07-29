import datetime as datetime_module

import yaml
import pytest
from fastapi import HTTPException

import services.import_jobs as import_jobs_module
from services.import_jobs import start_import, _backup_layer2


def _write_registry(config_dir, modules: dict):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "module_registry.yaml").write_text(
        yaml.safe_dump({"modules": modules}), encoding="utf-8"
    )


# CONFIG_DIR được import module-level trong import_jobs.py -> patch đúng tên đó.
# executor.submit bị thay bằng no-op để KHÔNG chạy _run_import_job thật (hàm đó
# gọi thẳng pipeline_API.run_batch — thuộc 2.pipeline, ngoài phạm vi test này,
# và sẽ đụng vào dữ liệu/tài liệu nguồn thật nếu chạy thật trong background thread).
@pytest.fixture
def fake_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(import_jobs_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(import_jobs_module.executor, "submit", lambda *a, **k: None)
    import_jobs_module.import_jobs.clear()
    return tmp_path


# TC-REG-01: module vừa deactivate (status "deprecated") -> import bị chặn
# 400 MODULE_NOT_ACTIVE, không tạo job.
def test_start_import_blocks_deprecated_module(fake_registry):
    _write_registry(fake_registry, {"ticket": {"status": "deprecated"}})

    with pytest.raises(HTTPException) as exc_info:
        start_import(module="ticket")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "MODULE_NOT_ACTIVE"
    assert import_jobs_module.import_jobs == {}


# TC-REG-02: module đã reactivate (status "active") -> import không bị chặn,
# tạo job bình thường (job_id trả về, job được lưu vào import_jobs).
def test_start_import_allows_active_module(fake_registry):
    _write_registry(fake_registry, {"ticket": {"status": "active"}})

    result = start_import(module="ticket")

    assert "job_id" in result
    assert result["job_id"] in import_jobs_module.import_jobs


def test_start_import_404_when_module_not_in_registry(fake_registry):
    _write_registry(fake_registry, {"ticket": {"status": "active"}})

    with pytest.raises(HTTPException) as exc_info:
        start_import(module="khong_ton_tai")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "MODULE_NOT_FOUND"


def test_start_import_404_when_registry_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(import_jobs_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        start_import(module="ticket")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "REGISTRY_NOT_FOUND"


# Không truyền module (import "all") nhưng registry không có module nào active.
def test_start_import_400_when_no_active_module_and_no_module_given(fake_registry):
    _write_registry(fake_registry, {"ticket": {"status": "draft"}})

    with pytest.raises(HTTPException) as exc_info:
        start_import(module=None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "NO_ACTIVE_MODULE"


# DEF-01: trước fix, backup_dir chỉ dựa timestamp giây -> gọi 2 lần liên tiếp
# trong cùng 1 giây (mock datetime.now() trả cùng 1 giá trị cả 2 lần, mô phỏng
# đúng tình huống 2 import rất sát nhau) sẽ tạo trùng tên -> shutil.copytree()
# lần 2 ném FileExistsError, backup lần 2 mất âm thầm. Sau fix (thêm UUID vào
# tên), 2 lần gọi liên tiếp phải ra 2 backup_dir khác nhau, cả 2 đều còn nguyên.
def test_backup_layer2_does_not_collide_when_called_twice_in_same_second(
    tmp_path, monkeypatch
):
    class _FixedDatetime(datetime_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime_module.datetime(2026, 1, 1, 12, 0, 0)

    monkeypatch.setattr(import_jobs_module.datetime, "datetime", _FixedDatetime)

    paths_dir = tmp_path / "source" / "paths"
    paths_dir.mkdir(parents=True)
    (paths_dir / "get_ticket.yaml").write_text("get: {}", encoding="utf-8")
    schemas_dir = tmp_path / "source" / "schemas"  # không tồn tại, không backup
    base_backup_dir = tmp_path / "backups"

    first = _backup_layer2(base_backup_dir, "ticket", paths_dir, schemas_dir)
    second = _backup_layer2(base_backup_dir, "ticket", paths_dir, schemas_dir)

    assert first != second
    assert (first / "paths" / "get_ticket.yaml").exists()
    assert (second / "paths" / "get_ticket.yaml").exists()


def test_backup_layer2_returns_none_when_nothing_to_backup(tmp_path):
    result = _backup_layer2(
        tmp_path / "backups", "ticket", tmp_path / "no_paths", tmp_path / "no_schemas"
    )
    assert result is None
