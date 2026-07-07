from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse, PlainTextResponse

from services import ai_fix, bundle_content, docs_build, operations, schema_fields

router = APIRouter()


@router.post("/docs/build")
def build_docs():
    """Bundle + lint (Spectral/Redocly) + build Swagger UI HTML từ trạng thái 5.openapi/ hiện tại."""
    return docs_build.build_docs()


@router.get("/docs/status")
def docs_status():
    """Trạng thái tài liệu hiện tại: bundle và HTML đã tồn tại trên đĩa chưa."""
    return docs_build.get_status()


@router.get("/docs/download-html")
def download_docs_html():
    """Trả file api-docs.html (Swagger UI đã build sẵn) để người dùng tải về."""
    html_path = docs_build.get_html_path_or_404()
    return FileResponse(
        path=str(html_path),
        media_type="text/html",
        filename="api-docs.html",
    )


@router.get("/docs/bundle-content")
def get_docs_bundle_content():
    """Trả về nội dung file bundle dưới dạng plain text."""
    content = bundle_content.read_bundle_content()
    return PlainTextResponse(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@router.put("/docs/bundle-content")
async def save_docs_bundle_content(request: Request):
    """Lưu nội dung bundle sau khi user chỉnh sửa (plain text)."""
    new_content = (await request.body()).decode("utf-8")
    return bundle_content.save_bundle_content(new_content)


@router.post("/docs/relint")
def relint_docs():
    """Chạy lại Spectral + Redocly + build HTML từ bundle hiện tại (không bundle lại)."""
    return docs_build.relint_docs()


@router.post("/docs/bundle/ai-fix")
def ai_fix_bundle(payload: dict = Body(...)):
    """Dùng Claude để sửa YAML bundle theo lỗi Spectral/Redocly hiện có."""
    return ai_fix.fix_bundle(payload)


@router.get("/docs/operations")
def get_operations():
    """Trả về danh sách operations từ bundle để hiển thị trong form editor."""
    return operations.list_operations()


@router.patch("/docs/operations")
def update_operations(updates: list = Body(...)):
    """Cập nhật summary/description của một hoặc nhiều operations."""
    return operations.update_operations(updates)


@router.post("/docs/operations/ai-suggest")
def ai_suggest_operation(payload: dict = Body(...)):
    """Gợi ý bằng Claude cho các field đang trống (summary/description/parameter & response description)."""
    return operations.ai_suggest_operation(payload)

@router.get("/docs/schema-fields")
def get_schema_fields():
    """Trả danh sách các schema field theo từng operation (request/reponse data schema)
    để hiển thị trong section 'Trường dữ liệu' của Form Editor."""
    return schema_fields.list_operation_data_schemas()

@router.patch("/docs/schema-fields")
def update_schema_fields(updates: list = Body(...)):
    """Cập nhật description của field bên trong components/schemas."""
    return schema_fields.update_schema_fields(updates)