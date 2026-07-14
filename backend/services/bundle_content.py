from api_utils.yaml_io import load_yaml_cached, _LOADER
from core.config import DIST_DIR
from core.errors import ErrorCode, http_error
from services.bundle_sync import (
    diff_bundle,
    sync_operation_fields,
    sync_schema_fields,
    _index_schema_files,
)


# Đọc nội dung của file bundle
def read_bundle_content() -> str:
    bundle_path = DIST_DIR / "openapi-bundled.yaml" # Lấy đường dẫn của file bundle
    # Nếu đường dẫn file bundle không tồn tại
    if not bundle_path.exists(): 
        raise http_error(
            404,
            ErrorCode.BUNDLE_NOT_FOUND,
            "Bundle chưa được tạo, hãy build tài liệu trước",
        )
    # Nếu đường dẫn  file bundle tồn tại
    try:
        return bundle_path.read_text(encoding="utf-8")
    except Exception as e:
        raise http_error(
            500, ErrorCode.BUNDLE_READ_FAILED, f"Không thể đọc file bundle: {e}"
        )


# Logic rút từ route PUT /docs/bundle-content — lưu nội dung bundle sau khi user
# chỉnh sửa (plain text). So sánh với bundle cũ để đồng bộ field thay đổi xuống
# tầng 2 (5.openapi/), tránh mất khi build lại.
def save_bundle_content(new_content: str) -> dict:
    import yaml as _yaml

    bundle_path = DIST_DIR / "openapi-bundled.yaml" # Xác định vị trí bundle
    if not bundle_path.exists():
        raise http_error(404, ErrorCode.BUNDLE_NOT_FOUND, "Bundle chưa được tạo, hãy build tài liệu trước")

    old_bundle = load_yaml_cached(bundle_path)
    try:
        new_bundle = _yaml.load(new_content, Loader=_LOADER) or {}
    except Exception as e:
        raise http_error(400, ErrorCode.BUNDLE_INVALID_YAML, f"YAML không hợp lệ: {e}")
    if not isinstance(new_bundle, dict): # Kiểm tra xem new_bundle phải là dict không
        raise http_error(400, ErrorCode.BUNDLE_INVALID_YAML, "Cấu trúc bundle không hợp lệ")

    changes = diff_bundle(old_bundle, new_bundle) # So sánh 2 bundle
    sync_operation_fields(new_bundle, changes) # Đồng bộ Operation
    sync_schema_fields(new_bundle, changes, _index_schema_files()) # Đồng bộ Schema

    bundle_path.write_text(new_content, encoding="utf-8") # Ghi bundle
    return {"ok": True}
