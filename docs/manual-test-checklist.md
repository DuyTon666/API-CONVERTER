# Manual Test Checklist — Backend/Frontend

Checklist test thủ công cho các tính năng: module workflow (scan → suggest → approve →
apply → activate → import → docs), upload bảo mật, Form Editor, đồng bộ sửa tay tầng 2+3
(backup/conflict), Manual Edit Conflicts, YAML thô, và AI-fix.

Tài liệu này gồm 3 phần tách biệt:

- **Phần A — Test Case Design**: checklist cố định, có ID (`TC-xxx`), không gắn ngày —
  dùng lại được cho mọi lần test sau (kể cả regression test khi sửa code mới).
- **Phần B — Execution Log**: lịch sử các lần chạy thật theo ngày, ghi dữ liệu cụ thể đã
  dùng + kết quả thực tế quan sát được, tham chiếu ngược về `TC-xxx` ở Phần A.
- **Phần C — Defect Log**: danh sách bug/finding phát hiện được qua các lần test, có
  trạng thái fix.

## Setup môi trường

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

## Cách ghi kết quả

Mỗi `TC-xxx` khi chạy: ✅ pass / ❌ fail / ⚠️ pass với rough edge + mô tả ngắn (response
thật nhận được, screenshot console error nếu có). Ghi vào Phần B (Execution Log), không
sửa trực tiếp vào Phần A.

---

# Phần A — Test Case Design

## A1. Module Workflow — happy path

| ID       | Mô tả                                               | Tiền điều kiện                              | Các bước                               | Kết quả mong đợi                                                                                                                                    |
| -------- | --------------------------------------------------- | ------------------------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| TC-WF-01 | Scan phát hiện module có sẵn + file chưa gán module | Có file trong `1.docs/source/api_contract/` | Click nút scan ở ScanCard              | Thấy danh sách module có sẵn + danh sách file `unassigned`                                                                                          |
| TC-WF-02 | Suggest-root gợi ý module cho file unassigned       | Đã chạy TC-WF-01, có file unassigned        | Chạy suggest-root ở SuggestCard        | Mỗi file unassigned được gợi ý 1 module kèm `confidence_score`                                                                                      |
| TC-WF-03 | Approve suggestion                                  | Đã có suggestion từ TC-WF-02                | Approve all suggestion                 | Suggestion chuyển trạng thái `approved`                                                                                                             |
| TC-WF-04 | Apply suggestion                                    | Suggestion đã `approved`                    | Apply suggestions                      | File được copy vào đúng `1.docs/source/api_contract/<module>/`; nếu file đích đã tồn tại thì skip (`skip_reason: target_file_exists`), không ghi đè |
| TC-WF-05 | Activate module                                     | Module đang `draft`                         | Activate 1 module ở ModuleRegistryCard | Status đổi `draft` → `active`                                                                                                                       |
| TC-WF-06 | Trigger import cho module                           | Module đang `active`                        | Trigger import                         | SSE chạy, progress cập nhật real-time, kết thúc hiện `success/failed/skipped`; nếu version doc không đổi thì hash-based skip hoạt động              |
| TC-WF-07 | Build docs                                          | Đã import ít nhất 1 module                  | Build docs ở SwaggerDocsCard           | Build/lint chạy xong (`bundle_ready: true`, `html_ready: true`), link Swagger UI hoạt động                                                          |

## A2. Upload — bảo mật (`POST /source/upload`)

Test bằng **ImportCard** (UI) và **curl trực tiếp** (đảm bảo không phải frontend tự chặn
trước khi tới backend).

| ID        | Mô tả                                | Các bước                                                                                                | Kết quả mong đợi                                                                                                                                                  |
| --------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TC-SEC-01 | Path traversal filename tương đối    | `curl -X POST .../source/upload -F 'files=@sample.docx;filename=../../backend/main.py'`                 | 400 `INVALID_FILENAME` (extension không hợp lệ) hoặc bị flatten về basename trong `SOURCE_DIR` nếu extension hợp lệ — **không bao giờ** ghi ra ngoài `SOURCE_DIR` |
| TC-SEC-02 | Path traversal absolute filename     | `curl -X POST .../source/upload -F 'files=@sample.docx;filename=/tmp/evil.docx'` hoặc `/etc/evil.pdf`   | Flatten về basename, lưu an toàn trong `SOURCE_DIR`, không ghi được ra `/tmp`, `/etc`                                                                             |
| TC-SEC-03 | Filename literally `.` hoặc `..`     | Upload với filename là đúng `.` hoặc `..`                                                               | 400 `INVALID_FILENAME`                                                                                                                                            |
| TC-SEC-04 | Sai extension                        | Upload file `.zip`/`.exe` qua UI                                                                        | 400 `UNSUPPORTED_FILE_TYPE`                                                                                                                                       |
| TC-SEC-05 | File vượt size cap                   | `dd if=/dev/zero of=/tmp/big.pdf bs=1M count=25`, upload                                                | 400 `FILE_TOO_LARGE`, không lọt vào disk                                                                                                                          |
| TC-SEC-06 | File hợp lệ trong cap (control case) | Upload file PDF/DOCX hợp lệ < 20MB                                                                      | Upload thành công bình thường, không bị block oan                                                                                                                 |
| TC-SEC-07 | Import job lỗi giữa đường            | Sửa tạm 1 file config (`4.config/*.yaml`) thành sai cú pháp YAML, trigger import, restore file sau test | Job kết thúc đúng `status: done`, SSE đóng kết nối sạch, không treo vô hạn; traceback được log ở backend, không nuốt im lặng                                      |
| TC-SEC-08 | Spam import liên tục                 | Gọi `POST /modules/import` ~60 lần liên tiếp (script loop)                                              | Server không OOM/crash, job cũ tự dọn sau khi `status=done`, vẫn phản hồi `/health`                                                                               |

## A3. Form Editor (`PATCH /docs/operations`)

| ID       | Mô tả                                                | Các bước                                                                                                | Kết quả mong đợi                                                                                                                                         |
| -------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TC-FE-01 | Sửa `summary`/`description` cơ bản                   | Sửa qua UI hoặc `curl -X PATCH .../docs/operations -d '[{"operationId":"<id>","summary":"..."}]'`       | Cả tầng 2 (`5.openapi/paths/...`) và tầng 3 (`dist/openapi-bundled.yaml`) đều cập nhật; marker `x-manual-edit-fields` ghi đúng field vừa sửa ở cả 2 tầng |
| TC-FE-02 | PATCH nhiều operation cùng 1 request                 | Payload là mảng nhiều object, mỗi object 1 `operationId` khác nhau                                      | Tất cả operation trong payload đều được cập nhật đúng, `updated` = đúng số lượng                                                                         |
| TC-FE-03 | PATCH `operationId` không tồn tại trong bundle       | Payload với `operationId` ngẫu nhiên không có thật                                                      | Bỏ qua êm, `updated: 0`, không lỗi                                                                                                                       |
| TC-FE-04 | PATCH tham số có `name` không khớp operation thật    | Payload `parameters[].name` không tồn tại trong operation đó                                            | No-op — marker không bị thêm field rác                                                                                                                   |
| TC-FE-05 | Giá trị có ký tự đặc biệt                            | PATCH `description` chứa `\n`, dấu `"`, emoji, dấu `:`; đọc lại tầng 2 bằng `yaml.safe_load` để so khớp | ruamel.yaml escape đúng, đọc lại ra y nguyên giá trị gốc                                                                                                 |
| TC-FE-06 | File tầng 2 bị hỏng cú pháp YAML trước khi PATCH tới | Ghi tay YAML sai cú pháp vào file tầng 2, rồi PATCH đúng operation đó                                   | Tầng 3 vẫn ghi thành công (200 OK), tầng 2 hỏng bị bỏ qua an toàn (không crash, không ghi đè thêm)                                                       |
| TC-FE-07 | Marker cộng dồn qua nhiều lần sửa                    | PATCH field A, sau đó PATCH field B (cùng operation)                                                    | Marker tầng 2 cộng dồn đúng (`[A]` → `[A, B]`), không mất field cũ                                                                                       |
| TC-FE-08 | AI Suggest điền mô tả tiếng Việt cho field trống     | Bấm "✨ Gợi ý AI" trong Form Editor (cần `backend/.env` có `ANTHROPIC_*`)                                | `POST /docs/operations/ai-suggest` trả 200, điền tiếng Việt vào field đang trống; **không** ghi đè field đã có nội dung                                  |

## A4. Backup + Capture/Compare khi reimport (`backend/services/import_jobs.py`, `manual_edit_conflicts.py`)

| ID         | Mô tả                                                                          | Các bước                                                                                                                                                              | Kết quả mong đợi                                                                                                                |
| ---------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| TC-SYNC-01 | Marker tồn tại trước import, version doc không đổi (case phổ biến nhất)        | PATCH đánh dấu 1 field, sau đó import lại đúng module đó                                                                                                              | Pipeline skip do `version_unchanged` → marker giữ nguyên 100%, không tạo entry conflict                                         |
| TC-SYNC-02 | Backup chạy trước mỗi lần import                                               | Quan sát `3.build/backups/` ngay sau khi import                                                                                                                       | Folder `openapi_<module>_<timestamp>/{paths,schemas}` chứa đúng snapshot **trước** khi `run_batch()` chạy                       |
| TC-SYNC-03 | Conflict thật (version đổi + giá trị mới khác giá trị sửa tay)                 | Gọi trực tiếp `_resolve_manual_edits_after_import()` qua script Python cách ly với `captured` chứa giá trị cũ, file giả lập có giá trị mới khác                       | Field conflict không bị tự ghi đè (giữ giá trị mới), marker của field đó bị bỏ, entry ghi đúng vào `manual_edit_conflicts.json` |
| TC-SYNC-04 | Module import lần đầu (`paths_dir` chưa tồn tại)                               | Gọi `_scan_manual_edits()` với thư mục tạm chưa từng tồn tại                                                                                                          | Trả `{}` rỗng, không exception, backup tự skip                                                                                  |
| TC-SYNC-05 | 1 operation có 2 field marker, sau import 1 field conflict + 1 field không đổi | Script Python: `captured` chứa 2 field, 1 giá trị khớp, 1 giá trị khác                                                                                                | Marker chỉ giữ field không-conflict, field conflict bị rớt khỏi marker + đúng 1 entry conflict                                  |
| TC-SYNC-06 | Tham số bị xoá khỏi doc mới                                                    | `captured["fields"]` có 1 key mà file tầng 2 giả không còn tham số đó                                                                                                 | Field bị xoá tự rớt khỏi marker, **không** tạo conflict giả                                                                     |
| TC-SYNC-07 | 2 lần backup trùng giây                                                        | Gọi `shutil.copytree()` 2 lần liên tiếp với cùng `backup_dir`                                                                                                         | (xem DEF-01 ở Phần C)                                                                                                           |
| TC-SYNC-08 | Import nhiều module cùng lúc (`module=None`)                                   | `POST /modules/import` không truyền `module`, theo dõi SSE tới `done`                                                                                                 | Tất cả module import đồng thời trong 1 job, mỗi module có backup folder riêng biệt không đụng nhau                              |
| TC-SYNC-09 | `run_batch()` throw exception giữa lúc chạy                                    | Đọc code xác nhận vị trí gọi `_resolve_manual_edits_after_import()` nằm trong nhánh chỉ chạy khi không có exception (verify tĩnh, không trigger lỗi thật qua runtime) | Import lỗi không trigger so sánh/làm mất marker sai                                                                             |

## A5. Manual Edit Conflicts — API + UI (`GET/POST /modules/manual-edit-conflicts`)

| ID             | Mô tả                                                                               | Các bước                                                                                     | Kết quả mong đợi                                                                             |
| -------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| TC-CONFLICT-01 | Card ẩn khi không có conflict                                                       | Mở trang chủ, `manual_edit_conflicts.json` rỗng                                              | Card "Xung đột sửa tay khi import lại" không render                                          |
| TC-CONFLICT-02 | Card hiện đúng dữ liệu                                                              | Bơm 1+ conflict giả vào JSON, reload trang                                                   | Hiện đúng `operationId`/`field`/giá trị cũ/mới cho từng entry                                |
| TC-CONFLICT-03 | Bấm "Giữ bản cũ"                                                                    | Click nút trên UI cho 1 field                                                                | Tầng 2 + tầng 3 đổi về đúng `old_value`, marker được set lại, entry biến mất khỏi queue      |
| TC-CONFLICT-04 | Bấm "Lấy bản mới"                                                                   | Click nút trên UI cho 1 field                                                                | Tầng 2 + tầng 3 **không đổi gì**, entry biến mất khỏi queue                                  |
| TC-CONFLICT-05 | Double-resolve cùng 1 entry                                                         | Gọi `POST .../resolve` 2 lần liên tiếp cùng `operationId`+`field`                            | Lần 1 `200`, lần 2 `404 CONFLICT_NOT_FOUND`                                                  |
| TC-CONFLICT-06 | Payload thiếu field / `choice` sai giá trị                                          | `POST .../resolve` thiếu `field`, hoặc `choice: "yolo"`                                      | `400 INVALID_CONFLICT_RESOLVE` cho cả 2 case                                                 |
| TC-CONFLICT-07 | `operationId` không còn tồn tại ở đâu cả lúc resolve                                | Bơm conflict với `operationId` giả không tồn tại trong bundle lẫn tầng 2, resolve `keep_old` | (xem DEF-02 ở Phần C)                                                                        |
| TC-CONFLICT-08 | File tầng 2 bị xoá nhưng entry vẫn còn trong queue (operation vẫn còn trong bundle) | Xoá file tầng 2 của 1 operation, bơm conflict cho operation đó, resolve `keep_old`           | Tầng 3 sửa đúng giá trị cũ, tầng 2 thiếu file thì bỏ qua an toàn                             |
| TC-CONFLICT-09 | Mất kết nối backend giữa lúc resolve                                                | Bơm conflict, tắt backend, click "Giữ bản cũ" trên UI thật                                   | Hiện lỗi kết nối rõ ràng, nút bấm lại được ngay (không stuck), entry không bị xoá khỏi queue |
| TC-CONFLICT-10 | `old_value`/`new_value` là chuỗi rỗng                                               | Bơm conflict với `old_value: ""`                                                             | UI hiện `(rỗng)` thay vì khoảng trắng vô nghĩa                                               |
| TC-CONFLICT-11 | Nhiều conflict hiện cùng lúc, resolve 1 cái                                         | Bơm 2 conflict khác operation, resolve 1 entry trên UI                                       | Entry còn lại không bị ảnh hưởng                                                             |

## A6. YAML thô (`PUT /docs/bundle-content`)

| ID         | Mô tả                                                                               | Các bước                                                                                                                                                              | Kết quả mong đợi                                                                          |
| ---------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| TC-YAML-01 | Sửa field bất kỳ qua field-path generic (không giới hạn 4 field cũ của Form Editor) | Tab "YAML thô", sửa 1 field qua Monaco, bấm Lưu                                                                                                                       | Tầng 2 nhận đúng giá trị mới + marker field-path đúng; tầng 3 ghi verbatim giữ format gốc |
| TC-YAML-02 | Build lại tài liệu sau khi sửa field tầng 2 mới                                     | Sau TC-YAML-01, bấm "Tạo lại tài liệu" (`POST /docs/build`)                                                                                                           | Giá trị vừa sửa **không bị mất** sau build lại                                            |
| TC-YAML-03 | Paste YAML lỗi cú pháp, bấm Lưu                                                     | Thêm đoạn YAML không hợp lệ vào nội dung Monaco, bấm Lưu                                                                                                              | `400 BUNDLE_INVALID_YAML`, checksum cả 2 tầng không đổi                                   |
| TC-YAML-04 | Marker không tự tham chiếu chính nó khi diff stale                                  | Sửa ở tab Form Editor (marker ghi vào tầng 2+3), chuyển sang tab YAML thô **không** đóng/mở lại modal (giữ bundle content cũ trong state), sửa tiếp 1 field khác, Lưu | Marker cộng dồn đúng field thật, **không** tự liệt kê `x-manual-edit-fields` vào chính nó |

## A7. AI-fix (`POST /docs/bundle/ai-fix`)

| ID          | Mô tả                                                             | Các bước                                                                                                      | Kết quả mong đợi                                                                               |
| ----------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| TC-AIFIX-01 | Bấm "Áp dụng" patch lưu ngay                                      | Tạo lỗi lint thật, bấm "AI tự fix lỗi", bấm "Áp dụng"                                                         | `PUT /docs/bundle-content` bắn ngay sau khi Áp dụng, không cần thêm hành động nào khác         |
| TC-AIFIX-02 | Marker + đồng bộ tầng 2 cho field schema (không phải operation)   | AI-fix thêm `description` cho field trong `components/schemas/`                                               | `sync_schema_fields` ghi đúng field + marker dạng dot-path                                     |
| TC-AIFIX-03 | Chất lượng description khi fix batch nhiều operation cùng lúc     | 1 lượt AI-fix sửa nhiều lỗi "thiếu description" cho nhiều operation khác nhau trong 1 batch                   | Description sinh ra đúng nghiệp vụ của từng operation, không generic/sai (xem DEF-03 nếu fail) |
| TC-AIFIX-04 | `_get_breadcrumb` build đúng đường dẫn khóa từ root tới field lỗi | Unit test với YAML mẫu nhiều cấp lồng nhau, field lỗi nằm sâu trong `paths.../properties/<field>/description` | Breadcrumb trả về đúng chuỗi path từ `paths` tới field, nối bằng dấu `.`                       |
| TC-AIFIX-05 | `_get_parent_block` lấy đúng entity cha chứa sibling field        | Cùng YAML mẫu, field lỗi có sibling cùng cấp (vd `priority` cạnh `status`)                                    | `parent_text` trả về block chứa cả field lỗi lẫn sibling, không chỉ riêng field đang sửa       |

## A8. Regression

| ID        | Mô tả                                                          | Các bước                                                     | Kết quả mong đợi                                                                       |
| --------- | -------------------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| TC-REG-01 | Deactivate module đang active                                  | Deactivate 1 module, thử import lại                          | Bị chặn `400 MODULE_NOT_ACTIVE`                                                        |
| TC-REG-02 | Reactivate module                                              | Activate lại module vừa deactivate                           | Status trở về `active`, import lại bình thường                                         |
| TC-REG-03 | Module đã import trước đó không bị ảnh hưởng bởi thay đổi khác | Mở lại BundleEditorModal của module cũ, sửa Form Editor, lưu | File YAML cập nhật đúng như TC-FE-01, không có hành vi lạ do thay đổi ở tính năng khác |

---

# Phần B — Execution Log

## 2026-06-25 — Module Workflow + Upload Security (TC-WF-01..07, TC-SEC-01..08, TC-REG-01..02, TC-FE-08)

Chạy qua API/curl trực tiếp (không qua click UI browser) — backend `make dev` (port
8000) + frontend `npm run dev` (port 3000), không lỗi `load_dotenv`.

| TC ID     | Kết quả thực tế                                                                                                                                                                                                                      |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| TC-WF-01  | ✅ Đúng 4 module có sẵn (`ticket`, `service`, `statistic`, `department`) + 21 file unassigned                                                                                                                                         |
| TC-WF-02  | ✅ Mỗi file unassigned có `suggested_module` + `confidence_score` + `conflict` detection đúng                                                                                                                                         |
| TC-WF-03  | ✅ `approval_status: pending → approved` (test với 1 file, `mode=file`), không skip sai                                                                                                                                               |
| TC-WF-04  | ✅ Phát hiện đúng `skip_reason: target_file_exists`, không ghi đè file đã tồn tại                                                                                                                                                     |
| TC-WF-06  | ✅ Re-run module `department`: SSE emit đúng event module + `done`; hash-based skip hoạt động (`skipped: 1`)                                                                                                                          |
| TC-WF-07  | ✅ `bundle_ready: true`, `html_ready: true`, Spectral lint chạy bình thường (chỉ warning license-url/contact có từ trước)                                                                                                             |
| TC-SEC-01 | ✅ `../../backend/main.py` bị chặn (extension `.py` không cho phép), `main.py` không đổi (hash giống trước/sau). `../../evil.pdf` (extension hợp lệ) bị flatten về basename `evil_traversal_test.pdf`, lưu an toàn trong `SOURCE_DIR` |
| TC-SEC-02 | ✅ `/etc/evil.pdf` flatten về basename, không ghi được vào `/etc/`                                                                                                                                                                    |
| TC-SEC-03 | ✅ Filename `.` và `..` đều 400 `INVALID_FILENAME`                                                                                                                                                                                    |
| TC-SEC-04 | ✅ `.exe`/`.zip` đều 400 `UNSUPPORTED_FILE_TYPE`                                                                                                                                                                                      |
| TC-SEC-05 | ✅ File 25MB (vượt cap 20MB) → 400 `FILE_TOO_LARGE`, không lọt disk                                                                                                                                                                   |
| TC-SEC-06 | ✅ File 5MB hợp lệ upload thành công bình thường                                                                                                                                                                                      |
| TC-SEC-07 | ✅ Làm hỏng tạm `4.config/import_flow.yaml`: job kết thúc đúng `status: done` ngay, SSE đóng sạch, không treo; traceback `yaml.scanner.ScannerError` log đầy đủ. File restore 100% (verify `diff`)                                    |
| TC-SEC-08 | ✅ Spam 60 request liên tiếp: server không crash/OOM, RAM ổn định (48MB trước/sau), vẫn phản hồi `/health`                                                                                                                            |
| TC-REG-01 | ✅ Deactivate `department` → import bị chặn đúng `400 MODULE_NOT_ACTIVE`                                                                                                                                                              |
| TC-REG-02 | ✅ Reactivate `department` → status về `active`                                                                                                                                                                                       |
| TC-REG-03 | ✅ Sửa "Mô tả chi tiết" qua UI thật (Playwright) → `PATCH /docs/operations` ghi đúng vào bundle, không đụng file gốc tầng 2 (đúng thiết kế tại thời điểm này — trước khi có TC-FE-01 ghi cả 2 tầng ở đợt 2026-06-26)                  |
| TC-FE-08  | ✅ Bấm "✨ Gợi ý AI" qua UI thật: trả 200, điền tiếng Việt vào 2 field `parameters[].description` đang trống, độ hoàn chỉnh 67% → 100%; không ghi đè field đã có nội dung                                                              |

**Dọn dẹp:** file test tạm đã xoá hết; `4.config/import_flow.yaml` restore 100%
(diff sạch); `4.config/module_registry.yaml` chỉ đổi `last_import_at` (dấu vết hợp lệ).

**Kết luận:** 19/19 case pass, không phát hiện regression hay bug mới.

## 2026-06-26 (đợt 1) — Persist Form Editor edits qua tầng 2 (TC-FE-01, TC-SYNC-01..03, TC-CONFLICT-01..06)

Theo plan "Persist Form Editor edits qua tầng 2 + backup + review xung đột khi
reimport". Test qua curl trực tiếp + 1 script cách ly (Python) cho case cần giả lập,
backend `make dev` (port 8000), UI qua Playwright cho Phần Conflict.

| TC ID          | Kết quả thực tế                                                                                                                                                                                                                                                        |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TC-FE-01       | ✅ PATCH `summary` + mô tả tham số `user_id` của `getTicket`: cả tầng 2 (`get_ticket.yaml`) và tầng 3 (bundle) có giá trị mới; marker `x-manual-edit-fields: {summary: true, parameters: [user_id]}` đúng ở cả 2 file; style ruamel.yaml (comment, indent) không bị phá |
| TC-SYNC-01     | ✅ Marker `summary` của `getTicket` tồn tại trước import module `ticket`: toàn bộ 8 file bị skip (`version_unchanged`) → marker giữ nguyên 100%, không tạo `manual_edit_conflicts.json`                                                                                 |
| TC-SYNC-02     | ✅ Folder `openapi_ticket_<timestamp>/{paths,schemas}` tạo đúng, đối chiếu `get_ticket.yaml` trong backup khớp bản trước import                                                                                                                                         |
| TC-SYNC-03     | ✅ Gọi `_resolve_manual_edits_after_import()` qua script cách ly: field conflict không bị tự ghi đè, marker field đó bị bỏ, entry ghi đúng format (`operationId`, `module`, `field`, `old_value`, `new_value`, `detected_at`)                                           |
| TC-CONFLICT-01 | ✅ Card ẩn khi JSON rỗng. ⚠️ Flash brief "Đang tải..." lúc trang vừa load — UX rough edge nhỏ, chưa fix                                                                                                                                                                  |
| TC-CONFLICT-02 | ✅ Bơm 2 conflict giả (`summary`, `description` của `getTicket`) → hiện đúng cả 2                                                                                                                                                                                       |
| TC-CONFLICT-03 | ✅ Click "Giữ bản cũ" cho `summary`: tầng 2+3 đổi về `old_value`, marker set lại, entry biến mất, UI tự cập nhật không cần reload                                                                                                                                       |
| TC-CONFLICT-04 | ✅ Click "Lấy bản mới" cho `description`: tầng 2+3 không đổi, entry biến mất, card tự ẩn khi queue rỗng                                                                                                                                                                 |
| TC-CONFLICT-05 | ✅ Resolve conflict đã resolve trước đó → `404 CONFLICT_NOT_FOUND`                                                                                                                                                                                                      |
| TC-CONFLICT-06 | ✅ Thiếu `field` / `choice: "yolo"` → cả 2 đều `400 INVALID_CONFLICT_RESOLVE`                                                                                                                                                                                           |

**Dọn dẹp:** `dist/openapi-bundled.yaml` revert `git checkout`; `get_ticket.yaml` khôi
phục tay; backup folder + `manual_edit_conflicts.json` tạo trong test đã xoá;
`module_registry.yaml` revert `git checkout`.

**⚠️ Gap chưa đóng — chưa test qua pipeline thật với version đổi thật:** TC-SYNC-03 chỉ
test qua script cách ly (dữ liệu giả lập), chưa chạy qua `run_batch()` thật với tài
liệu nguồn (tầng 1) thật sự đổi version. Cần 1 trong 2 điều kiện: (1) sửa nội dung tài
liệu nguồn thật, hoặc (2) sửa `3.build/reports/file_versions.json` để giả lập version
khác. User đã quyết định để lại làm known gap, test sau khi có tài liệu nguồn thật đổi
version qua quy trình bình thường. **Gap này vẫn còn mở tính đến lần test gần nhất
(2026-06-29).**

**Kết luận:** Pass trên các nhánh test được (skip case phổ biến nhất; conflict logic
qua script cách ly + UI thật). Gap version-đổi-thật vẫn mở.

## 2026-06-26 (đợt 2) — Edge case bổ sung (TC-FE-02..07, TC-SYNC-04..09, TC-CONFLICT-07..11)

Brainstorm sau khi đợt 1 pass, nhằm soi edge case checklist hình thức dễ bỏ qua. Case
API/logic qua curl + script Python gọi đúng hàm thật (không mock); case UI qua
Playwright (click nút thật). Backend `uvicorn` port 8000, frontend `npm run dev` port
3000.

| TC ID          | Kết quả thực tế                                                                                                                                                                                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| TC-FE-02       | ✅ PATCH `getTicket` + `createTickets` trong 1 request: cả 2 cập nhật đúng, `updated: 2`                                                                                                                                                                      |
| TC-FE-03       | ✅ `operationId: "khongTonTai123"` → bỏ qua êm, `updated: 0`                                                                                                                                                                                                  |
| TC-FE-04       | ✅ `parameters[].name: "khong_ton_tai"` → no-op, marker không thêm field rác                                                                                                                                                                                  |
| TC-FE-05       | ✅ `description` chứa `\n`, `"`, emoji 🎉, `:` → ruamel.yaml escape đúng, đọc lại y nguyên                                                                                                                                                                     |
| TC-FE-06       | ✅ Ghi tay YAML sai cú pháp (`summary: [unclosed bracket {`) vào tầng 2, PATCH vẫn `200 OK` ở tầng 3, tầng 2 hỏng bị bỏ qua an toàn                                                                                                                           |
| TC-FE-07       | ✅ PATCH `summary` rồi `description` (cùng operation): marker cộng dồn `{summary: true}` → `{summary: true, description: true}`                                                                                                                               |
| TC-SYNC-04     | ✅ `_scan_manual_edits(never_imported_dir)` với thư mục tạm chưa tồn tại: trả `{}` rỗng, không exception                                                                                                                                                      |
| TC-SYNC-05     | ✅ `captured` 2 field (1 khớp, 1 khác): marker chỉ giữ field không-conflict, đúng 1 entry conflict cho field kia                                                                                                                                              |
| TC-SYNC-06     | ✅ `captured["fields"]` có key tham số đã bị xoá khỏi file tầng 2 giả: field tự rớt khỏi marker, không tạo conflict giả                                                                                                                                       |
| TC-SYNC-07     | ⚠️ Xác nhận DEF-01 (xem Phần C) — 2 lần `shutil.copytree()` liên tiếp cùng `backup_dir`: lần 2 ném `FileExistsError`                                                                                                                                          |
| TC-SYNC-08     | ✅ Import 4 module đồng thời (`module=None`) qua SSE: tất cả skip đúng (version không đổi), marker `getTicket` không bị ảnh hưởng, 4 backup folder riêng biệt không đụng nhau                                                                                 |
| TC-SYNC-09     | ✅ Đọc `backend/routers/modules.py` xác nhận `_resolve_manual_edits_after_import()` nằm trong nhánh chỉ chạy khi `run_batch()` không raise — verify tĩnh, chưa trigger lỗi thật qua runtime (rủi ro thấp, khó dựng input lỗi an toàn không đụng `2.pipeline`) |
| TC-CONFLICT-07 | 🐛 Xác nhận DEF-02 (xem Phần C) — `operationId: "totallyFakeOpId999"` (không tồn tại đâu cả), resolve `keep_old` trả `200 {"ok": true}` nhưng không ghi gì                                                                                                    |
| TC-CONFLICT-08 | ✅ Xoá tạm `get_ticket.yaml`, conflict `getTicket` resolve `keep_old`: tầng 3 sửa đúng giá trị cũ, tầng 2 thiếu file bỏ qua an toàn                                                                                                                           |
| TC-CONFLICT-09 | ✅ `pkill` backend giữa lúc bấm "Giữ bản cũ" trên UI thật: hiện đúng lỗi kết nối, nút bấm lại được ngay (không stuck), entry không bị xoá khỏi queue                                                                                                          |
| TC-CONFLICT-10 | ✅ `old_value: ""` → UI hiện `<em>(rỗng)</em>`                                                                                                                                                                                                                |
| TC-CONFLICT-11 | ✅ 2 conflict khác operation, resolve 1 cái: entry còn lại không bị ảnh hưởng                                                                                                                                                                                 |

**Dọn dẹp:** `get_ticket.yaml`, `create_tickets.yaml` khôi phục tay (giá trị gốc
`createTickets.summary` lấy lại từ bundle revert qua `git checkout` vì không còn
backup); bundle revert nhiều lần trong suốt vòng test; `manual_edit_conflicts.json`
xoá sau mỗi case; 4 backup folder từ TC-SYNC-08 đã xoá; `module_registry.yaml` revert
`git checkout`.

**Kết luận:** 16/18 case pass đúng thiết kế. 2 case lộ bug thật — xem DEF-01, DEF-02 ở
Phần C.

## 2026-06-29 — Đồng bộ tầng 2+3 cho AI-fix/YAML thô + generic-hoá marker (TC-FE-01, TC-YAML-01..04, TC-AIFIX-01..03, TC-CONFLICT-03 lặp lại)

Theo plan "Đồng bộ tầng 2 + tầng 3 cho AI-fix / sửa tay YAML thô" — fix bug chính:
`PUT /docs/bundle-content` (YAML thô + AI-fix) trước đây chỉ ghi tầng 3, mất khi "Build
tài liệu" chạy lại. Marker `x-manual-edit-fields` đổi từ dict cố định 4 field sang list
field-path tổng quát. Test qua UI thật (Playwright) + Python script cách ly, backend
`uvicorn` port 8000 + frontend `npm run dev` port 3000.

| TC ID                                       | Kết quả thực tế                                                                                                                                                                                                                                 |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TC-FE-01 (marker format mới)                | ✅ Sửa `description` của `getTicket` qua UI: `PATCH /docs/operations` ghi đúng cả 2 tầng; marker đổi đúng format mới `x-manual-edit-fields: [description]` (list field-path, không còn dict cố định)                                             |
| TC-YAML-01                                  | ✅ Đổi `required: true → false` của parameter `user_id` trong `updateClose` qua tab YAML thô (field ngoài 4 field cũ của Form Editor): tầng 2 nhận đúng giá trị + marker `parameters[name=user_id].required`; tầng 3 ghi verbatim giữ format gốc |
| TC-YAML-02                                  | ✅ Bấm "Tạo lại tài liệu" sau khi sửa ở TC-YAML-01: `required: false` **không bị mất** — đây là bug chính đã fix (trước fix sẽ bị đè mất)                                                                                                        |
| TC-YAML-03                                  | ✅ Paste `[invalid, yaml,, ,, {{{ ]]]`, bấm Lưu: alert lỗi `400 BUNDLE_INVALID_YAML`, checksum cả 2 tầng không đổi                                                                                                                               |
| TC-YAML-04                                  | 🐛→✅ Xác nhận DEF-03 (xem Phần C) lúc test, **đã fix ngay trong vòng test này** — verify lại: tab YAML thô với fetch mới, marker cộng dồn đúng `[description, responses[422].description]`, không tự tham chiếu nữa                              |
| TC-AIFIX-01                                 | ✅ Tạo lỗi lint thật, bấm "AI tự fix lỗi" (26 patch), bấm "Áp dụng": `PUT /docs/bundle-content` bắn ngay (thấy trong Network tab), checksum đổi ngay                                                                                             |
| TC-AIFIX-02                                 | ✅ AI-fix thêm `description` cho `properties.id`/`properties.name` trong `UserInfo.yaml`: `sync_schema_fields` ghi đúng cả 2 field + marker dạng dot-path `[properties.id.description, properties.name.description]`                             |
| TC-AIFIX-03                                 | ⚠️ Xác nhận DEF-04 (xem Phần C) — batch fix nhiều operation cùng lúc, AI sinh description chung chung/sai nghiệp vụ cho 5 operation                                                                                                              |
| TC-CONFLICT-03 (lặp lại với marker generic) | ✅ Bơm conflict field `description` (format mới), click "Giữ bản cũ" trên UI: ghi đúng `old_value` vào cả 2 tầng, entry biến mất khỏi queue                                                                                                      |

**Dọn dẹp:** `get_ticket.yaml`, `update_close.yaml` khôi phục tay, xoá marker test;
5 file operation liên quan DEF-04 revert `description`/`parameters[].description` về
rỗng như gốc; 3 schema file (`StandardSuccess`, `StandardError`, `UserInfo`) **giữ lại**
theo quyết định user (nội dung AI sinh đúng, fix đúng lint warning thật); bundle build
lại lần cuối phản ánh trạng thái sạch; `manual_edit_conflicts.json` về `[]`; backend/
frontend tắt hẳn, xác nhận bằng `ss -ltnp`.

**⚠️ Gap kế thừa từ 2026-06-26:** vẫn chưa test qua pipeline thật với version đổi thật
(xem gap ở đợt 2026-06-26 đợt 1) — lần này user chủ động chọn cách test rẻ hơn (bơm
conflict giả) để tránh tốn token AI + tránh đụng dữ liệu ticket thật qua pipeline thật.
Quyết định có chủ ý, không phải do quên.

**Kết luận:** Cơ chế đồng bộ tầng 2+3 (Form Editor, YAML thô, AI-fix, duyệt conflict)
PASS qua UI thật với marker format mới. DEF-03 phát hiện và fix ngay trong test. DEF-04
ghi nhận làm input cải thiện prompt AI-fix.

## 2026-06-30 — Breadcrumb + parent context cho prompt AI-fix (TC-AIFIX-04, TC-AIFIX-05)

Liên quan DEF-04 (AI sinh description sai nghiệp vụ khi thiếu context riêng từng
field). Unit test 2 hàm `_get_breadcrumb`/`_get_parent_block`
(`backend/services/ai_fix.py`) qua standalone script Python (không qua pytest vì
backend chưa có infra test) — import `indent_of`/`extract_key`/`find_block_end` từ
`backend/utils/yaml_line.py`, copy logic 2 hàm để chạy cách ly (không import được
`ai_fix.py` trực tiếp vì cần `anthropic`/`core.errors` full backend env).

| TC ID       | Kết quả thực tế                                                                                                                                                                                                               |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TC-AIFIX-04 | ✅ YAML mẫu 9 cấp lồng nhau (path → operation → response → content → schema → properties → field): breadcrumb trả đúng `paths./tickets/{id}.get.responses.'200'.content.application/json.schema.properties.status.description` |
| TC-AIFIX-05 | ✅ Cùng YAML mẫu, field `status.description` có sibling `priority` cùng cấp: `parent_text` trả đúng block `properties` chứa cả `status` lẫn `priority` (lấy 2 cấp cha, đủ thấy sibling)                                        |

**Dọn dẹp:** script test standalone đã xoá, không phải file của project.

**⚠️ Gap — chưa test end-to-end qua API thật để xác nhận DEF-04 đã được khắc phục:** 2
hàm helper đã verify đúng ở mức unit (pure function, dữ liệu giả lập nhỏ). Chưa chạy
lại đúng kịch bản TC-AIFIX-03 (AI-fix 1 batch nhiều operation cùng lúc, lỗi "thiếu
description") qua API thật để so sánh: có breadcrumb/parent_text thì AI có còn sinh
description sai nghiệp vụ như DEF-04 không. Vì đây là lỗi chất lượng đầu ra của AI
(không tất định 100%), cần chạy lại với cùng bộ lỗi lint thật và tốn 1 lần gọi AI thật
mới kết luận được.

---

# Phần C — Defect Log

| ID     | Mô tả                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Phát hiện qua                     | Mức độ                                                       | Trạng thái                                                                                                                                                                                       |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| DEF-01 | 2 lần backup trùng giây (`shutil.copytree()` gọi liên tiếp với cùng tên `backup_dir` dựa trên `strftime` giây) → lần 2 ném `FileExistsError`; code có `try/except` bọc quanh nên không crash job, nhưng **backup của lần import thứ 2 bị mất âm thầm**, chỉ log traceback ở backend, không cảnh báo user. Đề xuất fix: thêm microsecond/UUID vào tên folder backup                                                                                                                                                                                  | TC-SYNC-07 (2026-06-26 đợt 2)     | Nhẹ — edge case hiếm (2 import rất sát giây cho cùng module) | ❌ Chưa fix                                                                                                                                                                                       |
| DEF-02 | Resolve "thành công giả": khi `operationId` trong 1 conflict entry không còn tồn tại ở bất kỳ đâu (bundle và tầng 2 đều không có, vd do AI sinh lại `operationId` khác sau lần import sau) — resolve `keep_old` trả `200 {"ok": true}` như thành công nhưng **không ghi gì vào đâu cả**, entry biến mất khỏi queue vĩnh viễn, mất luôn dữ liệu cũ không cách nào lấy lại từ UI. Đề xuất fix: trước khi xoá entry khỏi queue, kiểm tra có thực sự tìm thấy operation trong bundle hoặc tầng 2 không — nếu không, trả lỗi (404/410) thay vì `200` giả | TC-CONFLICT-07 (2026-06-26 đợt 2) | Trung bình — mất dữ liệu im lặng                             | ❌ Chưa fix                                                                                                                                                                                       |
| DEF-03 | `x-manual-edit-fields` tự tham chiếu chính nó khi diff: sửa ở tab Form Editor (marker ghi tầng 2+3) → chuyển tab YAML thô **không** đóng/mở lại modal (bundle content cũ còn trong state) → sửa tiếp 1 field khác, Lưu → `diff_bundle` so `old_bundle` (đã có marker mới) với `new_bundle` (bản stale, chưa có marker) → coi marker là field user sửa → marker tự liệt kê chính nó                                                                                                                                                                  | TC-YAML-04 (2026-06-29)           | Trung bình — phá marker tracking                             | ✅ Đã fix (2026-06-29) — thêm `if key == "x-manual-edit-fields": continue` vào đầu loop `_diff_recursive` (`backend/services/bundle_sync.py`), loại trừ marker khỏi diff vì là bookkeeping nội bộ |
| DEF-04 | Chất lượng AI-fix: khi 1 lượt fix nhiều lỗi "thiếu description" cùng lúc cho nhiều operation khác nhau trong 1 batch, AI sinh description chung chung/sai nghiệp vụ (vd `createReopen` → "Lấy danh sách tài nguyên." dù là API mở lại ticket; sai tương tự cho 4 operation khác). Khác với field schema (Phần A7/TC-AIFIX-02, nội dung AI sinh đúng) — do thiếu context riêng từng operation khi fix dồn 1 lượt                                                                                                                                     | TC-AIFIX-03 (2026-06-29)          | Chất lượng output AI, không phải bug logic                   | ⚠️ Đang xử lý — TC-AIFIX-04/05 (breadcrumb + parent context, 2026-06-30) là hướng fix, nhưng **chưa verify end-to-end** có thực sự giải quyết DEF-04 hay không (xem gap ở đợt 2026-06-30)         |
