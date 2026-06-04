# Backend — API Converter

## Tổng quan

FastAPI server đóng vai trò trung gian giữa frontend và pipeline xử lý. Nhận file từ người dùng, chạy pipeline convert sang OpenAPI YAML, cung cấp SSE để stream tiến trình, và orchestrate bundle + lint + build docs khi export.

---

## Công nghệ

| Công nghệ | Phiên bản | Vai trò |
|---|---|---|
| **Python** | 3.10 | Runtime |
| **FastAPI** | 0.136.3 | Web framework, định nghĩa API endpoints |
| **Uvicorn** | 0.48.0 | ASGI server chạy FastAPI |
| **Starlette** | 1.2.1 | Core của FastAPI — middleware, request/response |
| **Pydantic** | 2.13.4 | Validation dữ liệu (dùng ngầm bởi FastAPI) |
| ThreadPoolExecutor | stdlib | Chạy pipeline blocking trên thread riêng |
| **subprocess** | stdlib | Gọi npm scripts (Redocly, Spectral, build docs) |
| **tempfile** | stdlib | Tạo thư mục tạm cho từng file khi pipeline chạy |

---

## Cấu trúc

```
backend/
├── main.py     # Toàn bộ backend — duy nhất 1 file
└── venv/       # Python virtual environment
```

Backend chỉ có 1 file `main.py`. Không tách module vì logic đủ nhỏ.

---

## Khởi động

```bash
cd backend
source venv/bin/activate   # hoặc: backend/venv/bin/activate
uvicorn backend.main:app --port 8000 --reload
```

Yêu cầu: `ANTHROPIC_API_KEY` phải có trong environment (dùng bởi pipeline).

---

## Hằng số đường dẫn

```python
PIPELINE_DIR = project_root / "2.pipeline"    # import pipeline_Ticket từ đây
OUTPUT_DIR   = project_root / "5.openapi"     # nơi ghi YAML output
DIST_DIR     = project_root / "dist"          # openapi-bundled.yaml
CONFIG_DIR   = project_root / "4.config"      # module configs
```

Khi khởi động, backend inject `PIPELINE_DIR` vào `sys.path` và gọi `init_config()` của emitter để load config một lần duy nhất.

---

## Data Model

### `FileResult` — trạng thái từng file trong job

```python
@dataclass
class FileResult:
    file_id: str          # UUID
    filename: str         # tên file gốc
    status: Literal["pending", "processing", "done", "error", "flagged"]
    yaml: str             # nội dung YAML output (string)
    flags: list           # danh sách cờ cần human review
    error: str            # thông báo lỗi nếu status == "error"
    action_name: str      # tên action tính từ method + path (vd: "list", "create")
    schemas: dict         # { "ticket.yaml": "..." } — schema files đi kèm
```

### `Job` — một lần chạy pipeline

```python
@dataclass
class Job:
    job_id: str
    files: list[FileResult]
    status: Literal["running", "done"]
```

### Storage

```python
jobs: dict[str, Job] = {}   # in-memory, mất khi restart
```

Không có database. Toàn bộ job state tồn tại trong RAM.

---

## Các endpoint API

### `GET /health`
Kiểm tra server còn sống.
```json
{ "status": "ok" }
```

---

### `POST /jobs`
Upload file và tạo job mới.

**Request:** `multipart/form-data`, field `files` (nhiều file).

**Xử lý:**
1. Tạo `Job` với `job_id` mới (UUID)
2. Với mỗi file: tạo `FileResult` status `pending`, submit `process_file()` vào ThreadPoolExecutor
3. Return ngay — không chờ pipeline xong

**Response:**
```json
{ "job_id": "uuid", "total": 3 }
```

---

### `GET /jobs/{job_id}/stream`
SSE stream — push tiến trình xử lý về frontend theo thời gian thực.

**Cơ chế:**
- Vòng lặp poll `jobs[job_id]` mỗi 0.5 giây
- Khi file chuyển khỏi `pending`/`processing` → gửi 1 event
- Dùng `seen` set để không gửi lại event đã gửi
- Khi tất cả file xong → gửi event `done` rồi đóng stream

**Format event:**
```
data: {"file_id": "...", "filename": "...", "status": "done", "error": ""}

data: {"event": "done", "job_id": "..."}
```

---

### `GET /jobs/{job_id}/flags`
Trả về danh sách file có status `flagged` hoặc `error`.

**Response:**
```json
[
  {
    "file_id": "...",
    "filename": "...",
    "status": "error",
    "flags": [],
    "error": "Pipeline không sinh ra output"
  }
]
```

---

### `GET /jobs/{job_id}/files/{file_id}/yaml`
Đọc YAML output của một file cụ thể.

**Response:**
```json
{ "file_id": "...", "filename": "...", "yaml": "openapi: ...", "error": "" }
```

---

### `PUT /jobs/{job_id}/files/{file_id}/yaml`
Lưu YAML đã chỉnh sửa vào `FileResult.yaml` trong memory.

**Request body:** `{ "yaml": "..." }`

**Response:** `{ "ok": true }`

---

### `POST /jobs/{job_id}/files/{file_id}/approve`
Đặt status file thành `done` (dùng khi file đang `flagged`).

**Response:** `{ "ok": true }`

---

### `POST /jobs/{job_id}/export`
Bundle toàn bộ file đã approve → lint → build HTML.

**Điều kiện:** Phải có ít nhất 1 file status `done` và có `yaml`.

**Các bước thực hiện:**
1. Ghi YAML từng file vào `5.openapi/paths/tickets/{action_name}.yaml`
2. Ghi schema files vào `5.openapi/components/schemas/ticket/`
3. `npm run bundle:api` — Redocly bundle thành `dist/openapi-bundled.yaml`
4. `npm run --silent lint:spectral` — Spectral lint, parse JSON output
5. `npm run --silent validate:api` — Redocly lint, parse qua `_parse_redocly_output()`
6. `npm run build:docs` — build Swagger UI HTML vào `public/api-docs.html`

**Response:**
```json
{
  "bundle_ready": true,
  "html_ready": true,
  "spectral": [ { "code": "...", "severity": 1, "message": "...", "path": [...], "range": {...} } ],
  "redocly":  [ { "ruleId": "...", "severity": "warn", "message": "...", "location": [...] } ]
}
```

Lỗi ở bước 3 (bundle fail) → raise HTTP 500 với stderr.

---

### `GET /jobs/{job_id}/bundle-content`
Đọc nội dung `dist/openapi-bundled.yaml` dưới dạng plain text.

**Response:** `text/plain; charset=utf-8` với header `Cache-Control: no-store`.

---

### `PUT /jobs/{job_id}/bundle-content`
Lưu nội dung bundle đã chỉnh sửa vào `dist/openapi-bundled.yaml`.

**Request body:** plain text (raw YAML string).

**Response:** `{ "ok": true }`

---

### `POST /jobs/{job_id}/relint`
Chạy lại Spectral + Redocly + build HTML **từ bundle hiện tại**, không bundle lại.

Dùng sau khi user chỉnh sửa bundle thủ công và muốn kiểm tra lại.

**Response:** cùng format với `/export`.

---

### `GET /jobs/{job_id}/download-html`
Trả về file `public/api-docs.html` để download.

**Response:** `FileResponse` với `Content-Disposition: attachment`.

---

## Luồng xử lý file — `process_file()`

Chạy trên thread pool (không block event loop):

```
1. Đặt status → "processing"
2. Load module config (action_names) từ 4.config/modules/{domain}.yaml
3. Tạo tempdir:
   ├── input/{filename}.docx   ← ghi file bytes
   ├── output/{stem}.yaml      ← pipeline ghi ra đây
   └── schemas/                ← schema files
4. Gọi pipeline_Ticket.run(input, output, schemas_dir, domain)
5. Nếu output tồn tại:
   ├── Đọc YAML → FileResult.yaml
   ├── Tính action_name từ method + path
   ├── Đọc schemas → FileResult.schemas
   └── status → "done"
6. Nếu không có output → status "error"
7. Exception bất kỳ → status "error", lưu traceback vào FileResult.error
```

---

## Hàm tiện ích

### `_compute_action_name(op, non_resource_actions)`

Tính tên file output từ HTTP method và URL path:

| Path | Method | Kết quả |
|---|---|---|
| `/v1/tickets` | GET | `list` |
| `/v1/tickets` | POST | `create` |
| `/v1/tickets/{id}` | GET | `detail` |
| `/v1/tickets/{id}` | PUT/PATCH | `update` |
| `/v1/tickets/{id}` | DELETE | `delete` |
| `/v1/tickets/search` | POST | `search` (nếu có trong non_resource_actions) |

Segment `v1` bị bỏ qua khi parse path.

---

### `_parse_redocly_output(result)`

Parse JSON output của Redocly CLI, xử lý 2 format:

```
Redocly v2:  { "totals": {...}, "problems": [...] }   → trả về problems[]
Older:       [{ "filePath": "...", "problems": [...] }] → gộp tất cả problems
```

Dùng `--silent` khi gọi npm để loại bỏ npm header khỏi stdout trước khi parse.

---

## CORS

Chỉ cho phép `http://localhost:3000`. Nếu frontend chạy ở port khác phải sửa:

```python
allow_origins=["http://localhost:3000"]
```

---

## Concurrency model

```
FastAPI (async event loop)
    │
    ├── SSE stream         → async generator, await asyncio.sleep(0.5)
    ├── export/relint      → subprocess.run() blocking — chạy trên event loop (⚠ có thể block)
    │
    └── process_file()     → executor.submit() → ThreadPoolExecutor (4 workers)
                             Pipeline chạy trên thread riêng, không block event loop
```

**Điểm chú ý:** `subprocess.run()` trong `/export` và `/relint` là blocking call chạy trực tiếp trên async handler — nếu nhiều người dùng export cùng lúc sẽ block lẫn nhau. Nên dùng `asyncio.to_thread()` hoặc `loop.run_in_executor()` để fix về sau.

---

## Thiếu sót hiện tại (Known Gaps)

| Vấn đề | Ghi chú |
|---|---|
| State chỉ trong RAM | Restart server mất toàn bộ job |
| Export hardcode `tickets` | Path `5.openapi/paths/tickets/` và `schemas/ticket/` không lấy từ config |
| `subprocess.run()` block event loop | Trong `/export` và `/relint` — cần wrap bằng `asyncio.to_thread()` |
| Không validate file type phía backend | Chỉ frontend filter `.docx`, backend nhận bất kỳ file gì |
| CORS chỉ cho `localhost:3000` | Dev frontend ở port khác (3001...) bị block |
| Không có auth | Bất kỳ ai biết `job_id` đều đọc/sửa được job |
| `flags` field chưa được populate | `FileResult.flags` luôn là `[]`, pipeline chưa ghi vào đây |
