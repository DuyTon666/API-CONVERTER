from fastapi import APIRouter, Body

from services import error_codes

router = APIRouter()


@router.get("/errors/{module}")
def get_error_entries(module: str):
    """Trả về report review mã lỗi (entries + summary) của 1 module."""
    return error_codes.list_error_entries(module)


@router.post("/errors/{module}/resolve")
def resolve_error_entry(
    module: str,
    code: str = Body(...),
    decision: str = Body(...),
    approved_by: str = Body(...),
    new_code: str | None = Body(None),
    source_file: str | None = Body(None),
):
    """Ghi quyết định (keep_existing/reassign/approve_new/repair_existing) cho 1 mã lỗi."""
    return error_codes.resolve_error_entry(
        module, code, decision, approved_by, new_code, source_file
    )


@router.post("/errors/{module}/apply")
def apply_error_entries(module: str):
    """Đẩy toàn bộ entry đã resolve lên 4.config/errors/ chính thức."""
    return error_codes.apply_error_entries(module)
