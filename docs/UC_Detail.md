# Đặc tả Use Case Chi Tiết — API Converter

## Danh sách UC

| STT  | UC                                | Actor              |
| ---- | --------------------------------- | ------------------ |
| UC01 | Quản lý tài liệu đầu vào          | Người dùng         |
| UC02 | Phân loại file vào module         | Người dùng         |
| UC03 | Quản lý module registry           | Người dùng         |
| UC04 | Import module                     | Người dùng         |
| UC05 | Kiểm duyệt & xuất YAML            | Người dùng         |
| UC06 | Build & xuất bản tài liệu         | Người dùng         |
| UC07 | Xem tài liệu API                  | Người dùng         |
| UC08 | Enrich metadata API               | Claude AI          |
| UC09 | Bundle toàn bộ YAML thành 1 file  | Redocly / Spectral |
| UC10 | Lint bundle theo chuẩn OpenAPI    | Redocly / Spectral |
| UC11 | Lint bundle theo governance rules | Redocly / Spectral |

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
| 1    | Kéo thả hoặc chọn file (PDF / DOCX / TXT) vào vùng upload |                                                                  |
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
- Tại bước 2, file không phải PDF / DOCX / TXT → hệ thống báo lỗi, không lưu file → người dùng chọn lại file khác.

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

## UC05 — Kiểm duyệt & xuất YAML

| Trường                   | Nội dung                                                                                                                                                                |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mã UC**                | UC05                                                                                                                                                                    |
| **Tên UC**               | Kiểm duyệt & xuất YAML                                                                                                                                                  |
| **Tác nhân chính**       | Người dùng                                                                                                                                                              |
| **Mô tả**                | Người dùng xem xét các file YAML được pipeline tạo ra, chỉnh sửa thủ công nếu cần, approve hoặc reject từng file, sau đó export toàn bộ file đã duyệt ra thư mục output |
| **Điều kiện tiên quyết** | UC04 đã hoàn thành. Có ít nhất một file ở trạng thái `flagged` hoặc `done` trong job                                                                                    |
| **Điều kiện hậu**        | File YAML đã duyệt được ghi ra `5.openapi/`. Pipeline bundle và lint được kích hoạt tự động                                                                             |

### Luồng chính

| Bước | Người dùng                              | Hệ thống                                                                        |
| ---- | --------------------------------------- | ------------------------------------------------------------------------------- |
| 1    | Truy cập trang review job               |                                                                                 |
| 2    |                                         | Hiển thị danh sách file flagged cần review kèm lý do (thiếu trường, lỗi LLM...) |
| 3    | Chọn file muốn xem xét                  |                                                                                 |
| 4    |                                         | Mở Monaco Editor hiển thị nội dung YAML của file                                |
| 5    | Đọc và chỉnh sửa YAML trực tiếp nếu cần |                                                                                 |
| 6    |                                         | Lưu thay đổi vào bộ nhớ tạm (in-memory job state)                               |
| 7    | Bấm "Approve"                           |                                                                                 |
| 8    |                                         | Đánh dấu file là `done`                                                         |
| 9    | Lặp lại bước 3–8 cho các file còn lại   |                                                                                 |
| 10   | Bấm "Export"                            |                                                                                 |
| 11   |                                         | Ghi toàn bộ file đã approve ra `5.openapi/`                                     |
| 12   |                                         | Tự động kích hoạt bundle → lint `<<include UC09, UC10, UC11>>`                  |

### Luồng thay thế

**A1 — Reject file:**
- Tại bước 7, người dùng bấm "Reject" thay vì "Approve" → file bị đánh dấu là `rejected`, không được export.

**A2 — Không có file flagged:**
- Tại bước 2, tất cả file đã ở trạng thái `done` → hệ thống hiển thị thông báo không còn file cần review → người dùng bấm thẳng Export.

### Luồng ngoại lệ

**E1 — YAML không hợp lệ sau khi chỉnh sửa:**
- Tại bước 5, người dùng nhập sai cú pháp YAML → Monaco Editor hiển thị lỗi inline → hệ thống không cho approve cho đến khi YAML hợp lệ.

**E2 — Job hết hạn (restart backend):**
- Backend không có database → khi restart, toàn bộ job state bị mất → người dùng phải chạy lại UC04.

### Quan hệ

| Loại          | UC liên quan                             |
| ------------- | ---------------------------------------- |
| `<<include>>` | UC09 — Bundle toàn bộ YAML thành 1 file  |
| `<<include>>` | UC10 — Lint bundle theo chuẩn OpenAPI    |
| `<<include>>` | UC11 — Lint bundle theo governance rules |

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
| 7    | Bấm "Developer Portal" xem giao diện |                                                                         |

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
| **Mô tả**                | Người dùng xem tài liệu API đã được build dưới dạng Swagger UI tương tác hoặc Developer Portal dạng danh sách, có thể tìm kiếm và lọc endpoint |
| **Điều kiện tiên quyết** | UC06 đã hoàn thành. Tệp `dist/openapi-bundled.yaml` tồn tại                                                                                    |
| **Điều kiện hậu**        | Không thay đổi dữ liệu. Người dùng đọc được thông tin API cần tìm                                                                              |

### Luồng chính

| Bước | Người dùng                                      | Hệ thống                                                                    |
| ---- | ----------------------------------------------- | --------------------------------------------------------------------------- |
| 1    | Truy cập trang Swagger UI hoặc Developer Portal |                                                                             |
| 2    |                                                 | Tải `openapi-bundled.yaml` từ server                                        |
| 3    |                                                 | Render danh sách endpoint với method, path, summary, description            |
| 4    | Nhập từ khóa vào ô tìm kiếm                     |                                                                             |
| 5    |                                                 | Fuse.js thực hiện fuzzy search trên operationId, path, summary, description |
| 6    |                                                 | Hiển thị kết quả khớp theo độ liên quan                                     |
| 7    | Bấm vào endpoint muốn xem chi tiết              |                                                                             |
| 8    |                                                 | Hiển thị parameters, request body schema, response schema, error codes      |

### Luồng thay thế

**A1 — Xem qua Developer Portal:**
- Tại bước 1, người dùng chọn Developer Portal thay vì Swagger UI → giao diện hiển thị dạng card theo nhóm module thay vì danh sách Swagger chuẩn.

**A2 — Không nhập tìm kiếm:**
- Người dùng bỏ qua bước 4–6, duyệt toàn bộ danh sách endpoint theo thứ tự mặc định.

### Luồng ngoại lệ

**E1 — Bundle chưa tồn tại:**
- Tại bước 2, file `openapi-bundled.yaml` không tìm thấy → hệ thống hiển thị thông báo chưa có tài liệu → người dùng cần thực hiện UC06 trước.

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
| Được gọi bởi | UC05 — Kiểm duyệt & xuất YAML (`<<include>>`)    |
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
| Được gọi bởi | UC05 — Kiểm duyệt & xuất YAML (`<<include>>`)    |
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
| Được gọi bởi | UC05 — Kiểm duyệt & xuất YAML (`<<include>>`)    |
| Được gọi bởi | UC06 — Build & xuất bản tài liệu (`<<include>>`) |