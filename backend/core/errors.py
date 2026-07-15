from fastapi import HTTPException


# Bảng hằng số mã lỗi dùng chung cho cả backend — không có __init__, không ai tạo
# instance, class này chỉ đóng vai trò "không gian tên" để gọi ErrorCode.XXX
# (giống static class chứa const string của C#, hoặc enum chuỗi).
class ErrorCode:
    PIPELINE_FAILED = "PIPELINE_FAILED"
    PATH_STUB_FAILED = "PATH_STUB_FAILED"
    SUGGEST_FAILED = "SUGGEST_FAILED"
    SUGGEST_REPORT_MISSING = "SUGGEST_REPORT_MISSING"
    SUGGESTIONS_NOT_FOUND = "SUGGESTIONS_NOT_FOUND"
    MISSING_MODULE_FIELD = "MISSING_MODULE_FIELD"
    MISSING_FILE_FIELD = "MISSING_FILE_FIELD"
    INVALID_APPROVE_MODE = "INVALID_APPROVE_MODE"
    APPROVE_FAILED = "APPROVE_FAILED"
    APPLY_FAILED = "APPLY_FAILED"
    APPLY_REPORT_MISSING = "APPLY_REPORT_MISSING"
    REGISTRY_NOT_FOUND = "REGISTRY_NOT_FOUND"
    MODULE_NOT_FOUND = "MODULE_NOT_FOUND"
    MODULE_ACTIVATE_FAILED = "MODULE_ACTIVATE_FAILED"
    MODULE_DEACTIVATE_FAILED = "MODULE_DEACTIVATE_FAILED"
    MODULE_NOT_ACTIVE = "MODULE_NOT_ACTIVE"
    NO_ACTIVE_MODULE = "NO_ACTIVE_MODULE"
    IMPORT_JOB_NOT_FOUND = "IMPORT_JOB_NOT_FOUND"
    HTML_NOT_FOUND = "HTML_NOT_FOUND"
    BUNDLE_NOT_FOUND = "BUNDLE_NOT_FOUND"
    BUNDLE_READ_FAILED = "BUNDLE_READ_FAILED"
    BUNDLE_INVALID_YAML = "BUNDLE_INVALID_YAML"
    EMPTY_BUNDLE = "EMPTY_BUNDLE"
    AI_CALL_FAILED = "AI_CALL_FAILED"
    AI_INVALID_YAML = "AI_INVALID_YAML"
    INVALID_FILENAME = "INVALID_FILENAME"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_CONFLICT_RESOLVE = "INVALID_CONFLICT_RESOLVE"
    CONFLICT_NOT_FOUND = "CONFLICT_NOT_FOUND"
    CONFLICT_ENTITY_GONE = "CONFLICT_ENTITY_GONE"
    ERROR_REPORT_NOT_FOUND = "ERROR_REPORT_NOT_FOUND"
    INVALID_ERROR_RESOLVE = "INVALID_ERROR_RESOLVE"



# Tạo và TRẢ VỀ (không tự raise) 1 HTTPException theo format {code, message} —
# đúng khớp với phần frontend đọc lỗi (api.ts/parseErrorDetail). Người gọi luôn
# phải viết "raise http_error(...)", hàm này không tự throw.
# Type hint (status_code: int, ...) chỉ là gợi ý cho người đọc/IDE — Python không
# ép kiểu lúc chạy, gọi sai kiểu vẫn không bị chặn ngay tại đây.
def http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail={"code": code, "message": message}
    )
