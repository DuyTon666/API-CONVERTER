# CI/CD — Các Tình Huống Lỗi & Debugging

> Validation chạy trên file **`dist/openapi-bundled.yaml`** (sau bước bundle). Cả Spectral và Redocly đều đọc file này, không phải `5.openapi/openapi.yaml`.
>
> Thứ tự local chuẩn:
> ```bash
> npm run bundle:api       # tạo dist/openapi-bundled.yaml
> npm run lint:spectral    # kiểm tra custom rules
> npm run validate:api     # kiểm tra OpenAPI 3.1 spec
> ```

---

## 1. Spectral Lint Failures

### 1.1 Lỗi Format operationId

**Lỗi:**
```
5:17  error  operation-id-verb-noun  operationId "create_ticket" sai format.
Phải dùng camelCase và bắt đầu bằng động từ — ví dụ: listUsers, createOrder, reopenTicket.
```

**Nguyên nhân:** operationId dùng snake_case thay vì camelCase. Pattern yêu cầu: `^[a-z][a-zA-Z0-9]+$`

**Fix:**
```yaml
# ❌ TRƯỚC
post:
  operationId: create_ticket

# ✅ SAU
post:
  operationId: createTicket
```

**Verify:** `npm run lint:spectral`

---

### 1.2 Lỗi readOnly Trên Server Fields

Có **hai rule riêng biệt** kiểm tra theo chiều ngược nhau:

#### Rule `server-id-must-be-readonly` — field `id` trong response 200 phải có `readOnly: true`

**Lỗi:**
```
error  server-id-must-be-readonly  Trường "id" trong response 200 phải có readOnly: true
```

**Fix:**
```yaml
# ❌ TRƯỚC — response schema thiếu readOnly
properties:
  id:
    type: integer
  created_at:
    type: string
    format: date-time

# ✅ SAU
properties:
  id:
    type: integer
    readOnly: true
  created_at:
    type: string
    format: date-time
    readOnly: true
  updated_at:
    type: string
    format: date-time
    readOnly: true
```

> Các field server-managed: `id`, `created_at`, `updated_at` (xem `4.config/global/server_managed_fields.yaml`).

---

#### Rule `client-id-must-not-be-readonly` — field `id` trong requestBody không được có `readOnly: true`

**Lỗi:**
```
error  client-id-must-not-be-readonly  Trường "id" trong requestBody không được có readOnly: true
```

**Fix:**
```yaml
# ❌ TRƯỚC — request schema chứa readOnly
properties:
  id:
    type: integer
    readOnly: true   # sai — client không set được field này

# ✅ SAU — request schema không có id (pipeline tự xóa created_at/updated_at)
properties:
  title:
    type: string
  description:
    type: string
```

**Verify:** `npm run lint:spectral`

---

### 1.3 Thiếu 401/403 Trên Private Endpoints

**Lỗi:**
```
10:3  error  private-endpoint-must-have-401-403  Endpoint private phải có response 401 (Unauthorized)
10:3  error  private-endpoint-must-have-401-403  Endpoint private phải có response 403 (Forbidden)
```

**Nguyên nhân:** Endpoint có `security: [bearerAuth: []]` nhưng thiếu response 401/403.

**Fix:**
```yaml
# ❌ TRƯỚC
post:
  security:
    - bearerAuth: []
  responses:
    "200":
      description: Success

# ✅ SAU
post:
  security:
    - bearerAuth: []
  responses:
    "200":
      description: Success
    "401":
      $ref: "../../components/responses/Unauthorized.yaml"
    "403":
      $ref: "../../components/responses/Forbidden.yaml"
```

> Đường dẫn `../../components/responses/` tính từ `5.openapi/paths/<module>/` lên `5.openapi/components/responses/`.

---

### 1.4 Endpoint Có requestBody Nhưng Thiếu Response 400

**Lỗi:**
```
error  has-request-body-must-have-400  Endpoint có requestBody phải có response 400 (Bad Request)
```

**Nguyên nhân:** Operation có `requestBody` (tức nhận input từ client) mà không document trường hợp input không hợp lệ.

**Fix:**
```yaml
post:
  requestBody:
    required: true
    content:
      application/json:
        schema:
          $ref: "../../components/schemas/ticket/CreateTicketRequest.yaml"
  responses:
    "200":
      description: Tạo thành công
    "400":
      $ref: "../../components/responses/BadRequest.yaml"
    "401":
      $ref: "../../components/responses/Unauthorized.yaml"
    "403":
      $ref: "../../components/responses/Forbidden.yaml"
```

**Verify:** `npm run lint:spectral`

---

### 1.5 Enum Không Có Description

**Lỗi:**
```
error  enum-has-description  Property có enum phải có description mô tả từng giá trị
```

**Fix:**
```yaml
# ❌ TRƯỚC
status:
  type: string
  enum: [CREATED, IN_PROGRESS, CLOSED]

# ✅ SAU
status:
  type: string
  description: |
    Trạng thái ticket:
    - CREATED: Mới tạo, chưa xử lý
    - IN_PROGRESS: Đang xử lý
    - CLOSED: Đã đóng
  enum: [CREATED, IN_PROGRESS, CLOSED]
```

---

### 1.6 Endpoint Có Path Parameter Nhưng Thiếu 404 (Warning)

**Lỗi:**
```
warn  operation-with-id-must-have-404  Operation với path parameter phải có response 404 (Not Found)
```

Warning level — không chặn CI nhưng nên fix.

**Fix:** Thêm 404 vào mọi endpoint có `{id}` hoặc path parameter khác:
```yaml
responses:
  "200":
    description: Thành công
  "401":
    $ref: "../../components/responses/Unauthorized.yaml"
  "403":
    $ref: "../../components/responses/Forbidden.yaml"
  "404":
    $ref: "../../components/responses/NotFound.yaml"
```

---

## 2. Redocly Validation Failures

> Redocly validate `dist/openapi-bundled.yaml` sau khi đã bundle. Nếu `dist/` chưa có file, chạy `npm run bundle:api` trước.

### 2.1 Đường Dẫn $ref Không Hợp Lệ

**Lỗi:**
```
Referenced schema not found: ../../components/schemas/ticket/TicketResponse.yaml
❌ Validation failed with 1 error.
```

**Nguyên nhân:** `$ref` trỏ tới file không tồn tại, sai đường dẫn, hoặc file đã đổi tên.

**Fix:**
```bash
# Kiểm tra file có tồn tại
ls -la 5.openapi/components/schemas/ticket/TicketResponse.yaml

# Tìm tất cả chỗ dùng schema này
grep -r "TicketResponse" --include="*.yaml" 5.openapi/

# Tạo file hoặc sửa đường dẫn $ref cho đúng
```

**Verify:** `npm run validate:api`

---

### 2.2 Circular Reference

**Lỗi:**
```
Circular reference detected:
  TicketDetail → Conversation → TicketDetail
```

**Fix — phá vòng lặp:**
```yaml
# ❌ TRƯỚC: Conversation.yaml tham chiếu ngược lại TicketDetail
properties:
  ticket:
    $ref: "./TicketDetail.yaml"

# ✅ SAU: dùng ID thay vì $ref
properties:
  ticket_id:
    type: integer
    description: Reference to ticket ID (tránh circular ref)
```

---

### 2.3 Cú Pháp OpenAPI Không Hợp Lệ

**Lỗi:**
```
Property `requestbody` is not expected here. Did you mean `requestBody`?
```

**Fix:**
```yaml
# ❌ TRƯỚC
post:
  requestbody:   # chữ 'b' thường

# ✅ SAU
post:
  requestBody:   # camelCase
```

---

## 3. Inline Schema — Convention Không Có File Checker Tự Động

Project quy ước **không dùng inline schema** trong `5.openapi/paths/` — tất cả schema phải dùng `$ref`. Tuy nhiên, **không có script CI tự động kiểm tra** convention này. Vi phạm sẽ vượt qua CI nếu không bị code review bắt.

Redocly chỉ báo lỗi khi `$ref` trỏ đến file không tồn tại (rule `no-unresolved-refs`), không báo khi schema inline hợp lệ.

**Cách phát hiện thủ công:**
```bash
# Tìm inline schemas trong paths/
grep -rn "type: object" 5.openapi/paths/ --include="*.yaml"
grep -rn "type: array" 5.openapi/paths/ --include="*.yaml"
```

**Fix — chuyển inline thành $ref:**
```yaml
# ❌ TRƯỚC (inline trong 5.openapi/paths/ticket/create.yaml)
post:
  requestBody:
    content:
      application/json:
        schema:
          type: object
          properties:
            title:
              type: string

# ✅ SAU
# Bước 1: Tạo 5.openapi/components/schemas/ticket/CreateTicketRequest.yaml
type: object
properties:
  title:
    type: string

# Bước 2: Thay bằng $ref
post:
  requestBody:
    content:
      application/json:
        schema:
          $ref: "../../components/schemas/ticket/CreateTicketRequest.yaml"
```

---

## 4. GitHub Actions Failures

### 4.1 npm ci Thất Bại

**Lỗi:**
```
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json are in sync.
```

**Fix:**
```bash
rm -rf node_modules package-lock.json
npm install
git add package-lock.json
git commit -m "chore: regenerate package-lock.json"
git push
```

---

### 4.2 Checkout Thất Bại

**Lỗi:**
```
Error: fatal: repository not found
Error: Process completed with exit code 128.
```

**Fix:**
```yaml
permissions:
  contents: read
  pull-requests: write
```

---

### 4.3 Slack Notification Thất Bại

**Lỗi:**
```
{"ok":false,"error":"invalid_auth"}
```

**Fix:**
```bash
# Kiểm tra GitHub Secrets:
# Settings → Secrets and variables → Actions
# SLACK_BOT_TOKEN — token của Slack App
# SLACK_CHANNEL_ID — ID của channel nhận thông báo
# Slack App → OAuth & Permissions → Scopes cần: chat:write, chat:write.public
```

---

## 5. Quy Trình Debugging

```
┌─────────────────────────────────────────┐
        CI/CD Pipeline Thất Bại
└─────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────┐
      Bước 1: Xác Định Job Thất Bại
      → GitHub Actions → Click run fail
      → Mở rộng step bị lỗi
      → Đọc error message, ghi số dòng
└─────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────┐
      Bước 2: Tái Hiện Trên Local
      → git pull origin <branch>
      → npm ci
      → npm run bundle:api
      → npm run lint:spectral
      → npm run validate:api
└─────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
      Bước 3: Sửa Lỗi
      → Sửa file theo error message
      → Chạy lại lệnh tương ứng
      → Lặp lại cho đến khi pass
└─────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
      Bước 4: Commit & Push
      → git add <files>
      → git commit -m "fix: ..."
      → git push
└─────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
      Bước 5: Xác Minh CI Pass
      → Đợi GitHub Actions hoàn thành
      → Kiểm tra tất cả jobs đều xanh
└─────────────────────────────────────────┘
```

---

## 6. Bảng Tham Chiếu Nhanh

| Lỗi | Rule / Tool | Severity | Fix |
|---|---|---|---|
| `operationId "x_y"` sai format | `operation-id-verb-noun` (Spectral) | error | Dùng camelCase `verbNoun` |
| `id` thiếu `readOnly` trong response | `server-id-must-be-readonly` (Spectral) | error | Thêm `readOnly: true` vào response schema |
| `id` có `readOnly` trong request | `client-id-must-not-be-readonly` (Spectral) | error | Xóa `readOnly` khỏi request schema |
| Thiếu 401/403 trên private endpoint | `private-endpoint-must-have-401-403` (Spectral) | error | Thêm `$ref` đến Unauthorized/Forbidden |
| Có requestBody nhưng thiếu 400 | `has-request-body-must-have-400` (Spectral) | error | Thêm `$ref` đến BadRequest |
| Enum không có description | `enum-has-description` (Spectral) | error | Thêm description mô tả các giá trị |
| Path parameter thiếu 404 | `operation-with-id-must-have-404` (Spectral) | warning | Thêm `$ref` đến NotFound |
| `$ref` trỏ file không tồn tại | `no-unresolved-refs` (Redocly) | error | Tạo file hoặc sửa đường dẫn |
| Circular reference | Redocly | error | Phá vòng lặp bằng ID reference |
| Lỗi chính tả OpenAPI keyword | Redocly | error | Sửa case (vd: `requestBody`) |
| `npm ci` thất bại | GitHub Actions | error | Tái tạo `package-lock.json` |
| Slack `invalid_auth` | deploy.yaml | error | Kiểm tra `SLACK_BOT_TOKEN` trong Secrets |
