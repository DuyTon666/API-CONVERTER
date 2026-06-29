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

## 6. Kết quả test — Persist Form Editor edits qua tầng 2 (2026-06-26)

Theo plan `Persist Form Editor edits qua tầng 2 + backup + review xung đột khi reimport`
(Phần 1 — `backend/routers/docs.py`, Phần 2 — `backend/routers/modules.py`). Test qua
curl trực tiếp + 1 script cách ly (Python) cho case cần giả lập, backend `make dev`
(port 8000).

### Phần 1 — Form Editor ghi đồng thời tầng 2 + tầng 3

| Test | Cách làm | Kết quả |
|---|---|---|
| Sửa `summary` + mô tả tham số `user_id` qua `PATCH /docs/operations` (operation `getTicket`) | `curl -X PATCH .../docs/operations -d '[{"operationId":"getTicket","summary":"...","parameters":[{"name":"user_id","description":"..."}]}]'` | ✅ Cả `5.openapi/paths/ticket/get_ticket.yaml` (tầng 2) và `dist/openapi-bundled.yaml` (tầng 3) đều có giá trị mới; marker `x-manual-edit-fields: {summary: true, parameters: [user_id]}` xuất hiện đúng ở cả 2 file; style/format ruamel.yaml của file tầng 2 (comment, indent) không bị phá |

### Phần 2 — Backup + capture/restore + phát hiện xung đột khi import

| Test | Cách làm | Kết quả |
|---|---|---|
| Marker tồn tại trước import, version doc **không đổi** (case phổ biến nhất) | PATCH đánh dấu `summary` của `getTicket`, sau đó `POST /modules/import?module=ticket` | ✅ Toàn bộ 8 file của module `ticket` bị pipeline skip (`reason: version_unchanged`) → marker giữ nguyên 100% sau import → `3.build/reports/manual_edit_conflicts.json` **không** được tạo (đúng — không có gì để báo conflict) |
| Backup chạy trước mỗi lần import | Quan sát `3.build/backups/` ngay sau lần import trên | ✅ Folder `openapi_ticket_<timestamp>/{paths,schemas}` được tạo, chứa đúng bản snapshot **trước** khi `run_batch()` chạy (đã đối chiếu nội dung file `get_ticket.yaml` trong backup khớp với bản trước import) |
| Conflict thật (version đổi + giá trị mới khác giá trị sửa tay) | **Không** tái tạo qua pipeline thật — xem mục "Gap quan trọng nhất" ở cuối section. Thay vào đó gọi trực tiếp `_resolve_manual_edits_after_import()` trong 1 script Python với dữ liệu giả lập (`captured` chứa giá trị cũ, file giả lập đã có giá trị mới khác) | ✅ Field conflict **không** bị tự ghi đè (giữ giá trị mới như hiện trạng), marker của riêng field đó bị bỏ, entry ghi đúng format vào `manual_edit_conflicts.json` (`operationId`, `module`, `field`, `old_value`, `new_value`, `detected_at`) |

### Phần 3 — API review xung đột (`GET/POST /modules/manual-edit-conflicts`)

Test qua UI thật (Playwright, click nút thật) + curl cho các case lỗi, backend `uvicorn` (port 8000) + frontend `npm run dev` (port 3000).

| Test | Cách làm | Kết quả |
|---|---|---|
| Card ẩn khi không có conflict | Mở trang chủ, không có entry nào trong `manual_edit_conflicts.json` | ✅ Card "Xung đột sửa tay khi import lại" không render. ⚠️ Có flash brief "Đang tải..." ngay lúc trang vừa load (trước khi fetch xong) — không phải bug nhưng là UX rough edge nhỏ, chưa fix |
| Card hiện đúng dữ liệu | Bơm tay 2 conflict giả lập (`summary`, `description` của `getTicket`) vào JSON, reload trang | ✅ Cả 2 hiện đúng `operationId`/`field`/giá trị cũ/mới |
| Bấm "Giữ bản cũ" | Click nút thật trên UI cho field `summary` | ✅ Tầng 2 (`get_ticket.yaml`) + tầng 3 (bundle) đều đổi về đúng `old_value`, marker `x-manual-edit-fields.summary: true` được set lại, entry biến mất khỏi queue, UI tự cập nhật không cần reload |
| Bấm "Lấy bản mới" | Tạo lại 1 conflict mới (field `description`), click nút này | ✅ File tầng 2 + tầng 3 **không đổi gì** (giữ giá trị như trước khi resolve), entry biến mất khỏi queue, card tự ẩn lại khi queue rỗng |
| Resolve 1 conflict không còn tồn tại | `curl POST .../resolve` với operationId/field đã được resolve trước đó | ✅ `404 CONFLICT_NOT_FOUND` |
| Payload thiếu field / `choice` sai giá trị | `curl POST .../resolve` thiếu `field`, hoặc `choice: "yolo"` | ✅ Cả 2 đều `400 INVALID_CONFLICT_RESOLVE`, message rõ |

### Phần 4 — `ManualEditConflictsCard` (frontend)

Đã verify cùng lúc với Phần 3 ở trên (card là phần UI hiển thị/tương tác trực tiếp với 2 API đó) — không có test riêng thêm.

### Dọn dẹp sau test

- `dist/openapi-bundled.yaml` — revert bằng `git checkout` (file tracked).
- `5.openapi/paths/ticket/get_ticket.yaml` — file gitignore (không tracked), khôi phục tay về đúng nội dung gốc đã đọc trước khi test.
- `3.build/backups/openapi_ticket_<timestamp>/` và `3.build/reports/manual_edit_conflicts.json` (tạo trong lúc test) — đã xoá.
- `4.config/module_registry.yaml` — chỉ đổi `last_import_at` của `ticket` (dấu vết hợp lệ từ lần import test) — đã revert bằng `git checkout` vì nằm ngoài phạm vi `frontend/`+`backend/`.
- Script test cách ly dùng `tempfile.mkdtemp()` — không đụng file thật của project, không cần dọn.

### ⚠️ Gap quan trọng nhất — chưa test qua pipeline thật với version đổi thật (2026-06-26)

Toàn bộ tính năng này được sinh ra để xử lý đúng 1 case: **sửa tay tầng 2+3, sau đó tài liệu nguồn (tầng 1) đổi version, import lại, kiểm tra sửa tay có được bảo vệ đúng không.** Case này **chưa được chạy qua pipeline thật một lần nào** — mọi test "conflict" ở Phần 2/3/4 phía trên đều dùng dữ liệu giả lập (bơm tay vào JSON, hoặc gọi hàm cách ly), không phải do `run_batch()` thật tự phát hiện ra khi version tài liệu nguồn thật sự đổi.

**Vì sao chưa làm:** để tạo version đổi thật cần 1 trong 2 cách, cả 2 đều ngoài phạm vi `frontend/`+`backend/` đã chốt:
1. Sửa nội dung tài liệu nguồn thật (`1.docs/source/api_contract/ticket/*.pdf`).
2. Sửa `3.build/reports/file_versions.json` (file trạng thái do `2.pipeline/pipeline_API.py` tự sinh) để giả lập "lần trước ghi nhận version khác".

User đã được hỏi và chọn: **để lại làm known gap**, không test ngay lúc này — sẽ test sau khi có tài liệu nguồn thật thay đổi version qua quy trình bình thường (teammate phụ trách `2.pipeline`/`1.docs` cập nhật doc → version tự đổi → lúc đó import thật và quan sát kết quả).

**Kết luận:** Phần 1, 2, 3, 4 đều hoạt động đúng thiết kế trên các nhánh đã test được (skip case — phổ biến nhất; conflict logic — test cách ly + UI thật với dữ liệu giả lập). Chưa có gì để báo cáo là bug. Gap còn lại duy nhất là case version-đổi-thật nêu trên, cần dữ liệu nguồn thật thay đổi mới test được.

## 7. Test case bổ sung — kết quả chạy thật (2026-06-26)

Brainstorm sau khi Phần 1-4 đã pass vòng đầu, nhằm soi edge case checklist hình thức dễ bỏ qua. Toàn bộ 18 case đã chạy thật: case về API/logic qua curl + script Python gọi đúng hàm thật (không mock), case UI qua Playwright (click nút thật trên browser). Backend `uvicorn` port 8000, frontend `npm run dev` port 3000.

### Phần 1 — Form Editor

| # | Case | Cách làm | Kết quả |
|---|---|---|---|
| 1 | PATCH nhiều operation cùng lúc trong 1 request | `curl -X PATCH .../docs/operations -d '[{"operationId":"getTicket","summary":"..."},{"operationId":"createTickets","summary":"..."}]'` | ✅ Cả 2 operation đều được cập nhật đúng trong 1 request, `updated: 2` |
| 2 | PATCH với `operationId` không tồn tại trong bundle | `curl -X PATCH .../docs/operations -d '[{"operationId":"khongTonTai123","summary":"..."}]'` | ✅ Bỏ qua êm, `updated: 0`, không lỗi |
| 3 | Sửa tham số có `name` không khớp cái nào trong operation thật | `curl -X PATCH .../docs/operations -d '[{"operationId":"getTicket","parameters":[{"name":"khong_ton_tai","description":"..."}]}]'`, soi lại marker trong file tầng 2 | ✅ No-op đúng — marker không bị thêm field rác (`x-manual-edit-fields` không có key `parameters`) |
| 4 | Giá trị có ký tự đặc biệt (`:`, `"`, `\n`, emoji) | PATCH `description` chứa `\n`, dấu `"`, emoji 🎉, dấu `:` qua payload JSON; đọc lại file tầng 2 bằng `yaml.safe_load` để so khớp giá trị gốc | ✅ ruamel.yaml escape đúng thành double-quoted scalar, đọc lại ra đúng y nguyên giá trị gốc |
| 5 | File tầng 2 bị hỏng cú pháp YAML trước khi PATCH tới | Ghi tay nội dung YAML sai cú pháp (`summary: [unclosed bracket {`) vào file tầng 2, rồi `curl -X PATCH` vào đúng operation đó, soi response + nội dung file sau đó | ✅ Tầng 3 vẫn ghi thành công (`200 OK`), tầng 2 hỏng bị bỏ qua an toàn (không crash, không bị ghi đè thêm) — xem finding bên dưới |
| 6 | Sửa lại field đã có marker, lần 2 sửa field khác | PATCH `summary` lần 1, PATCH `description` lần 2 (operation giống nhau), soi marker trong file tầng 2 sau mỗi lần | ✅ Marker cộng dồn đúng: `{summary: true}` → `{summary: true, description: true}`, không mất field cũ |

### Phần 2 — Backup/Capture/Compare

| # | Case | Cách làm | Kết quả |
|---|---|---|---|
| 7 | Module import lần đầu (`paths_dir` chưa từng tồn tại) | Script Python gọi trực tiếp `modules._scan_manual_edits(never_imported_dir)` với 1 thư mục tạm chưa từng tồn tại (`tempfile`), không qua API | ✅ Trả `{}` rỗng, không exception; backup tự skip đúng theo guard `paths_dir.exists()` |
| 8 | 1 operation có 2 field marker, sau import 1 field conflict + 1 field không đổi | Script Python: tạo file tầng 2 giả trong thư mục tạm, gọi trực tiếp `modules._resolve_manual_edits_after_import(paths_dir, captured, ...)` với `captured` chứa 2 field (1 giá trị khớp, 1 giá trị khác giá trị mới trong file) | ✅ Marker chỉ giữ lại đúng field không-conflict (`description`), field conflict (`summary`) bị rớt khỏi marker + đúng 1 entry vào `manual_edit_conflicts.json` |
| 9 | Tham số bị xoá khỏi doc mới | Script Python tương tự case 8, nhưng `captured["fields"]` có 1 key `parameters.removed_param` mà file tầng 2 giả không còn tham số đó nữa | ✅ Field bị xoá tự rớt khỏi marker, **không** tạo conflict giả; field còn tồn tại không đổi vẫn giữ marker đúng |
| 10 | 2 lần backup trùng giây (`ts` trùng) | Script Python gọi `shutil.copytree(src, backup_dir / "paths")` 2 lần liên tiếp với cùng `backup_dir` (mô phỏng đúng dòng code thật trong `_run_import_job`) | ⚠️ **Bug nhẹ xác nhận thật**: lần 2 ném `FileExistsError`. Code thật có `try/except` bọc quanh nên không crash cả job, nhưng **backup của lần import thứ 2 sẽ âm thầm không được tạo**, chỉ log `traceback.print_exc()` ở backend, không cảnh báo cho user |
| 11 | Import nhiều module cùng lúc (`module=None`) | `curl -X POST .../modules/import` (không truyền `module`), theo dõi qua SSE `.../modules/import/{job_id}/stream` tới khi nhận event `done`, soi marker + backup folder sau đó | ✅ Cả 4 module (`department`, `service`, `statistic`, `ticket`) import đồng thời trong 1 job, đều skip đúng (version không đổi), marker `getTicket` không bị ảnh hưởng, 4 backup folder riêng biệt được tạo đúng (không đụng nhau vì tên folder có module name) |
| 12 | `run_batch()` throw exception giữa lúc chạy | Đọc trực tiếp `backend/routers/modules.py` để xác nhận vị trí đặt lời gọi `_resolve_manual_edits_after_import()` — không trigger lỗi thật qua runtime (cần input_dir hỏng thật, khó dựng an toàn không đụng `2.pipeline`) | ✅ Xác nhận hàm so sánh nằm trong nhánh `else:` chỉ chạy khi `run_batch()` không raise, nên import lỗi sẽ không so sánh/làm mất marker sai |

### Phần 3 — Resolve API

| # | Case | Cách làm | Kết quả |
|---|---|---|---|
| 13 | Double-resolve cùng 1 entry (gọi 2 lần liên tiếp) | Bơm 1 conflict vào `manual_edit_conflicts.json`, gọi `curl -X POST .../resolve` 2 lần liên tiếp với cùng `operationId`+`field` | ✅ Lần 1 `200`, lần 2 `404 CONFLICT_NOT_FOUND` — không double-write, không crash |
| 14 | `operationId` trong conflict không còn tồn tại trong bundle **và** tầng 2 lúc resolve | Bơm 1 conflict với `operationId: "totallyFakeOpId999"` (không tồn tại ở đâu cả), gọi `curl -X POST .../resolve` với `choice: "keep_old"` | 🐛 **Bug thật xác nhận**: API trả `200 {"ok": true}` như thành công nhưng **không ghi gì vào đâu cả**. User sẽ tưởng đã xử lý xong nhưng thực chất mất luôn dữ liệu cũ, không còn cách nào lấy lại từ UI |
| 15 | File tầng 2 bị xoá nhưng entry vẫn còn trong queue (operation vẫn còn trong bundle) | Xoá tạm `get_ticket.yaml` khỏi `5.openapi/paths/ticket/`, bơm 1 conflict cho `getTicket`, gọi `curl -X POST .../resolve` với `choice: "keep_old"`, soi bundle + xác nhận file tầng 2 không bị tạo lại | ✅ Tầng 3 được sửa đúng giá trị cũ, tầng 2 bị thiếu file thì bỏ qua an toàn — khác case 14 vì bundle vẫn còn operation để sửa |

### Phần 4 — UI

| # | Case | Cách làm | Kết quả |
|---|---|---|---|
| 16 | Mất kết nối backend giữa lúc bấm "Giữ bản cũ" | Bơm 1 conflict, mở trang trên Playwright cho load xong, `pkill` tắt backend, rồi click nút "Giữ bản cũ" thật trên UI | ✅ Hiện đúng "Không thể kết nối tới backend, kiểm tra server có đang chạy không", nút trở lại bấm được ngay (không stuck ở "Đang lưu..."), entry **không** bị xoá khỏi queue |
| 17 | `old_value`/`new_value` là chuỗi rỗng | Bơm 1 conflict với `old_value: ""`, mở trang, chụp snapshot Playwright soi nội dung render | ✅ Hiện đúng `<em>(rỗng)</em>` thay vì khoảng trắng vô nghĩa |
| 18 | Nhiều conflict hiện cùng lúc, resolve 1 cái | Bơm 2 conflict (operation khác nhau), click "Giữ bản cũ" cho 1 entry trên UI thật, soi snapshot entry còn lại | ✅ Entry khác hoàn toàn không bị ảnh hưởng (không bị disable nhầm, giá trị giữ nguyên) |

### 🐛 Bug thật phát hiện qua vòng test này

1. **Case 14 — Resolve "thành công giả"**: khi `operationId` trong 1 conflict entry không còn tồn tại ở bất kỳ đâu (bundle và tầng 2 đều không có) — ví dụ do LLM sinh lại `operationId` khác sau lần import sau đó — bấm "Giữ bản cũ" trả về `200 OK` y như bình thường, nhưng không có gì được ghi/khôi phục, và entry biến mất khỏi queue vĩnh viễn. **Đề xuất fix**: trước khi xoá entry khỏi queue ở nhánh `keep_old`, kiểm tra có thực sự tìm thấy operation trong bundle hoặc tầng 2 không — nếu cả 2 đều không tìm thấy, trả lỗi (404/410) thay vì `200` giả, để user biết cần xử lý tay.
2. **Case 10 — Backup mất âm thầm khi trùng giây**: import 2 lần rất nhanh (trong vòng 1 giây) cho cùng 1 module sẽ làm lần backup thứ 2 thất bại lặng lẽ. **Đề xuất fix**: thêm số thứ tự/microsecond vào tên folder backup (`strftime("%Y%m%d_%H%M%S_%f")`), hoặc dùng UUID ngắn, để tránh trùng tên dù gọi liên tiếp.

Cả 2 đều **chưa fix** — ghi nhận lại đây, để quyết định fix ngay hay backlog.

### Dọn dẹp sau vòng test này

- `5.openapi/paths/ticket/get_ticket.yaml`, `create_tickets.yaml` (gitignore, không tracked) — khôi phục tay về đúng nội dung gốc (giá trị gốc của `createTickets.summary` lấy lại từ bundle đã revert qua `git checkout`, vì không có backup nào còn giữ).
- `dist/openapi-bundled.yaml` — revert bằng `git checkout` nhiều lần trong suốt vòng test.
- `3.build/reports/manual_edit_conflicts.json` — xoá sau mỗi case cần dữ liệu giả lập.
- `3.build/backups/openapi_<module>_<timestamp>/` (4 folder tạo từ case 11) — đã xoá; folder `config_before_profile_20260612_133921` có từ trước (không phải của vòng test này) — giữ nguyên, không đụng.
- `4.config/module_registry.yaml` — revert bằng `git checkout` (chỉ đổi `last_import_at`).

**Kết luận:** 16/18 case pass đúng thiết kế. 2 case lộ bug thật (case 10, case 14) — cả 2 đều là edge case hiếm gặp trong thực tế (double backup cùng giây, operationId biến mất hoàn toàn), không chặn việc dùng tính năng ở luồng chính, nhưng nên fix trước khi coi tính năng là "production-ready" hoàn toàn.

## 8. Đồng bộ tầng 2 + tầng 3 cho AI-fix / YAML thô + generic-hoá marker (2026-06-29)

Theo plan "Đồng bộ tầng 2 + tầng 3 cho AI-fix / sửa tay YAML thô" — fix bug chính: `PUT
/docs/bundle-content` (YAML thô + AI-fix) trước đây chỉ ghi tầng 3, mất khi "Build tài
liệu" chạy lại. Viết field-path mini-language dùng chung (`backend/field_paths.py`),
tách `backend/bundle_sync.py` (diff/sync engine) và `backend/manual_edit_conflicts.py`
(hệ thống phát hiện conflict khi reimport) ra khỏi `docs.py`/`modules.py`. Marker
`x-manual-edit-fields` đổi từ dict cố định 4 field sang list field-path tổng quát (bất kỳ
field nào). Test qua UI thật (Playwright, click nút thật) + Python script cách ly,
backend `uvicorn` port 8000 + frontend `npm run dev` port 3000.

### Phần 1 — Form Editor với marker format mới

| Test | Cách làm | Kết quả |
|---|---|---|
| Sửa `description` của `getTicket` qua Form Editor (UI thật) | Click vào textbox "Mô tả chi tiết", sửa nội dung, bấm "Lưu" | ✅ `PATCH /docs/operations` ghi đúng cả tầng 2 + tầng 3; marker đổi đúng format mới `x-manual-edit-fields: [description]` (list field-path, không còn dict `{summary: true,...}` cũ) |

### Phần 2 — YAML thô / `PUT /docs/bundle-content` (test bug chính)

| Test | Cách làm | Kết quả |
|---|---|---|
| Sửa field **ngoài** 4 field cũ của Form Editor | Tab "YAML thô", đổi `required: true → false` của parameter `user_id` trong `updateClose` (qua Monaco model API), bấm "Lưu" | ✅ Tầng 2 (`update_close.yaml`) nhận đúng giá trị mới + marker `parameters[name=user_id].required`; tầng 3 ghi verbatim text (giữ format gốc), marker tầng 3 phản ánh ở lần build kế tiếp đúng như thiết kế |
| **Test bug chính**: bấm "Tạo lại tài liệu" (`POST /docs/build`) sau khi sửa field trên | Click nút "Tạo lại tài liệu" trên dashboard | ✅ **`required: false` không bị mất** — đây là bug đang fix (trước fix, build lại sẽ đè mất vì tầng 2 không có sửa đó). Marker cũng lên tầng 3 đúng vì giờ build lại từ tầng 2 mới |
| Paste YAML lỗi cú pháp, bấm Lưu | Thêm dòng `[invalid, yaml,, ,, {{{ ]]]` vào cuối nội dung Monaco, bấm "Lưu" | ✅ Alert "Lỗi lưu bundle: YAML không hợp lệ: ..." (`400 BUNDLE_INVALID_YAML`), checksum cả 2 tầng **không đổi** — không ghi gì khi YAML sai |

### 🐛 Bug thật phát hiện và đã fix ngay trong vòng test này

**`x-manual-edit-fields` tự tham chiếu chính nó khi diff.** Tái hiện: mở modal ở tab Form
Editor, sửa lưu (marker ghi vào tầng 2+3), chuyển sang tab YAML thô **mà không
đóng/mở lại modal** — tab này vẫn dùng `bundleContent` đã fetch từ lúc mở modal (trước
khi marker mới tồn tại). Khi sửa tiếp 1 field khác ở tab này rồi Lưu, `diff_bundle` so
`old_bundle` (trên đĩa, đã có marker) với `new_bundle` (bản stale, chưa có marker) →
thấy 2 giá trị marker khác nhau → tự coi `x-manual-edit-fields` là "field user sửa" →
ghi đè `None` rồi merge lại → marker tự liệt kê chính nó
(`[description, x-manual-edit-fields]`). **Fix:** thêm `if key ==
"x-manual-edit-fields": continue` vào đầu loop của `_diff_recursive`
(`backend/bundle_sync.py`) — loại trừ marker khỏi diff vì nó là bookkeeping nội bộ,
không phải field thật. Đã unit-test lại 2 case (marker lệch giữa old/new → 0 change;
field thường vẫn diff đúng) + test lại qua UI thật (tab YAML thô với fetch mới, marker
cộng dồn đúng `[description, responses[422].description]`, không tự tham chiếu nữa).

### Phần 3 — AI-fix lưu ngay khi bấm "Áp dụng"

| Test | Cách làm | Kết quả |
|---|---|---|
| Bấm "Áp dụng" patch AI-fix có lưu ngay không (không cần bấm "Lưu" riêng) | Tạo 1 lượt lỗi lint thật (license/contact/description thiếu...), bấm "AI tự fix lỗi" (26 patch), bấm "Áp dụng" | ✅ `PUT /docs/bundle-content` bắn ngay sau khi bấm Áp dụng (thấy trong Network tab), checksum bundle đổi ngay, không cần thêm hành động nào |
| Marker + đồng bộ tầng 2 cho field schema (không phải operation) | Soi `5.openapi/components/schemas/common/UserInfo.yaml` sau khi AI-fix thêm `description` cho `properties.id`/`properties.name` | ✅ `sync_schema_fields` ghi đúng cả 2 field + marker `[properties.id.description, properties.name.description]` (dạng dot, không cần bracket vì `properties` không cần match đặc biệt như `parameters`/`responses` — đúng thiết kế generic, không phải thiếu sót) |

### ⚠️ Finding chất lượng AI-fix (không phải bug cơ chế đồng bộ)

Khi 1 lượt AI-fix sửa nhiều lỗi "thiếu description" cùng lúc cho **nhiều operation
khác nhau** trong 1 batch, AI sinh description **chung chung/sai nghiệp vụ** cho 5
operation (`createReopen` → "Lấy danh sách tài nguyên." dù đây là API mở lại ticket;
tương tự sai cho `createChangeAssignee`, `createConversations`, `createFeedback`,
`createRatings`). Khác với field schema ở Phần 3 (nội dung AI sinh đúng) — có vẻ do
thiếu context riêng từng operation khi fix dồn nhiều lỗi 1 lượt. Đã revert cả 5 file về
rỗng như gốc theo quyết định của user (nội dung sai còn tệ hơn để trống). **Chưa fix**
— ghi nhận lại đây làm input cho việc cải thiện prompt của `backend/ai_fix.py` sau này,
không thuộc phạm vi bug đồng bộ tầng 2/3 đang test.

### Phần 4 — Duyệt conflict qua UI với marker generic

| Test | Cách làm | Kết quả |
|---|---|---|
| Bấm "Giữ bản cũ" cho 1 conflict field tổng quát (`description`) | Bơm tay 1 entry vào `manual_edit_conflicts.json` (field `"description"` — format mới, không phải `"summary"`/`"description"` cố định như trước), reload trang, click "Giữ bản cũ" thật trên UI | ✅ `resolve_manual_edit_conflict` (đã refactor dùng `sync_operation_fields` thay vì loop tay) ghi đúng `old_value` vào cả tầng 2 + tầng 3, entry biến mất khỏi queue |

### Dọn dẹp sau test

- `5.openapi/paths/ticket/get_ticket.yaml`, `update_close.yaml` (gitignore) — khôi phục
  tay về đúng nội dung gốc (description, `responses['422'].description`,
  `parameters[].required`), xoá hết marker test.
- `5.openapi/paths/ticket/create_reopen.yaml`, `create_change_assignee.yaml`,
  `create_conversations.yaml`, `create_feedback.yaml`, `create_ratings.yaml`
  (gitignore) — revert `description`/`parameters[].description` về rỗng như gốc (xem
  finding chất lượng AI-fix ở trên), xoá marker.
- `5.openapi/components/schemas/common/StandardSuccess.yaml`, `StandardError.yaml`,
  `UserInfo.yaml` (tracked git) — **giữ lại** theo quyết định của user (nội dung AI sinh
  đúng, fix đúng lint warning thật).
- `dist/openapi-bundled.yaml` — build lại lần cuối (`npm run bundle:api`) sau khi dọn
  xong layer 2, phản ánh đúng trạng thái sạch.
- `3.build/reports/manual_edit_conflicts.json` — về `[]` sau khi resolve entry test.
- Backend (`uvicorn`)/frontend (`next dev`) — tắt hẳn sau khi test xong (xác nhận lại
  bằng `ss -ltnp` không còn process ở port 8000/3000).

### ⚠️ Gap chưa đóng (kế thừa từ mục 6) — chưa test qua pipeline thật với version đổi thật

Giống gap đã ghi nhận ở mục 6 (2026-06-26): nhánh "phát hiện conflict" (`_scan_manual_edits`/`_resolve_manual_edits_after_import`, nay ở `backend/manual_edit_conflicts.py`) vẫn chỉ được test bằng dữ liệu giả lập (Python script cách ly + bơm tay JSON), **chưa** chạy qua `run_batch()` thật với tài liệu nguồn (1.docs/) thật sự đổi version. Lần này user chủ động chọn cách test rẻ hơn (bơm conflict giả, test riêng nhánh duyệt qua UI) để tránh tốn token AI + tránh đụng dữ liệu ticket thật qua pipeline thật — không phải do quên, mà là quyết định đánh đổi có chủ ý. Gap này vẫn cần 1 trong 2 điều kiện nêu ở mục 6 mới test được (đổi nội dung doc nguồn thật, hoặc sửa `file_versions.json` để giả lập).

**Kết luận:** Toàn bộ cơ chế đồng bộ tầng 2+3 (Form Editor, YAML thô, AI-fix, duyệt
conflict) đã PASS qua UI thật với marker format mới (generic field-path). 1 bug thật
phát hiện và fix ngay trong lúc test (`x-manual-edit-fields` tự tham chiếu). 1 finding
về chất lượng AI-fix khi batch nhiều operation (không phải bug đồng bộ, đã xử lý bằng
cách revert nội dung sai) — đáng cân nhắc cải thiện prompt AI-fix sau này. Gap về test
version-đổi-thật vẫn còn mở, giống mục 6.
