from pathlib import Path

from core.config import SOURCE_DIR
from core.errors import ErrorCode, http_error

MAX_UPLOAD_SIZE = 20 * 1024 * 1024


# Logic rút từ route POST /source/upload — validate + ghi file vào
# 1.docs/source/api_contract/. Nhận (raw_filename, bytes) — phần đọc bytes từ
# UploadFile (async) vẫn ở router vì đó là việc thuộc framework/request layer,
# còn việc sanitize tên file là validate nên ở đây.
def save_uploaded_files(items: list[tuple[str, bytes]]) -> dict:
    from import_flow.config import load_import_config, supported_extensions

    cfg = load_import_config()
    allowed_ext = supported_extensions(cfg)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    resolved_source_dir = SOURCE_DIR.resolve()
    saved = []
    for raw_filename, file_bytes in items:
        safe_name = Path(raw_filename).name
        if not safe_name or safe_name in (".", ".."):
            raise http_error(400, ErrorCode.INVALID_FILENAME, "Tên file không hợp lệ")

        if Path(safe_name).suffix.lower() not in allowed_ext:
            raise http_error(
                400,
                ErrorCode.UNSUPPORTED_FILE_TYPE,
                f"Định dạng file không được hổ trợ: {safe_name}",
            )

        dest = (SOURCE_DIR / safe_name).resolve()
        if not dest.is_relative_to(resolved_source_dir):
            raise http_error(400, ErrorCode.INVALID_FILENAME, "Tên file không hợp lệ")

        if len(file_bytes) > MAX_UPLOAD_SIZE:
            raise http_error(
                400,
                ErrorCode.FILE_TOO_LARGE,
                f"File quá lớn (tối đa {MAX_UPLOAD_SIZE // (1024 * 1024)} MB): {safe_name}",
            )

        dest.write_bytes(file_bytes)
        saved.append(safe_name)
    return {"saved": saved, "total": len(saved)}
