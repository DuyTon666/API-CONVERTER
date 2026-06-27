# Persist Form Editor edits qua tầng 2 + backup + review xung đột khi reimport

> **Trạng thái:** Plan đã được duyệt nội dung (2026-06-25). User yêu cầu hoãn triển khai
> sang **ngày mai (2026-06-26)**, chưa code gì lúc này. Khi quay lại, đọc thẳng plan này
> và bắt đầu từ Phần 1.

## Context

API Converter có 3 tầng dữ liệu OpenAPI:
- **Tầng 1**: tài liệu nguồn (`1.docs/source/api_contract/<module>/*.pdf|docx`)
- **Tầng 2**: file fragment do pipeline sinh, 1 file/operation, ví dụ `5.openapi/paths/ticket/get_ticket.yaml` (chứa `summary`, `operationId`, `description`, `parameters`, `responses` trực tiếp)
- **Tầng 3**: bundle `dist/openapi-bundled.yaml`

Form Editor (`PATCH /docs/operations`) hiện chỉ ghi tầng 3. Mỗi lần import lại, pipeline có thể ghi đè tầng 2 → tầng 3 build lại từ tầng 2 → mất sửa tay.

**Phát hiện quan trọng làm gọn bài toán** (`2.pipeline/pipeline_API.py:280-321`, không sửa file này): pipeline đã có cơ chế skip theo version — nếu version đọc từ nội dung tài liệu nguồn **không đổi** so với lần import trước, file đó bị `continue` bỏ qua hoàn toàn, `emit_yaml()` không được gọi. Tức là: **đa số các lần "Import lại" không hề đụng tới tầng 2** — sửa tay tự nhiên an toàn. Chỉ khi tài liệu nguồn thật sự được cập nhật version mới thì file tầng 2 tương ứng mới bị ghi đè, và đây là lúc cần xử lý.

## Quyết định đã chốt với user

1. `PATCH /docs/operations` ghi tầng 2 + tầng 3 **đồng thời, tự động**, không thêm nút riêng.
2. Backup tầng 2 chạy **trước mỗi lần import**, dạng **thư mục copy có timestamp** dưới `3.build/backups/`.
3. Khi version doc đổi thật và giá trị sửa tay khác với giá trị pipeline sinh mới (xung đột thật) → **không tự động ghi đè** — ghi vào danh sách review, user duyệt sau (giữ bản cũ hay lấy bản mới), giống UX `SuggestCard` đang có.
4. **Toàn bộ thay đổi nằm trong `backend/` + `frontend/`. Không sửa bất kỳ file nào trong `2.pipeline/`** (do teammate khác phụ trách phần đó). Tận dụng `run_batch()` y nguyên như hiện có (tham số `output_dir`/`schemas_dir` đã đủ dùng, không cần đổi gì bên trong).

## Cơ chế marker: `x-manual-edit-fields`

Field extension ghi vào operation object trong file tầng 2 (theo tiền lệ `x-permission` đã có sẵn, không cần sửa gì trong `2.pipeline/` để "dạy" nó hiểu field này — pipeline đơn giản là không biết tới field này, và đó là chủ đích: khi pipeline ghi đè file (version đổi), field này tự nhiên biến mất khỏi file mới, và chính backend — không phải pipeline — chịu trách nhiệm ghi lại nó sau khi `run_batch()` chạy xong):

```yaml
get:
  summary: "..."
  operationId: getTicket
  x-permission: CHECK_NEWUPDATE
  x-manual-edit-fields:
    summary: true
    description: true
    parameters: ["user_id", "id"]
    responses: ["404", "422"]
  parameters: [...]
```

## Phần 1 — `backend/routers/docs.py`: Form Editor ghi tầng 2

Trong `update_operations()` (`PATCH /docs/operations`, hiện chỉ ghi `dist/openapi-bundled.yaml`):

- Thêm `OUTPUT_DIR` vào import (`from config import DIST_DIR, OUTPUT_DIR`).
- Tách logic áp dụng update hiện có (match `summary`/`description`/`parameters[].description`/`responses[].description`, giữ đúng guard `"$ref" not in p`/`resp`) thành hàm chung `_apply_operation_update(operation: dict, upd: dict) -> dict` (trả về `touched` fields) — dùng lại được cho cả dict của bundle và dict của file tầng 2.
- Thêm `_index_operation_files() -> dict[str, Path]`: quét `OUTPUT_DIR / "paths"` 1 lần, dùng `_HTTP_METHODS` (đã có ở dòng ~248) tìm method key trong mỗi file, lấy `operationId`, build map.
- Thêm `_merge_marker(existing: dict | None, touched: dict) -> dict | None` — union, trả `None` nếu rỗng.
- Trong loop hiện có của `update_operations()`: với mỗi `op_id` khớp — áp update + merge marker vào bundle (như cũ), **đồng thời** tra `index.get(op_id)`, nếu có file tầng 2 thì đọc bằng `ruamel.yaml.YAML()` (style giống file gốc: `default_flow_style=False`, `indent(mapping=2, sequence=4, offset=2)`), áp lại `_apply_operation_update` trên dict của file đó, merge marker, ghi đè file. Không tìm thấy file → bỏ qua, không fail cả request.

## Phần 2 — `backend/routers/modules.py`: backup + capture/restore + phát hiện xung đột

Toàn bộ nằm trong `_run_import_job()`, vòng `for m, mr in zip(to_run, job.modules):`, quanh lời gọi `run_batch(...)` hiện có.

### 2a. Trước `run_batch()` (backup + capture)

```python
import shutil, datetime

paths_dir = output_root / m["name"]
schemas_dir_m = schemas_root / m["name"]

# Backup — copy nguyên trạng trước khi pipeline có thể ghi đè
if paths_dir.exists() or schemas_dir_m.exists():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = CONFIG_DIR.parent / "3.build" / "backups" / f"openapi_{m['name']}_{ts}"
    if paths_dir.exists():
        shutil.copytree(paths_dir, backup_dir / "paths")
    if schemas_dir_m.exists():
        shutil.copytree(schemas_dir_m, backup_dir / "schemas")

# Capture — lưu giá trị field đã sửa tay (theo marker) trước khi pipeline đụng vào
captured = _scan_manual_edits(paths_dir)   # {operationId: {"file": Path, "fields": {...}}}
```

`_scan_manual_edits(paths_dir)` (hàm mới, riêng cho `modules.py`, không tái dùng helper của `docs.py` để tránh tạo module dùng chung mới — duplicate logic quét file ở mức nhỏ, chấp nhận được): quét mọi `*.yaml` dưới `paths_dir`, với operation có `x-manual-edit-fields`, trích đúng giá trị hiện tại của các field/param/response được đánh dấu.

### 2b. Gọi `run_batch()` — giữ nguyên, không đổi gì

(File version không đổi → tự skip, tầng 2 không bị đụng. File version đổi → bị ghi đè như hiện tại, marker bị mất theo.)

### 2c. Sau `run_batch()` (so sánh + áp dụng/khoanh vùng xung đột)

Với mỗi `operationId` trong `captured`:
- Tìm lại operation đó trong `paths_dir` sau khi import (quét theo `operationId`, không theo tên file — chịu được việc pipeline đổi tên file giữa 2 lần chạy).
- **Không tìm thấy file** → file bị skip (version không đổi) hoặc operation biến mất khỏi doc → giữ nguyên, không cần làm gì (file vốn không bị đụng, marker vẫn còn nếu skip).
- **Tìm thấy, giá trị field mới == giá trị cũ đã capture** → không xung đột (có thể do skip, hoặc tình cờ sinh giống) → ghi lại marker (đảm bảo marker không bị mất nếu file vừa bị ghi đè trùng giá trị).
- **Tìm thấy, giá trị field mới != giá trị cũ đã capture** → **xung đột thật**: KHÔNG tự ghi đè. Giữ giá trị mới (vừa sinh) trong file như hiện trạng, KHÔNG set lại marker cho field đó (để field này tạm thoát khỏi vùng bảo vệ cho tới khi được duyệt). Append 1 entry vào file review queue mới: `3.build/reports/manual_edit_conflicts.json` — gồm `operationId`, `module`, `field` (hoặc `parameters.<name>` / `responses.<code>`), `old_value`, `new_value`, `detected_at`.

## Phần 3 — API mới cho review xung đột (`backend/routers/modules.py` hoặc file router mới nhỏ)

- `GET /modules/manual-edit-conflicts` — đọc `manual_edit_conflicts.json`, trả list pending.
- `POST /modules/manual-edit-conflicts/resolve` — body `{operationId, field, choice: "keep_old" | "accept_new"}`:
  - `keep_old`: ghi `old_value` vào file tầng 2 (qua `_apply_operation_update`-style helper, tái dùng từ Phần 1) + vào bundle, set lại marker cho field đó.
  - `accept_new`: không đổi gì trong file (giá trị mới đã sẵn đó), chỉ đơn giản không set marker (field này không còn được coi là "đã sửa tay" nữa).
  - Cả 2 trường hợp: xoá entry khỏi `manual_edit_conflicts.json`.

## Phần 4 — Frontend: card review xung đột nhỏ

Component mới `ManualEditConflictsCard` (đặt cạnh `SuggestCard` trong `app/_dashboard/`), theo đúng UX pattern đã có:
- Gọi `GET /modules/manual-edit-conflicts` lúc load + sau mỗi lần import xong.
- Hiển thị list: operationId, field, giá trị cũ (sửa tay) vs giá trị mới (pipeline sinh), 2 nút "Giữ bản cũ" / "Lấy bản mới" gọi `POST /modules/manual-edit-conflicts/resolve`.
- Ẩn card nếu list rỗng (không làm rối UI lúc không có gì cần duyệt).

## Rủi ro / edge case

- **`operationId` đổi giữa 2 lần import** (hiếm, do LLM sinh operationId khác): `_scan_manual_edits` sau import không tìm thấy operationId cũ → coi như "không tìm thấy", sửa tay cũ bị mất lặng lẽ. Chấp nhận làm hạn chế đã biết (đã nêu rõ, không che giấu).
- **Tham số/response bị xoá khỏi doc khi version đổi**: so sánh theo key (tên param / status code) — nếu key không còn tồn tại trong file mới, coi như "không tìm thấy" cho riêng field đó, marker tự rớt field đó (không tạo conflict giả cho thứ không còn tồn tại).
- **Backup/capture lỗi (disk đầy...)**: bọc try/except, log lỗi, không chặn import tiếp tục chạy.
- **`manual_edit_conflicts.json` đồng thời bị nhiều request đọc/ghi**: vì backend hiện tại không có khoá tiến trình cho các file JSON khác (`import_suggestions.json` cũng đọc/ghi tương tự không lock) — theo đúng pattern hiện có của project, không thêm cơ chế lock mới (out of scope, rủi ro thấp với quy mô 1 người dùng nội bộ).

## Kiểm chứng (verification)

1. Sửa tay `description` 1 operation qua Form Editor → kiểm tra `5.openapi/paths/.../*.yaml` có giá trị mới + marker đúng, `dist/openapi-bundled.yaml` cùng giá trị.
2. Import lại module đó **khi version doc nguồn không đổi** → file tầng 2 giữ nguyên 100% (do pipeline tự skip) → không có gì trong conflict queue.
3. Sửa version trong 1 file nguồn (giả lập doc được update) rồi import lại → file tầng 2 operation đó bị ghi đè bởi pipeline → kiểm tra: nếu giá trị mới sinh khác giá trị sửa tay, phải xuất hiện đúng 1 entry trong `manual_edit_conflicts.json` và hiển thị trên `ManualEditConflictsCard`; field đó **không** tự bị ghi đè ngược lại.
4. Bấm "Giữ bản cũ" trên 1 conflict → xác nhận file tầng 2 + bundle đổi lại đúng giá trị cũ, entry biến mất khỏi queue, marker được set lại.
5. Bấm "Lấy bản mới" trên 1 conflict khác → xác nhận file giữ giá trị mới (không đổi gì thêm), entry biến mất khỏi queue, marker không còn field đó.
6. Kiểm tra `3.build/backups/openapi_<module>_<timestamp>/` xuất hiện đúng trước mỗi lần import, chứa bản nội dung **trước** khi bị ghi đè.
7. Module chưa từng import — import lần đầu — không có backup nào được tạo, không có gì trong capture (vì `paths_dir` chưa tồn tại).
