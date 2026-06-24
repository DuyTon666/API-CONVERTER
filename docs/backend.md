# Backend — API Converter

## Tổng quan

FastAPI server (`backend/`, tách theo router — `main.py` chỉ còn app setup + đăng ký router) đóng vai trò trung gian giữa frontend và pipeline xử lý (`2.pipeline/`). Cung cấp 2 nhóm chức năng:

1. **Module workflow** — scan tài liệu nguồn, gợi ý module, duyệt, áp dụng, activate/deactivate, import theo module (dùng cho dashboard chính)
2. **Docs & Operations** — bundle, lint (Spectral/Redocly), build Swagger UI HTML, **form editor** chỉnh sửa summary/description trực tiếp trên bundle, và 2 endpoint AI hỗ trợ (gợi ý mô tả còn trống, tự sửa lỗi lint)

> Nhóm "file-upload job" (`POST /jobs` và các endpoint con) đã bị **xóa** — không có UI nào tạo job nên route không bao giờ được dùng tới (xem mục Lịch sử thay đổi).

Tất cả lỗi do backend tự raise đều đi qua `http_error()` → trả `detail: {code, message}` thay vì chuỗi thường (xem mục **Hệ thống mã lỗi**).

---

## Công nghệ

| Công nghệ                        | Vai trò                                                                                |
| -------------------------------- | -------------------------------------------------------------------------------------- |
| **FastAPI**                      | Web framework, định nghĩa API endpoints                                                |
| **Uvicorn**                      | ASGI server chạy FastAPI (`--reload` khi dev)                                          |
| `ThreadPoolExecutor` (4 workers) | Chạy pipeline (blocking) trên thread riêng, tránh block event loop                     |
| `subprocess`                     | Gọi npm scripts (Redocly bundle/lint, Spectral lint, build docs)                       |
| `asyncio.to_thread`              | Wrap các handler `async def` có gọi `subprocess.run()` để không block event loop       |
| `pyyaml` (`import yaml`)         | Đọc/ghi `module_registry.yaml` và `dist/openapi-bundled.yaml`                          |
| `python-dotenv`                  | Load `backend/.env` (gitignored) — cần cho 2 endpoint AI gọi Claude qua gateway nội bộ |
| `anthropic` SDK                  | Gọi Claude (`/docs/bundle/ai-fix`, `/docs/operations/ai-suggest`)                      |

---

## Cấu trúc

```
backend/
├── main.py             # FastAPI() + CORS + load_dotenv + include_router() — không chứa route nào (~24 dòng)
├── config.py            # Hằng số đường dẫn + inject 2.pipeline vào sys.path + init_emitter (side-effect khi import)
├── errors.py             # ErrorCode + http_error() — hệ thống mã lỗi, dùng chung mọi router
├── routers/
│   ├── health.py          # GET /health
│   ├── modules.py         # Module workflow: scan/suggest/approve/apply/activate/deactivate/import + SSE,
│   │                      # import_jobs dict, executor (ThreadPoolExecutor), ImportModuleResult/ImportJob, _run_import_job()
│   └── docs.py             # Docs & Operations: build/lint/bundle-content/operations/ai-suggest/ai-fix,
│                           # _bundle_lint_build_docs(), _parse_redocly_output(), _parse_ai_json()
├── requirements.txt    # fastapi, uvicorn, python-dotenv, anthropic, + deps parsing mà pipeline_API.py import trực tiếp
├── .env                # Gitignored — biến cho gateway Claude nội bộ (xem dưới)
└── venv/               # Python virtual environment riêng (khác .venv root)
```

**Quy ước tách file**: mỗi router sở hữu state/helper riêng của domain đó (ví dụ `import_jobs`/`executor` chỉ nằm trong `modules.py`, không global ở `main.py`) — `main.py` không bao giờ phình to thêm khi thêm route mới, chỉ cần thêm hàm vào router phù hợp hoặc tạo router mới + 1 dòng `include_router()`.

## Khởi động

```bash
cd backend && make dev
# hoặc: source backend/venv/bin/activate && uvicorn main:app --reload --port 8000
```

`load_dotenv(Path(__file__).parent / ".env")` chạy ngay khi import `main.py`. `backend/.env` cần:

```
ANTHROPIC_BASE_URL=...
ANTHROPIC_AUTH_TOKEN=...
ANTHROPIC_MODEL=cc/claude-sonnet-4-6
ANTHROPIC_API_KEY=...
```

Project gọi Claude qua gateway nội bộ, không phải `api.anthropic.com` trực tiếp. Thiếu file này → `POST /docs/operations/ai-suggest` và `POST /docs/bundle/ai-fix` trả lỗi 502 (`AI_CALL_FAILED`).

---

## Hằng số đường dẫn (`backend/config.py`)

```python
PIPELINE_DIR = project_root / "2.pipeline"
OUTPUT_DIR   = project_root / "5.openapi"
DIST_DIR     = project_root / "dist"
CONFIG_DIR   = project_root / "4.config"
SOURCE_DIR   = project_root / "1.docs" / "source" / "api_contract"
```

File này có side-effect khi import: inject `PIPELINE_DIR` vào `sys.path`, gọi `init_config()` của
`generator.emitter` một lần. `main.py` import `config` đầu tiên (trước `routers`) để đảm bảo side-effect
này chạy trước khi route nào trong `routers/modules.py`/`routers/docs.py` cần import từ `2.pipeline`.

---

## CORS

```python
allow_origins=["http://localhost:3000"]
```

Frontend chạy port khác phải sửa tay trong `main.py`.

---

## Hệ thống mã lỗi

Mọi lỗi backend tự raise dùng `http_error(status_code, code, message)` thay vì
`HTTPException(status_code, detail="...")` trực tiếp:

```python
def http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
```

Response lỗi có shape `{"detail": {"code": "MODULE_NOT_FOUND", "message": "..."}}` — `code` là
định danh cố định để frontend map sang chữ hiển thị riêng (xem `docs/frontend.md`), `message` là
câu tiếng Việt gốc, dùng làm fallback khi frontend không override mã đó.

`class ErrorCode` (`backend/errors.py`, cùng `http_error()`) định nghĩa ~23 mã, gom theo nhóm chức
năng (`SUGGEST_FAILED`, `MODULE_NOT_FOUND`, `BUNDLE_NOT_FOUND`, `AI_CALL_FAILED`...). Mọi router
(`modules.py`, `docs.py`) đều `from errors import ErrorCode, http_error` — dùng chung 1 nguồn, không
định nghĩa riêng. Nhiều endpoint khác nhau dùng chung 1 mã khi cùng message (ví dụ `BUNDLE_NOT_FOUND`
dùng ở 5 nơi).

**Lỗi 422 validation của FastAPI** (body thiếu field, sai type) không đi qua `http_error` — vẫn
giữ format gốc (`detail` là `list[{loc, msg, type}]`); frontend xử lý riêng cho trường hợp này
(fallback về `res.statusText`).

---

## Data Model

### Module import job (`import_jobs: dict[str, ImportJob]`, `routers/modules.py`)

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

| Method | Path                              | Mô tả                                                                                                                                              |
| ------ | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/modules/scan`                   | Scan `1.docs/source/api_contract/`, trả về modules đã có file + file chưa gán module                                                               |
| `GET`  | `/modules`                        | List module từ `module_registry.yaml` (status, file_count, endpoint_count, last_import)                                                            |
| `POST` | `/source/upload`                  | Upload file thô vào `SOURCE_DIR` (chưa convert, chỉ lưu)                                                                                           |
| `GET`  | `/modules/suggestions`            | Đọc `import_suggestions.json` (nếu có)                                                                                                             |
| `POST` | `/modules/suggest`                | Chạy `cmd_suggest_root()` — phân tích file, gợi ý module cho từng endpoint                                                                         |
| `POST` | `/modules/suggestions/approve`    | Duyệt suggestion — `mode`: `"all"` / `"module"` / `"file"`, có `override_module`                                                                   |
| `POST` | `/modules/apply`                  | Copy file đã duyệt vào `1.docs/source/api_contract/<module>/`. Bỏ qua file đã tồn tại đích (`target_file_exists`) hoặc chưa duyệt (`not_approved`) |
| `POST` | `/modules/{module}/activate`      | draft/deprecated → active                                                                                                                          |
| `POST` | `/modules/{module}/deactivate`    | active → deprecated                                                                                                                                |
| `POST` | `/modules/import?module=<name>`   | Chạy `run_batch()` theo từng module active (hoặc tất cả module active nếu không truyền `module`). Trả `job_id`                                     |
| `GET`  | `/modules/import/{job_id}/stream` | SSE — emit khi 1 module xong (chỉ emit lúc transition khỏi `running`, **không** stream per-file)                                                   |

**Lưu ý activate/deactivate:** route `POST /modules/{module}/activate` không xung đột với `POST /modules/import` vì FastAPI match theo path segment — `import` (2 segments) khác `{module}/activate` (3 segments).

---

## Endpoint — Docs & Operations

| Method       | Path                          | Mô tả                                                                                                                                                                                                                                                                  |
| ------------ | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST`       | `/docs/build`                 | Bundle (`npm run bundle:api`) → Spectral lint → Redocly lint → build HTML (`npm run build:docs`)                                                                                                                                                                       |
| `GET`        | `/docs/status`                | `{ bundle_ready, html_ready }` — chỉ check file tồn tại trên đĩa                                                                                                                                                                                                       |
| `GET` `/PUT` | `/docs/bundle-content`        | Đọc/ghi `dist/openapi-bundled.yaml` plain text                                                                                                                                                                                                                         |
| `POST`       | `/docs/relint`                | Lint lại + build HTML từ bundle hiện tại, không bundle lại                                                                                                                                                                                                             |
| `GET`        | `/docs/download-html`         | Download `public/api-docs.html`                                                                                                                                                                                                                                        |
| `GET`        | `/docs/operations`            | Parse bundle, trả về list operations: `{operationId, method, path, tags, summary, description, parameters[], responses[]}` — dùng cho Form Editor. `parameters`/`responses` loại trừ entry `$ref`'d (tránh 1 operation sửa ảnh hưởng operation khác dùng chung `$ref`) |
| `PATCH`      | `/docs/operations`            | Nhận `list[{operationId, summary?, description?, parameters?, responses?}]`, chỉ ghi đè field mô tả (summary/description + `parameters[].description` + `responses[].description` không `$ref`), không đụng path/method/schema/response codes                          |
| `POST`       | `/docs/operations/ai-suggest` | Gọi Claude gợi ý summary/description/parameter & response description cho 1 operation — **chỉ điền field đang trống**, không ghi đè field đã có nội dung                                                                                                               |
| `POST`       | `/docs/bundle/ai-fix`         | Gọi Claude sửa toàn bộ bundle YAML theo danh sách lỗi Spectral/Redocly hiện có. Trả YAML đã sửa để hiển thị trong Monaco — **không ghi xuống đĩa**, dev tự review rồi bấm "Lưu & Kiểm tra lại". Rủi ro cao hơn `ai-suggest` vì có thể sửa cả path/schema/$ref          |

**`_bundle_lint_build_docs(project_root, do_bundle)`** là hàm core dùng chung bởi `/docs/build` và `/docs/relint`. Trả về:

```json
{
  "bundle_ready": true,
  "html_ready": true,
  "spectral": [ { "code", "severity", "message", "path", "range" } ],
  "redocly":  [ { "ruleId", "severity", "message", "location" } ]
}
```

**Vùng an toàn khi PATCH operations:** chỉ `summary`, `description`, `parameters[].description`, `responses[].description` (không `$ref`). Không cho sửa `path`, `method`, parameter name/type/schema, `requestBody` schema, response codes, `$ref`, `servers`, `security` — các field này client/SDK dùng trực tiếp, sửa sai sẽ break consumer.

---

## Hàm tiện ích

### `_parse_redocly_output(result)` (`routers/docs.py`)

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
    └── _run_import_job() (routers/modules.py) → executor.submit() → ThreadPoolExecutor riêng (4 workers)
```

---

## Thiếu sót hiện tại (Known Gaps)

| Vấn đề                                                                             | Ghi chú                                                                                                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| State chỉ trong RAM                                                                | Restart server mất toàn bộ `import_jobs`                                                                                                                                                                                                                                           |
| Không validate file type phía backend                                              | Backend nhận bất kỳ file gì, chỉ frontend filter theo extension                                                                                                                                                                                                                    |
| CORS chỉ cho `localhost:3000`                                                      | Dev frontend port khác bị block                                                                                                                                                                                                                                                    |
| Không có auth                                                                      | Dashboard mở public trong mạng nội bộ                                                                                                                                                                                                                                              |
| `/docs/operations` PATCH dùng `pyyaml.dump`                                        | Format lại toàn bộ bundle (mất format gốc của Redocly), nhưng vẫn là YAML hợp lệ — không ảnh hưởng Spectral/Redocly                                                                                                                                                                |
| Không có publish/deploy tự động                                                    | Tải HTML thủ công, chưa có nút commit+push lên git                                                                                                                                                                                                                                 |
| Form Editor / AI-fix / AI-suggest chỉ ghi vào `dist/openapi-bundled.yaml` (tầng 3) | Bấm "Build tài liệu" sinh lại bundle từ `5.openapi/paths/<module>/*.yaml` (tầng 2) → nội dung đã sửa qua các tính năng này bị mất. Cần ghi đè ngược vào tầng 2 (dựa `$ref` map trong `5.openapi/openapi.yaml`) — **chưa triển khai, đang chờ thảo luận thêm**                      |
| `5.openapi/openapi.yaml` thiếu `$ref` cho 1 số module                              | Chỉ `ticket` được wire vào `paths:` — tài liệu cuối (`dist/openapi-bundled.yaml`) không thấy `service`/`department`/`statistic` dù đã import. Sửa phải động tới `2.pipeline` (ngoài phạm vi cho phép hiện tại của backend/frontend) — **chưa triển khai, đang chờ thảo luận thêm** |

---

## Lịch sử thay đổi đáng chú ý

**Tách `main.py` (854 dòng) thành nhiều file theo domain** (`config.py`, `errors.py`,
`routers/health.py`, `routers/modules.py`, `routers/docs.py`) — `main.py` giờ chỉ còn ~24 dòng:
tạo `FastAPI()`, CORS, `load_dotenv()`, `include_router()`. Mỗi router sở hữu state/helper riêng
của domain đó (ví dụ `import_jobs`/`executor` chỉ nằm trong `modules.py`). Hàm `_compute_action_name`
(không còn được gọi từ đâu — dead code) đã bị xóa luôn trong lúc tách, không di chuyển sang đâu.
Hành vi mọi endpoint giữ nguyên 100% — đã verify bằng cách chạy `uvicorn` thật + `curl` từng route
ở cả 3 router sau khi tách.

**Đã xóa nhóm endpoint `/jobs/*`** (12 endpoint: `POST /jobs`, `GET stream`, `GET flags`, `GET/PUT files/{fid}/yaml`, `POST approve`, `POST reject`, `POST export`, `GET download-html`, `GET/PUT bundle-content`, `POST relint`) cùng `FileResult`, `Job` dataclass, `jobs: dict` storage, và hàm `process_file()`.

**Lý do:** không có UI nào gọi `POST /jobs` để tạo job → `jobs` dict luôn trống → route `app/jobs/[job_id]` (frontend) không thể truy cập được trong thực tế. Dashboard chính dùng `/source/upload` + `/modules/import` thay thế hoàn toàn cho chức năng này.
