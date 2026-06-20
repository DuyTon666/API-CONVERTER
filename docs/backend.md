# Backend — API Converter

## Tổng quan

FastAPI server (`backend/main.py`, 1 file duy nhất) đóng vai trò trung gian giữa frontend và pipeline xử lý (`2.pipeline/`). Cung cấp 2 nhóm chức năng:

1. **Module workflow** — scan tài liệu nguồn, gợi ý module, duyệt, áp dụng, activate/deactivate, import theo module (dùng cho dashboard chính)
2. **Docs & Operations** — bundle, lint (Spectral/Redocly), build Swagger UI HTML, và **form editor** chỉnh sửa summary/description trực tiếp trên bundle

> Nhóm "file-upload job" (`POST /jobs` và các endpoint con) đã bị **xóa** — không có UI nào tạo job nên route không bao giờ được dùng tới (xem mục Lịch sử thay đổi).

---

## Công nghệ

| Công nghệ | Vai trò |
|---|---|
| **FastAPI** | Web framework, định nghĩa API endpoints |
| **Uvicorn** | ASGI server chạy FastAPI (`--reload` khi dev) |
| `ThreadPoolExecutor` (4 workers) | Chạy pipeline (blocking) trên thread riêng, tránh block event loop |
| `subprocess` | Gọi npm scripts (Redocly bundle/lint, Spectral lint, build docs) |
| `asyncio.to_thread` | Wrap các handler `async def` có gọi `subprocess.run()` để không block event loop |
| `pyyaml` (`import yaml`) | Đọc/ghi `module_registry.yaml` và `dist/openapi-bundled.yaml` |

---

## Cấu trúc

```
backend/
├── main.py     # Toàn bộ backend
└── venv/       # Python virtual environment riêng (khác .venv root)
```

## Khởi động

```bash
cd backend && make dev
# hoặc: source backend/venv/bin/activate && uvicorn main:app --reload --port 8000
```

Yêu cầu: `ANTHROPIC_API_KEY` đã export trong environment (dùng bởi pipeline khi enrich).

---

## Hằng số đường dẫn

```python
PIPELINE_DIR = project_root / "2.pipeline"
OUTPUT_DIR   = project_root / "5.openapi"
DIST_DIR     = project_root / "dist"
CONFIG_DIR   = project_root / "4.config"
SOURCE_DIR   = project_root / "1.docs" / "source" / "api_contract"
```

Khi khởi động: inject `PIPELINE_DIR` vào `sys.path`, gọi `init_config()` của `generator.emitter` một lần.

---

## CORS

```python
allow_origins=["http://localhost:3000"]
```

Frontend chạy port khác phải sửa tay trong `main.py`.

---

## Data Model

### Module import job (`import_jobs: dict[str, ImportJob]`)

```python
@dataclass
class ImportModuleResult:
    name: str
    status: Literal["pending", "running", "done", "error"] = "pending"
    total: int; success: int; failed: int; skipped: int; needs_review: int
    error: str = ""

@dataclass
class ImportJob:
    job_id: str
    modules: list[ImportModuleResult]
    status: Literal["running", "done"] = "running"
```

`import_jobs` là **in-memory only** — mất khi restart server. Không có database.

---

## Endpoint — Module Workflow

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/modules/scan` | Scan `1.docs/source/api_contract/`, trả về modules đã có file + file chưa gán module |
| `GET` | `/modules` | List module từ `module_registry.yaml` (status, file_count, endpoint_count, last_import) |
| `POST` | `/source/upload` | Upload file thô vào `SOURCE_DIR` (chưa convert, chỉ lưu) |
| `GET` | `/modules/suggestions` | Đọc `import_suggestions.json` (nếu có) |
| `POST` | `/modules/suggest` | Chạy `cmd_suggest_root()` — phân tích file, gợi ý module cho từng endpoint |
| `POST` | `/modules/suggestions/approve` | Duyệt suggestion — `mode`: `"all"` / `"module"` / `"file"`, có `override_module` |
| `POST` | `/modules/apply` | Copy file đã duyệt vào `1.docs/source/api_contract/<module>/`. Bỏ qua file đã tồn tại đích (`target_file_exists`) hoặc chưa duyệt (`not_approved`) |
| `POST` | `/modules/{module}/activate` | draft/deprecated → active |
| `POST` | `/modules/{module}/deactivate` | active → deprecated |
| `POST` | `/modules/import?module=<name>` | Chạy `run_batch()` theo từng module active (hoặc tất cả module active nếu không truyền `module`). Trả `job_id` |
| `GET` | `/modules/import/{job_id}/stream` | SSE — emit khi 1 module xong (chỉ emit lúc transition khỏi `running`, **không** stream per-file) |

**Lưu ý activate/deactivate:** route `POST /modules/{module}/activate` không xung đột với `POST /modules/import` vì FastAPI match theo path segment — `import` (2 segments) khác `{module}/activate` (3 segments).

---

## Endpoint — Docs & Operations

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/docs/build` | Bundle (`npm run bundle:api`) → Spectral lint → Redocly lint → build HTML (`npm run build:docs`) |
| `GET` | `/docs/status` | `{ bundle_ready, html_ready }` — chỉ check file tồn tại trên đĩa |
| `GET` `/PUT` | `/docs/bundle-content` | Đọc/ghi `dist/openapi-bundled.yaml` plain text |
| `POST` | `/docs/relint` | Lint lại + build HTML từ bundle hiện tại, không bundle lại |
| `GET` | `/docs/download-html` | Download `public/api-docs.html` |
| `GET` | `/docs/operations` | Parse bundle, trả về list operations: `{operationId, method, path, tags, summary, description}` — dùng cho Form Editor |
| `PATCH` | `/docs/operations` | Nhận `list[{operationId, summary?, description?}]`, chỉ ghi đè 2 field này trong bundle, không đụng path/method/schema/parameters/responses |

**`_bundle_lint_build_docs(project_root, do_bundle)`** là hàm core dùng chung bởi `/docs/build`, `/docs/relint`, `/jobs/{id}/export`, `/jobs/{id}/relint`. Trả về:
```json
{
  "bundle_ready": true,
  "html_ready": true,
  "spectral": [ { "code", "severity", "message", "path", "range" } ],
  "redocly":  [ { "ruleId", "severity", "message", "location" } ]
}
```

**Vùng an toàn khi PATCH operations:** chỉ `summary` + `description`. Không cho sửa `path`, `method`, `parameters`, `requestBody` schema, `responses` codes, `$ref`, `servers`, `security` — các field này client/SDK dùng trực tiếp, sửa sai sẽ break consumer.

---

## Hàm tiện ích

### `_compute_action_name(op, non_resource_actions)`
Tính tên file output từ HTTP method + path (segment `v1` bị bỏ qua khi parse):

| Path | Method | Kết quả |
|---|---|---|
| `/v1/tickets` | GET | `list` |
| `/v1/tickets` | POST | `create` |
| `/v1/tickets/{id}` | GET | `detail` |
| `/v1/tickets/{id}` | PUT/PATCH | `update` |
| `/v1/tickets/{id}` | DELETE | `delete` |

### `_parse_redocly_output(result)`
Parse JSON từ Redocly CLI, hỗ trợ 2 format: `{totals, problems: [...]}` (v2) và `[{filePath, problems: [...]}]` (cũ).

---

## Concurrency model

```
FastAPI (async event loop)
    │
    ├── SSE stream (/modules/import/.../stream)
    │       → async generator, await asyncio.sleep(0.5)
    │
    ├── /docs/build, /docs/relint  → def (sync) — Starlette tự chạy trong threadpool, an toàn
    │
    └── _run_import_job()          → executor.submit() → ThreadPoolExecutor riêng (4 workers)
```

---

## Thiếu sót hiện tại (Known Gaps)

| Vấn đề | Ghi chú |
|---|---|
| State chỉ trong RAM | Restart server mất toàn bộ `import_jobs` |
| Không validate file type phía backend | Backend nhận bất kỳ file gì, chỉ frontend filter theo extension |
| CORS chỉ cho `localhost:3000` | Dev frontend port khác bị block |
| Không có auth | Dashboard mở public trong mạng nội bộ |
| `/docs/operations` PATCH dùng `pyyaml.dump` | Format lại toàn bộ bundle (mất format gốc của Redocly), nhưng vẫn là YAML hợp lệ — không ảnh hưởng Spectral/Redocly |
| Không có publish/deploy tự động | Tải HTML thủ công, chưa có nút commit+push lên git |

---

## Lịch sử thay đổi đáng chú ý

**Đã xóa nhóm endpoint `/jobs/*`** (12 endpoint: `POST /jobs`, `GET stream`, `GET flags`, `GET/PUT files/{fid}/yaml`, `POST approve`, `POST reject`, `POST export`, `GET download-html`, `GET/PUT bundle-content`, `POST relint`) cùng `FileResult`, `Job` dataclass, `jobs: dict` storage, và hàm `process_file()`.

**Lý do:** không có UI nào gọi `POST /jobs` để tạo job → `jobs` dict luôn trống → route `app/jobs/[job_id]` (frontend) không thể truy cập được trong thực tế. Dashboard chính dùng `/source/upload` + `/modules/import` thay thế hoàn toàn cho chức năng này.
