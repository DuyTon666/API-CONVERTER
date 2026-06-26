import asyncio
import json
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, File, UploadFile
from fastapi.responses import StreamingResponse

from config import CONFIG_DIR, SOURCE_DIR
from errors import ErrorCode, http_error

router = APIRouter()

# Pool thread riêng để chạy job import (nặng, chậm) ở background, không chặn server.
executor = ThreadPoolExecutor(max_workers=4)


# Tiến trình import của 1 module — cập nhật dần khi _run_import_job chạy,
# stream_import_job đọc lại để gửi tiến trình qua SSE cho frontend.
@dataclass
class ImportModuleResult:
    name: str
    status: Literal["pending", "running", "done", "error"] = "pending"
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    needs_review: int = 0
    error: str = ""


# 1 job import — gồm nhiều module, mỗi module có 1 ImportModuleResult riêng.
@dataclass
class ImportJob:
    job_id: str
    modules: list[ImportModuleResult] = field(default_factory=list)
    status: Literal["running", "done"] = "running"
    created_at: float = field(default_factory=time.time)


# Lưu mọi job import đang/đã chạy — chỉ ở RAM, mất khi restart backend.
import_jobs: dict[str, ImportJob] = {}

# Job "done" sống quá lâu hoặc quá nhiều thì bị dọn — tránh import_jobs phình
# vô hạn nếu /modules/import bị gọi liên tục (DoS bộ nhớ). Job "running" không
# bao giờ bị xoá dù cũ, tránh làm hỏng job đang chạy thật.
JOB_TTL_SECONDS = 3600
MAX_STORED_JOBS = 50


def _prune_old_jobs() -> None:
    now = time.time()
    for jid, job in list(import_jobs.items()):
        if job.status == "done" and now - job.created_at > JOB_TTL_SECONDS:
            del import_jobs[jid]

    if len(import_jobs) > MAX_STORED_JOBS:
        done_jobs = sorted(
            (j for j in import_jobs.values() if j.status == "done"),
            key=lambda j: j.created_at,
        )
        for job in done_jobs[: len(import_jobs) - MAX_STORED_JOBS]:
            del import_jobs[job.job_id]


# Quét 1.docs/source/ xem có module/file nào, gom theo phần mở rộng file —
# phục vụ ScanCard ở frontend.
@router.get("/modules/scan")
def scan_modules():
    from import_flow.config import (
        load_import_config,
        get_source_root,
        supported_extensions,
        ignore_dirs,
    )
    from import_flow.scanner import scan_source_root

    cfg = load_import_config()
    source_root = get_source_root(cfg)
    result = scan_source_root(source_root, supported_extensions(cfg), ignore_dirs(cfg))
    modules = []
    for m in result["modules"]:
        by_extension: dict[str, int] = {}
        for f in m["files"]:
            ext = f.suffix.lower().lstrip(".")
            by_extension[ext] = by_extension.get(ext, 0) + 1
        modules.append(
            {"name": m["name"], "total": len(m["files"]), "by_extension": by_extension}
        )

    return {
        "source_root": str(source_root),
        "modules": modules,
        "unassigned": [{"name": f.name} for f in result["unassigned"]],
    }


# Đọc 4.config/module_registry.yaml, đếm số module theo status —
# phục vụ ModuleRegistryCard ở frontend.
@router.get("/modules")
def list_modules():
    import yaml as _yaml

    registry_path = CONFIG_DIR / "module_registry.yaml"
    raw = {}
    if registry_path.exists():
        raw = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    raw_modules = raw.get("modules", {})
    modules = []
    by_status: dict[str, int] = {}
    for name, info in raw_modules.items():
        status = info.get("status", "draft")
        by_status[status] = by_status.get(status, 0) + 1
        modules.append(
            {
                "name": name,
                "status": status,
                "file_count": info.get("file_count", 0),
                "endpoint_count": info.get("endpoint_count", 0),
                "last_import_at": info.get("last_import_at"),
                "last_import_status": info.get("last_import_status"),
                "created_at": info.get("created_at"),
            }
        )
    return {
        "modules": modules,
        "summary": {"total": len(modules), "by_status": by_status},
    }


# Nhận file upload từ ImportCard, lưu thẳng vào 1.docs/source/api_contract/.
MAX_UPLOAD_SIZE = 20 * 1024 * 1024


@router.post("/source/upload")
async def upload_source_files(files: list[UploadFile] = File(...)):
    from import_flow.config import load_import_config, supported_extensions

    cfg = load_import_config()
    allowed_ext = supported_extensions(cfg)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    resolved_source_dir = SOURCE_DIR.resolve()
    saved = []
    for upload in files:
        safe_name = Path(upload.filename).name
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

        file_bytes = await upload.read()
        if len(file_bytes) > MAX_UPLOAD_SIZE:
            raise http_error(
                400,
                ErrorCode.FILE_TOO_LARGE,
                f"File quá lớn (tối đa {MAX_UPLOAD_SIZE // (1024 * 1024)} MB): {safe_name}",
            )

        dest.write_bytes(file_bytes)
        saved.append(safe_name)
    return {"saved": saved, "total": len(saved)}


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


# Đọc file import_suggestions.json, đếm số item theo approval_status —
# dùng chung cho cả 3 route suggestions/suggest/approve dưới đây.
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


# Trả về suggestions hiện có (không chạy gì mới) — gọi lúc load trang.
@router.get("/modules/suggestions")
def get_suggestions():
    from run_api_import import REPORT_DIR

    suggestions_path = REPORT_DIR / "import_suggestions.json"
    if not suggestions_path.exists():
        return {
            "exists": False,
            "items": [],
            "summary": {"pending": 0, "approved": 0, "rejected": 0},
        }
    return _read_suggestions(suggestions_path)


# Chạy lại suggest-root (CLI 2.pipeline) để phân loại module cho từng file nguồn.
@router.post("/modules/suggest")
def suggest_modules():
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


# Duyệt 1 hoặc nhiều suggestion (theo file/module/tất cả), có thể override module —
# trả kèm "skipped" để báo file nào bị bỏ qua ngầm (xem _skip_reason).
@router.post("/modules/suggestions/approve")
def approve_suggestions(
    mode: str = Body(...),
    module: str | None = Body(None),
    file: str | None = Body(None),
    override_module: str | None = Body(None),
):
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


# Copy file đã duyệt vào đúng thư mục module (1.docs/source/api_contract/<module>/).
@router.post("/modules/apply")
def apply_suggestions():
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


# Chuyển module sang status "active" (hoặc "reactivate" nếu đang deprecated)
# để được phép import (xem điều kiện ở start_import).
@router.post("/modules/{module}/activate")
def activate_module(module: str):
    import yaml as _yaml
    from run_api_import import cmd_activate_module, cmd_reactivate_module

    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        raise http_error(404, ErrorCode.REGISTRY_NOT_FOUND, "Không tìm thấy registry")
    registry = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if module not in registry.get("modules", {}):
        raise http_error(
            404,
            ErrorCode.MODULE_NOT_FOUND,
            f"Module '{module}' không có trong registry",
        )

    status = registry["modules"][module].get("status")
    try:
        if status == "deprecated":
            cmd_reactivate_module(module=module, actor="ui")
        else:
            cmd_activate_module(module=module, actor="ui")
    except SystemExit:
        raise http_error(
            400,
            ErrorCode.MODULE_ACTIVATE_FAILED,
            f"Không thể activate module '{module}' — kiểm tra trạng thái và đường dẫn (xem log backend)",
        )

    return list_modules()


# Chuyển module sang status "deprecated" — không import được nữa tới khi activate lại.
@router.post("/modules/{module}/deactivate")
def deactivate_module(module: str):
    import yaml as _yaml
    from run_api_import import cmd_deactivate_module

    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        raise http_error(404, ErrorCode.REGISTRY_NOT_FOUND, "Không tìm thấy registry")
    registry = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if module not in registry.get("modules", {}):
        raise http_error(
            404,
            ErrorCode.MODULE_NOT_FOUND,
            f"Module '{module}' không có trong registry",
        )

    try:
        cmd_deactivate_module(module=module, actor="ui")
    except SystemExit:
        raise http_error(
            400,
            ErrorCode.MODULE_DEACTIVATE_FAILED,
            f"Không thể deactivate module '{module}' — kiểm tra log backend",
        )

    return list_modules()


# Kiểm tra module hợp lệ/active, tạo job mới, giao cho executor chạy ở background
# rồi trả job_id ngay — không đợi import xong (frontend dùng job_id để mở SSE).
@router.post("/modules/import")
def start_import(module: str | None = None):
    import yaml as _yaml

    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        raise http_error(404, ErrorCode.REGISTRY_NOT_FOUND, "Không tìm thấy registry")
    registry = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    reg_modules = registry.get("modules", {})

    if module:
        if module not in reg_modules:
            raise http_error(
                404,
                ErrorCode.MODULE_NOT_FOUND,
                f"Module '{module}' không có trong registry",
            )
        if reg_modules[module].get("status") != "active":
            raise http_error(
                400,
                ErrorCode.MODULE_NOT_ACTIVE,
                f"Module '{module}' chưa active — hãy activate trước",
            )
    elif not any(info.get("status") == "active" for info in reg_modules.values()):
        raise http_error(
            400, ErrorCode.NO_ACTIVE_MODULE, "Không có module active nào để import"
        )

    _prune_old_jobs()
    job_id = str(uuid.uuid4())
    import_jobs[job_id] = ImportJob(job_id=job_id)
    executor.submit(_run_import_job, job_id, module)
    return {"job_id": job_id}


# Mở kết nối SSE — đọc import_jobs[job_id] mỗi 0.5s, gửi tiến trình module nào
# vừa xong (không gửi trùng nhờ "seen"), tự đóng kết nối khi job báo "done".
@router.get("/modules/import/{job_id}/stream")
async def stream_import_job(job_id: str):
    if job_id not in import_jobs:
        raise http_error(404, ErrorCode.IMPORT_JOB_NOT_FOUND, "Job không tồn tại")

    async def event_generator():
        seen = set()
        while True:
            job = import_jobs[job_id]
            for mr in job.modules:
                if mr.name not in seen and mr.status not in ("pending", "running"):
                    seen.add(mr.name)
                    data = {
                        "name": mr.name,
                        "status": mr.status,
                        "total": mr.total,
                        "success": mr.success,
                        "failed": mr.failed,
                        "skipped": mr.skipped,
                        "needs_review": mr.needs_review,
                        "error": mr.error,
                    }
                    yield f"data: {json.dumps(data)}\n\n"
            all_done = all(
                mr.status not in ("pending", "running") for mr in job.modules
            )
            if job.status == "done" and all_done:
                yield f"data: {json.dumps({'event': 'done', 'job_id': job_id})}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Set các key hợp lệ trong 1 path item của OpenAPI — bản riêng cho modules.py,
# không tái dùng từ routers/docs.py (chấp nhận duplicate nhỏ, xem plan Phần 2).
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


# Quét toàn bộ file tầng 2 dưới paths_dir, build map operationId -> (file, operation
# dict) — dùng chung cho cả lúc capture (trước import) và compare (sau import).
def _index_operations(paths_dir: Path) -> dict[str, tuple[Path, dict]]:
    import yaml as _yaml

    index: dict[str, tuple[Path, dict]] = {}
    if not paths_dir.exists():
        return index
    for file in paths_dir.glob("**/*.yaml"):
        try:
            doc = _yaml.safe_load(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        for method, operation in doc.items():
            if method in _HTTP_METHODS and isinstance(operation, dict):
                op_id = operation.get("operationId")
                if op_id:
                    index[op_id] = (file, operation)
    return index


# Lấy đúng giá trị hiện tại của các field được đánh dấu trong marker
# x-manual-edit-fields — dùng cả lúc capture (giá trị trước import) và lúc lấy
# giá trị sau import để so sánh. Field summary/description -> giá trị thẳng;
# parameters/responses -> ghép key dạng "parameters.<name>" / "responses.<code>"
# để biết chính xác field con nào (đồng nhất với key dùng trong conflict entry).
def _extract_marked_fields(operation: dict, marker: dict) -> dict:
    fields = {}
    if marker.get("summary"):
        fields["summary"] = operation.get("summary", "")
    if marker.get("description"):
        fields["description"] = operation.get("description", "")
    for name in marker.get("parameters") or []:
        for p in operation.get("parameters") or []:
            if isinstance(p, dict) and p.get("name") == name:
                fields[f"parameters.{name}"] = p.get("description", "")
                break
    for code in marker.get("responses") or []:
        resp = (operation.get("responses") or {}).get(code)
        if isinstance(resp, dict):
            fields[f"responses.{code}"] = resp.get("description", "")
    return fields


# Capture — trước khi run_batch() có thể ghi đè file, lưu lại giá trị hiện tại
# của mọi field đã từng được đánh dấu sửa tay, để so sánh sau khi import xong.
def _scan_manual_edits(paths_dir: Path) -> dict:
    captured: dict[str, dict] = {}
    for op_id, (file, operation) in _index_operations(paths_dir).items():
        marker = operation.get("x-manual-edit-fields")
        if not marker:
            continue
        fields = _extract_marked_fields(operation, marker)
        if fields:
            captured[op_id] = {"file": file, "fields": fields}
    return captured


# Lấy giá trị hiện tại của 1 field theo field_key ("summary"/"description" hoặc
# "parameters.<name>"/"responses.<code>"). Trả None nếu field đó không còn tồn
# tại trong operation (tham số/response bị xoá khỏi doc) — phân biệt với "" (field
# còn tồn tại nhưng rỗng), để không tạo conflict giả cho thứ không còn tồn tại.
def _get_field_value(operation: dict, field_key: str) -> str | None:
    if field_key in ("summary", "description"):
        return operation.get(field_key, "")
    if field_key.startswith("parameters."):
        name = field_key.split(".", 1)[1]
        for p in operation.get("parameters") or []:
            if isinstance(p, dict) and p.get("name") == name:
                return p.get("description", "")
        return None
    if field_key.startswith("responses."):
        code = field_key.split(".", 1)[1]
        resp = (operation.get("responses") or {}).get(code)
        if isinstance(resp, dict):
            return resp.get("description", "")
        return None
    return None


# Đổi list field_key (dạng dotted) ngược lại thành dict x-manual-edit-fields —
# chiều ngược của _extract_marked_fields, dùng khi ghi lại marker sau so sánh.
def _field_keys_to_marker(field_keys: list[str]) -> dict | None:
    marker: dict = {}
    for key in field_keys:
        if key in ("summary", "description"):
            marker[key] = True
        elif key.startswith("parameters."):
            marker.setdefault("parameters", []).append(key.split(".", 1)[1])
        elif key.startswith("responses."):
            marker.setdefault("responses", []).append(key.split(".", 1)[1])
    if "parameters" in marker:
        marker["parameters"] = sorted(marker["parameters"])
    if "responses" in marker:
        marker["responses"] = sorted(marker["responses"])
    return marker or None


# Append conflict entries vào 3.build/reports/manual_edit_conflicts.json — đọc
# toàn bộ, nối thêm, ghi lại (không khoá tiến trình, xem rủi ro đã ghi trong plan).
def _append_manual_edit_conflicts(conflicts: list[dict]) -> None:
    if not conflicts:
        return
    from import_flow.config import REPORT_DIR

    path = REPORT_DIR / "manual_edit_conflicts.json"
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.extend(conflicts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# Sau khi run_batch() chạy xong cho 1 module: so sánh giá trị field đã sửa tay
# (captured trước import) với giá trị hiện tại. Field không đổi (hoặc file bị
# pipeline skip do version không đổi) -> ghi lại marker, không bị mất qua nhiều
# lần import. Field đổi thật (version đổi + giá trị mới khác giá trị sửa tay)
# -> KHÔNG ghi đè, đẩy vào hàng đợi review (API Phần 3 sẽ đọc file này).
def _resolve_manual_edits_after_import(
    paths_dir: Path, captured: dict, module_name: str, detected_at: str
) -> None:
    from ruamel.yaml import YAML

    fragment_yaml = YAML()
    fragment_yaml.default_flow_style = False
    fragment_yaml.indent(mapping=2, sequence=4, offset=2)

    after_index = _index_operations(paths_dir)
    conflicts = []

    for op_id, cap in captured.items():
        after = after_index.get(op_id)
        if after is None:
            continue  # file bị skip (marker vẫn còn) hoặc operation biến mất khỏi doc

        after_file, after_operation = after
        kept_fields = []
        for field_key, old_value in cap["fields"].items():
            new_value = _get_field_value(after_operation, field_key)
            if new_value is None:
                continue  # field không còn tồn tại — bỏ qua, không tạo conflict giả
            if new_value == old_value:
                kept_fields.append(field_key)
            else:
                conflicts.append(
                    {
                        "operationId": op_id,
                        "module": module_name,
                        "field": field_key,
                        "old_value": old_value,
                        "new_value": new_value,
                        "detected_at": detected_at,
                    }
                )

        new_marker = _field_keys_to_marker(kept_fields)
        try:
            fragment = fragment_yaml.load(after_file.read_text(encoding="utf-8"))
            for method, operation in fragment.items():
                if (
                    method in _HTTP_METHODS
                    and isinstance(operation, dict)
                    and operation.get("operationId") == op_id
                ):
                    if new_marker:
                        operation["x-manual-edit-fields"] = new_marker
                    else:
                        operation.pop("x-manual-edit-fields", None)
            with after_file.open("w", encoding="utf-8") as f:
                fragment_yaml.dump(fragment, f)
        except Exception:
            traceback.print_exc()

    _append_manual_edit_conflicts(conflicts)


# Đổi field_key (dạng "summary"/"description"/"parameters.<name>"/"responses.<code>")
# + giá trị muốn ghi, thành đúng shape "upd" mà _apply_operation_update() (routers/docs.py)
# đang nhận — chiều ngược của _get_field_value ở trên.
def _field_key_to_upd(field_key: str, value: str) -> dict:
    if field_key in ("summary", "description"):
        return {field_key: value}
    if field_key.startswith("parameters."):
        name = field_key.split(".", 1)[1]
        return {"parameters": [{"name": name, "description": value}]}
    if field_key.startswith("responses."):
        code = field_key.split(".", 1)[1]
        return {"responses": [{"code": code, "description": value}]}
    return {}


# Trả về danh sách xung đột đang chờ duyệt — đọc thẳng manual_edit_conflicts.json
# (ghi bởi _append_manual_edit_conflicts ở Phần 2), dùng cho ManualEditConflictsCard.
@router.get("/modules/manual-edit-conflicts")
def get_manual_edit_conflicts():
    from import_flow.config import REPORT_DIR

    path = REPORT_DIR / "manual_edit_conflicts.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


# Duyệt 1 xung đột. "keep_old": ghi old_value trở lại tầng 2 + tầng 3 (tái dùng
# _apply_operation_update/_merge_marker từ routers/docs.py — đúng logic Form Editor
# đang dùng, tránh viết lại lần 2 dễ lệch nhau). "accept_new": không đổi gì trong
# file (giá trị mới đã có sẵn từ lúc Phần 2 phát hiện conflict). Cả 2 case: xoá
# entry khỏi hàng đợi.
@router.post("/modules/manual-edit-conflicts/resolve")
def resolve_manual_edit_conflict(payload: dict = Body(...)):
    import yaml as _yaml
    from ruamel.yaml import YAML
    from config import DIST_DIR
    from import_flow.config import REPORT_DIR
    from routers.docs import (
        _apply_operation_update,
        _merge_marker,
        _index_operation_files,
    )

    op_id = payload.get("operationId")
    field_key = payload.get("field")
    choice = payload.get("choice")
    if not op_id or not field_key or choice not in ("keep_old", "accept_new"):
        raise http_error(
            400,
            ErrorCode.INVALID_CONFLICT_RESOLVE,
            "Thiếu operationId/field hoặc choice không hợp lệ (phải là 'keep_old'/'accept_new')",
        )

    path = REPORT_DIR / "manual_edit_conflicts.json"
    if not path.exists():
        raise http_error(
            404, ErrorCode.CONFLICT_NOT_FOUND, "Không có xung đột nào đang chờ duyệt"
        )
    conflicts = json.loads(path.read_text(encoding="utf-8"))

    match = next(
        (c for c in conflicts if c["operationId"] == op_id and c["field"] == field_key),
        None,
    )
    if match is None:
        raise http_error(
            404,
            ErrorCode.CONFLICT_NOT_FOUND,
            "Không tìm thấy xung đột này (có thể đã được duyệt trước đó)",
        )

    if choice == "keep_old":
        upd = _field_key_to_upd(field_key, match["old_value"])

        # Tầng 3 — bundle. Cùng cấu trúc loop với update_operations() (docs.py),
        # chỉ khác: chỉ xử lý đúng 1 operationId, không cần update_map.
        bundle_path = DIST_DIR / "openapi-bundled.yaml"
        bundle = _yaml.safe_load(bundle_path.read_text(encoding="utf-8")) or {}
        for path_item in bundle.get("paths", {}).values():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if (
                    method in _HTTP_METHODS
                    and isinstance(operation, dict)
                    and operation.get("operationId") == op_id
                ):
                    touched = _apply_operation_update(operation, upd)
                    operation["x-manual-edit-fields"] = _merge_marker(
                        operation.get("x-manual-edit-fields"), touched
                    )
        bundle_path.write_text(
            _yaml.dump(
                bundle, allow_unicode=True, sort_keys=False, default_flow_style=False
            ),
            encoding="utf-8",
        )

        # Tầng 2 — tìm đúng file qua _index_operation_files(), đọc/ghi bằng
        # ruamel.yaml để giữ style file gốc (giống Phần 1).
        index = _index_operation_files()
        file_path = index.get(op_id)
        if file_path is not None:
            fragment_yaml = YAML()
            fragment_yaml.default_flow_style = False
            fragment_yaml.indent(mapping=2, sequence=4, offset=2)
            try:
                fragment = fragment_yaml.load(file_path.read_text(encoding="utf-8"))
                for method, operation in fragment.items():
                    if method in _HTTP_METHODS and isinstance(operation, dict):
                        touched = _apply_operation_update(operation, upd)
                        operation["x-manual-edit-fields"] = _merge_marker(
                            operation.get("x-manual-edit-fields"), touched
                        )
                with file_path.open("w", encoding="utf-8") as f:
                    fragment_yaml.dump(fragment, f)
            except Exception:
                traceback.print_exc()

    # accept_new: không cần đụng file gì — giá trị mới đã sẵn ở đó từ Phần 2.

    remaining = [
        c
        for c in conflicts
        if not (c["operationId"] == op_id and c["field"] == field_key)
    ]
    path.write_text(
        json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"ok": True, "remaining": len(remaining)}


def _run_import_job(job_id: str, module_filter: str | None = None) -> None:
    """Chạy cmd_import theo từng module để có thể báo tiến trình per-module qua SSE."""
    import datetime
    import shutil
    import yaml as _yaml
    from import_flow.config import (
        load_import_config,
        get_source_root,
        get_output_root,
        get_schemas_root,
        supported_extensions,
        ignore_dirs,
        REPORT_DIR,
    )
    from import_flow.scanner import scan_source_root
    from pipeline_API import run_batch

    job = import_jobs[job_id]

    # try/finally bọc toàn bộ phần xử lý — đảm bảo job.status luôn được set về
    # "done" dù lỗi xảy ra ở đâu (kể cả ngoài phần try/except per-module bên
    # dưới, ví dụ lỗi đọc registry/scan trước loop hoặc ghi registry sau loop).
    # Thiếu try/finally này thì job kẹt mãi ở "running", _prune_old_jobs()
    # không bao giờ dọn được (chỉ dọn job "done"), và SSE (stream_import_job)
    # cũng treo vô hạn vì chờ job.status == "done" không bao giờ tới.
    try:
        cfg = load_import_config()
        source_root = get_source_root(cfg)
        output_root = get_output_root(cfg)
        schemas_root = get_schemas_root(cfg)
        result = scan_source_root(
            source_root, supported_extensions(cfg), ignore_dirs(cfg)
        )

        registry_path = CONFIG_DIR / "module_registry.yaml"
        raw = registry_path.read_text(encoding="utf-8").strip()
        registry_data = _yaml.safe_load(raw) if raw else {}
        registry_modules = registry_data.get("modules", {})

        to_run = []
        for m in result["modules"]:
            if not m["files"]:
                continue
            if module_filter and m["name"] != module_filter:
                continue
            info = registry_modules.get(m["name"])
            if info is None or info.get("status") != "active":
                continue
            to_run.append(m)

        job.modules = [
            ImportModuleResult(name=m["name"], total=len(m["files"])) for m in to_run
        ]

        batch_log_path = REPORT_DIR / "batch_log_by_module.json"

        for m, mr in zip(to_run, job.modules):
            mr.status = "running"
            now = datetime.datetime.now().isoformat(timespec="seconds")
            import_status = "success"

            paths_dir = output_root / m["name"]
            schemas_dir_m = schemas_root / m["name"]

            # Backup tầng 2 trước khi pipeline có thể ghi đè — bọc try/except
            # riêng, lỗi backup (disk đầy...) không được chặn import tiếp tục chạy.
            try:
                if paths_dir.exists() or schemas_dir_m.exists():
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_dir = (
                        CONFIG_DIR.parent
                        / "3.build"
                        / "backups"
                        / f"openapi_{m['name']}_{ts}"
                    )
                    if paths_dir.exists():
                        shutil.copytree(paths_dir, backup_dir / "paths")
                    if schemas_dir_m.exists():
                        shutil.copytree(schemas_dir_m, backup_dir / "schemas")
            except Exception:
                traceback.print_exc()

            # Capture — giá trị field đã sửa tay trước khi run_batch() có thể đè file.
            captured = _scan_manual_edits(paths_dir)

            try:
                run_batch(
                    input_dir=str(m["path"]),
                    module=m["name"],
                    output_dir=str(output_root / m["name"]),
                    schemas_dir=str(schemas_root / m["name"]),
                )
            except Exception as e:
                traceback.print_exc()
                mr.status = "error"
                mr.error = str(e)
                import_status = "failed"
            else:
                mr.status = "done"
                if batch_log_path.exists():
                    log = json.loads(batch_log_path.read_text(encoding="utf-8"))
                    entry = log.get("modules", {}).get(m["name"], {}).get("mixed", {})
                    mr.success = entry.get("success", 0)
                    mr.failed = entry.get("failed", 0)
                    mr.skipped = entry.get("skipped", 0)
                    mr.needs_review = entry.get("needs_review_count", 0)

                # So sánh với giá trị đã capture — chỉ chạy khi import thành công
                # (import lỗi thì file tầng 2 có thể đang ở trạng thái dở, không so).
                if captured:
                    _resolve_manual_edits_after_import(
                        paths_dir, captured, m["name"], now
                    )

            if m["name"] in registry_modules:
                info = registry_modules[m["name"]]
                info["last_import_at"] = now
                info["last_import_status"] = import_status

                out_dir = output_root / m["name"]
                if out_dir.exists():
                    info["endpoint_count"] = len(
                        [
                            f
                            for f in out_dir.iterdir()
                            if f.is_file() and f.suffix.lower() in (".yaml", ".yml")
                        ]
                    )

        if registry_modules:
            raw_full = registry_path.read_text(encoding="utf-8").strip()
            reg_full = _yaml.safe_load(raw_full) if raw_full else {}
            reg_full["modules"] = registry_modules
            registry_path.write_text(
                _yaml.safe_dump(reg_full, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
    except Exception:
        traceback.print_exc()
    finally:
        job.status = "done"
