# Spectral — `.spectral.yaml`

> Giải thích chi tiết từng rule đang bật trong `.spectral.yaml` (gốc repo) — rule đó check gì, khi nào fail, và cách sửa. Không lặp lại quy trình chạy lint (`npm run lint`/`lint:spectral`) — xem `docs/devops/setup-cicd.md` mục 3-4 cho phần đó.

## Chạy ở đâu

```bash
npm run lint            # người đọc được, dùng khi tự kiểm tra local
npm run lint:spectral    # JSON, dùng bởi backend (build_and_lint()) và validate.yaml (CI)
```

Cả 2 đều lint `dist/openapi-bundled.yaml` (bản đã bundle) chứ **không** lint trực tiếp từng file trong `5.openapi/` — phải chạy `npm run bundle:api` trước nếu sửa tay `5.openapi/` mà chưa bundle lại.

---

## Nền tảng: `extends: [["spectral:oas", "all"]]`

Dòng đầu tiên trong `.spectral.yaml` kế thừa **toàn bộ** ruleset chuẩn OpenAPI có sẵn của Spectral (`spectral:oas`), bật ở mức `all` (mọi rule trong bộ đó, kể cả rule mặc định là `off`). Bộ này gồm hàng chục rule OpenAPI 3.x chuẩn — ví dụ `operation-operationId-unique` (operationId không trùng), `no-$ref-siblings`, `oas3-schema` (schema phải hợp lệ theo JSON Schema), `oas3-valid-media-example`... Tài liệu này **không liệt kê lại** bộ rule chuẩn đó (xem [Spectral OAS ruleset docs](https://docs.stoplight.io/docs/spectral/4dec24461f3af-open-api-rules) nếu cần tra cứu) — chỉ tập trung vào **14 rule tự viết riêng cho dự án này**, nằm dưới key `functions:`/`rules:` trong file.

14 rule này chia làm 2 nhóm: **7 rule dùng custom function** (code JS riêng, nằm trong `functions/*.js` ở gốc repo) và **7 rule dùng function có sẵn của Spectral** (`pattern`/`truthy`/`schema`) với điều kiện tự định nghĩa.

---

## Nhóm 1 — Custom function (`functions/*.js`)

### `enum-has-description` — severity `error`

**Given:** `parameters[*].schema`, `requestBody...schema.properties[*]`, `responses['200']...schema.properties[*]`, `components.schemas[*].properties[*]`
**Check** (`functions/enum-has-description.js`): field có `enum` mà không có `description` → lỗi.

```yaml
# ❌ Lỗi — enum không có description
status:
  type: string
  enum: [active, inactive, pending]

# ✅ Đúng
status:
  type: string
  enum: [active, inactive, pending]
  description: "Trạng thái tài khoản: active (đang hoạt động), inactive (đã khoá), pending (chờ duyệt)"
```

### `private-endpoint-must-have-401-403` — severity `error`

**Given:** mọi operation (`$.paths[*][*]`)
**Check** (function `private-must-have-401-403`, `functions/private-must-have-401-403.js`): operation được coi là **public** nếu có `security: []` (mảng rỗng) — operation public thì bỏ qua rule này. Operation còn lại (private, tức cần auth) **bắt buộc** phải có cả `responses.401` VÀ `responses.403`, thiếu cái nào báo lỗi cái đó (có thể báo cả 2 lỗi cùng lúc nếu thiếu cả hai).

```yaml
# ❌ Lỗi — operation private (không có security: []) nhưng thiếu 403
security:
  - bearerAuth: []
responses:
  "200": { ... }
  "401": { $ref: "#/components/responses/Unauthorized" }
  # thiếu 403

# ✅ Đúng
responses:
  "200": { ... }
  "401": { $ref: "#/components/responses/Unauthorized" }
  "403": { $ref: "#/components/responses/Forbidden" }
```

### `has-request-body-must-have-400` — severity `error`

**Given:** mọi operation
**Check** (`functions/has-request-body-must-have-400.js`): operation có `requestBody` mà không có `responses['400']` → lỗi. Operation không có `requestBody` thì bỏ qua hoàn toàn (không áp dụng).

### `server-id-must-be-readonly` — severity `error`

**Given:** `responses['200'].content` (toàn bộ media type trong response 200)
**Check** (`functions/server-id-must-be-readonly.js`): đệ quy qua mọi `properties` trong schema response (kể cả lồng qua `properties` con hoặc `array.items`, và có xử lý riêng nếu schema là `allOf`), tìm field có tên là ID (`id`, hoặc kết thúc bằng `_id`/`Id` — hàm `isIdField()`). Field ID nào **không** có `readOnly: true` → lỗi. Đây là cơ chế tự động hoá cho quy tắc "server-managed field phải readOnly" (nhắc trong PR checklist), áp dụng cho **mọi** field có tên giống ID, không chỉ riêng `id`.

```yaml
# ❌ Lỗi — service_id trong response 200 thiếu readOnly
properties:
  service_id:
    type: string

# ✅ Đúng
properties:
  service_id:
    type: string
    readOnly: true
```

### `client-id-must-not-be-readonly` — severity `error`

**Given:** `requestBody.content` (toàn bộ media type trong request body)
**Check** (`functions/client-id-must-not-be-readonly.js`): ngược lại rule trên — field tên giống ID trong **request** (client tự gửi lên) mà lại có `readOnly: true` → lỗi (khác `server-id-must-be-readonly`: hàm này **không** tự bung `allOf`, chỉ đệ quy qua `properties`/`array.items` thường).

```yaml
# ❌ Lỗi — user_id trong request lại đánh dấu readOnly
properties:
  user_id:
    type: string
    readOnly: true

# ✅ Đúng — bỏ hẳn readOnly (readOnly chỉ có ý nghĩa ở response)
properties:
  user_id:
    type: string
```

### `property-must-have-description` — severity `warn`

**Given:** `components.schemas[*]`, `components.schemas[*].properties[*]`, request/response 200 schema
**Check** (`functions/property-must-have-description.js`): mọi property trong `properties` của schema đang xét mà thiếu `description` (hoặc `description` là chuỗi rỗng/toàn khoảng trắng) → 1 lỗi riêng cho từng property thiếu. Đây là rule bắt lỗi phổ biến nhất trong thực tế (rất dễ quên mô tả 1-2 field khi viết schema mới).

### `post-must-have-2xx` — severity `warn`

**Given:** `$.paths[*].post` (chỉ operation `POST`)
**Check** (function `has-2xx-response`, `functions/has-2xx-response.js`): operation `POST` phải có ít nhất 1 response status khớp `2xx` (regex `^2\d\d$`) — thiếu `responses` hoàn toàn hoặc có `responses` nhưng không status nào 2xx đều báo lỗi.

---

## Nhóm 2 — Rule đơn giản (dùng function có sẵn của Spectral)

| Rule                              | Severity | Given                                        | Function     | Check                                                                                                    |
| ----------------------------------- | ---------- | ----------------------------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------- |
| `path-kebab-case`                  | `warn`   | `$.paths.*~` (tên key path)                    | `pattern`      | URL path phải khớp regex `^(/[a-z0-9-]+\|/{[a-zA-Z0-9_]+})+$` — mỗi segment chữ thường + số + gạch ngang, hoặc `{param}` |
| `operation-id-verb-noun`           | `error`  | `operationId` của mọi operation                | `pattern`      | Khớp `^[a-z][a-zA-Z0-9]+$` — camelCase, ký tự đầu chữ thường (không tự check "có bắt đầu bằng động từ" thật sự — chỉ check hình thức camelCase, phần "động từ" là quy ước review bằng mắt) |
| `operation-must-have-description` | `warn`   | mọi operation                                   | `truthy`       | Field `description` phải có giá trị (không rỗng/không thiếu)                                              |
| `operation-with-id-must-have-404`  | `warn`   | operation của path có `{...}` (regex match), chỉ 4 method `get/put/patch/delete` | `truthy`  | Phải có `responses.404`                                                                                    |
| `info-must-have-contact`           | `info`   | `$.info`                                       | `truthy`       | Object `info` phải có field `contact`                                                                     |
| `delete-must-have-204`             | `warn`   | mọi operation `DELETE`                          | `truthy`       | Phải có `responses.204`                                                                                    |
| `operation-must-have-tags`         | `warn`   | mọi operation                                   | `schema`       | Field `tags` phải là array có ít nhất 1 phần tử (`minItems: 1`) — chỉ yêu cầu **có tag**, không yêu cầu đúng 1 tag (khác Redocly `operation-singular-tag`, xem `docs/guidelines/conventions/redocly.md`) |

**Lưu ý `operation-id-verb-noun`:** regex chỉ kiểm tra hình thức camelCase (`^[a-z][a-zA-Z0-9]+$`), **không** thật sự parse xem chữ đầu có phải động từ hay không (`tickets` vẫn khớp regex dù không phải verb) — phần "phải bắt đầu bằng động từ" trong message lỗi là quy ước, cần reviewer tự để ý thêm, Spectral không tự bắt được.

---

## Bảng tóm tắt severity → hành vi CI

| Severity | Chặn merge? (`validate.yaml`) | Ghi chú |
| ---------- | -------------------------------- | --------- |
| `error`  | Có                                | Toàn bộ 7 rule custom-function + `operation-id-verb-noun` |
| `warn`   | Không                             | Nên fix trước khi request review, không bắt buộc |
| `info`   | Không                             | Chỉ `info-must-have-contact` — mang tính gợi ý |

Xem `docs/devops/setup-cicd.md` mục 4/7 cho cách CI dùng kết quả lint này để block/không-block merge.
