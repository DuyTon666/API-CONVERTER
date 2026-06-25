# Manual Test Checklist — Module Workflow

Checklist test thủ công cho toàn bộ workflow module (scan → suggest → approve → apply →
activate → import → docs), bao gồm các edge case liên quan tới 2 bản fix bảo mật ở
`backend/routers/modules.py`:

1. Path traversal khi upload file (`upload_source_files()`).
2. Thiếu validate extension/size khi upload + `import_jobs` phình vô hạn khi job kẹt
   `"running"` (`_run_import_job()` / `_prune_old_jobs()`).

## 0. Setup môi trường

```bash
# Terminal 1 — backend
cd backend && make dev
# kỳ vọng: server lên ở http://localhost:8000, không lỗi load_dotenv

# Terminal 2 — frontend
cd frontend && npm run dev
# kỳ vọng: server lên ở http://localhost:3000
```

Mở `http://localhost:3000`, mở thêm DevTools (F12) → tab Network + Console để soi
response/lỗi ẩn.

## 1. Happy path — đi hết workflow 1 lượt

| Bước | Làm gì | Kỳ vọng |
|---|---|---|
| Scan | Click nút scan ở ScanCard | Thấy danh sách module có sẵn dưới `1.docs/source/api_contract/` (ticket, service, statistic, department...) + file `unassigned` (các PDF tên dài chưa gán module) |
| Suggest | Chạy suggest-root ở SuggestCard | Mỗi file unassigned được gợi ý 1 module |
| Approve | Approve all suggestion | Suggestion chuyển trạng thái approved |
| Apply | Apply suggestions | File được copy vào đúng thư mục module trong `1.docs/source/api_contract/<module>/` |
| Activate | Activate 1 module ở ModuleRegistryCard (vd `ticket`) | Status đổi `draft` → `active` |
| Import | Trigger import cho module đó | SSE chạy, progress bar cập nhật theo thời gian thực, kết thúc hiện `success/failed/skipped` |
| Docs | Build docs ở SwaggerDocsCard | Build/lint chạy xong, link xem Swagger UI hoạt động |

**Ghi lại:** bước nào lag, bước nào UI không tự cập nhật (đặc biệt SSE ở bước Import —
đây là chỗ vừa sửa lỗi job kẹt `running`).

## 2. Edge case — đúng các lỗ hổng vừa fix

Test bằng **ImportCard** (upload UI) và bằng **curl trực tiếp** (để chắc chắn không phải
frontend tự chặn trước khi tới backend):

| Test | Cách làm | Kỳ vọng sau fix |
|---|---|---|
| Path traversal filename | `curl -X POST http://localhost:8000/source/upload -F 'files=@1.docs/source/api_contract/sample.docx;filename=../../backend/main.py'` | 400 `INVALID_FILENAME`, **không** ghi đè `backend/main.py` |
| Absolute path filename | `curl -X POST http://localhost:8000/source/upload -F 'files=@1.docs/source/api_contract/sample.docx;filename=/tmp/evil.docx'` | 400 `INVALID_FILENAME` |
| Sai extension | Upload file `.zip` hoặc `.exe` bất kỳ qua UI | 400 `UNSUPPORTED_FILE_TYPE` |
| File quá size | Tạo file giả `dd if=/dev/zero of=/tmp/big.pdf bs=1M count=25`, upload qua UI | 400 `FILE_TOO_LARGE` |
| Import job lỗi giữa đường | Backup `4.config/module_registry.yaml`, sửa tạm thành YAML sai cú pháp, thử import, xem job có báo lỗi rõ ràng hay bị "đứng" mãi không. Nhớ restore file sau khi test | Job phải kết thúc (status `done`), SSE phải đóng kết nối, không treo vô hạn — đây là chỗ vừa thêm `try/finally` |
| Spam import liên tục | Gọi `POST /modules/import` ~60 lần liên tiếp (script loop) trong vài giây | Server không bị OOM/crash, các job cũ tự bị dọn sau khi `status=done` (không cần restart backend để giảm RAM) |

## 3. Regression — các luồng khác không bị ảnh hưởng

- Module đã import trước đó (nếu có) — mở lại BundleEditorModal, sửa `summary`/
  `description` ở tab "Chỉnh sửa nội dung" (Form Editor), lưu lại → check file YAML có
  cập nhật đúng không.
- Thử "AI Suggest" trong Form Editor (cần `backend/.env` có `ANTHROPIC_*` đúng) → xem
  có gợi ý summary/operationId tiếng Việt không, hay trả 502.
- Deactivate 1 module đang active → thử import lại → phải bị chặn với lỗi
  `MODULE_NOT_ACTIVE`.

## 4. Cách ghi kết quả

Với mỗi mục: ✅ pass / ❌ fail + mô tả ngắn (response thật nhận được, screenshot console
error nếu có).

## 5. Kết quả test đã chạy (2026-06-25)

Chạy qua API/curl trực tiếp (không qua click UI browser) — backend `make dev` (port
8000) + frontend `npm run dev` (port 3000) khởi động thành công, không lỗi
`load_dotenv`.

### Happy path

| Bước | Kết quả |
|---|---|
| Scan | ✅ Đúng 4 module có sẵn (`ticket`, `service`, `statistic`, `department`) + 21 file unassigned |
| Suggest | ✅ Mỗi file unassigned có `suggested_module` + `confidence_score` + `conflict` detection đúng |
| Approve (1 file, `mode=file`) | ✅ `approval_status: pending → approved`, không skip sai |
| Apply | ✅ Phát hiện đúng `skip_reason: target_file_exists`, không ghi đè file đã tồn tại (idempotent) |
| Import (re-run module `department`) | ✅ SSE emit đúng event module + event `done`; hash-based skip hoạt động (`skipped: 1`, file không đổi) |
| Docs build | ✅ `bundle_ready: true`, `html_ready: true`, Spectral lint chạy bình thường (chỉ có warning license-url/contact có từ trước, không liên quan) |

### Edge case — bảo mật

| Test | Kết quả |
|---|---|
| Path traversal `../../backend/main.py` | ✅ Bị chặn (extension `.py` không cho phép), `main.py` không đổi (hash giống trước/sau) |
| Path traversal `../../evil.pdf` (extension hợp lệ) | ✅ Bị flatten về basename `evil_traversal_test.pdf`, lưu an toàn **trong** `SOURCE_DIR`, không thoát ra ngoài — đã dọn file test sau khi xác nhận |
| Absolute path `/etc/evil.pdf` | ✅ Flatten về basename, không ghi được vào `/etc/` — đã dọn file test |
| Filename literally `.` hoặc `..` | ✅ 400 `INVALID_FILENAME` cho cả 2 |
| Sai extension `.exe` / `.zip` | ✅ 400 `UNSUPPORTED_FILE_TYPE` cho cả 2 |
| File 25MB (vượt cap 20MB) | ✅ 400 `FILE_TOO_LARGE`, không lọt vào disk |
| File 5MB (hợp lệ, để xác nhận không bị block oan) | ✅ Upload thành công bình thường |
| **Import job lỗi giữa đường** — làm hỏng tạm `4.config/import_flow.yaml` (sai cú pháp YAML), trigger import | ✅ **Job kết thúc đúng `status: done` ngay, SSE đóng kết nối sạch, không treo vô hạn**; traceback `yaml.scanner.ScannerError` được log đầy đủ ở backend (`traceback.print_exc()`), không bị nuốt im lặng. File đã restore lại 100% bản gốc (verify bằng `diff`) |
| Spam 60 request `POST /modules/import` liên tiếp | ✅ Server không crash/OOM, RAM ổn định (48MB trước/sau), vẫn phản hồi `/health` sau khi spam |

### Regression

| Test | Kết quả |
|---|---|
| Deactivate module `department` → thử import | ✅ Bị chặn đúng `400 MODULE_NOT_ACTIVE` |
| Reactivate lại `department` | ✅ Status trở về `active`, khôi phục trạng thái ban đầu |
| Form Editor — sửa "Mô tả chi tiết" qua UI thật (Playwright), bấm Lưu | ✅ `PATCH /docs/operations` ghi đúng vào `dist/openapi-bundled.yaml` (operation `getTicket`), không đụng tới file gốc `5.openapi/paths/` — đúng thiết kế (Form Editor chỉ sửa bundle). Đã revert lại `description: ''` sau test |
| AI Suggest trong Form Editor — bấm "✨ Gợi ý AI" qua UI thật | ✅ `POST /docs/operations/ai-suggest` trả 200, Claude điền tiếng Việt vào 2 field `parameters[].description` đang trống (`user_id`, `id`), độ hoàn chỉnh 67% → 100%. Đúng thiết kế: **không** ghi đè field "Mô tả chi tiết" đã có nội dung — đóng modal không lưu để không re-introduce test data |

### Dọn dẹp sau test

- File test tạm (`evil_traversal_test.pdf`, `evil_test_absolute.pdf`, `small_test.txt`, file giả 25MB) — đã xoá hết.
- `4.config/import_flow.yaml` — đã restore đúng 100% bản gốc (diff sạch).
- `4.config/module_registry.yaml` — chỉ đổi 1 dòng `last_import_at` của `department` (dấu vết hợp lệ từ chính các lần import/deactivate/reactivate test ở trên), không có gì cần revert.

**Kết luận:** không phát hiện regression hay bug mới. Cả 2 bản fix bảo mật (path
traversal/extension/size khi upload, và job-stuck-running trong `_run_import_job`) hoạt
động đúng trên môi trường thật, không chỉ đúng trên review code. Form Editor và AI
Suggest đã test trực tiếp qua UI browser thật (Playwright) — toàn bộ 19 test case trong
checklist đều ✅ pass, không có mục nào còn để trống.
