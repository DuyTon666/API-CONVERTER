import asyncio
import datetime
import json
import shutil
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal

from core.config import CONFIG_DIR
from core.errors import ErrorCode, http_error


# Pool thread riêng để chạy job import (nặng, chậm) ở background, không chặn server.
executor = ThreadPoolExecutor(max_workers=4)


# Tiến trình import của 1 module — cập nhật dần khi _run_import_job chạy,
# stream_events đọc lại để gửi tiến trình qua SSE cho frontend.
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


# Logic rút từ route POST /modules/import — kiểm tra module hợp lệ/active, tạo
# job mới, giao cho executor chạy ở background rồi trả job_id ngay — không đợi
# import xong (frontend dùng job_id để mở SSE).
def start_import(module: str | None = None) -> dict:
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


# Logic rút từ route GET /modules/import/{job_id}/stream — lookup-or-404, tách
# riêng khỏi stream_events() vì phải raise NGAY trong router trước khi
# StreamingResponse được tạo (raise trong async generator thì response 200 đã
# gửi header rồi, không 404 được nữa).
def get_job_or_404(job_id: str) -> ImportJob:
    if job_id not in import_jobs:
        raise http_error(404, ErrorCode.IMPORT_JOB_NOT_FOUND, "Job không tồn tại")
    return import_jobs[job_id]


# Đọc job mỗi 0.5s, gửi tiến trình module nào vừa xong (không gửi trùng nhờ
# "seen"), tự đóng kết nối khi job báo "done".
async def stream_events(job: ImportJob):
    seen = set()
    while True:
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
            yield f"data: {json.dumps({'event': 'done', 'job_id': job.job_id})}\n\n"
            break
        await asyncio.sleep(0.5)


def _run_import_job(job_id: str, module_filter: str | None = None) -> None:
    """Chạy cmd_import theo từng module để có thể báo tiến trình per-module qua SSE."""
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
    from services.manual_edit_conflicts import (
        _scan_manual_edits,
        _resolve_manual_edits_after_import,
        _scan_manual_schema_edits,
        _resolve_manual_schema_edits_after_import,
    )

    job = import_jobs[job_id]

    # try/finally bọc toàn bộ phần xử lý — đảm bảo job.status luôn được set về
    # "done" dù lỗi xảy ra ở đâu (kể cả ngoài phần try/except per-module bên
    # dưới, ví dụ lỗi đọc registry/scan trước loop hoặc ghi registry sau loop).
    # Thiếu try/finally này thì job kẹt mãi ở "running", _prune_old_jobs()
    # không bao giờ dọn được (chỉ dọn job "done"), và SSE (stream_events)
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
            captured_schemas = _scan_manual_schema_edits(schemas_dir_m)

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
                if captured_schemas:
                    _resolve_manual_schema_edits_after_import(
                        schemas_dir_m, captured_schemas, m["name"], now
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
