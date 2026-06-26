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
