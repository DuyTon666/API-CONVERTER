import asyncio
import json
import subprocess
import sys
import tempfile
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

PIPELINE_DIR = Path(__file__).parent.parent / "2.pipeline"
OUTPUT_DIR = Path(__file__).parent.parent / "5.openapi"
DIST_DIR = Path(__file__).parent.parent / "dist"
CONFIG_DIR = Path(__file__).parent.parent / "4.config"
SOURCE_DIR = Path(__file__).parent.parent / "1.docs" / "source" / "api_contract"

sys.path.insert(0, str(PIPELINE_DIR))

from generator.emitter import init_config as _init_emitter
_init_emitter(str(CONFIG_DIR))

executor = ThreadPoolExecutor(max_workers=4)


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
            raise HTTPException(status_code=500, detail=bundle_result.stderr)

    spectral_result = subprocess.run(
        ["npm", "run", "--silent", "lint:spectral"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    try:
        spectral_issues = json.loads(spectral_result.stdout) if spectral_result.stdout.strip() else []
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


def _compute_action_name(op, non_resource_actions: set) -> str:
    segments = [s for s in op.path.split('/') if s and s != 'v1']
    last = segments[-1] if segments else ""
    if not last.startswith('{'):
        if last in non_resource_actions:
            return last
        if op.method == 'GET':
            return 'list'
        if op.method == 'POST':
            return 'create'
        return last
    prev = segments[-2] if len(segments) >= 2 else ""
    prev_clean = prev if not prev.startswith('{') else ""
    if op.method == 'GET':
        return 'detail'
    if op.method in ('PUT', 'PATCH'):
        return 'update'
    if op.method == 'DELETE':
        return 'delete'
    if op.method == 'POST':
        return f"{prev_clean}-update" if prev_clean else 'create'
    return 'action'

@dataclass
class FileResult:
    file_id: str
    filename: str
    status: Literal["pending", "processing", "done", "error", "flagged"]
    yaml: str = ""
    flags: list = field(default_factory=list)
    error: str = ""
    action_name: str = ""
    schemas: dict = field(default_factory=dict)  # {filename.yaml: content}

@dataclass
class Job:
    job_id: str
    domain: str = ""
    files: list[FileResult] = field(default_factory=list)
    status: Literal["running", "done"] = "running"

jobs: dict[str, Job] = {}

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

@dataclass
class ImportJob:
    job_id: str
    modules: list[ImportModuleResult] = field(default_factory=list)
    status: Literal["running", "done"] = "running"

import_jobs: dict[str, ImportJob] = {}

app = FastAPI(title="API Converter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/modules/scan")
def scan_modules():
    from run_api_import import(
        _load_import_config,
        _get_source_root,
        _supported_extensions,
        _ignore_dirs,
        _scan_source_root,
    )

    cfg = _load_import_config()
    source_root = _get_source_root(cfg)
    result = _scan_source_root(source_root, _supported_extensions(cfg), _ignore_dirs(cfg))
    modules = []
    for m in result["modules"]:
        by_extension: dict[str, int] = {}
        for f in m["files"]:
            ext = f.suffix.lower().lstrip(".")
            by_extension[ext] = by_extension.get(ext, 0) + 1
        modules.append({"name": m["name"], "total": len(m["files"]), "by_extension": by_extension})

    return {
        "source_root": str(source_root),
        "modules": modules,
        "unassigned": [{"name": f.name} for f in result["unassigned"]],
    }

@app.get("/modules")
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
        modules.append({
            "name": name,
            "status": status,
            "file_count": info.get("file_count", 0),
            "endpoint_count": info.get("endpoint_count", 0),
            "last_import_at": info.get("last_import_at"),
            "last_import_status": info.get("last_import_status"),
            "created_at": info.get("created_at"),
        })
    return {"modules": modules, "summary": {"total": len(modules), "by_status": by_status}}

@app.post("/source/upload")
async def upload_source_files(files: list[UploadFile] = File(...)):
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for upload in files:
        file_bytes = await upload.read()
        (SOURCE_DIR / upload.filename).write_bytes(file_bytes)
        saved.append(upload.filename)
    return {"saved": saved, "total": len(saved)}


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


@app.get("/modules/suggestions")
def get_suggestions():
    from run_api_import import REPORT_DIR
    suggestions_path = REPORT_DIR / "import_suggestions.json"
    if not suggestions_path.exists():
        return {"exists": False, "items": [], "summary": {"pending": 0, "approved": 0, "rejected": 0}}
    return _read_suggestions(suggestions_path)


@app.post("/modules/suggest")
def suggest_modules():
    from run_api_import import cmd_suggest_root, REPORT_DIR
    try:
        cmd_suggest_root()
    except SystemExit:
        raise HTTPException(status_code=500, detail="suggest-root thất bại — xem log backend")
    suggestions_path = REPORT_DIR / "import_suggestions.json"
    if not suggestions_path.exists():
        raise HTTPException(status_code=500, detail="Không tạo được import_suggestions.json")
    return _read_suggestions(suggestions_path)


@app.post("/modules/suggestions/approve")
def approve_suggestions(
    mode: str = Body(...),
    module: str | None = Body(None),
    file: str | None = Body(None),
    override_module: str | None = Body(None),
):
    from run_api_import import cmd_approve_suggestions, REPORT_DIR
    suggestions_path = REPORT_DIR / "import_suggestions.json"
    if not suggestions_path.exists():
        raise HTTPException(status_code=400, detail="Chưa có suggestions — hãy chạy suggest trước")

    try:
        if mode == "all":
            cmd_approve_suggestions(str(suggestions_path), approve_all=True)
        elif mode == "module":
            if not module:
                raise HTTPException(status_code=400, detail="Thiếu 'module'")
            cmd_approve_suggestions(str(suggestions_path), module_filter=module, override_module=override_module)
        elif mode == "file":
            if not file:
                raise HTTPException(status_code=400, detail="Thiếu 'file'")
            cmd_approve_suggestions(str(suggestions_path), file_name=file, override_module=override_module)
        else:
            raise HTTPException(status_code=400, detail="mode phải là 'all', 'module' hoặc 'file'")
    except SystemExit:
        raise HTTPException(status_code=500, detail="approve-suggestions thất bại — xem log backend")

    return _read_suggestions(suggestions_path)


@app.post("/modules/apply")
def apply_suggestions():
    from run_api_import import cmd_apply_suggestions, REPORT_DIR
    suggestions_path = REPORT_DIR / "import_suggestions.json"
    if not suggestions_path.exists():
        raise HTTPException(status_code=400, detail="Chưa có suggestions — hãy chạy suggest trước")

    try:
        cmd_apply_suggestions(str(suggestions_path), move_files=False, convert=False)
    except SystemExit:
        raise HTTPException(status_code=500, detail="apply-suggestions thất bại — xem log backend")

    report_path = REPORT_DIR / "import_applied_suggestions.json"
    if not report_path.exists():
        raise HTTPException(status_code=500, detail="Không tạo được report apply-suggestions")
    return json.loads(report_path.read_text(encoding="utf-8"))

@app.post("/modules/{module}/activate")
def activate_module(module: str):
    import yaml as _yaml
    from run_api_import import cmd_activate_module

    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy registry")
    registry = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if module not in registry.get("modules", {}):
        raise HTTPException(status_code=404, detail=f"Module '{module}' không có trong registry")

    try:
        cmd_activate_module(module=module, actor="ui")
    except SystemExit:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể activate module '{module}' — kiểm tra trạng thái và đường dẫn (xem log backend)",
        )

    return list_modules()

@app.post("/modules/{module}/deactivate")
def deactivate_module(module: str):
    import yaml as _yaml
    from run_api_import import cmd_deactivate_module

    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy registry")
    registry = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if module not in registry.get("modules", {}):
        raise HTTPException(status_code=404, detail=f"Module '{module}' không có trong registry")

    try:
        cmd_deactivate_module(module=module, actor="ui")
    except SystemExit:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể deactivate module '{module}' — kiểm tra log backend",
        )

    return list_modules()


@app.post("/modules/import")
def start_import(module: str | None = None):
    import yaml as _yaml

    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy registry")
    registry = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    reg_modules = registry.get("modules", {})

    if module:
        if module not in reg_modules:
            raise HTTPException(status_code=404, detail=f"Module '{module}' không có trong registry")
        if reg_modules[module].get("status") != "active":
            raise HTTPException(status_code=400, detail=f"Module '{module}' chưa active — hãy activate trước")
    elif not any(info.get("status") == "active" for info in reg_modules.values()):
        raise HTTPException(status_code=400, detail="Không có module active nào để import")

    job_id = str(uuid.uuid4())
    import_jobs[job_id] = ImportJob(job_id=job_id)
    executor.submit(_run_import_job, job_id, module)
    return {"job_id": job_id}


@app.get("/modules/import/{job_id}/stream")
async def stream_import_job(job_id: str):
    if job_id not in import_jobs:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

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
            all_done = all(mr.status not in ("pending", "running") for mr in job.modules)
            if job.status == "done" and all_done:
                yield f"data: {json.dumps({'event': 'done', 'job_id': job_id})}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/docs/build")
def build_docs():
    """Bundle + lint (Spectral/Redocly) + build Swagger UI HTML từ trạng thái 5.openapi/ hiện tại."""
    project_root = Path(__file__).parent.parent
    return _bundle_lint_build_docs(project_root, do_bundle=True)


@app.get("/docs/status")
def docs_status():
    """Trạng thái tài liệu hiện tại: bundle và HTML đã tồn tại trên đĩa chưa."""
    project_root = Path(__file__).parent.parent
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    html_path = project_root / "public" / "api-docs.html"
    return {"bundle_ready": bundle_path.exists(), "html_ready": html_path.exists()}


@app.get("/docs/download-html")
def download_docs_html():
    project_root = Path(__file__).parent.parent
    html_path = project_root / "public" / "api-docs.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="HTML chưa được build, hãy build tài liệu trước")
    return FileResponse(
        path=str(html_path),
        media_type="text/html",
        filename="api-docs.html",
    )


@app.get("/docs/bundle-content")
def get_docs_bundle_content():
    """Trả về nội dung file bundle dưới dạng plain text."""
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Bundle chưa được tạo, hãy build tài liệu trước")
    try:
        content = bundle_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể đọc file bundle: {e}")
    return PlainTextResponse(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.put("/docs/bundle-content")
async def save_docs_bundle_content(request: Request):
    """Lưu nội dung bundle sau khi user chỉnh sửa (plain text)."""
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Bundle chưa được tạo, hãy build tài liệu trước")
    content = (await request.body()).decode("utf-8")
    bundle_path.write_text(content, encoding="utf-8")
    return {"ok": True}


@app.post("/docs/relint")
def relint_docs():
    """Chạy lại Spectral + Redocly + build HTML từ bundle hiện tại (không bundle lại)."""
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Bundle chưa được tạo, hãy build tài liệu trước")

    project_root = Path(__file__).parent.parent
    return _bundle_lint_build_docs(project_root, do_bundle=False)


def process_file(file_result: FileResult, file_bytes: bytes, domain: str = "ticket") -> None:
    file_result.status = "processing"
    try:
        from pipeline_DOCX import run
        import yaml as _yaml

        module_config_path = CONFIG_DIR / "modules" / f"{domain}.yaml"
        non_resource_actions: set = set()
        if module_config_path.exists():
            mod_cfg = _yaml.safe_load(module_config_path.read_text(encoding="utf-8")) or {}
            non_resource_actions = set(mod_cfg.get("action_names", []))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            schemas_tmp = tmp_path / "schemas"
            schemas_tmp.mkdir()
            input_path = tmp_path / file_result.filename
            output_path = tmp_path / (Path(file_result.filename).stem + ".yaml")
            input_path.write_bytes(file_bytes)
            op = run(str(input_path), str(output_path), schemas_dir=str(schemas_tmp), domain=domain)
            if output_path.exists():
                file_result.yaml = output_path.read_text(encoding="utf-8")
                if op and op.review_flags:
                    file_result.flags = op.review_flags
                    file_result.status = "flagged"
                else:
                    file_result.status = "done"
                if op and op.method and op.path:
                    file_result.action_name = _compute_action_name(op, non_resource_actions)
                for schema_file in schemas_tmp.glob("*.yaml"):
                    file_result.schemas[schema_file.name] = schema_file.read_text(encoding="utf-8")
            else:
                file_result.status = "error"
                file_result.error = "Pipeline không sinh ra output"
    except Exception as e:
        traceback.print_exc()
        file_result.status = "error"
        file_result.error = str(e)


def _run_import_job(job_id: str, module_filter: str | None = None) -> None:
    """Chạy cmd_import theo từng module để có thể báo tiến trình per-module qua SSE."""
    import datetime
    import yaml as _yaml
    from run_api_import import (
        _load_import_config,
        _get_source_root,
        _get_output_root,
        _get_schemas_root,
        _supported_extensions,
        _ignore_dirs,
        _scan_source_root,
        REPORT_DIR,
    )
    from pipeline_API import run_batch

    job = import_jobs[job_id]

    cfg = _load_import_config()
    source_root = _get_source_root(cfg)
    output_root = _get_output_root(cfg)
    schemas_root = _get_schemas_root(cfg)
    result = _scan_source_root(source_root, _supported_extensions(cfg), _ignore_dirs(cfg))

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

    job.modules = [ImportModuleResult(name=m["name"], total=len(m["files"])) for m in to_run]

    batch_log_path = REPORT_DIR / "batch_log_by_module.json"

    for m, mr in zip(to_run, job.modules):
        mr.status = "running"
        now = datetime.datetime.now().isoformat(timespec="seconds")
        import_status = "success"
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

        if m["name"] in registry_modules:
            info = registry_modules[m["name"]]
            info["last_import_at"] = now
            info["last_import_status"] = import_status

            out_dir = output_root / m["name"]
            if out_dir.exists():
                info["endpoint_count"] = len([
                    f for f in out_dir.iterdir()
                    if f.is_file() and f.suffix.lower() in (".yaml", ".yml")
                ])

    if registry_modules:
        raw_full = registry_path.read_text(encoding="utf-8").strip()
        reg_full = _yaml.safe_load(raw_full) if raw_full else {}
        reg_full["modules"] = registry_modules
        registry_path.write_text(
            _yaml.safe_dump(reg_full, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    job.status = "done"


@app.post("/jobs")
async def create_job(files: list[UploadFile] = File(...), domain: str=""):
    job_id = str(uuid.uuid4())
    job = Job(job_id=job_id, domain=domain)
    jobs[job_id] = job
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for upload in files:
        file_bytes = await upload.read()
        (SOURCE_DIR / upload.filename).write_bytes(file_bytes)
        file_result = FileResult(
            file_id=str(uuid.uuid4()),
            filename=upload.filename,
            status="pending",
        )
        job.files.append(file_result)
        executor.submit(process_file, file_result, file_bytes)
    return {"job_id": job_id, "total": len(job.files)}

@app.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    async def event_generator():
        seen = set()
        while True:
            job = jobs[job_id]
            for f in job.files:
                if f.file_id not in seen and f.status not in ("pending", "processing"):
                    seen.add(f.file_id)
                    data = {
                        "file_id": f.file_id,
                        "filename": f.filename,
                        "status": f.status,
                        "error": f.error,
                    }
                    yield f"data: {json.dumps(data)}\n\n"
            all_done = all(f.status not in ("pending", "processing") for f in job.files)
            if all_done:
                job.status = "done"
                yield f"data: {json.dumps({'event': 'done', 'job_id': job_id})}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/jobs/{job_id}/flags")
def get_flags(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    job = jobs[job_id]
    return [
        {
            "file_id": f.file_id,
            "filename": f.filename,
            "status": f.status,
            "flags": f.flags,
            "error": f.error,
        }
        for f in job.files
        if f.status in ("flagged", "error")
    ]


@app.get("/jobs/{job_id}/files/{file_id}/yaml")
def get_yaml(job_id: str, file_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    f = next((f for f in job.files if f.file_id == file_id), None)
    if not f:
        raise HTTPException(status_code=404, detail="File không tồn tại")
    return {"file_id": f.file_id, "filename": f.filename, "yaml": f.yaml, "error": f.error}


@app.put("/jobs/{job_id}/files/{file_id}/yaml")
def update_yaml(job_id: str, file_id: str, yaml: str = Body(..., embed=True)):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    f = next((f for f in job.files if f.file_id == file_id), None)
    if not f:
        raise HTTPException(status_code=404, detail="File không tồn tại")
    f.yaml = yaml
    return {"ok": True}


@app.post("/jobs/{job_id}/files/{file_id}/approve")
def approve_file(job_id: str, file_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    f = next((f for f in job.files if f.file_id == file_id), None)
    if not f:
        raise HTTPException(status_code=404, detail="File không tồn tại")
    f.status = "done"
    return {"ok": True}

@app.post("/jobs/{job_id}/files/{file_id}/reject")
def reject_file(job_id: str, file_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    f = next((f for f in job.files if f.file_id == file_id), None)
    if not f:
        raise HTTPException(status_code=404, detail="File không tồn tại")
    f.status = "rejected"
    return {"ok": True}

@app.post("/jobs/{job_id}/export")
async def export_bundle(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    approved = [f for f in job.files if f.status == "done" and f.yaml]
    if not approved:
        raise HTTPException(status_code=400, detail="Chưa có file nào được approve")

    # Lưu YAML vào 5.openapi/paths/tickets
    module_name = job.domain or "default"
    paths_dir = OUTPUT_DIR / "paths" / module_name
    paths_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir_out = OUTPUT_DIR / "components" / "schemas" / module_name

    for f in approved:
        out_name = f.action_name if f.action_name else Path(f.filename).stem
        out_path = paths_dir / f"{out_name}.yaml"
        out_path.write_text(f.yaml, encoding="utf-8")
        for schema_name, schema_content in f.schemas.items():
            (schemas_dir_out / schema_name).write_text(schema_content, encoding="utf-8")

    project_root = Path(__file__).parent.parent
    return _bundle_lint_build_docs(project_root, do_bundle=True)


@app.get("/jobs/{job_id}/download-html")
def download_html(job_id: str):
    project_root = Path(__file__).parent.parent
    html_path = project_root / "public" / "api-docs.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="HTML chưa được build, hãy export trước")
    return FileResponse(
        path=str(html_path),
        media_type="text/html",
        filename="api-docs.html",
    )


@app.get("/jobs/{job_id}/bundle-content")
def get_bundle_content(job_id: str):
    """Trả về nội dung file bundle dưới dạng plain text."""
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Bundle chưa được tạo, hãy export trước")
    try:
        content = bundle_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể đọc file bundle: {e}")
    return PlainTextResponse(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.put("/jobs/{job_id}/bundle-content")
async def save_bundle_content(job_id: str, request: Request):
    """Lưu nội dung bundle sau khi user chỉnh sửa (plain text)."""
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Bundle chưa được tạo, hãy export trước")
    content = (await request.body()).decode("utf-8")
    bundle_path.write_text(content, encoding="utf-8")
    return {"ok": True}


@app.post("/jobs/{job_id}/relint")
async def relint(job_id: str):
    """Chạy lại Spectral + Redocly + build HTML từ bundle hiện tại (không bundle lại)."""
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Bundle chưa được tạo, hãy export trước")

    project_root = Path(__file__).parent.parent
    return _bundle_lint_build_docs(project_root, do_bundle=False)