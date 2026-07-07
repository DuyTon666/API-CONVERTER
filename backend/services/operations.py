from services import ai_fix, schema_fields
from core.config import DIST_DIR
from core.errors import ErrorCode, http_error
from services import ai_fix
from services.bundle_sync import (
    _HTTP_METHODS,
    _is_inline,
    _apply_operation_update,
    diff_bundle,
    sync_operation_fields,
    _index_operation_files,
)


# Logic rút từ route GET /docs/operations — trả về danh sách operations từ
# bundle để hiển thị trong form editor.
def list_operations() -> list[dict]:
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


# Logic rút từ route PATCH /docs/operations — cập nhật summary/description của
# một hoặc nhiều operations. Ghi đồng thời tầng 3 (bundle) và tầng 2 (file
# fragment riêng dưới 5.openapi/paths/), kèm marker x-manual-edit-fields để
# pipeline biết field nào đã bị sửa tay khi import lại (xem
# 2.pipeline/pipeline_API.py — không sửa file đó, chỉ đọc/ghi field này từ phía
# backend).
def update_operations(updates: list) -> dict:
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


# Logic rút từ route POST /docs/operations/ai-suggest — gợi ý bằng Claude cho
# các field đang trống (summary/description/parameter & response description).
# Chỉ trả về field đang trống ở phía client — không ghi đè field đã có nội
# dung, để tránh mất nội dung non-dev đã viết tay khi bấm nhầm.
def ai_suggest_operation(payload: dict) -> dict:
    import anthropic

    method = (payload.get("method") or "").upper()
    path = payload.get("path") or ""
    op_id = payload.get("operationId") or ""
    summary = payload.get("summary") or ""
    description = payload.get("description") or ""
    parameters = payload.get("parameters") or []
    responses = payload.get("responses") or []
    data_schemas = payload.get("dataSchemas") or {}

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

    request_fields = schema_fields.flatten_schema_group(data_schemas.get("request"))
    response_fields = schema_fields.flatten_schema_group(data_schemas.get("response"))
    empty_request_fields = [f for f in request_fields if not f.get("description")]
    empty_response_fields = [f for f in response_fields if not f.get("description")]

    if (
        summary
        and description
        and not empty_param_names
        and not empty_response_codes
        and not empty_request_fields
        and not empty_response_fields
    ):
        return {}

    prompt_lines = [
        "Bạn là kỹ sư viết tài liệu OpenAPI cho dự án phần mềm tiếng Việt.",
        f"Operation: {method} {path}",
        f"operationId: {op_id}",
        f"Tham số cần viết mô tả: {', '.join(empty_param_names) or 'không có'}",
        f"Response code cần viết mô tả: {', '.join(empty_response_codes) or 'không có'}",
    ]
    if empty_request_fields:
        prompt_lines.append(
            "Field dữ liệu gửi lên cần viết mô tả (schema.path — kiểu dữ liệu): "
            + "; ".join(f"{f['schemaName']}.{f['path']} ({f['type']})" for f in empty_request_fields)
        )
    if empty_response_fields:
        prompt_lines.append(
            "Field dữ liệu trả về cần viết mô tả (schema.path — kiểu dữ liệu): "
            + "; ".join(f"{f['schemaName']}.{f['path']} ({f['type']})" for f in empty_response_fields)
        )
    prompt_lines += [
        "Chỉ trả JSON, không thêm chữ nào khác, theo cấu trúc:",
        '{"summary": "...", "description": "...", '
        '"parameters": [{"name": "...", "description": "..."}], '
        '"responses": [{"code": "...", "description": "..."}], '
        '"dataSchemas": {"request": [{"schemaName": "...", "path": "...", "description": "..."}], '
        '"response": [{"schemaName": "...", "path": "...", "description": "..."}]}}',
        "summary tối đa 10 từ. description 1-2 câu. Mô tả field ngắn gọn 1 câu.",
        "Bỏ qua key nào không cần điền.",
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
            max_tokens=4000,
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

    suggested_schemas = suggestion.get("dataSchemas") or {}
    if empty_request_fields:
        allowed = {(f["schemaName"], f["path"]) for f in empty_request_fields}
        req = [
            f
            for f in (suggested_schemas.get("request") or [])
            if isinstance(f, dict)
            and (f.get("schemaName"), f.get("path")) in allowed
            and f.get("description")
        ]
        if req:
            result.setdefault("dataSchemas", {})["request"] = req
    if empty_response_fields:
        allowed = {(f["schemaName"], f["path"]) for f in empty_response_fields}
        resp = [
            f
            for f in (suggested_schemas.get("response") or [])
            if isinstance(f, dict)
            and (f.get("schemaName"), f.get("path")) in allowed
            and f.get("description")
        ]
        if resp:
            result.setdefault("dataSchemas", {})["response"] = resp

    return result