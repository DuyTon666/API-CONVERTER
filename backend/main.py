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

sys.path.insert(0, str(PIPELINE_DIR))

executor = ThreadPoolExecutor(max_workers=4)

@dataclass
class FileResult:
    file_id: str
    filename: str
    status: Literal["pending", "processing", "done", "error", "flagged"]
    yaml: str = ""
    flags: list = field(default_factory=list)
    error: str = ""

@dataclass
class Job:
    job_id: str
    files: list[FileResult] = field(default_factory=list)
    status: Literal["running", "done"] = "running"

jobs: dict[str, Job] = {}

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

def process_file(file_result: FileResult, file_bytes: bytes) -> None:
    file_result.status = "processing"
    try:
        from pipeline_Ticket import run
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            input_path = tmp / file_result.filename
            output_path = tmp / (Path(file_result.filename).stem + ".yaml")
            input_path.write_bytes(file_bytes)
            run(str(input_path), str(output_path))
            if output_path.exists():
                file_result.yaml = output_path.read_text(encoding="utf-8")
                file_result.status = "done"
            else:
                file_result.status = "error"
                file_result.error = "Pipeline không sinh ra output"
    except Exception as e:
        traceback.print_exc()
        file_result.status = "error"
        file_result.error = str(e)

@app.post("/jobs")
async def create_job(files: list[UploadFile] = File(...)):
    job_id = str(uuid.uuid4())
    job = Job(job_id=job_id)
    jobs[job_id] = job
    for upload in files:
        file_bytes = await upload.read()
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

@app.post("/jobs/{job_id}/export")
async def export_bundle(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    approved = [f for f in job.files if f.status == "done" and f.yaml]
    if not approved:
        raise HTTPException(status_code=400, detail="Chưa có file nào được approve")

    # Lưu YAML vào 5.openapi/paths
    paths_dir = OUTPUT_DIR / "paths"
    paths_dir.mkdir(parents=True, exist_ok=True)
    for f in approved:
        out_path = paths_dir / f.filename.replace(".docx", ".yaml")
        out_path.write_text(f.yaml, encoding="utf-8")

    project_root = Path(__file__).parent.parent
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # Bước 1: Redocly bundle
    bundle_result = subprocess.run(
        ["npx", "redocly", "bundle", "5.openapi/openapi.yaml", "-o", "dist/openapi-bundled.yaml"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    if bundle_result.returncode != 0:
        raise HTTPException(status_code=500, detail=bundle_result.stderr)

    # Bước 2: Spectral lint
    spectral_result = subprocess.run(
        ["npx", "spectral", "lint", "dist/openapi-bundled.yaml",
         "--ruleset", ".spectral.yaml", "--format", "json"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    try:
        spectral_issues = json.loads(spectral_result.stdout) if spectral_result.stdout.strip() else []
    except Exception:
        spectral_issues = []

    # Bước 3: Redocly lint
    redocly_result = subprocess.run(
        ["npx", "redocly", "lint", "dist/openapi-bundled.yaml", "--format", "json"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    try:
        redocly_raw = json.loads(redocly_result.stdout) if redocly_result.stdout.strip() else []
        redocly_issues = redocly_raw if isinstance(redocly_raw, list) else []
    except Exception:
        redocly_issues = []

    # Bước 4: Build Swagger UI HTML
    html_path = project_root / "public" / "api-docs.html"
    (project_root / "public").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["node", "scripts/build-swagger-ui.js"],
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
    return PlainTextResponse(
        content=bundle_path.read_text(encoding="utf-8"),
        media_type="text/plain; charset=utf-8",
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

    spectral_result = subprocess.run(
        ["npx", "spectral", "lint", "dist/openapi-bundled.yaml",
         "--ruleset", ".spectral.yaml", "--format", "json"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    try:
        spectral_issues = json.loads(spectral_result.stdout) if spectral_result.stdout.strip() else []
    except Exception:
        spectral_issues = []

    redocly_result = subprocess.run(
        ["npx", "redocly", "lint", "dist/openapi-bundled.yaml", "--format", "json"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    try:
        redocly_raw = json.loads(redocly_result.stdout) if redocly_result.stdout.strip() else []
        redocly_issues = redocly_raw if isinstance(redocly_raw, list) else []
    except Exception:
        redocly_issues = []

    html_path = project_root / "public" / "api-docs.html"
    (project_root / "public").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["node", "scripts/build-swagger-ui.js"],
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

