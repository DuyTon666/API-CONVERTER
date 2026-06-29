import json
import subprocess
import ai_fix
from pathlib import Path

from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse, PlainTextResponse

from config import DIST_DIR, OUTPUT_DIR
from errors import ErrorCode, http_error
from bundle_sync import (
    _HTTP_METHODS,
    _is_inline,
    _apply_operation_update,
    _index_operation_files,
    _index_schema_files,
    diff_bundle,
    sync_operation_fields,
    sync_schema_fields

)


router = APIRouter()


# Parse stdout của lệnh "redocly lint --format json" thành list issue —
# tự xử lý 2 format khác nhau tuỳ phiên bản Redocly CLI (v2 mới và bản cũ).
def _parse_redocly_output(result: subprocess.CompletedProcess) -> list:
    raw = result.stdout.strip() or result.stderr.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        # Redocly v2: single object {totals, version, problems: [...]}
        if isinstance(data, dict) and "problems" in data:
            return data["problems"]
        # Older format: [{filePath, problems: [...]}, ...]
        if isinstance(data, list):
            issues = []
            for entry in data:
                if isinstance(entry, dict) and "problems" in entry:
                    issues.extend(entry["problems"])
                elif isinstance(entry, dict) and "ruleId" in entry:
                    issues.append(entry)
            return issues
    except Exception:
        pass
    return []


# Gắn line/column thật vào từng redocly issue, dựa vào kết quả lint dạng checkstyle
# (chạy song song, vì bản JSON của Redocly không có line/column, chỉ có JSON Pointer).
def _enrich_redocly_with_line_col(
    redocly_issues: list[dict], checkstyle_xml: str
) -> list[dict]:
    checkstyle_issues = ai_fix._parse_checkstyle_output(checkstyle_xml)

    # Khớp theo cặp (ruleId, message) — dùng danh sách "còn lại" để khớp đúng
    # theo thứ tự xuất hiện khi có nhiều issue trùng cả ruleId và message.
    remaining = list(checkstyle_issues)
    for issue in redocly_issues:
        rule_id = issue.get("ruleId")
        message = issue.get("message")
        for i, cs in enumerate(remaining):
            if cs["ruleId"] == rule_id and cs["message"] == message:
                issue["line"] = (
                    cs["line"] - 1
                )  # đổi về 0-indexed, đồng nhất với Spectral
                issue["column"] = cs["column"] - 1
                remaining.pop(i)
                break

    return redocly_issues


def _bundle_lint_build_docs(project_root: Path, do_bundle: bool = True) -> dict:
    """Chạy bundle (tuỳ chọn) → lint Spectral/Redocly → build Swagger UI HTML."""
    if do_bundle:
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        bundle_result = subprocess.run(
            ["npm", "run", "bundle:api"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        if bundle_result.returncode != 0:
            raise http_error(500, ErrorCode.PIPELINE_FAILED, bundle_result.stderr)

    spectral_result = subprocess.run(
        ["npm", "run", "--silent", "lint:spectral"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    try:
        spectral_issues = (
            json.loads(spectral_result.stdout) if spectral_result.stdout.strip() else []
        )
        if not isinstance(spectral_issues, list):
            spectral_issues = []
    except Exception:
        spectral_issues = []

    redocly_result = subprocess.run(
        ["npm", "run", "--silent", "validate:api"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    redocly_issues = _parse_redocly_output(redocly_result)

    # Chạy thêm bản --format checkstyle (gọi npx trực tiếp vì package.json không có
    # script riêng cho format này) chỉ để lấy line/column thật, gắn vào redocly_issues.
    checkstyle_result = subprocess.run(
        [
            "npx",
            "@redocly/cli",
            "lint",
            "dist/openapi-bundled.yaml",
            "--config",
            "redocly.yaml",
            "--format",
            "checkstyle",
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    redocly_issues = _enrich_redocly_with_line_col(
        redocly_issues, checkstyle_result.stdout
    )

    html_path = project_root / "public" / "api-docs.html"
    (project_root / "public").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["npm", "run", "build:docs"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )

    return {
        "bundle_ready": True,
        "html_ready": html_path.exists(),
        "spectral": spectral_issues,
        "redocly": redocly_issues,
    }


@router.post("/docs/build")
def build_docs():
    """Bundle + lint (Spectral/Redocly) + build Swagger UI HTML từ trạng thái 5.openapi/ hiện tại."""
    project_root = Path(__file__).parent.parent.parent
    return _bundle_lint_build_docs(project_root, do_bundle=True)


@router.get("/docs/status")
def docs_status():
    """Trạng thái tài liệu hiện tại: bundle và HTML đã tồn tại trên đĩa chưa."""
    project_root = Path(__file__).parent.parent.parent
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    html_path = project_root / "public" / "api-docs.html"
    return {"bundle_ready": bundle_path.exists(), "html_ready": html_path.exists()}


@router.get("/docs/download-html")
def download_docs_html():
    """Trả file api-docs.html (Swagger UI đã build sẵn) để người dùng tải về."""
    project_root = Path(__file__).parent.parent.parent
    html_path = project_root / "public" / "api-docs.html"
    if not html_path.exists():
        raise http_error(
            404,
            ErrorCode.HTML_NOT_FOUND,
            "HTML chưa được build, hãy build tài liệu trước",
        )
    return FileResponse(
        path=str(html_path),
        media_type="text/html",
        filename="api-docs.html",
    )


@router.get("/docs/bundle-content")
def get_docs_bundle_content():
    """Trả về nội dung file bundle dưới dạng plain text."""
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise http_error(
            404,
            ErrorCode.BUNDLE_NOT_FOUND,
            "Bundle chưa được tạo, hãy build tài liệu trước",
        )
    try:
        content = bundle_path.read_text(encoding="utf-8")
    except Exception as e:
        raise http_error(
            500, ErrorCode.BUNDLE_READ_FAILED, f"Không thể đọc file bundle: {e}"
        )
    return PlainTextResponse(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@router.put("/docs/bundle-content")
async def save_docs_bundle_content(request: Request):
    """Lưu nội dung bundle sau khi user chỉnh sửa (plain text). So sánh với bundle cũ
    để đồng bộ field thay đổi xuống tầng 2 (5.openapi/), tránh mất khi build lại."""
    import yaml as _yaml

    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise http_error(
            404,
            ErrorCode.BUNDLE_NOT_FOUND,
            "Bundle chưa được tạo, hãy build tài liệu trước",
        )

    old_content = bundle_path.read_text(encoding="utf-8")
    new_content = (await request.body()).decode("utf-8")
    old_bundle = _yaml.safe_load(old_content) or {}
    try:
        new_bundle = _yaml.safe_load(new_content) or {}
    except Exception as e:
        raise http_error(400, ErrorCode.BUNDLE_INVALID_YAML, f"YAML không hợp lệ: {e}")
    if not isinstance(new_bundle, dict):
        raise http_error(400, ErrorCode.BUNDLE_INVALID_YAML, "Cấu trúc bundle không hợp lệ")

    changes = diff_bundle(old_bundle, new_bundle)
    sync_operation_fields(new_bundle, changes, _index_operation_files())
    sync_schema_fields(new_bundle, changes, _index_schema_files())

    bundle_path.write_text(new_content, encoding="utf-8")
    return {"ok": True}



@router.post("/docs/relint")
def relint_docs():
    """Chạy lại Spectral + Redocly + build HTML từ bundle hiện tại (không bundle lại)."""
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise http_error(
            404,
            ErrorCode.BUNDLE_NOT_FOUND,
            "Bundle chưa được tạo, hãy build tài liệu trước",
        )

    project_root = Path(__file__).parent.parent.parent
    return _bundle_lint_build_docs(project_root, do_bundle=False)


@router.post("/docs/bundle/ai-fix")
def ai_fix_bundle(payload: dict = Body(...)):
    """Dùng Claude để sửa YAML bundle theo lỗi Spectral/Redocly hiện có.

    Chỉ sửa ĐÚNG những vị trí bị lỗi (không động tới phần còn lại của file) và
    KHÔNG ghi xuống đĩa — trả về danh sách patch để frontend hiển thị diff kiểu
    conflict, người dùng tự chọn giữ bản gốc/bản AI sửa/cả hai rồi mới lưu.
    """
    content = payload.get("content") or ""
    spectral = payload.get("spectral") or []
    redocly = payload.get("redocly") or []

    if not content.strip():
        raise http_error(400, ErrorCode.EMPTY_BUNDLE, "Bundle rỗng, không có gì để sửa")
    if not spectral and not redocly:
        return {"patches": [], "unresolved": [], "failed": []}

    return ai_fix.run(content, spectral, redocly)


@router.get("/docs/operations")
def get_operations():
    """Trả về danh sách operations từ bundle để hiển thị trong form editor."""
    import yaml as _yaml

    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise http_error(
            404,
            ErrorCode.BUNDLE_NOT_FOUND,
            "Bundle chưa được tạo, hãy build tài liệu trước",
        )
    bundle = _yaml.safe_load(bundle_path.read_text(encoding="utf-8")) or {}
    ops = []
    for path, path_item in bundle.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            parameters = [
                {
                    "name": p.get("name", ""),
                    "in": p.get("in", ""),
                    "description": p.get("description") or "",
                }
                for p in (operation.get("parameters") or [])
                if _is_inline(p)
            ]
            responses = [
                {"code": code, "description": resp.get("description") or ""}
                for code, resp in (operation.get("responses") or {}).items()
                if _is_inline(resp)
            ]
            ops.append(
                {
                    "operationId": operation.get("operationId") or "",
                    "method": method.upper(),
                    "path": path,
                    "tags": operation.get("tags") or [],
                    "summary": operation.get("summary") or "",
                    "description": operation.get("description") or "",
                    "parameters": parameters,
                    "responses": responses,
                }
            )
    return ops

@router.patch("/docs/operations")
async def update_operations(updates: list = Body(...)):
    """Cập nhật summary/description của một hoặc nhiều operations.

    Ghi đồng thời tầng 3 (bundle) và tầng 2 (file fragment riêng dưới
    5.openapi/paths/), kèm marker x-manual-edit-fields để pipeline biết field
    nào đã bị sửa tay khi import lại (xem 2.pipeline/pipeline_API.py — không sửa
    file đó, chỉ đọc/ghi field này từ phía backend).
    """
    import copy
    import yaml as _yaml

    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise http_error(404, ErrorCode.BUNDLE_NOT_FOUND, "Bundle chưa được tạo, hãy build tài liệu trước")

    old_bundle = _yaml.safe_load(bundle_path.read_text(encoding="utf-8")) or {}
    update_map = {u["operationId"]: u for u in updates if u.get("operationId")}

    new_bundle = copy.deepcopy(old_bundle)
    updated = 0
    for path_item in new_bundle.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            op_id = operation.get("operationId", "")
            if op_id not in update_map:
                continue
            _apply_operation_update(operation, update_map[op_id])
            updated += 1

    changes = diff_bundle(old_bundle, new_bundle)
    sync_operation_fields(new_bundle, changes, _index_operation_files())

    bundle_path.write_text(
        _yaml.dump(new_bundle, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return {"ok": True, "updated": updated}

@router.post("/docs/operations/ai-suggest")
def ai_suggest_operation(payload: dict = Body(...)):
    """Gợi ý bằng Claude cho các field đang trống (summary/description/parameter & response description).

    Chỉ trả về field đang trống ở phía client — không ghi đè field đã có nội dung,
    để tránh mất nội dung non-dev đã viết tay khi bấm nhầm.
    """
    import anthropic

    method = (payload.get("method") or "").upper()
    path = payload.get("path") or ""
    op_id = payload.get("operationId") or ""
    summary = payload.get("summary") or ""
    description = payload.get("description") or ""
    parameters = payload.get("parameters") or []
    responses = payload.get("responses") or []

    empty_param_names = [
        p.get("name")
        for p in parameters
        if isinstance(p, dict) and not p.get("description")
    ]
    empty_response_codes = [
        r.get("code")
        for r in responses
        if isinstance(r, dict) and not r.get("description")
    ]

    if summary and description and not empty_param_names and not empty_response_codes:
        return {}

    prompt_lines = [
        "Bạn là kỹ sư viết tài liệu OpenAPI cho dự án phần mềm tiếng Việt.",
        f"Operation: {method} {path}",
        f"operationId: {op_id}",
        f"Tham số cần viết mô tả: {', '.join(empty_param_names) or 'không có'}",
        f"Response code cần viết mô tả: {', '.join(empty_response_codes) or 'không có'}",
        "Chỉ trả JSON, không thêm chữ nào khác, theo cấu trúc:",
        '{"summary": "...", "description": "...", '
        '"parameters": [{"name": "...", "description": "..."}], '
        '"responses": [{"code": "...", "description": "..."}]}',
        "summary tối đa 10 từ. description 1-2 câu. Bỏ qua key nào không cần điền.",
        "Toàn bộ nội dung bằng tiếng Việt.",
    ]
    if summary:
        prompt_lines.append(f"summary đã có sẵn (không cần gợi ý lại): {summary}")
    if description:
        prompt_lines.append(
            f"description đã có sẵn (không cần gợi ý lại): {description}"
        )

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="cc/claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": "\n".join(prompt_lines)}],
        )
        raw = response.content[0].text.strip()
    except Exception as e:
        raise http_error(502, ErrorCode.AI_CALL_FAILED, f"Lỗi gọi AI: {e}")

    suggestion = ai_fix._parse_ai_json(raw)

    result: dict = {}
    if not summary and suggestion.get("summary"):
        result["summary"] = suggestion["summary"]
    if not description and suggestion.get("description"):
        result["description"] = suggestion["description"]
    if empty_param_names:
        result["parameters"] = [
            p
            for p in (suggestion.get("parameters") or [])
            if isinstance(p, dict)
            and p.get("name") in empty_param_names
            and p.get("description")
        ]
    if empty_response_codes:
        result["responses"] = [
            r
            for r in (suggestion.get("responses") or [])
            if isinstance(r, dict)
            and r.get("code") in empty_response_codes
            and r.get("description")
        ]
    return result
