# Backend — API Converter

## Tổng quan

FastAPI server (`backend/`, tách theo layer `routers/` → `services/` → `core/`/`utils/`) đóng vai trò trung gian giữa frontend và pipeline xử lý (`2.pipeline/`). Cung cấp 2 nhóm chức năng:

1. **Module workflow** — scan tài liệu nguồn, gợi ý module, duyệt, áp dụng, activate/deactivate, import theo module (dùng cho dashboard chính); kèm backup tự động + phát hiện xung đột với sửa tay khi import lại (xem mục **Persist sửa tay qua tầng 2**)
2. **Docs & Operations** — bundle, lint (Spectral/Redocly), build Swagger UI HTML, **form editor** chỉnh sửa summary/description (ghi đồng thời tầng 2 + tầng 3), **YAML thô** (sửa field bất kỳ, không giới hạn form editor), và 2 endpoint AI hỗ trợ (gợi ý mô tả còn trống, tự sửa lỗi lint)

> Nhóm "file-upload job" (`POST /jobs` và các endpoint con) đã bị **xóa** từ lâu — không có UI nào tạo job nên route không bao giờ được dùng tới.

Tất cả lỗi do backend tự raise đều đi qua `http_error()` → trả `detail: {code, message}` thay vì chuỗi thường (xem mục **Hệ thống mã lỗi**).

---

## Công nghệ

| Công nghệ                        | Vai trò                                                                                                                    |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **FastAPI**                      | Web framework, định nghĩa API endpoints                                                                                    |
| **Uvicorn**                      | ASGI server chạy FastAPI (`--reload` khi dev)                                                                              |
| `ThreadPoolExecutor` (4 workers) | Chạy job import module (blocking) trên thread riêng, tránh block event loop                                                |
| `subprocess`                     | Gọi npm scripts (Redocly bundle/lint, Spectral lint, build docs)                                                           |
| `pyyaml` (`import yaml`)         | Đọc/ghi `module_registry.yaml` và `dist/openapi-bundled.yaml` (tầng 3, không giữ format)                                   |
| `ruamel.yaml`                    | Round-trip YAML cho file tầng 2 (`5.openapi/paths/`, `components/schemas/`) — giữ comment/indent gốc khi ghi field sửa tay |
| `python-dotenv`                  | Load `backend/.env` (gitignored) — cần cho 2 endpoint AI gọi Claude qua gateway nội bộ                                     |
| `anthropic` SDK                  | Gọi Claude (`/docs/bundle/ai-fix`, `/docs/operations/ai-suggest`)                                                          |

---

## Cấu trúc

```
backend/
├── main.py                 # FastAPI() + CORS + load_dotenv + include_router() — không chứa route nào (~25 dòng)
├── core/
│   ├── config.py           # Hằng số đường dẫn + inject 2.pipeline vào sys.path + init_emitter (side-effect khi import)
│   └── errors.py           # ErrorCode (27 mã) + http_error() — hệ thống mã lỗi, dùng chung mọi router/service
├── utils/                  # Helper domain-agnostic, không có nghiệp vụ OpenAPI riêng
│   ├── field_paths.py      # Field-path mini-language (PathSegment, parse_path/format_path/get_value_at_path/set_value_at_path)
│   └── yaml_line.py        # Helper xử lý YAML theo dòng text (indent_of, extract_key, find_block_end) — dùng cho services/ai_fix.py
├── routers/                 # CHỈ parse request → gọi services.* → return/raise, không chứa business logic
│   ├── health.py           # GET /health
│   ├── modules.py          # Module workflow: scan/suggest/approve/apply/activate/deactivate/import + SSE + manual-edit-conflicts
│   └── docs.py              # Docs & Operations: build/lint/bundle-content/operations/ai-suggest/ai-fix
├── services/                 # Toàn bộ business logic nằm ở đây
│   ├── docs_build.py        # Build/lint/status/download-html — build_and_lint(), _parse_redocly_output(), _enrich_redocly_with_line_col()
│   ├── bundle_content.py    # Đọc/ghi tầng 3 (YAML thô) — read_bundle_content()/save_bundle_content()
│   ├── operations.py        # Form Editor — list_operations()/update_operations()/ai_suggest_operation()
│   ├── bundle_sync.py        # Engine diff-and-sync dùng chung — Change, diff_bundle(), sync_operation_fields(), sync_schema_fields()
│   ├── manual_edit_conflicts.py  # Phát hiện/duyệt xung đột — list_conflicts()/resolve_conflict() + helper import-time (_scan_manual_edits, _resolve_manual_edits_after_import)
│   ├── ai_fix.py             # run()/fix_bundle() — gọi Claude sửa lỗi lint theo batch patch
│   ├── module_registry.py    # scan_modules()/list_modules()/activate_module()/deactivate_module()
│   ├── upload.py             # save_uploaded_files() — validate filename/extension/size, chặn path traversal
│   ├── suggestions.py        # suggest-root workflow — get_suggestions()/suggest_modules()/approve_suggestions()/apply_suggestions()
│   └── import_jobs.py        # import_jobs dict, executor (ThreadPoolExecutor), ImportModuleResult/ImportJob, start_import()/stream_events()/_run_import_job()
├── models/, repositories/, schemas/  # Tồn tại nhưng CỐ Ý không dùng (xem mục Quy ước layer)
├── requirements.txt          # fastapi, uvicorn, python-dotenv, anthropic, ruamel.yaml, + deps parsing mà pipeline_API.py import trực tiếp
├── .env                       # Gitignored — biến cho gateway Claude nội bộ (xem dưới)
└── venv/                      # Python virtual environment riêng (khác .venv root)
```

### Quy ước layer

- **`routers/`**: chỉ parse request → gọi 1 hàm `services.*` → return/raise. Không có business logic trong route handler.
- **`services/`**: toàn bộ logic. Mỗi file sở hữu state/helper riêng của domain đó (ví dụ `import_jobs`/`executor` chỉ nằm trong `services/import_jobs.py`).
- **`core/`**: config + error infra dùng chung mọi nơi.
- **`utils/`**: helper domain-agnostic, không biết gì về nghiệp vụ OpenAPI.

`main.py` không bao giờ phình to thêm khi thêm route mới — chỉ cần thêm hàm vào router/service phù hợp hoặc tạo router mới + 1 dòng `include_router()`.

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

## Hằng số đường dẫn (`backend/core/config.py`)

```python
PIPELINE_DIR = project_root / "2.pipeline"
OUTPUT_DIR   = project_root / "5.openapi"
DIST_DIR     = project_root / "dist"
CONFIG_DIR   = project_root / "4.config"
SOURCE_DIR   = project_root / "1.docs" / "source" / "api_contract"
```

Tính từ `Path(__file__).parent.parent.parent` — 3 cấp lên (`core/` → `backend/` → gốc project). File này có side-effect khi import: inject `PIPELINE_DIR` vào `sys.path`, gọi `init_config()` của `generator.emitter` một lần. `main.py` import `core.config` đầu tiên (trước `routers`) để đảm bảo side-effect này chạy trước khi route nào trong `routers/modules.py`/`routers/docs.py` cần import từ `2.pipeline`.

---

## CORS

```python
allow_origins=["http://localhost:3000"]
```

Frontend chạy port khác phải sửa tay trong `main.py`.

---

## Hệ thống mã lỗi

Mọi lỗi backend tự raise dùng `http_error(status_code, code, message)` (`backend/core/errors.py`) thay vì
`HTTPException(status_code, detail="...")` trực tiếp:

```python
def http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
```

Response lỗi có shape `{"detail": {"code": "MODULE_NOT_FOUND", "message": "..."}}` — `code` là
định danh cố định để frontend map sang chữ hiển thị riêng (xem `docs/frontend.md`), `message` là
câu tiếng Việt gốc, dùng làm fallback khi frontend không override mã đó.

`class ErrorCode` định nghĩa 27 mã, gom theo nhóm chức năng (`SUGGEST_FAILED`, `MODULE_NOT_FOUND`,
`BUNDLE_NOT_FOUND`, `AI_CALL_FAILED`, `INVALID_CONFLICT_RESOLVE`, `CONFLICT_NOT_FOUND`...). Mọi
router/service đều `from core.errors import ErrorCode, http_error` — dùng chung 1 nguồn, không
định nghĩa riêng. Nhiều endpoint khác nhau dùng chung 1 mã khi cùng message (ví dụ `BUNDLE_NOT_FOUND`
dùng ở nhiều nơi: `bundle_content.py`, `operations.py`, `ai_fix.py`...).

**Lỗi 422 validation của FastAPI** (body thiếu field, sai type) không đi qua `http_error` — vẫn
giữ format gốc (`detail` là `list[{loc, msg, type}]`); frontend xử lý riêng cho trường hợp này
(fallback về `res.statusText`).

---

## Data Model

### Module import job (`services/import_jobs.py`)

```python
@dataclass
class ImportModuleResult:
    name: str
    status: Literal["pending", "running", "done", "error"] = "pending"
    total: int = 0; success: int = 0; failed: int = 0; skipped: int = 0; needs_review: int = 0
    error: str = ""

@dataclass
class ImportJob:
    job_id: str
    modules: list[ImportModuleResult] = field(default_factory=list)
    status: Literal["running", "done"] = "running"
    created_at: float = field(default_factory=time.time)
```

`import_jobs: dict[str, ImportJob]` là **in-memory only** — mất khi restart server. Không có database.

### Field-path mini-language (`utils/field_paths.py`)

Cú pháp dùng chung để địa chỉ hoá 1 field bất kỳ trong operation/schema, không giới hạn 1 danh sách field cố định:

| Cú pháp            | Ý nghĩa                         | Ví dụ                                  |
| ------------------ | ------------------------------- | -------------------------------------- |
| `a.b.c`            | key lồng nhau thường            | `responses.200.description`            |
| `key[selector]`    | index vào dict con theo key     | `responses[422].description`           |
| `key[field=value]` | tìm trong list theo match field | `parameters[name=user_id].description` |

`PathSegment` (dataclass) + 4 hàm: `parse_path` (chuỗi → list segment), `format_path` (ngược lại), `get_value_at_path`/`set_value_at_path` (đọc/ghi giá trị tại path, trả `(found, value)`/`bool` thành công). Dùng bởi `bundle_sync.py` (diff/sync) và `manual_edit_conflicts.py` (capture/compare).

### YAML line-position helpers (`utils/yaml_line.py`)

```python
def indent_of(line: str) -> int | None  # độ thụt lề, None nếu dòng trống/comment
def extract_key(line: str) -> str       # tên key của 1 dòng YAML (bỏ "- " và phần value)
def find_block_end(lines: list[str], start_line: int) -> int  # dòng kết thúc của 1 block, dựa vào indent
```

Xử lý YAML ở mức **text/dòng** (không parse AST) — dùng khi cần định vị 1 đoạn theo số dòng (line/column từ Spectral/Redocly) thay vì theo cấu trúc dict đã parse. Dùng bởi `services/ai_fix.py`.

---

## Endpoint — Module Workflow

| Method | Path                                     | Mô tả                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------ | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/modules/scan`                          | Scan `1.docs/source/api_contract/`, trả về modules đã có file + file chưa gán module                                                                                                                                                                                                                                                                                                                                            |
| `GET`  | `/modules`                               | List module từ `module_registry.yaml` (status, file_count, endpoint_count, last_import)                                                                                                                                                                                                                                                                                                                                         |
| `POST` | `/source/upload`                         | Upload file thô vào `SOURCE_DIR` (chưa convert, chỉ lưu). Validate: tên file flatten về basename (chặn path traversal `../` và absolute path), `.`/`..` literal bị từ chối (`INVALID_FILENAME`), extension phải nằm trong whitelist `import_flow.yaml` (`UNSUPPORTED_FILE_TYPE`), size tối đa 20MB (`FILE_TOO_LARGE`)                                                                                                           |
| `GET`  | `/modules/suggestions`                   | Đọc `import_suggestions.json` (nếu có)                                                                                                                                                                                                                                                                                                                                                                                          |
| `POST` | `/modules/suggest`                       | Chạy `cmd_suggest_root()` (qua `2.pipeline`) — phân tích file, gợi ý module cho từng endpoint                                                                                                                                                                                                                                                                                                                                   |
| `POST` | `/modules/suggestions/approve`           | Duyệt suggestion — `mode`: `"all"` / `"module"` / `"file"`, có `override_module`                                                                                                                                                                                                                                                                                                                                                |
| `POST` | `/modules/apply`                         | Copy file đã duyệt vào `1.docs/source/api_contract/<module>/`. Bỏ qua file đã tồn tại đích (`target_file_exists`) hoặc chưa duyệt (`not_approved`)                                                                                                                                                                                                                                                                              |
| `POST` | `/modules/{module}/activate`             | draft/deprecated → active                                                                                                                                                                                                                                                                                                                                                                                                       |
| `POST` | `/modules/{module}/deactivate`           | active → deprecated                                                                                                                                                                                                                                                                                                                                                                                                             |
| `POST` | `/modules/import?module=<name>`          | Backup `5.openapi/paths/<module>` + `schemas/<module>` vào `3.build/backups/`, chụp lại field đã sửa tay (`x-manual-edit-fields`) của module đó, rồi chạy `run_batch()` theo từng module active (hoặc tất cả module active nếu không truyền `module`). Sau khi `run_batch()` xong, so sánh lại field đã chụp — field bị pipeline đổi giá trị → ghi vào hàng đợi xung đột (xem mục **Persist sửa tay qua tầng 2**). Trả `job_id` |
| `GET`  | `/modules/import/{job_id}/stream`        | SSE — emit khi 1 module xong (chỉ emit lúc transition khỏi `running`, **không** stream per-file)                                                                                                                                                                                                                                                                                                                                |
| `GET`  | `/modules/manual-edit-conflicts`         | Đọc `3.build/reports/manual_edit_conflicts.json` (`[]` nếu chưa có file) — danh sách field bị conflict giữa sửa tay và lần import gần nhất                                                                                                                                                                                                                                                                                      |
| `POST` | `/modules/manual-edit-conflicts/resolve` | Body `{operationId, field, choice: "keep_old"\|"accept_new"}`. `keep_old` ghi giá trị cũ trở lại cả tầng 2 + tầng 3 (qua `sync_operation_fields()`, cùng cơ chế dual-write dùng cho Form Editor/YAML thô); `accept_new` không đổi gì (giá trị mới đã có sẵn từ import). Cả 2 case xoá entry khỏi hàng đợi. 400 `INVALID_CONFLICT_RESOLVE` nếu payload sai, 404 `CONFLICT_NOT_FOUND` nếu entry không còn                         |

**Lưu ý activate/deactivate:** route `POST /modules/{module}/activate` không xung đột với `POST /modules/import` vì FastAPI match theo path segment — `import` (2 segments) khác `{module}/activate` (3 segments).

**Job pruning** (`_prune_old_jobs()`, gọi trước khi tạo job mới): job `done` quá `JOB_TTL_SECONDS` (1 giờ) hoặc khi tổng số job vượt `MAX_STORED_JOBS` (50) sẽ bị xoá khỏi `import_jobs` — tránh phình RAM vô hạn nếu `/modules/import` bị gọi liên tục. Job `running` không bao giờ bị xoá dù cũ. `_run_import_job()` bọc toàn bộ xử lý trong `try/finally` để đảm bảo `job.status` luôn về `"done"` dù lỗi xảy ra ở bất kỳ đâu — thiếu `try/finally` này thì job kẹt mãi ở `"running"`, SSE treo vô hạn và `_prune_old_jobs()` không dọn được job đó.

---

## Endpoint — Docs & Operations

| Method       | Path                          | Mô tả                                                                                                                                                                                                                                                                                                                                                              |
| ------------ | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `POST`       | `/docs/build`                 | Bundle (`npm run bundle:api`) → Spectral lint → Redocly lint → build HTML (`npm run build:docs`)                                                                                                                                                                                                                                                                   |
| `GET`        | `/docs/status`                | `{ bundle_ready, html_ready }` — chỉ check file tồn tại trên đĩa                                                                                                                                                                                                                                                                                                   |
| `GET` `/PUT` | `/docs/bundle-content`        | Đọc/ghi `dist/openapi-bundled.yaml` plain text (tầng 3). `PUT` so sánh nội dung mới với cũ (`diff_bundle()`), đồng bộ field thay đổi xuống tầng 2 qua `sync_operation_fields()` + `sync_schema_fields()`, rồi mới ghi đè tầng 3 verbatim (giữ nguyên format người dùng vừa sửa, không re-serialize)                                                                |
| `POST`       | `/docs/relint`                | Lint lại + build HTML từ bundle hiện tại, không bundle lại                                                                                                                                                                                                                                                                                                         |
| `GET`        | `/docs/download-html`         | Download `public/api-docs.html`                                                                                                                                                                                                                                                                                                                                    |
| `GET`        | `/docs/operations`            | Parse bundle, trả về list operations: `{operationId, method, path, tags, summary, description, parameters[], responses[]}` — dùng cho Form Editor. `parameters`/`responses` loại trừ entry `$ref`'d (tránh 1 operation sửa ảnh hưởng operation khác dùng chung `$ref`)                                                                                             |
| `PATCH`      | `/docs/operations`            | Nhận `list[{operationId, summary?, description?, parameters?, responses?}]`, áp update vào bản copy bundle, `diff_bundle()` so với bản gốc rồi `sync_operation_fields()` ghi đồng thời tầng 2 + tầng 3 — chỉ field mô tả (summary/description + `parameters[].description` + `responses[].description` không `$ref`), không đụng path/method/schema/response codes |
| `POST`       | `/docs/operations/ai-suggest` | Gọi Claude gợi ý summary/description/parameter & response description cho 1 operation — **chỉ điền field đang trống**, không ghi đè field đã có nội dung                                                                                                                                                                                                           |
| `POST`       | `/docs/bundle/ai-fix`         | Gọi Claude sửa theo batch các đoạn YAML lỗi (Spectral/Redocly hiện có). Trả `{patches, unresolved, failed}` để hiển thị diff trong `AiFixPanel` — **không tự ghi xuống đĩa**, dev review từng patch (giữ gốc/giữ bản sửa/giữ cả hai) rồi bấm "Áp dụng" → frontend gọi `PUT /docs/bundle-content` ngay (đã đồng bộ cả tầng 2+3, xem trên)                           |

**`build_and_lint(project_root, do_bundle)`** (`services/docs_build.py`) là hàm core dùng chung bởi `/docs/build` và `/docs/relint`. Trả về:

```json
{
  "bundle_ready": true,
  "html_ready": true,
  "spectral": [ { "code", "severity", "message", "path", "range" } ],
  "redocly":  [ { "ruleId", "severity", "message", "location" } ]
}
```

**Vùng an toàn khi PATCH operations (Form Editor):** chỉ `summary`, `description`, `parameters[].description`, `responses[].description` (không `$ref`). Không cho sửa `path`, `method`, parameter name/type/schema, `requestBody` schema, response codes, `$ref`, `servers`, `security` — các field này client/SDK dùng trực tiếp, sửa sai sẽ break consumer. **Tab YAML thô** (`PUT /docs/bundle-content`) thì không giới hạn field nào — sửa được bất kỳ field nào qua field-path generic, đổi lại là validate ít chặt hơn (chỉ check YAML hợp lệ, không check "vùng an toàn").

### AI-fix — breadcrumb + parent context cho prompt (`services/ai_fix.py`)

Mỗi đoạn lỗi gửi cho Claude trong `_build_batch_prompt()` được annotate thêm 2 trường tính bởi `utils/yaml_line.py`:

- **`_get_breadcrumb(lines, target_line)`** — đường dẫn khóa từ root tới dòng lỗi (vd `paths./tickets/{id}.get.responses.200...properties.status.description`), cho Claude biết chính xác field này thuộc operation/schema nào.
- **`_get_parent_block(lines, target_line)`** — block của entity cha **2 cấp** trên dòng lỗi (vd toàn bộ `properties:` chứa cả field đang sửa lẫn sibling khác), cho Claude thấy field cạnh bên để viết `summary`/`description` nhất quán thay vì chỉ phán đoán từ 1 đoạn cô lập.

Lý do thêm: trước đây prompt chỉ gửi `original_text` (đúng đoạn lỗi) + danh sách issue — khi 1 lượt AI-fix sửa nhiều lỗi "thiếu description" cho nhiều operation cùng lúc, Claude từng sinh mô tả chung chung/sai nghiệp vụ do thiếu ngữ cảnh (xem `docs/manual-test-checklist.md` mục Defect Log, DEF-04). 2 hàm này được unit-test (xem mục Execution Log của checklist đó), nhưng **chưa verify end-to-end** đã giải quyết DEF-04 hay chưa.

---

## Persist sửa tay qua tầng 2 + backup + review xung đột khi reimport

Trước đây Form Editor (`PATCH /docs/operations`) chỉ ghi vào `dist/openapi-bundled.yaml` (tầng 3)
— bấm "Build tài liệu" sinh lại bundle từ `5.openapi/paths/<module>/*.yaml` (tầng 2) sẽ làm mất hết
nội dung đã sửa tay. Tính năng này (4 phần) giải quyết việc đó, và sau đó được generic-hoá để dùng chung cho cả YAML thô và AI-fix:

**Phần 1 — Diff-and-sync engine dùng chung (`services/bundle_sync.py`)**

`diff_bundle(old_bundle, new_bundle)` so sánh 2 bundle (theo `operationId` cho operation, theo tên cho schema), đệ quy qua mọi field ở bất kỳ độ sâu (`_diff_recursive`, có xử lý riêng cho `parameters`/`responses` để match đúng phần tử trong list), trả về list `Change(kind, key, path, new_value)`. Marker `x-manual-edit-fields` (key đặc biệt) bị loại trừ khỏi diff — nó là bookkeeping nội bộ, không phải field user sửa (xem bug đã fix bên dưới).

`sync_operation_fields()`/`sync_schema_fields()` áp list `Change` vào cả tầng 3 (node trong bundle đang xử lý) và tầng 2 (đúng file fragment tương ứng, ghi bằng **ruamel.yaml round-trip** để giữ format/comment gốc), gắn/merge marker `x-manual-edit-fields` ở cả 2 nơi (`_merge_marker()` — list field-path, union qua nhiều lần sửa, không mất field cũ).

Marker giờ là **list field-path tổng quát** (`["description", "responses[422].description", ...]`), không còn dict cố định 4 field như thiết kế ban đầu — sửa được field bất kỳ (tab YAML thô, AI-fix) chứ không giới hạn 4 field của Form Editor.

3 nơi dùng chung 1 engine này: `services/operations.py` (Form Editor), `services/bundle_content.py` (YAML thô + AI-fix, vì AI-fix ghi qua `PUT /docs/bundle-content`), `services/manual_edit_conflicts.py` (resolve conflict).

**Phần 2 — Backup + capture/compare khi import lại (`services/import_jobs.py`, `services/manual_edit_conflicts.py`)**

Trước khi `run_batch()` chạy cho 1 module:

1. `shutil.copytree` sao lưu `5.openapi/paths/<module>` + `schemas/<module>` vào
   `3.build/backups/openapi_<module>_<timestamp>/` (tên folder theo giây — xem DEF-01 trong checklist).
2. `_scan_manual_edits(paths_dir)` quét toàn bộ operation có marker `x-manual-edit-fields`, chụp lại
   giá trị hiện tại của từng field đã đánh dấu (`captured`).

Sau khi `run_batch()` chạy xong (pipeline có thể đổi file, hoặc skip nếu version doc không đổi),
`_resolve_manual_edits_after_import()` quét lại lần 2, so giá trị mới với `captured`:

- Giá trị không đổi → giữ field trong marker.
- Field không còn tồn tại (tham số/response bị xoá) → bỏ field khỏi marker, không tính là conflict.
- Giá trị bị pipeline đổi khác → bỏ field khỏi marker (giá trị mới được giữ, **không** tự ghi đè
  ngược) và đẩy 1 entry vào `3.build/reports/manual_edit_conflicts.json`.

**Phần 3 — API review xung đột**

`GET /modules/manual-edit-conflicts` trả nguyên nội dung file JSON trên (`[]` nếu chưa có).
`POST /modules/manual-edit-conflicts/resolve` cho chọn `keep_old` (ghi giá trị cũ lại vào cả tầng 2 +
tầng 3, tái dùng `sync_operation_fields()` từ `bundle_sync.py`) hoặc `accept_new` (không đổi gì, giá
trị mới từ pipeline đã có sẵn). Cả 2 case xoá entry khỏi hàng đợi.

**Phần 4 — `ManualEditConflictsCard` (frontend)** — xem `docs/frontend.md`.

**2 bug đã biết, ghi nhận nhưng chưa fix** (xem `docs/manual-test-checklist.md` Phần C — Defect Log, DEF-01 và DEF-02 để biết cách tái hiện):

1. Backup dùng tên folder theo giây — import 2 lần cùng module trong vòng 1 giây làm `shutil.copytree` lần 2 ném `FileExistsError`, bị `try/except` nuốt im lặng, backup lần thứ 2 không được tạo.
2. `POST /modules/manual-edit-conflicts/resolve` với `choice: "keep_old"` cho 1 `operationId` đã biến mất hoàn toàn (không còn ở cả bundle và tầng 2) vẫn trả `200 {"ok": true}` y như thành công, nhưng không ghi gì — entry vẫn bị xoá khỏi hàng đợi, mất khả năng khôi phục từ UI.

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
    └── start_import() (services/import_jobs.py) → executor.submit(_run_import_job) → ThreadPoolExecutor riêng (4 workers)
```

---

## Thiếu sót hiện tại (Known Gaps)

| Vấn đề                                                         | Ghi chú                                                                                                                                                                                                                                                                            |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| State chỉ trong RAM                                            | Restart server mất toàn bộ `import_jobs`                                                                                                                                                                                                                                           |
| Không validate file type phía backend trước khi convert        | `upload.py` đã validate extension/size khi nhận file thô; pipeline convert vẫn tin nội dung file                                                                                                                                                                                   |
| CORS chỉ cho `localhost:3000`                                  | Dev frontend port khác bị block                                                                                                                                                                                                                                                    |
| Không có auth                                                  | Dashboard mở public trong mạng nội bộ                                                                                                                                                                                                                                              |
| Không có publish/deploy tự động                                | Tải HTML thủ công, chưa có nút commit+push lên git                                                                                                                                                                                                                                 |
| AI-fix (`/docs/bundle/ai-fix`) chỉ trả patch, không tự ghi đĩa | Dev phải tự bấm "Áp dụng" trong `AiFixPanel` để lưu (qua `PUT /docs/bundle-content`, đã đồng bộ tầng 2+3) — cố tình không tự ghi ngay vì AI-fix có thể sửa cả path/schema/$ref nên rủi ro cao hơn Form Editor                                                                      |
| Chất lượng output AI-fix khi batch nhiều operation             | DEF-04 (`docs/manual-test-checklist.md`) — AI từng sinh description sai nghiệp vụ khi fix dồn nhiều operation 1 lượt. Đang thử fix bằng breadcrumb/parent context (xem mục AI-fix ở trên), chưa verify end-to-end                                                                  |
| 2 bug nhẹ ở tính năng persist sửa tay qua tầng 2 (chưa fix)    | (1) backup trùng tên folder nếu import cùng module 2 lần trong 1 giây; (2) resolve `keep_old` cho `operationId` đã biến mất hoàn toàn vẫn trả `200` giả thành công. Xem `docs/manual-test-checklist.md` Phần C, DEF-01/DEF-02                                                      |
| `5.openapi/openapi.yaml` thiếu `$ref` cho 1 số module          | Chỉ `ticket` được wire vào `paths:` — tài liệu cuối (`dist/openapi-bundled.yaml`) không thấy `service`/`department`/`statistic` dù đã import. Sửa phải động tới `2.pipeline` (ngoài phạm vi cho phép hiện tại của backend/frontend) — **chưa triển khai, đang chờ thảo luận thêm** |

---

## Lịch sử thay đổi đáng chú ý

**Tách `main.py` (854 dòng) thành nhiều file theo domain** — `main.py` giờ chỉ còn ~25 dòng:
tạo `FastAPI()`, CORS, `load_dotenv()`, `include_router()`. Đợt đầu tách thành `config.py`,
`errors.py`, `routers/*` ở root `backend/`; đợt sau tách tiếp thành layer `core/`/`services/`/`utils/`
như hiện tại — mỗi router chỉ còn gọi vào 1 hàm `services.*`, không business logic trong route nữa.

**Đã xóa nhóm endpoint `/jobs/*`** (12 endpoint cũ, upload đơn lẻ) cùng `FileResult`, `Job`
dataclass, `jobs: dict` storage — không có UI nào gọi `POST /jobs` để tạo job, dashboard chính dùng
`/source/upload` + `/modules/import` thay thế hoàn toàn.

**Vá bảo mật upload + chống phình RAM**: `/source/upload` validate filename (chặn path traversal,
absolute path, `.`/`..` literal), extension whitelist, cap size 20MB. `import_jobs` có
`_prune_old_jobs()` (TTL 1 giờ, tối đa 50 job) + `_run_import_job()` bọc `try/finally` để job không
kẹt mãi ở `"running"`.

**Persist sửa tay qua tầng 2 + backup + review xung đột**: Form Editor ghi đồng thời tầng 2 (giữ qua
"Build tài liệu") + tầng 3, mỗi lần import có backup tự động và phát hiện xung đột nếu giá trị sửa
tay bị pipeline ghi đè, kèm UI review để chọn giữ bản cũ hay lấy bản mới.

**Đồng bộ tầng 2+3 cho AI-fix/YAML thô + generic-hoá marker**: fix bug chính — `PUT
/docs/bundle-content` (YAML thô + AI-fix) trước đây chỉ ghi tầng 3, mất khi "Build tài liệu" chạy
lại. Viết `utils/field_paths.py` (field-path mini-language dùng chung), tách `services/bundle_sync.py`
(diff/sync engine) và `services/manual_edit_conflicts.py` ra khỏi router. Marker `x-manual-edit-fields`
đổi từ dict cố định 4 field sang list field-path tổng quát (bất kỳ field nào). 1 bug phát hiện và fix
ngay trong lúc test: marker tự tham chiếu chính nó khi diff (đã loại trừ key marker khỏi `_diff_recursive`).

**Breadcrumb + parent context cho prompt AI-fix**: tách `utils/yaml_line.py` (line-position YAML
helper dùng chung, trước đó định nghĩa local trong `ai_fix.py`), thêm `_get_breadcrumb()`/
`_get_parent_block()` để mỗi đoạn lỗi gửi Claude có thêm ngữ cảnh vị trí + entity cha — hướng giải
quyết DEF-04 (chất lượng description khi batch nhiều operation), chưa verify end-to-end.
