# Kiến trúc Backend — API Converter

> Viết lại từ nội dung Backend trong `03_phan_tich_va_thiet_ke_he_thong.tex`, có sửa các điểm đã phát hiện sai lệch với code thật (bảng biến môi trường, số file trong `services/`). Mục tiêu: đọc xong hình dung được toàn bộ bức tranh Backend đang làm gì, không chỉ thuộc từng bảng riêng lẻ.

## 1. Backend là gì trong bức tranh tổng thể

Trước khi đi vào chi tiết, cần nắm 1 điều: **Backend không phải nơi chứa logic nghiệp vụ chính** — nó là lớp điều phối mỏng, đứng giữa Frontend và 2 thứ khác:

```
┌──────────┐   fetch / SSE    ┌───────────────┐   import thẳng    ┌──────────────┐
│ Frontend │ ───────────────▶ │   Backend     │ ─────────────────▶│   Pipeline   │
│ (Next.js)│ ◀─────────────── │   (FastAPI)   │ (cùng process,     │ (2.pipeline/)│
└──────────┘   JSON / SSE     └───────┬───────┘  không qua mạng)  └──────────────┘
                                       │
                                       │ đọc/ghi trực tiếp
                                       ▼
                        ┌─────────────────────────────┐
                        │ Filesystem                  │
                        │ 5.openapi/  dist/  4.config/│
                        │ 3.build/reports/             │
                        └─────────────────────────────┘
```

Điểm quan trọng nhất cần nhớ: **Backend "import thẳng" Pipeline như 1 thư viện Python bình thường, không gọi qua network.** `backend/core/config.py` làm việc này bằng cách chèn thư mục `2.pipeline/` vào `sys.path` lúc backend khởi động:

```python
PIPELINE_DIR = Path(__file__).parent.parent.parent / "2.pipeline"
sys.path.insert(0, str(PIPELINE_DIR))
```

Hệ quả 2 chiều:
- **Được:** không cần deploy Pipeline như 1 service riêng, không cần thêm 1 network call/1 điểm lỗi mạng nào — gọi `run_batch()` cũng như gọi 1 hàm Python bình thường.
- **Mất:** Backend và Pipeline bắt buộc phải sync version code với nhau — nếu ai đó sửa `2.pipeline/` (thuộc quyền teammate khác) mà đổi signature hàm, Backend hỏng ngay lập tức không cần deploy riêng gì cả để "kích hoạt" lỗi.

Một điểm tương tự nhưng ngược hướng: **Deploy tài liệu (UC12) không đi qua Backend FastAPI** — route deploy nằm ở Next.js server (`frontend/app/api/deploy-docs/route.ts`), gọi thẳng GitHub REST API. Nghĩa là logic nghiệp vụ của cả hệ thống hiện chia làm 2 nơi độc lập (Backend FastAPI xử lý phần convert/edit, Next.js server route xử lý phần deploy) — không có 1 "backend duy nhất" theo đúng nghĩa.

## 2. Một request đi qua bao nhiêu lớp

```
Request  →  routers/*.py  →  services/*.py  →  core/ + api_utils/
             (parse, gọi          (TOÀN BỘ         (hạ tầng dùng
              service,             logic nằm         chung, không
              return/raise)        ở đây)            biết gì về
                                                       nghiệp vụ)
```

Nguyên tắc cứng: **router không chứa logic.** Mở bất kỳ file nào trong `routers/` sẽ chỉ thấy 3 việc — nhận request, gọi 1 hàm trong `services/`, trả kết quả hoặc để exception tự bay lên. Toàn bộ quyết định (validate, đọc/ghi file, gọi Pipeline, gọi Claude API...) nằm trong `services/`.

Vì sao tách vậy: service function là 1 hàm Python thuần, không phụ thuộc FastAPI — test được độc lập, đọc được độc lập, không cần dựng cả server lên mới hiểu code làm gì. Router chỉ là "lớp vỏ" dịch giữa HTTP và Python function.

Cây thư mục thật (đã đếm lại chính xác):

```
backend/
├── main.py            FastAPI() + CORS + load_dotenv() + include_router() x3
├── core/               2 file
│   ├── config.py        hằng số đường dẫn, inject Pipeline vào sys.path
│   └── errors.py         ErrorCode (30 mã) + http_error()
├── api_utils/           3 file — helper KHÔNG biết gì về nghiệp vụ
│   ├── field_paths.py     mini-language địa chỉ field trong operation/schema
│   ├── yaml_io.py          load_yaml_cached() / dump_yaml_fast() — cache theo mtime file
│   └── yaml_line.py        đọc indent/key theo dòng, không parse AST — dùng cho ai_fix.py
├── routers/             2 file nghiệp vụ (+ health.py)
│   ├── health.py           1 endpoint
│   ├── modules.py          13 endpoint — luồng "đưa tài liệu vào hệ thống"
│   └── docs.py             12 endpoint — luồng "sửa & xuất tài liệu"
└── services/            11 file — toàn bộ business logic thật sự nằm ở đây
    ├── module_registry.py, upload.py, suggestions.py, import_jobs.py
    ├── docs_build.py, bundle_content.py, operations.py, schema_fields.py
    └── bundle_sync.py, manual_edit_conflicts.py, ai_fix.py
```

`backend/models/`, `backend/repositories/`, `backend/schemas/` cũng tồn tại trong cây thư mục nhưng **để trống có chủ đích** — dự tính cho 1 kiến trúc phân lớp đầy đủ hơn sau này (khi có DB thật), hiện chưa dùng.

## 3. Toàn cảnh 26 endpoint — nhìn theo luồng, không phải theo thứ tự file

Thay vì đọc 26 dòng liệt kê phẳng, dễ hình dung hơn nếu nhóm theo đúng thứ tự người dùng thao tác trên dashboard:

### Nhóm A — Đưa tài liệu vào & phân loại module (`routers/modules.py`, 13 endpoint)

```
upload → scan → suggest → duyệt gợi ý → apply → activate → import (SSE) → xử lý xung đột
```

| Bước trong luồng | Method + Path |
|---|---|
| Upload file nguồn | `POST /source/upload` |
| Quét thư mục nguồn | `GET /modules/scan` |
| Xem danh sách module + trạng thái | `GET /modules` |
| Chạy gợi ý module tự động | `POST /modules/suggest` |
| Xem gợi ý đang chờ duyệt | `GET /modules/suggestions` |
| Duyệt gợi ý | `POST /modules/suggestions/approve` |
| Copy file vào đúng thư mục module | `POST /modules/apply` |
| Kích hoạt / vô hiệu hóa module | `POST /modules/{module}/activate`, `POST /modules/{module}/deactivate` |
| Chạy Pipeline cho module active | `POST /modules/import` |
| Theo dõi tiến trình import | `GET /modules/import/{job_id}/stream` (SSE) |
| Xem / xử lý xung đột sửa tay khi import lại | `GET /modules/manual-edit-conflicts`, `POST /modules/manual-edit-conflicts/resolve` |

### Nhóm B — Sửa & xuất bản tài liệu (`routers/docs.py`, 12 endpoint)

```
build → xem lint → sửa (Form Editor / YAML thô / AI fix) → relint → tải HTML
```

| Bước trong luồng | Method + Path |
|---|---|
| Bundle + lint + build Swagger UI | `POST /docs/build` |
| Xem trạng thái build/lint gần nhất | `GET /docs/status` |
| Tải file HTML đã build | `GET /docs/download-html` |
| Đọc / ghi nội dung bundle thô | `GET /docs/bundle-content`, `PUT /docs/bundle-content` |
| Lint lại không build lại từ đầu | `POST /docs/relint` |
| Claude đề xuất patch sửa lỗi lint | `POST /docs/bundle/ai-fix` |
| Đọc / ghi summary-description (Form Editor) | `GET /docs/operations`, `PATCH /docs/operations` |
| Claude gợi ý mô tả cho field trống | `POST /docs/operations/ai-suggest` |
| Đọc / ghi schema field dạng cây | `GET /docs/schema-fields`, `PATCH /docs/schema-fields` |

Cộng thêm `GET /health` (health check) = **26 endpoint**, khớp đúng `1 (health) + 13 (modules) + 12 (docs)`.

## 4. Mọi lỗi trả về client đều đi qua đúng 1 điểm

`core/errors.py`'s `http_error(status_code, code, message)` — hàm này **tạo và trả về** (không tự raise) 1 `HTTPException`:

```python
def http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
```

FastAPI tự bọc `detail` vào key `"detail"` khi trả JSON, nên body thật sự client nhận luôn có dạng:

```json
{ "detail": { "code": "MODULE_NOT_ACTIVE", "message": "Module 'ticket' chưa active — hãy activate trước" } }
```

Frontend đọc đúng khớp shape này (`lib/api/client.ts`'s `parseErrorDetail()`) rồi map `code` qua bảng dịch tiếng Việt thân thiện hơn nếu có (`resolveErrorMessage()`) — hiện bảng này rỗng nên gần như luôn hiện nguyên `message` backend viết sẵn.

Toàn hệ thống chỉ dùng **4 mức status code** — không có 401/403/409:

| Status | Dùng khi | Ví dụ |
|---|---|---|
| 400 | Input sai/thiếu, YAML sai cú pháp | `MISSING_MODULE_FIELD`, `BUNDLE_INVALID_YAML` |
| 404 | Không tìm thấy resource | `MODULE_NOT_FOUND`, `BUNDLE_NOT_FOUND` |
| 500 | Lỗi nội bộ (pipeline, path-stub) | `PIPELINE_FAILED` |
| 502 | Gọi Claude API thất bại | `AI_CALL_FAILED` |

## 5. Vì sao chạy Pipeline lâu mà server không bị treo — 2 cơ chế khác nhau

Đây là phần hay bị hiểu nhầm là 1 cơ chế duy nhất, thực ra là 2, dùng cho 2 tình huống khác nhau:

**Cơ chế 1 — route `def` thường (không phải `async def`) + threadpool tự động của Starlette.** Dùng cho việc chạy 1 lần rồi trả kết quả ngay: `/docs/build`, `/docs/relint` — bên trong gọi `subprocess.run(["npm", "run", ...])` để chạy `redocly`/`spectral` (mất vài giây). FastAPI/Starlette thấy handler khai báo `def` thường thì tự động đẩy nó vào 1 thread pool riêng — request đó vẫn phải đợi xong mới có response, nhưng **cái đang đợi không phải event-loop thread**, nên các request khác (kể cả SSE của import đang chạy song song) không bị chặn.

**Cơ chế 2 — `ThreadPoolExecutor` riêng + dict RAM + SSE polling.** Dùng cho `/modules/import`, vì việc này lâu hơn nhiều và cần báo tiến trình real-time chứ không thể để client đợi trơ:

```python
executor = ThreadPoolExecutor(max_workers=4)          # sống suốt vòng đời process
import_jobs: dict[str, ImportJob] = {}                 # chỉ ở RAM
```

- `POST /modules/import` tạo `job_id`, giao việc cho `executor.submit()`, **trả `job_id` ngay** — không đợi import xong.
- Việc chạy Pipeline nằm trong 1 thread riêng của executor — không đụng event loop.
- Frontend mở `GET /modules/import/{job_id}/stream` (SSE) → mỗi 0.5s đọc lại state của `ImportJob` (đang được thread kia cập nhật dần) và phát event nếu có module vừa xong. Đây là **polling qua state dùng chung**, không phải push trực tiếp từ thread nền.
- `job_id` sống **chỉ trong RAM** — mất sạch khi backend restart; restart giữa lúc đang import thì không resume được, phải chạy lại từ đầu.
- Có dọn rác: job `done` quá 1 giờ (`JOB_TTL_SECONDS`) hoặc vượt 50 job lưu trữ (`MAX_STORED_JOBS`) thì bị xóa dần — job `running` không bao giờ bị dọn dù cũ.

## 6. Cấu hình & biến môi trường

Cần tách bạch 2 loại hay bị nhầm là 1 vì cùng nằm cạnh nhau trong `core/config.py`/`.env`:

**Biến môi trường thật — đọc từ OS lúc chạy** (`backend/.env`, load qua `load_dotenv()` trong `main.py`):

| Biến | Đọc ở đâu | Dùng để |
|---|---|---|
| `ANTHROPIC_API_KEY` | SDK `anthropic.Anthropic()` tự đọc | Auth gọi Claude API |
| `ANTHROPIC_BASE_URL` | SDK tự đọc | Trỏ qua gateway nội bộ thay vì `api.anthropic.com` |
| `ANTHROPIC_MODEL` | **Khai báo nhưng không có code nào đọc** | — model đang bị hardcode cứng `"cc/claude-sonnet-4-6"` ở `services/ai_fix.py` và `services/operations.py`, đổi giá trị biến này không có tác dụng gì |
| `ANTHROPIC_SMALL_FAST_MODEL` | **Khai báo nhưng không có code nào đọc** | tương tự trên |

> Lưu ý: `backend/.env.example` chỉ có đúng 4 biến trên. Không có biến `ANTHROPIC_AUTH_TOKEN` nào trong project — nếu tài liệu khác còn nhắc biến này thì đó là thông tin sai, cần sửa lại.

**Không phải env var — hằng số đường dẫn tính từ vị trí file** (`core/config.py`):

```python
PIPELINE_DIR = Path(__file__).parent.parent.parent / "2.pipeline"
OUTPUT_DIR   = ... / "5.openapi"
DIST_DIR     = ... / "dist"
CONFIG_DIR   = ... / "4.config"
SOURCE_DIR   = ... / "1.docs" / "source" / "api_contract"
```

5 hằng số này không đọc `os.environ`, không cấu hình được qua `.env` — đổi vị trí thư mục thì phải sửa code, không phải sửa `.env`.

## 7. Xác thực/phân quyền — không có

Không có `Authorization`, JWT, session, hay `Depends()` xác thực nào trong `routers/`, `core/`, `main.py`. CORS chỉ giới hạn origin (`allow_origins=["http://localhost:3000"]`, hardcode) — đây là kiểm soát nguồn gọi, không phải cơ chế xác thực người dùng. 4 mức status code toàn hệ thống (400/404/500/502) không có 401/403, khớp với việc không có tầng phân quyền nào được thiết kế.

Hợp lý với vai trò hiện tại: **tool nội bộ, chạy local, 1 người dùng/1 máy tại 1 thời điểm.** Nhưng đáng ghi rõ trong tài liệu để người đọc không tự hỏi có phải bị bỏ sót.

## 8. Validate input — không dùng Pydantic

Toàn bộ route nhận `dict = Body(...)` hoặc `list = Body(...)`, không có model nào khai báo shape trước. Validate làm thủ công bằng `if`/`.get()` ngay bên trong service, thiếu field thì tự `raise http_error(400, ...)`.

Đây là 1 hạn chế thật của hệ thống: input sai định dạng chỉ được bắt theo từng trường hợp cụ thể người viết code có nghĩ tới, không có 1 lớp chặn tự động từ đầu như Pydantic (tự trả `422` kèm chi tiết field nào sai, tự sinh schema cho Swagger docs). Rủi ro là dễ sót trường hợp biên so với validate khai báo qua schema chuẩn.

## 9. State sống ở đâu — cái gì mất khi restart

| Loại state | Nơi lưu | Sống qua restart? |
|---|---|---|
| Import job đang chạy | RAM (dict trong Backend) | **Không** |
| Danh sách/trạng thái module | `4.config/module_registry.yaml` | Có |
| Version file nguồn (để bỏ qua import không đổi) | `3.build/reports/file_versions.json` | Có |
| Lịch sử chạy pipeline | `3.build/reports/version_run_history.jsonl` | Có (append-only) |
| Gợi ý module chưa duyệt | `3.build/reports/import_suggestions.json` | Có |
| Xung đột sửa tay chưa xử lý | `3.build/reports/manual_edit_conflicts.json` | Có |

Chỉ đúng 1 loại state sống trong RAM — cũng là loại duy nhất mất khi restart. Mọi thứ còn lại đều ghi ra file, nên backend restart giữa chừng (trừ lúc đang import dở) không mất gì.

## 10. Tổng hợp giới hạn kiến trúc đáng lưu ý

- Backend & Pipeline bắt buộc cùng version code (import thẳng, không qua network) — sửa `2.pipeline/` sai signature là hỏng Backend ngay.
- Logic nghiệp vụ chia 2 nơi độc lập: Backend FastAPI (convert/edit) và Next.js server route (deploy) — không có 1 backend duy nhất.
- Import job sống trong RAM — restart giữa chừng là mất tiến trình, không resume được.
- Không có tầng validate schema tự động (Pydantic) — dễ sót input sai ở edge case.
- Không có xác thực/phân quyền — chấp nhận được với quy mô hiện tại, cần đánh giá lại nếu mở rộng nhiều người dùng.
- 2 biến `.env` (`ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`) khai báo nhưng không dùng — nên xóa khỏi `.env.example` hoặc sửa code để đọc chúng, tránh gây hiểu nhầm.
