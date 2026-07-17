# Redocly — `redocly.yaml`

> Giải thích chi tiết từng rule đang cấu hình trong `redocly.yaml` (gốc repo) — rule đó check gì, khi nào fail, và cách sửa. Không lặp lại quy trình chạy validate (`npm run validate`/`validate:api`) — xem `docs/setup-cicd.md` mục 3-4 cho phần đó.

## Chạy ở đâu

```bash
npm run validate        # người đọc được, dùng khi tự kiểm tra local
npm run validate:api     # JSON, dùng bởi backend (build_and_lint()) và validate.yaml (CI)
npm run bundle:api       # redocly bundle — gộp 5.openapi/** thành dist/openapi-bundled.yaml
npm run build:docs:redocly  # build HTML bằng chính theme Redocly (khác scripts/build-swagger-ui.js dùng Swagger UI)
```

Redocly lint chạy trên `dist/openapi-bundled.yaml` (bản đã bundle), giống Spectral — phải `bundle:api` trước nếu vừa sửa tay `5.openapi/`.

---

## Cấu hình gốc

```yaml
apis:
  main:
    root: dist/openapi-bundled.yaml
extends:
  - recommended
```

`apis.main.root` khai báo file gốc mà mọi lệnh Redocly (`lint`, `bundle`, `build-docs`) mặc định thao tác — không cần truyền path thủ công mỗi lần gọi lệnh. `extends: recommended` kế thừa bộ rule khuyến nghị chuẩn của Redocly (không phải bộ lỏng nhất `minimal`, cũng không phải bộ chặt nhất `all`) — dự án chỉnh lại severity của 1 số rule cụ thể so với mặc định của bộ `recommended` (xem bảng dưới), không tự viết custom rule/function nào (khác Spectral — Redocly ở dự án này thuần dùng rule có sẵn, không có thư mục `functions/` riêng).

---

## Rule được chỉnh lại (`rules:` trong `redocly.yaml`)

| Rule                        | Severity trong file | Check                                                                                                                                          |
| ----------------------------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `tag-description`            | `off`                  | (Tắt hẳn) Mặc định `recommended` yêu cầu mỗi tag khai báo ở `$.tags[*]` (top-level) phải có `description` — dự án này **tắt** rule đó, tag không bắt buộc có mô tả |
| `path-parameters-defined`   | `error`                | Mỗi `{param}` xuất hiện trong URL path phải có 1 entry tương ứng trong `parameters` (khai theo `in: path`) — thiếu khai báo, hoặc khai thừa param không có trong URL, đều lỗi |
| `no-unresolved-refs`        | `error`                | Mọi `$ref` phải trỏ tới đích thật sự tồn tại trong spec (không trỏ tới file/anchor không có) — lỗi hay gặp nhất khi đổi tên file schema mà quên cập nhật hết `$ref` |
| `no-unused-components`      | `error`                | Object trong `components/*` (schema, response, parameter...) được định nghĩa nhưng **không có `$ref` nào trỏ tới** → coi là rác, phải xoá hoặc dùng tới |
| `no-identical-paths`        | `error`                | 2 path template khác chữ nhưng **cùng hình dạng** khi khớp request thật (vd `/tickets/{id}` và `/tickets/{ticketId}` — chỉ khác tên param) → ambiguous, router không phân biệt được |
| `no-enum-type-mismatch`     | `error`                | Giá trị trong `enum` phải cùng kiểu dữ liệu với `type` đã khai (vd `type: string` mà có 1 phần tử enum là số) |
| `no-ambiguous-paths`        | `error`                | Path template có thể match nhầm request của path khác (khác `no-identical-paths` — đây là overlap từng phần, không hẳn giống hệt nhau) |
| `no-empty-servers`          | `error`                | `servers` không được là mảng rỗng nếu có khai báo — khai `servers: []` thì lỗi (không khai `servers` gì cả lại không bị bắt bởi rule này) |
| `operation-summary`         | `error`                | Mọi operation phải có `summary` |
| `operation-2xx-response`    | `error`                | Mọi operation phải có ít nhất 1 response mã `2xx` — **áp dụng cho mọi method** (GET/PUT/PATCH/DELETE...), rộng hơn rule tương tự bên Spectral (`post-must-have-2xx` chỉ áp cho `POST`, xem `docs/conventions/spectral.md`) |
| `operation-operationId`     | `error`                | Mọi operation phải có `operationId` |
| `operation-singular-tag`    | `error`                | Mỗi operation phải có **đúng 1** tag — không phải "ít nhất 1" |

**Điểm cần lưu ý — 2 công cụ không hoàn toàn đồng nhất về tag:** Spectral (`operation-must-have-tags`) chỉ yêu cầu operation có **ít nhất 1** tag; Redocly (`operation-singular-tag`) yêu cầu **chính xác 1** tag. Operation gắn 2 tag trở lên sẽ **pass Spectral nhưng fail Redocly** — nếu CI báo lỗi tag mà Spectral không thấy gì, kiểm tra lại operation đó có đang gắn nhiều hơn 1 tag không.

---

## Rule thừa kế từ `recommended` (không liệt kê lại toàn bộ)

Bộ `recommended` của Redocly còn có rất nhiều rule khác không bị override trong `redocly.yaml` (dùng nguyên severity mặc định của bộ đó) — ví dụ `operation-parameters-unique`, `no-server-example.com`, `spec-strict-refs`, `no-invalid-media-type-examples`... Tài liệu này chỉ liệt kê phần **dự án chủ động chỉnh severity** (bảng trên); phần còn lại xem [Redocly built-in rules reference](https://redocly.com/docs/cli/rules/) nếu cần tra cứu rule cụ thể đang fail mà không thấy tên trong bảng trên.

---

## Bảng tóm tắt severity → hành vi CI

| Severity | Chặn merge? (`validate.yaml`) |
| ---------- | -------------------------------- |
| `error`  | Có — toàn bộ rule bị override trong bảng trên đều là `error`                        |
| Mặc định của `recommended` (không override) | Tuỳ rule — phần lớn là `warn`, xem link Redocly rules reference nếu cần biết chính xác |

Xem `docs/setup-cicd.md` mục 4/7 cho cách CI dùng kết quả validate này để block/không-block merge.
