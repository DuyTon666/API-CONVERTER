import yaml
import pytest
from fastapi import HTTPException
from ruamel.yaml import YAML

import services.bundle_content as bundle_content_module
import services.bundle_sync as bundle_sync_module
from services.bundle_content import save_bundle_content

_yaml = YAML()

# Field "required" của tham số user_id -- nằm NGOÀI 4 field cố định của Form
# Editor (summary/description/parameter desc/response desc), đúng tinh thần
# TC-YAML-01 ("sửa field bất kỳ qua field-path generic").
INITIAL_BUNDLE = """paths:
  /tickets/{id}:
    patch:
      operationId: updateClose
      summary: Đóng ticket
      parameters:
        - name: user_id
          in: query
          required: true
"""

NEW_BUNDLE_REQUIRED_FALSE = """paths:
  /tickets/{id}:
    patch:
      operationId: updateClose
      summary: Đóng ticket
      parameters:
        - name: user_id
          in: query
          required: false
"""

FRAGMENT_INITIAL = {
    "patch": {
        "operationId": "updateClose",
        "summary": "Đóng ticket",
        "parameters": [{"name": "user_id", "in": "query", "required": True}],
    }
}


@pytest.fixture
def bundle_setup(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    output_dir = tmp_path / "5.openapi"
    dist_dir.mkdir()
    (dist_dir / "openapi-bundled.yaml").write_text(INITIAL_BUNDLE, encoding="utf-8")

    paths_dir = output_dir / "paths"
    paths_dir.mkdir(parents=True)
    with (paths_dir / "update_close.yaml").open("w", encoding="utf-8") as f:
        _yaml.dump(FRAGMENT_INITIAL, f)

    monkeypatch.setattr(bundle_content_module, "DIST_DIR", dist_dir)
    monkeypatch.setattr(bundle_sync_module, "OUTPUT_DIR", output_dir)
    return dist_dir, paths_dir


# TC-YAML-01: sửa field "required" (ngoài 4 field cố định của Form Editor) qua
# tab YAML thô -- tầng 2 nhận đúng giá trị mới + marker field-path đúng;
# tầng 3 ghi verbatim giữ NGUYÊN định dạng người dùng gõ (không bị reformat).
def test_save_bundle_content_syncs_generic_field_to_layer2(bundle_setup):
    dist_dir, paths_dir = bundle_setup

    save_bundle_content(NEW_BUNDLE_REQUIRED_FALSE)

    # Tầng 3: ghi verbatim, đúng y hệt chuỗi truyền vào, không bị serialize lại.
    assert (dist_dir / "openapi-bundled.yaml").read_text(encoding="utf-8") == NEW_BUNDLE_REQUIRED_FALSE

    # Tầng 2: field "required" cập nhật + marker field-path generic đúng.
    fragment = _yaml.load((paths_dir / "update_close.yaml").read_text(encoding="utf-8"))
    assert fragment["patch"]["parameters"][0]["required"] is False
    assert fragment["patch"]["x-manual-edit-fields"] == ["parameters[name=user_id].required"]


# TC-YAML-03: paste YAML lỗi cú pháp, bấm Lưu -> 400 BUNDLE_INVALID_YAML,
# checksum (nội dung) cả 2 tầng không đổi.
def test_save_bundle_content_rejects_invalid_yaml(bundle_setup):
    dist_dir, paths_dir = bundle_setup
    broken_yaml = "paths:\n  /tickets/{id}:\n    patch: [unclosed bracket {\n"

    with pytest.raises(HTTPException) as exc_info:
        save_bundle_content(broken_yaml)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "BUNDLE_INVALID_YAML"
    # Nội dung tầng 3 không đổi (vẫn là bundle gốc trước khi Lưu lỗi).
    assert (dist_dir / "openapi-bundled.yaml").read_text(encoding="utf-8") == INITIAL_BUNDLE
    fragment = _yaml.load((paths_dir / "update_close.yaml").read_text(encoding="utf-8"))
    assert fragment["patch"]["parameters"][0]["required"] is True


# TC-YAML-04 (DEF-03 đã fix): bundle CŨ (đang trên đĩa) đã có marker "summary"
# từ 1 lần sửa trước, còn nội dung frontend vừa gửi lên (new_content) là bản cũ
# hơn, KHÔNG có key x-manual-edit-fields -- diff_bundle phải bỏ qua key này
# (không coi marker "biến mất" là 1 field bị sửa), nếu không sẽ tự nhét chữ
# "x-manual-edit-fields" vào làm entry của chính marker (bug DEF-03).
# Lưu ý: dist_bundle được ghi verbatim (đúng chuỗi new_content), nên phải xem
# marker ĐÃ ĐỒNG BỘ ở tầng 2 (file fragment) mới thấy tác dụng của sync, không
# xem ở tầng 3.
def test_save_bundle_content_does_not_self_reference_marker(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    output_dir = tmp_path / "5.openapi"
    dist_dir.mkdir()

    bundle_with_marker = (
        "paths:\n"
        "  /tickets/{id}:\n"
        "    patch:\n"
        "      operationId: updateClose\n"
        "      summary: Đóng ticket\n"
        "      x-manual-edit-fields: [summary]\n"
    )
    (dist_dir / "openapi-bundled.yaml").write_text(bundle_with_marker, encoding="utf-8")

    paths_dir = output_dir / "paths"
    paths_dir.mkdir(parents=True)
    with (paths_dir / "update_close.yaml").open("w", encoding="utf-8") as f:
        _yaml.dump({"patch": {"operationId": "updateClose", "summary": "Đóng ticket"}}, f)

    monkeypatch.setattr(bundle_content_module, "DIST_DIR", dist_dir)
    monkeypatch.setattr(bundle_sync_module, "OUTPUT_DIR", output_dir)

    new_content = (
        "paths:\n"
        "  /tickets/{id}:\n"
        "    patch:\n"
        "      operationId: updateClose\n"
        "      summary: Đóng ticket\n"
        "      description: Mô tả mới thêm\n"
    )

    save_bundle_content(new_content)  # không được raise

    fragment = _yaml.load((paths_dir / "update_close.yaml").read_text(encoding="utf-8"))
    marker = fragment["patch"]["x-manual-edit-fields"]
    assert "x-manual-edit-fields" not in marker
    assert set(marker) == {"description"}
