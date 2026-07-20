from pathlib import Path

import pytest
from fastapi import HTTPException

import services.upload as upload_module
from services.upload import save_uploaded_files


# monkeypatch.setattr đánh tráo SOURCE_DIR bên trong module services.upload
# (không phải core.config) -> ghi file test vào tmp_path, không đụng project thật.
def _use_tmp_source_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_module, "SOURCE_DIR", tmp_path)


# TC-SEC-06 (control case): file hợp lệ phải upload thành công bình thường.
def test_save_uploaded_files_writes_valid_file(tmp_path, monkeypatch):
    _use_tmp_source_dir(tmp_path, monkeypatch)
    result = save_uploaded_files([("valid.docx", b"noi dung gia")])
    assert result == {"saved": ["valid.docx"], "total": 1}
    assert (tmp_path / "valid.docx").read_bytes() == b"noi dung gia"


# TC-SEC-04: sai extension phải bị chặn 400 UNSUPPORTED_FILE_TYPE.
def test_save_uploaded_files_rejects_unsupported_extension(tmp_path, monkeypatch):
    _use_tmp_source_dir(tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as exc_info:
        save_uploaded_files([("malware.exe", b"xx")])
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "UNSUPPORTED_FILE_TYPE"


# TC-SEC-01: filename path traversal tương đối phải bị "làm phẳng" về basename,
# không bao giờ ghi ra ngoài SOURCE_DIR.
def test_save_uploaded_files_flattens_relative_path_traversal_filename(tmp_path, monkeypatch):
    _use_tmp_source_dir(tmp_path, monkeypatch)
    result = save_uploaded_files([("../../evil.docx", b"xx")])
    assert result == {"saved": ["evil.docx"], "total": 1}
    assert (tmp_path / "evil.docx").exists()
    assert not (tmp_path.parent / "evil.docx").exists()


# TC-SEC-02: filename path traversal tuyệt đối (/etc/evil.pdf) cũng phải bị làm
# phẳng về basename, ghi an toàn trong SOURCE_DIR, không ghi ra /etc thật.
def test_save_uploaded_files_flattens_absolute_path_traversal_filename(tmp_path, monkeypatch):
    _use_tmp_source_dir(tmp_path, monkeypatch)
    result = save_uploaded_files([("/etc/evil.pdf", b"xx")])
    assert result == {"saved": ["evil.pdf"], "total": 1}
    assert (tmp_path / "evil.pdf").exists()
    assert not Path("/etc/evil.pdf").exists()


# TC-SEC-03: filename literally "." hoặc ".." phải bị chặn 400 INVALID_FILENAME.
def test_save_uploaded_files_rejects_dot_and_dotdot_filename(tmp_path, monkeypatch):
    _use_tmp_source_dir(tmp_path, monkeypatch)
    for bad_name in (".", ".."):
        with pytest.raises(HTTPException) as exc_info:
            save_uploaded_files([(bad_name, b"xx")])
        assert exc_info.value.detail["code"] == "INVALID_FILENAME"


# TC-SEC-05: file vượt size cap (20MB) phải bị chặn 400 FILE_TOO_LARGE, không
# được ghi ra đĩa trước khi validate.
def test_save_uploaded_files_rejects_file_too_large(tmp_path, monkeypatch):
    _use_tmp_source_dir(tmp_path, monkeypatch)
    big_bytes = b"0" * (21 * 1024 * 1024)
    with pytest.raises(HTTPException) as exc_info:
        save_uploaded_files([("big.pdf", big_bytes)])
    assert exc_info.value.detail["code"] == "FILE_TOO_LARGE"
    assert not (tmp_path / "big.pdf").exists()
