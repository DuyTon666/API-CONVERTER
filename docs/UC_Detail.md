# Đặc tả Use Case Chi Tiết — API Converter

## Danh sách UC

| STT  | UC                                | Actor              |
| ---- | --------------------------------- | ------------------ |
| UC01 | Quản lý tài liệu đầu vào          | Người dùng         |
| UC02 | Phân loại file vào module         | Người dùng         |
| UC03 | Quản lý module registry           | Người dùng         |
| UC04 | Import module                     | Người dùng         |
| UC05 | Chỉnh sửa & duyệt nội dung        | Người dùng         |
| UC06 | Build & xuất bản tài liệu         | Người dùng         |
| UC07 | Xem tài liệu API                  | Người dùng         |
| UC08 | Enrich metadata API               | Claude AI          |
| UC09 | Bundle toàn bộ YAML thành 1 file  | Redocly / Spectral |
| UC10 | Lint bundle theo chuẩn OpenAPI    | Redocly / Spectral |
| UC11 | Lint bundle theo governance rules | Redocly / Spectral |
| UC12 | Deploy tài liệu                   | Người dùng          |

---

## UC01 — Quản lý tài liệu đầu vào

| Trường                   | Nội dung                                                                                                           |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| **Mã UC**                | UC01                                                                                                               |
| **Tên UC**               | Quản lý tài liệu đầu vào                                                                                           |
| **Tác nhân chính**       | Người dùng                                                                                                         |
| **Mô tả**                | Người dùng tải tài liệu đặc tả API lên hệ thống và quét thư mục nguồn để phát hiện các file mới chưa được xử lý    |
| **Điều kiện tiên quyết** | Người dùng đã truy cập vào dashboard. Hệ thống backend đang chạy                                                   |
| **Điều kiện hậu**        | File được lưu vào thư mục `1.docs/source/api_contract/`. Danh sách file và module hiển thị cập nhật trên giao diện |

### Luồng chính

| Bước | Người dùng                                                | Hệ thống                                                         |
| ---- | --------------------------------------------------------- | ---------------------------------------------------------------- |
| 1    | Kéo thả hoặc chọn file (PDF / DOCX) vào vùng upload |                                                                  |
| 2    |                                                           | Kiểm tra định dạng file hợp lệ                                   |
| 3    |                                                           | Lưu file vào `1.docs/source/api_contract/`                       |
| 4    |                                                           | Trả về danh sách file đã upload kèm tên và dung lượng            |
| 5    | Bấm "Quét nguồn dữ liệu"                                  |                                                                  |
| 6    |                                                           | Quét toàn bộ thư mục nguồn                                       |
| 7    |                                                           | Phân loại: file nằm trong module folder / file chưa gán module   |
| 8    |                                                           | Hiển thị danh sách module folders và file chưa gán lên giao diện |

### Luồng thay thế

**A1 — File đã tồn tại:**
- Tại bước 3, nếu file trùng tên đã có trong thư mục → hệ thống ghi đè file cũ → tiếp tục bước 4.

**A2 — Bỏ qua bước upload, chỉ quét:**
- Người dùng bỏ qua bước 1–4, bấm thẳng "Quét nguồn dữ liệu" → luồng tiếp tục từ bước 6.

### Luồng ngoại lệ

**E1 — Sai định dạng file:**
- Tại bước 2, file không phải PDF / DOCX → hệ thống báo lỗi, không lưu file → người dùng chọn lại file khác.

**E2 — Upload TXT/MD thành công nhưng import luôn thất bại:**
- Bước kiểm tra định dạng (bước 2) thực chất chấp nhận cả `.txt`/`.md` (khai báo trong `4.config/import_flow.yaml`), nên file vẫn lưu được — nhưng đến bước import (UC04), `parse_text()` chỉ nhận diện được method/path khi text có đúng label chuẩn hóa mà `read_docx()`/`read_pdf()` tự sinh ra (vd `"Method: GET"`) — file `.txt`/`.md` thô hầu như không có label này nên luôn báo lỗi `"Không tìm thấy method hoặc path trong tài liệu."` (đã ghi nhận thực tế trong `3.build/reports/version_run_history.jsonl`, run `20260618_142727_ticket_api`). Coi như PDF/DOCX là 2 định dạng thực sự dùng được; TXT/MD chỉ nối dây ở tầng upload, chưa hoạt động.

**E2 — Backend không phản hồi:**
- Tại bước 3 hoặc 6 → hệ thống hiển thị thông báo lỗi kết nối → người dùng thử lại.

### Quan hệ

| Loại     | UC liên quan |
| -------- | ------------ |
| Không có | —            |

---

## UC02 — Phân loại file vào module

| Trường                   | Nội dung                                                                                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Mã UC**                | UC02                                                                                                                                                   |
| **Tên UC**               | Phân loại file vào module                                                                                                                              |
| **Tác nhân chính**       | Người dùng                                                                                                                                             |
| **Mô tả**                | Người dùng yêu cầu hệ thống tự động gợi ý module phù hợp cho từng file tài liệu, sau đó xem xét, duyệt và apply để chuyển file vào đúng thư mục module |
| **Điều kiện tiên quyết** | Đã có file tài liệu trong thư mục `1.docs/source/api_contract/`. UC01 đã được thực hiện                                                                |
| **Điều kiện hậu**        | File được sao chép vào thư mục module tương ứng. Registry cập nhật danh sách file theo module                                                          |

### Luồng chính

| Bước | Người dùng                                                 | Hệ thống                                                                   |
| ---- | ---------------------------------------------------------- | -------------------------------------------------------------------------- |
| 1    | Bấm "Gợi ý module"                                         |                                                                            |
| 2    |                                                            | Đọc từng file, trích xuất endpoint path và service field                   |
| 3    |                                                            | So khớp endpoint với rules trong `module_resolution.yaml`                  |
| 4    |                                                            | Tính confidence score cho từng gợi ý (high / medium / low)                 |
| 5    |                                                            | Hiển thị danh sách gợi ý kèm module, lý do, trạng thái chờ duyệt           |
| 6    | Xem xét từng gợi ý, nhập override module nếu muốn thay đổi |                                                                            |
| 7    | Chọn các file muốn duyệt, bấm "Duyệt (n) file"             |                                                                            |
| 8    |                                                            | Đánh dấu các file đã chọn là "Đã duyệt", lưu vào `import_suggestions.json` |
| 9    | Bấm "Apply suggestions"                                    |                                                                            |
| 10   |                                                            | Sao chép file vào thư mục `1.docs/source/api_contract/<module>/`           |
| 11   |                                                            | Cập nhật registry, hiển thị kết quả applied / skipped                      |

### Luồng thay thế

**A1 — Override module:**
- Tại bước 6, người dùng nhập tên module khác vào ô override → tại bước 8, hệ thống dùng module override thay vì module gợi ý.

**A2 — Duyệt tất cả cùng lúc:**
- Tại bước 6, người dùng tick checkbox "Chọn tất cả" → bước 7 duyệt toàn bộ file pending trong một lần.

**A3 — File đã được duyệt trước đó:**
- Tại bước 7, file đã có trạng thái "Đã duyệt" → hệ thống bỏ qua, không duyệt lại → checkbox bị disable.

### Luồng ngoại lệ

**E1 — Không tìm được module phù hợp:**
- Tại bước 3, endpoint không khớp với bất kỳ rule nào → confidence score = low, status = `needs_review` → file vẫn hiển thị nhưng cần người dùng nhập override thủ công.

**E2 — Conflict giữa endpoint rule và service field:**
- Tại bước 3, module từ endpoint rule khác với service ghi trong tài liệu → hệ thống đánh dấu conflict, confidence score = medium → người dùng tự quyết định duyệt hay override.

**E3 — Không có file nào được duyệt khi apply:**
- Tại bước 9, chưa có file nào ở trạng thái "Đã duyệt" → nút "Apply suggestions" bị disable, hệ thống không thực hiện.

### Quan hệ

| Loại     | UC liên quan |
| -------- | ------------ |
| Không có | —            |

---

## UC03 — Quản lý module registry

| Trường                   | Nội dung                                                                                                                                           |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mã UC**                | UC03                                                                                                                                               |
| **Tên UC**               | Quản lý module registry                                                                                                                            |
| **Tác nhân chính**       | Người dùng                                                                                                                                         |
| **Mô tả**                | Người dùng xem danh sách module trong hệ thống cùng trạng thái vòng đời, và kích hoạt module từ draft lên active để cho phép chạy pipeline convert |
| **Điều kiện tiên quyết** | Đã có ít nhất một module trong `module_registry.yaml`. UC02 đã được thực hiện                                                                      |
| **Điều kiện hậu**        | Module được cập nhật trạng thái active. Giao diện hiển thị trạng thái mới                                                                          |

### Luồng chính

| Bước | Người dùng                                       | Hệ thống                                                                                                              |
| ---- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| 1    | Truy cập dashboard                               |                                                                                                                       |
| 2    |                                                  | Đọc `module_registry.yaml`, hiển thị danh sách module kèm trạng thái, số file, số endpoint, thời điểm import gần nhất |
| 3    | Xem xét module có trạng thái draft cần kích hoạt |                                                                                                                       |
| 4    | Bấm "Activate" trên module muốn kích hoạt        |                                                                                                                       |
| 5    |                                                  | Cập nhật trạng thái module từ `draft` → `active` trong registry                                                       |
| 6    |                                                  | Hiển thị lại bảng module với trạng thái đã cập nhật                                                                   |

### Luồng thay thế

**A1 — Module đã ở trạng thái active:**
- Tại bước 4, module đã active → nút "Activate" không hiển thị → người dùng có thể dùng nút "Import" thay thế (chuyển sang UC04).

**A2 — Module ở trạng thái deprecated:**
- Module deprecated không có nút thao tác → người dùng chỉ xem, không thể kích hoạt lại từ giao diện.

### Luồng ngoại lệ

**E1 — Không có module nào trong registry:**
- Tại bước 2, registry rỗng → hệ thống hiển thị thông báo "Chưa có module nào" → người dùng cần thực hiện UC02 trước.

**E2 — Kích hoạt thất bại:**
- Tại bước 5, backend trả về lỗi → hệ thống hiển thị thông báo lỗi → trạng thái module không thay đổi.

### Quan hệ

| Loại     | UC liên quan |
| -------- | ------------ |
| Không có | —            |

---

## UC04 — Import module

| Trường                   | Nội dung                                                                                                                                                                           |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mã UC**                | UC04                                                                                                                                                                               |
| **Tên UC**               | Import module                                                                                                                                                                      |
| **Tác nhân chính**       | Người dùng                                                                                                                                                                         |
| **Mô tả**                | Người dùng kích hoạt pipeline convert để chuyển đổi tài liệu của một hoặc tất cả module active thành tệp OpenAPI YAML chuẩn hóa, đồng thời theo dõi tiến trình theo thời gian thực |
| **Điều kiện tiên quyết** | Có ít nhất một module ở trạng thái active. File tài liệu đã được sao chép vào thư mục module (UC02 hoàn tất)                                                                       |
| **Điều kiện hậu**        | Tệp OpenAPI YAML được tạo ra trong `5.openapi/paths/<module>/` và `5.openapi/schemas/`. Log kết quả được ghi vào `3.build/reports/`                                                |

### Luồng chính

| Bước | Người dùng                                               | Hệ thống                                                                                                  |
| ---- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 1    | Bấm "Import tất cả" hoặc "Import" trên một module cụ thể |                                                                                                           |
| 2    |                                                          | Lấy danh sách file thuộc module, kiểm tra hash để bỏ qua file chưa thay đổi                               |
| 3    |                                                          | Parse từng file tài liệu → trích xuất `ParsedOperation` (method, path, parameters, request/response body) |
| 4    |                                                          | Gọi Claude AI để enrich metadata `<<include UC08>>`                                                       |
| 5    |                                                          | Generate tệp OpenAPI YAML từ `ParsedOperation` đã enrich                                                  |
| 6    |                                                          | Post-process: gắn `readOnly` cho server-managed fields, thay thế trường lặp bằng `$ref`                   |
| 7    |                                                          | Phát SSE event cập nhật tiến trình (file đang xử lý, số thành công / lỗi / bỏ qua)                        |
| 8    | Theo dõi thanh tiến trình trên giao diện                 |                                                                                                           |
| 9    |                                                          | Phát SSE event `done` khi hoàn tất, hiển thị tổng kết                                                     |

### Luồng thay thế

**A1 — File không thay đổi (hash trùng):**
- Tại bước 2, file đã được convert trước đó và nội dung không thay đổi → hệ thống bỏ qua (skipped), không convert lại.

**A2 — Import một module riêng lẻ:**
- Tại bước 1, người dùng bấm "Import" trên một module cụ thể thay vì "Import tất cả" → hệ thống chỉ xử lý file của module đó.

### Luồng ngoại lệ

**E1 — Parse file thất bại:**
- Tại bước 3, file bị lỗi định dạng hoặc thiếu dữ liệu → hệ thống ghi lỗi vào `batch_log.json`, đánh dấu file là `error`, tiếp tục với file tiếp theo.

**E2 — Claude AI thất bại:**
- Tại bước 4, gọi API Claude thất bại hoặc timeout → hệ thống tự fallback: sinh `operationId` bằng rule-based (method + path), tiếp tục generate YAML với metadata tối thiểu, đánh dấu file vào `human_review_queue.json`.

**E3 — Không có module active:**
- Tại bước 1, nút "Import tất cả" bị disable → hệ thống không thực hiện → người dùng cần kích hoạt module trước (UC03).

### Quan hệ

| Loại          | UC liên quan                           |
| ------------- | -------------------------------------- |
| `<<include>>` | UC08 — Enrich metadata API (Claude AI) |

---

## UC05 — Chỉnh sửa & duyệt nội dung

| Trường                   | Nội dung                                                                                                                                                                                                                                     |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mã UC**                | UC05                                                                                                                                                                                                                                          |
| **Tên UC**               | Chỉnh sửa & duyệt nội dung                                                                                                                                                                                                                    |
| **Tác nhân chính**       | Người dùng                                                                                                                                                                                                                                    |
| **Mô tả**                | Người dùng chỉnh sửa `summary`/`description`/parameter/response description qua Form Editor, hoặc chỉnh sửa trực tiếp YAML thô của bundle; hệ thống đồng bộ ghi thay đổi vào cả tầng 2 (`5.openapi/`) và tầng 3 (`dist/openapi-bundled.yaml`), đồng thời phát hiện và cho xử lý xung đột khi import lại (UC04) đè lên nội dung đã sửa tay |
| **Điều kiện tiên quyết** | Đã có bundle (`dist/openapi-bundled.yaml`) — tức UC04 rồi UC06 (hoặc lần build gần nhất) đã chạy ít nhất 1 lần                                                                                                                                |
| **Điều kiện hậu**        | Nội dung đã sửa được ghi vào cả tầng 2 và tầng 3, có gắn marker `x-manual-edit-fields`. Xung đột phát sinh từ import lại (nếu có) được ghi vào `manual_edit_conflicts.json` chờ xử lý                                                        |

### Luồng chính (tab "Chỉnh sửa nội dung" — Form Editor)

| Bước | Người dùng                            | Hệ thống                                                                          |
| ---- | -------------------------------------- | ------------------------------------------------------------------------------- |
| 1    | Mở Bundle Editor cho 1 module          |                                                                                 |
| 2    |                                        | Gọi `GET /docs/operations`, `GET /docs/schema-fields`, đọc bundle hiện tại      |
| 3    |                                        | Trả về summary/description/parameter/schema field description                   |
| 4    | Chọn operation muốn sửa, sửa nội dung |                                                                                 |
| 5    | Bấm "Lưu"                              |                                                                                 |
| 6    |                                        | Gọi `PATCH /docs/operations`, `PATCH /docs/schema-fields`                       |
| 7    |                                        | Ghi field + marker `x-manual-edit-fields` vào tầng 2 (ruamel.yaml, giữ format gốc) |
| 8    |                                        | Ghi field tương ứng vào tầng 3 (đồng bộ 2 tầng)                                  |
| 9    |                                        | Trả `200 { updated: n }`                                                         |

### Luồng thay thế

**A1 — Sửa qua tab "YAML thô":**
- Người dùng chuyển sang tab "YAML thô" thay vì Form Editor → hệ thống gọi `GET /docs/bundle-content`, hiển thị toàn bộ nội dung bundle qua Monaco Editor → người dùng sửa trực tiếp, bấm Lưu → hệ thống gọi `PUT /docs/bundle-content`, diff với bản cũ rồi ghi field thay đổi + marker field-path vào tầng 2, ghi verbatim (giữ nguyên format gốc) vào tầng 3.

**A2 — Xử lý xung đột sửa tay khi import lại:**
- Nếu UC04 (import lại) phát hiện tài liệu nguồn đã đổi VÀ giá trị mới sinh ra khác giá trị đã sửa tay trước đó → hệ thống ghi vào `manual_edit_conflicts.json`. Người dùng mở card "Xung đột sửa tay khi import lại", xem `operationId`/field/giá trị cũ/giá trị mới, chọn "Giữ bản cũ" (ghi lại `old_value` vào cả tầng 2 + tầng 3) hoặc "Lấy bản mới" (không đổi gì, chỉ xóa entry khỏi hàng đợi).

### Luồng ngoại lệ

**E1 — YAML sai cú pháp ở tab "YAML thô":**
- Tại A1, người dùng lưu bundle với YAML sai cú pháp → hệ thống trả `400 BUNDLE_INVALID_YAML`, không ghi gì ở cả 2 tầng.

**E2 — Lỗi đọc/ghi 1 file lúc đồng bộ marker:**
- Khi ghi marker `x-manual-edit-fields` vào tầng 2, nếu đọc/ghi 1 file gặp lỗi → hệ thống bỏ qua file đó, không làm fail cả request.

### Quan hệ

| Loại     | UC liên quan |
| -------- | ------------ |
| Không có | —            |

---

## UC06 — Build & xuất bản tài liệu

| Trường                   | Nội dung                                                                                                                                                                |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mã UC**                | UC06                                                                                                                                                                    |
| **Tên UC**               | Build & xuất bản tài liệu                                                                                                                                               |
| **Tác nhân chính**       | Người dùng                                                                                                                                                              |
| **Mô tả**                | Người dùng kích hoạt quá trình bundle, lint và build Swagger UI HTML từ các tệp YAML đã export. Có thể xem, sửa bundle trực tiếp nếu có lỗi và tải HTML về để phân phối |
| **Điều kiện tiên quyết** | Đã có tệp YAML trong `5.openapi/`. UC05 đã hoàn thành hoặc bundle cũ đã tồn tại                                                                                         |
| **Điều kiện hậu**        | Tệp `dist/openapi-bundled.yaml` và `public/api-docs.html` được tạo ra. Kết quả lint hiển thị trên giao diện                                                             |

### Luồng chính

| Bước | Người dùng                           | Hệ thống                                                                |
| ---- | ------------------------------------ | ----------------------------------------------------------------------- |
| 1    | Bấm "Build tài liệu Swagger UI"      |                                                                         |
| 2    |                                      | Bundle toàn bộ YAML → `dist/openapi-bundled.yaml` `<<include UC09>>`    |
| 3    |                                      | Lint bundle `<<include UC10, UC11>>`                                    |
| 4    |                                      | Build Swagger UI HTML → `public/api-docs.html`                          |
| 5    |                                      | Hiển thị kết quả lint (số lỗi error / warning theo Spectral và Redocly) |
| 6    | Xem kết quả lint trên giao diện      |                                                                         |
| 7    | Bấm nút "Developer Portal" trên thanh điều hướng để xem giao diện | Mở `/swagger` (Swagger UI) ở tab mới — tên nút không khớp với trang portal riêng trong code, xem ghi chú ở UC07 |

### Luồng thay thế

**A1 — Sửa bundle khi có lỗi lint:**
- Tại bước 6, người dùng phát hiện lỗi → bấm "Xem / Sửa lỗi bundle" → mở editor hiển thị nội dung `openapi-bundled.yaml` → chỉnh sửa trực tiếp → lưu lại.

**A2 — Kiểm tra lỗi lại mà không build lại:**
- Người dùng bấm "Kiểm tra lỗi" (Relint) → hệ thống chỉ chạy lại lint trên bundle hiện tại, không convert lại từ đầu.

**A3 — Build lại từ đầu:**
- Người dùng bấm "Tạo lại tài liệu" → hệ thống chạy lại toàn bộ từ bước 2.

### Luồng ngoại lệ

**E1 — Không có file YAML để bundle:**
- Tại bước 2, thư mục `5.openapi/` rỗng → Redocly báo lỗi → hệ thống hiển thị thông báo → người dùng cần thực hiện UC05 trước.

**E2 — Lỗi cú pháp trong bundle sau khi sửa tay:**
- Tại A1, người dùng lưu bundle với YAML sai cú pháp → lint trả về lỗi parse → hệ thống hiển thị lỗi, không build HTML.

### Quan hệ

| Loại          | UC liên quan                             |
| ------------- | ---------------------------------------- |
| `<<include>>` | UC09 — Bundle toàn bộ YAML thành 1 file  |
| `<<include>>` | UC10 — Lint bundle theo chuẩn OpenAPI    |
| `<<include>>` | UC11 — Lint bundle theo governance rules |

---

## UC07 — Xem tài liệu API

| Trường                   | Nội dung                                                                                                                                       |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mã UC**                | UC07                                                                                                                                           |
| **Tên UC**               | Xem tài liệu API                                                                                                                               |
| **Tác nhân chính**       | Người dùng                                                                                                                                     |
| **Mô tả**                | Người dùng xem tài liệu API đã được build dưới dạng Swagger UI tương tác, có thể tìm kiếm và lọc endpoint |
| **Điều kiện tiên quyết** | UC06 đã hoàn thành. Tệp `dist/openapi-bundled.yaml` tồn tại                                                                                    |
| **Điều kiện hậu**        | Không thay đổi dữ liệu. Người dùng đọc được thông tin API cần tìm                                                                              |

### Luồng chính

| Bước | Người dùng                                      | Hệ thống                                                                    |
| ---- | ----------------------------------------------- | --------------------------------------------------------------------------- |
| 1    | Truy cập trang Swagger UI (qua nút "Developer Portal" trên thanh điều hướng, hoặc URL `/swagger` trực tiếp) |                                                                             |
| 2    |                                                 | Tải `openapi-bundled.yaml` từ server                                        |
| 3    |                                                 | Render danh sách endpoint với method, path, summary, description            |
| 4    | Nhập từ khóa vào ô tìm kiếm                     |                                                                             |
| 5    |                                                 | Fuse.js thực hiện fuzzy search trên operationId, path, summary, description |
| 6    |                                                 | Hiển thị kết quả khớp theo độ liên quan                                     |
| 7    | Bấm vào endpoint muốn xem chi tiết              |                                                                             |
| 8    |                                                 | Hiển thị parameters, request body schema, response schema, error codes      |

### Luồng thay thế

**A1 — Không nhập tìm kiếm:**
- Người dùng bỏ qua bước 4–6, duyệt toàn bộ danh sách endpoint theo thứ tự mặc định.

### Luồng ngoại lệ

**E1 — Bundle chưa tồn tại:**
- Tại bước 2, file `openapi-bundled.yaml` không tìm thấy → hệ thống hiển thị thông báo chưa có tài liệu → người dùng cần thực hiện UC06 trước.

**E2 — Trang Developer Portal thật (`/portal`) không có đường dẫn trỏ tới:**
- Hệ thống có sẵn 1 trang portal dạng card (bộ tìm kiếm Fuse.js riêng) tại route `/portal`, trùng chức năng với Swagger UI — nhưng không có link nào trong giao diện trỏ tới, kể cả nút ghi chữ "Developer Portal" (nút đó thực chất mở `/swagger`, xem UC06 bước 7). Trang `/portal` chỉ truy cập được nếu người dùng gõ thẳng URL, không phải luồng sử dụng bình thường — hiện coi là mồ côi (orphaned), chưa quyết định giữ hay xóa.

### Quan hệ

| Loại     | UC liên quan |
| -------- | ------------ |
| Không có | —            |

---

## UC08 — Enrich metadata API

| Trường                   | Nội dung                                                                                                                                         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Mã UC**                | UC08                                                                                                                                             |
| **Tên UC**               | Enrich metadata API                                                                                                                              |
| **Tác nhân chính**       | Claude AI (claude-sonnet-4-6)                                                                                                                    |
| **Tác nhân phụ**         | Hệ thống Pipeline                                                                                                                                |
| **Mô tả**                | Claude AI nhận dữ liệu `ParsedOperation` từ pipeline và sinh ra `summary`, `operationId`, `description` bằng tiếng Việt cho từng API endpoint    |
| **Điều kiện tiên quyết** | `ParsedOperation` hợp lệ đã được tạo ra từ bước parse. Biến môi trường `ANTHROPIC_API_KEY` đã được cấu hình                                      |
| **Điều kiện hậu**        | `ParsedOperation` được bổ sung đầy đủ `summary`, `operationId`, `description`. Nếu thất bại thì `operationId` được sinh bằng rule-based fallback |

### Luồng chính

| Bước | Pipeline                                                                               | Claude AI                                                                              |
| ---- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 1    | Gửi `ParsedOperation` (method, path, parameters, request/response body) lên Claude API |                                                                                        |
| 2    |                                                                                        | Phân tích ngữ nghĩa endpoint                                                           |
| 3    |                                                                                        | Sinh `summary` — mô tả ngắn bằng tiếng Việt                                            |
| 4    |                                                                                        | Sinh `operationId` — camelCase, bắt đầu bằng động từ (vd: `listTickets`, `createUser`) |
| 5    |                                                                                        | Sinh `description` — mô tả chi tiết chức năng endpoint bằng tiếng Việt                 |
| 6    | Nhận kết quả, gắn vào `ParsedOperation`                                                |                                                                                        |

### Luồng ngoại lệ

**E1 — Gọi API thất bại hoặc timeout:**
- Tại bước 1, Claude API không phản hồi → pipeline kích hoạt fallback: sinh `operationId` bằng rule-based (ghép method + path segment), `summary` và `description` để trống → file được đánh dấu vào `human_review_queue.json`.

**E2 — Kết quả trả về không đúng định dạng:**
- Tại bước 6, response từ Claude không parse được → pipeline dùng fallback tương tự E1.

### Quan hệ

| Loại         | UC liên quan                         |
| ------------ | ------------------------------------ |
| Được gọi bởi | UC04 — Import module (`<<include>>`) |

---

## UC09 — Bundle toàn bộ YAML thành 1 file

| Trường                   | Nội dung                                                                                                                                         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Mã UC**                | UC09                                                                                                                                             |
| **Tên UC**               | Bundle toàn bộ YAML thành 1 file                                                                                                                 |
| **Tác nhân chính**       | Redocly                                                                                                                                          |
| **Tác nhân phụ**         | Hệ thống Backend                                                                                                                                 |
| **Mô tả**                | Redocly CLI gom toàn bộ tệp YAML phân tán trong `5.openapi/` thành một tệp duy nhất `dist/openapi-bundled.yaml`, giải quyết tất cả `$ref` nội bộ |
| **Điều kiện tiên quyết** | Có tệp YAML trong `5.openapi/`. Redocly CLI đã được cài đặt                                                                                      |
| **Điều kiện hậu**        | Tệp `dist/openapi-bundled.yaml` được tạo ra hoặc cập nhật                                                                                        |

### Luồng chính

| Bước | Backend                                        | Redocly                                           |
| ---- | ---------------------------------------------- | ------------------------------------------------- |
| 1    | Gọi lệnh `redocly bundle openapi/openapi.yaml` |                                                   |
| 2    |                                                | Đọc file entry point, duyệt toàn bộ `$ref`        |
| 3    |                                                | Giải quyết và nội tuyến hóa các tham chiếu nội bộ |
| 4    |                                                | Ghi kết quả ra `dist/openapi-bundled.yaml`        |
| 5    | Nhận exit code 0, tiếp tục sang lint           |                                                   |

### Luồng ngoại lệ

**E1 — `$ref` trỏ đến file không tồn tại:**
- Tại bước 2, Redocly phát hiện `$ref` broken → trả về lỗi, không tạo bundle → backend ghi nhận lỗi, báo cáo lên giao diện.

### Quan hệ

| Loại         | UC liên quan                                     |
| ------------ | ------------------------------------------------ |
| Được gọi bởi | UC06 — Build & xuất bản tài liệu (`<<include>>`) |

---

## UC10 — Lint bundle theo chuẩn OpenAPI

| Trường                   | Nội dung                                                                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| **Mã UC**                | UC10                                                                                                                            |
| **Tên UC**               | Lint bundle theo chuẩn OpenAPI                                                                                                  |
| **Tác nhân chính**       | Redocly                                                                                                                         |
| **Tác nhân phụ**         | Hệ thống Backend                                                                                                                |
| **Mô tả**                | Redocly CLI kiểm tra tệp bundle theo chuẩn OpenAPI 3.1 — phát hiện thiếu trường bắt buộc, sai kiểu dữ liệu, `$ref` không hợp lệ |
| **Điều kiện tiên quyết** | UC09 đã hoàn thành. Tệp `dist/openapi-bundled.yaml` tồn tại                                                                     |
| **Điều kiện hậu**        | Danh sách lỗi / cảnh báo theo chuẩn OpenAPI được trả về cho backend                                                             |

### Luồng chính

| Bước | Backend                                             | Redocly                                                                     |
| ---- | --------------------------------------------------- | --------------------------------------------------------------------------- |
| 1    | Gọi lệnh `redocly lint dist/openapi-bundled.yaml`   |                                                                             |
| 2    |                                                     | Kiểm tra cấu trúc theo OpenAPI 3.1 spec                                     |
| 3    |                                                     | Sinh danh sách issues với `ruleId`, `message`, `severity` (error / warning) |
| 4    | Nhận danh sách issues, trả về cho frontend hiển thị |                                                                             |

### Luồng ngoại lệ

**E1 — Bundle không parse được:**
- Tại bước 2, file YAML sai cú pháp → Redocly trả về lỗi parse → backend ghi nhận, hiển thị lỗi tổng quát lên giao diện.

### Quan hệ

| Loại         | UC liên quan                                     |
| ------------ | ------------------------------------------------ |
| Được gọi bởi | UC06 — Build & xuất bản tài liệu (`<<include>>`) |

---

## UC11 — Lint bundle theo governance rules

| Trường                   | Nội dung                                                                                                                                                                         |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mã UC**                | UC11                                                                                                                                                                             |
| **Tên UC**               | Lint bundle theo governance rules của project                                                                                                                                    |
| **Tác nhân chính**       | Spectral                                                                                                                                                                         |
| **Tác nhân phụ**         | Hệ thống Backend                                                                                                                                                                 |
| **Mô tả**                | Spectral CLI kiểm tra tệp bundle theo bộ quy tắc tùy chỉnh của project — phát hiện vi phạm convention như schema inline, `operationId` sai định dạng, thiếu error response chuẩn |
| **Điều kiện tiên quyết** | UC09 đã hoàn thành. Tệp `dist/openapi-bundled.yaml` và file ruleset Spectral tồn tại                                                                                             |
| **Điều kiện hậu**        | Danh sách lỗi / cảnh báo theo governance rules được trả về cho backend                                                                                                           |

### Luồng chính

| Bước | Backend                                             | Spectral                                                                                                                                      |
| ---- | --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Gọi lệnh `spectral lint dist/openapi-bundled.yaml`  |                                                                                                                                               |
| 2    |                                                     | Tải ruleset tùy chỉnh của project                                                                                                             |
| 3    |                                                     | Kiểm tra từng rule: operationId camelCase, không dùng inline schema, error response phải dùng $ref chuẩn, server-managed fields phải readOnly |
| 4    |                                                     | Sinh danh sách issues với `code` (tên rule), `message`, `severity` (0=error, 1=warning), `path`                                               |
| 5    | Nhận danh sách issues, trả về cho frontend hiển thị |                                                                                                                                               |

### Luồng ngoại lệ

**E1 — Ruleset không tìm thấy:**
- Tại bước 2, file ruleset Spectral bị thiếu → Spectral báo lỗi cấu hình → backend ghi nhận, bỏ qua kết quả Spectral, chỉ hiển thị kết quả Redocly.

### Quan hệ

| Loại         | UC liên quan                                     |
| ------------ | ------------------------------------------------ |
| Được gọi bởi | UC06 — Build & xuất bản tài liệu (`<<include>>`) |

---

## UC12 — Deploy tài liệu

| Trường                   | Nội dung                                                                                                                                                                                                                                          |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mã UC**                | UC12                                                                                                                                                                                                                                              |
| **Tên UC**               | Deploy tài liệu                                                                                                                                                                                                                                    |
| **Tác nhân chính**       | Người dùng                                                                                                                                                                                                                                         |
| **Tác nhân phụ**         | GitHub Actions                                                                                                                                                                                                                                     |
| **Mô tả**                | Người dùng bấm nút Deploy trên dashboard; route server Next.js so sánh `5.openapi/**` cục bộ với nhánh đích trên GitHub qua GitHub REST API (Git Data API — không dùng git cục bộ), tạo nhánh + commit mới nếu có thay đổi, rồi dispatch workflow mở Pull Request tự động merge và deploy Swagger UI lên GitHub Pages |
| **Điều kiện tiên quyết** | Đã có bundle (UC06 đã chạy). Đã "Kiểm tra lỗi" (lint) ít nhất 1 lần và lint không còn lỗi mức error. Biến môi trường `GH_DISPATCH_TOKEN`, `GH_OWNER`, `GH_REPO` đã cấu hình trên Next.js server                                                    |
| **Điều kiện hậu**        | Nếu có thay đổi: nhánh `auto/update-openapi-<timestamp>` được tạo trên GitHub, Pull Request được mở và tự động merge nếu CI pass, GitHub Pages được cập nhật                                                                                       |

### Luồng chính

| Bước | Người dùng                     | Hệ thống / GitHub Actions                                                                                     |
| ---- | ------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 1    | Bấm "Deploy tài liệu"           |                                                                                                             |
| 2    |                                 | Gọi `POST /api/deploy-docs { baseBranch }`, kiểm tra branch đích tồn tại qua `GET /git/ref/heads/{baseBranch}` |
| 3    |                                 | Tính git-blob-SHA1 từng file trong `5.openapi/**` cục bộ, so sánh với SHA trên GitHub để xác định file thay đổi |
| 4    |                                 | Tạo blob cho từng file thay đổi qua GitHub REST API                                                          |
| 5    |                                 | Tạo tree mới từ blob + baseSha, tạo commit, tạo ref nhánh `auto/update-openapi-<timestamp>`                  |
| 6    |                                 | Dispatch workflow `create-doc-pr.yaml` (input: `base_branch`, `branch_name`)                                 |
| 7    |                                 | GitHub Actions mở Pull Request, tự động merge nếu CI (validate) pass                                         |
| 8    |                                 | `deploy.yaml` build Swagger UI → deploy GitHub Pages                                                         |
| 9    | Nhận thông báo kết quả (toast) | Trả `200 OK` về Frontend                                                                                      |

### Luồng thay thế

**A1 — Không có gì thay đổi:**
- Tại bước 3, hash blob local trùng với GitHub cho mọi file trong `5.openapi/**` → hệ thống không tạo commit/PR, báo cho người dùng là không có gì để deploy.

### Luồng ngoại lệ

**E1 — Branch đích không tồn tại:**
- Tại bước 2, GitHub trả `404` cho branch đích → hệ thống trả lỗi rõ ràng ("Branch chưa tồn tại trên remote"), không tạo gì thêm.

**E2 — Nút Deploy bị khóa trước khi bấm được:**
- Nút chỉ bật khi đã có bundle, đã "Kiểm tra lỗi" ít nhất 1 lần, và lint 0 lỗi mức error, và không có thao tác khác đang chạy — nếu chưa đủ điều kiện, nút disable kèm lý do cụ thể.

**E3 — CI (validate) không pass sau khi mở PR:**
- Tại bước 7, PR không được tự động merge, chờ xử lý thủ công trên GitHub.

### Quan hệ

| Loại         | UC liên quan                                                                       |
| ------------ | ----------------------------------------------------------------------------------- |
| `<<extend>>` | UC06 — Build & xuất bản tài liệu (cần bundle + lint đã chạy trước khi deploy được) |