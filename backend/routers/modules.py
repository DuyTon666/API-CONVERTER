from fastapi import APIRouter, Body, File, UploadFile
from fastapi.responses import StreamingResponse

from services import import_jobs, manual_edit_conflicts, module_registry, suggestions, upload

router = APIRouter()


@router.get("/modules/scan")
def scan_modules():
    """Quét 1.docs/source/ xem có module/file nào, gom theo phần mở rộng file."""
    return module_registry.scan_modules()


@router.get("/modules")
def list_modules():
    """Đọc 4.config/module_registry.yaml, đếm số module theo status."""
    return module_registry.list_modules()


@router.post("/source/upload")
async def upload_source_files(files: list[UploadFile] = File(...)):
    """Nhận file upload từ ImportCard, lưu thẳng vào 1.docs/source/api_contract/."""
    items = [(f.filename, await f.read()) for f in files]
    return upload.save_uploaded_files(items)


@router.get("/modules/suggestions")
def get_suggestions():
    """Trả về suggestions hiện có (không chạy gì mới) — gọi lúc load trang."""
    return suggestions.get_suggestions()


@router.post("/modules/suggest")
def suggest_modules():
    """Chạy lại suggest-root (CLI 2.pipeline) để phân loại module cho từng file nguồn."""
    return suggestions.suggest_modules()


@router.post("/modules/suggestions/approve")
def approve_suggestions(
    mode: str = Body(...),
    module: str | None = Body(None),
    file: str | None = Body(None),
    override_module: str | None = Body(None),
):
    """Duyệt 1 hoặc nhiều suggestion (theo file/module/tất cả), có thể override module."""
    return suggestions.approve_suggestions(mode, module, file, override_module)


@router.post("/modules/apply")
def apply_suggestions():
    """Copy file đã duyệt vào đúng thư mục module (1.docs/source/api_contract/<module>/)."""
    return suggestions.apply_suggestions()


@router.post("/modules/{module}/activate")
def activate_module(module: str):
    """Chuyển module sang status "active" (hoặc "reactivate" nếu đang deprecated)."""
    return module_registry.activate_module(module)


@router.post("/modules/{module}/deactivate")
def deactivate_module(module: str):
    """Chuyển module sang status "deprecated" — không import được nữa tới khi activate lại."""
    return module_registry.deactivate_module(module)


@router.post("/modules/import")
def start_import(module: str | None = None):
    """Kiểm tra module hợp lệ/active, tạo job mới chạy ở background, trả job_id ngay."""
    return import_jobs.start_import(module)


@router.get("/modules/import/{job_id}/stream")
def stream_import_job(job_id: str):
    """Mở kết nối SSE, gửi tiến trình import từng module tới khi job xong."""
    job = import_jobs.get_job_or_404(job_id)
    return StreamingResponse(import_jobs.stream_events(job), media_type="text/event-stream")


@router.get("/modules/manual-edit-conflicts")
def get_manual_edit_conflicts():
    """Trả về danh sách xung đột sửa tay đang chờ duyệt."""
    return manual_edit_conflicts.list_conflicts()


@router.post("/modules/manual-edit-conflicts/resolve")
def resolve_manual_edit_conflict(payload: dict = Body(...)):
    """Duyệt 1 xung đột sửa tay ("keep_old" hoặc "accept_new")."""
    return manual_edit_conflicts.resolve_conflict(payload)
