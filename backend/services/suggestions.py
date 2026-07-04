import json
from pathlib import Path

from core.errors import ErrorCode, http_error


# Đọc file import_suggestions.json, đếm số item theo approval_status — dùng
# chung cho cả 3 hàm suggestions/suggest/approve dưới đây.
def _read_suggestions(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    summary = {"pending": 0, "approved": 0, "rejected": 0}
    for item in items:
        status = item.get("approval_status", "pending")
        summary[status] = summary.get(status, 0) + 1
    return {
        "exists": True,
        "source_root": data.get("source_root"),
        "total": data.get("total", len(items)),
        "items": items,
        "summary": summary,
    }


# Trả về tên các file đang pending mà lệnh approve này nhắm tới — dùng để biết
# file nào bị resolver.py (2.pipeline) bỏ qua ngầm sau khi gọi cmd_approve_suggestions,
# vì hàm đó không trả về danh sách skip, chỉ print ra console.
def _pending_files_targeted(
    items: list[dict], mode: str, module: str | None, file: str | None
) -> set[str]:
    if mode == "file":
        return {file} if file else set()
    if mode == "all":
        return {i["file"] for i in items if i.get("approval_status") == "pending"}
    if mode == "module":
        return {
            i["file"]
            for i in items
            if i.get("approval_status") == "pending"
            and (i.get("final_module") or i.get("suggested_module") or "unknown")
            == module
        }
    return set()


# Đoán lý do 1 file bị skip khi duyệt, dựa theo đúng điều kiện skip thật trong
# cmd_approve_suggestions (2.pipeline/import_flow/resolver.py) — không có cách nào
# lấy lý do thật từ đó nên suy luận lại từ field có sẵn trên item.
def _skip_reason(item: dict, override_module: str | None) -> str:
    if item.get("status") == "failed_suggest":
        return (
            "File lỗi khi đọc nội dung (parse thất bại) — cần kiểm tra/import lại file"
        )
    if (
        not override_module
        and not item.get("final_module")
        and not item.get("suggested_module")
    ):
        return "Không xác định được module — cần nhập Override"
    return "Không rõ lý do — kiểm tra log backend"


# Logic rút từ route GET /modules/suggestions — trả về suggestions hiện có
# (không chạy gì mới), gọi lúc load trang.
def get_suggestions() -> dict:
    from run_api_import import REPORT_DIR

    suggestions_path = REPORT_DIR / "import_suggestions.json"
    if not suggestions_path.exists():
        return {
            "exists": False,
            "items": [],
            "summary": {"pending": 0, "approved": 0, "rejected": 0},
        }
    return _read_suggestions(suggestions_path)


# Logic rút từ route POST /modules/suggest — chạy lại suggest-root (CLI
# 2.pipeline) để phân loại module cho từng file nguồn.
def suggest_modules() -> dict:
    from run_api_import import cmd_suggest_root, REPORT_DIR

    try:
        cmd_suggest_root()
    except SystemExit:
        raise http_error(
            500, ErrorCode.SUGGEST_FAILED, "suggest-root thất bại — xem log backend"
        )
    suggestions_path = REPORT_DIR / "import_suggestions.json"
    if not suggestions_path.exists():
        raise http_error(
            500,
            ErrorCode.SUGGEST_REPORT_MISSING,
            "Không tạo được import_suggestions.json",
        )
    return _read_suggestions(suggestions_path)


# Logic rút từ route POST /modules/suggestions/approve — duyệt 1 hoặc nhiều
# suggestion (theo file/module/tất cả), có thể override module — trả kèm
# "skipped" để báo file nào bị bỏ qua ngầm (xem _skip_reason).
def approve_suggestions(
    mode: str,
    module: str | None,
    file: str | None,
    override_module: str | None,
) -> dict:
    from run_api_import import cmd_approve_suggestions, REPORT_DIR

    suggestions_path = REPORT_DIR / "import_suggestions.json"
    if not suggestions_path.exists():
        raise http_error(
            400,
            ErrorCode.SUGGESTIONS_NOT_FOUND,
            "Chưa có suggestions — hãy chạy suggest trước",
        )

    before = json.loads(suggestions_path.read_text(encoding="utf-8"))
    targeted_files = _pending_files_targeted(
        before.get("items", []), mode, module, file
    )

    try:
        if mode == "all":
            cmd_approve_suggestions(str(suggestions_path), approve_all=True)
        elif mode == "module":
            if not module:
                raise http_error(400, ErrorCode.MISSING_MODULE_FIELD, "Thiếu 'module'")
            cmd_approve_suggestions(
                str(suggestions_path),
                module_filter=module,
                override_module=override_module,
            )
        elif mode == "file":
            if not file:
                raise http_error(400, ErrorCode.MISSING_FILE_FIELD, "Thiếu 'file'")
            cmd_approve_suggestions(
                str(suggestions_path), file_name=file, override_module=override_module
            )
        else:
            raise http_error(
                400,
                ErrorCode.INVALID_APPROVE_MODE,
                "mode phải là 'all', 'module' hoặc 'file'",
            )
    except SystemExit:
        raise http_error(
            500,
            ErrorCode.APPROVE_FAILED,
            "approve-suggestions thất bại — xem log backend",
        )

    result = _read_suggestions(suggestions_path)

    # So sánh file nhắm tới trước/sau để phát hiện file bị resolver.py bỏ qua ngầm —
    # cmd_approve_suggestions không trả về thông tin này, chỉ print ra console.
    by_file = {item["file"]: item for item in result["items"]}
    result["skipped"] = [
        {"file": f, "reason": _skip_reason(by_file[f], override_module)}
        for f in targeted_files
        if f in by_file and by_file[f].get("approval_status") != "approved"
    ]
    return result


# Logic rút từ route POST /modules/apply — copy file đã duyệt vào đúng thư mục
# module (1.docs/source/api_contract/<module>/).
def apply_suggestions() -> dict:
    from run_api_import import cmd_apply_suggestions, REPORT_DIR

    suggestions_path = REPORT_DIR / "import_suggestions.json"
    if not suggestions_path.exists():
        raise http_error(
            400,
            ErrorCode.SUGGESTIONS_NOT_FOUND,
            "Chưa có suggestions — hãy chạy suggest trước",
        )

    try:
        cmd_apply_suggestions(str(suggestions_path), move_files=False, convert=False)
    except SystemExit:
        raise http_error(
            500, ErrorCode.APPLY_FAILED, "apply-suggestions thất bại — xem log backend"
        )

    report_path = REPORT_DIR / "import_applied_suggestions.json"
    if not report_path.exists():
        raise http_error(
            500,
            ErrorCode.APPLY_REPORT_MISSING,
            "Không tạo được report apply-suggestions",
        )
    return json.loads(report_path.read_text(encoding="utf-8"))
