# CI/CD — Ví Dụ Thực Tế

---

## Ví dụ 1: thêm endpoint mới

Thêm endpoint `POST /v1/users/{user_id}/tickets/{id}/reopen`

---

### Bước 1: Tạo schema file

```bash
touch components/schemas/ticket/ReopenTicketRequest.yaml
```

```yaml
# components/schemas/ticket/ReopenTicketRequest.yaml
type: object
required:
  - reason
properties:
  reason:
    type: string
    description: Lý do mở lại ticket
    example: "Vấn đề chưa được giải quyết hoàn toàn"
    maxLength: 500
  additional_info:
    type: string
    description: Thông tin bổ sung (không bắt buộc)
    maxLength: 1000
```

Lưu ý: tên file PascalCase, nằm trong `components/schemas/ticket/`, không có `readOnly` (đây là request schema).

---

### Bước 2: Tạo path file

```bash
touch paths/tickets/reopen.yaml
```

```yaml
# paths/tickets/reopen.yaml
post:
  summary: Mở lại ticket đã đóng
  operationId: reopenTicket
  description: Cho phép khách hàng mở lại ticket đã đóng nếu vấn đề chưa được giải quyết
  tags:
    - Ticket
  security:
    - bearerAuth: []
  parameters:
    - name: user_id
      in: path
      required: true
      schema:
        type: string
    - name: id
      in: path
      required: true
      schema:
        type: integer
  requestBody:
    required: true
    content:
      application/json:
        schema:
          $ref: "../../components/schemas/ticket/ReopenTicketRequest.yaml"
  responses:
    "200":
      description: Mở lại ticket thành công
      content:
        application/json:
          schema:
            $ref: "../../components/schemas/core/StandardSuccess.yaml"
    "401":
      $ref: "../../components/responses/Unauthorized.yaml"
    "403":
      $ref: "../../components/responses/Forbidden.yaml"
    "404":
      $ref: "../../components/responses/NotFound.yaml"
    "422":
      $ref: "../../components/responses/ValidationError.yaml"
    "500":
      $ref: "../../components/responses/InternalError.yaml"
```

---

### Bước 3: Cập nhật openapi.yaml

```yaml
paths:
  # ... existing paths ...
  /v1/users/{user_id}/tickets/{id}/reopen:
    $ref: "./paths/tickets/reopen.yaml"
```

---

### Bước 4: Validate local

```bash
npm run lint:api && npm run validate:api
```

```
✅ No inline schemas in paths/
Woohoo! Your OpenAPI definition is valid. 🎉
```

---

### Bước 5–8: Commit → PR → CI → Deploy

```bash
git checkout -b feat/schema-ticket-reopen
git add components/schemas/ticket/ReopenTicketRequest.yaml paths/tickets/reopen.yaml openapi.yaml
git commit -m "feat(schemas): add ticket reopen endpoint"
git push origin feat/schema-ticket-reopen

gh pr create --base develop --title "feat(schemas): add ticket reopen endpoint"
```

Sau khi CI pass và PR được approve:

```bash
gh pr merge 42 --squash
```

Slack thông báo:
```
✅ Deploy — Passed
Branch: `develop` | Commit: `a3f9c12`
Files changed: ReopenTicketRequest.yaml, reopen.yaml, openapi.yaml
```

---

## Ví Dụ 2: Các Lỗi Phổ Biến

Developer tạo endpoint với nhiều vi phạm

---

### Lỗi 1: Inline Schema

```yaml
# ❌ paths/tickets/feedback.yaml
post:
  requestBody:
    content:
      application/json:
        schema:
          type: object       # INLINE SCHEMA
          properties:
            rating:
              type: integer
```

**Fix:**
```bash
# Tạo file schema riêng
type: object
required:
  - rating
properties:
  rating:
    type: integer
    minimum: 1
    maximum: 5
  comment:
    type: string
    maxLength: 1000
```

---

### Lỗi 2: operationId sai format

```yaml
# ❌ snake_case
operationId: submit_feedback

# ✅ camelCase
operationId: submitFeedback
```

---

### Lỗi 3: Thiếu 401/403

```yaml
# ❌
security:
  - bearerAuth: []
responses:
  "200":
    description: Success
  # Thiếu 401, 403

# ✅ Thêm đủ
responses:
  "200":
    description: Success
  "401":
    $ref: "../../components/responses/Unauthorized.yaml"
  "403":
    $ref: "../../components/responses/Forbidden.yaml"
  "500":
    $ref: "../../components/responses/InternalError.yaml"
```

---

### Lỗi 4: Thiếu readOnly

```yaml
# ❌
properties:
  id:
    type: integer
  created_at:
    type: string

# ✅
properties:
  id:
    type: integer
    readOnly: true
  created_at:
    type: string
    readOnly: true
```

---

### Lỗi 5: Sai đường dẫn $ref

```yaml
# ❌ Thiếu thư mục /ticket/
$ref: "../../components/schemas/FeedbackRequest.yaml"

# ✅ Đúng đường dẫn
$ref: "../../components/schemas/ticket/SubmitFeedbackRequest.yaml"
```

---

## Ví Dụ 3: Response Schema Với Nested Objects

### Schema dùng chung (Reusable)

```yaml
# components/schemas/common/UserInfo.yaml
type: object
properties:
  id:
    type: integer
    readOnly: true
  name:
    type: string
    example: "Nguyễn Văn A"
  email:
    type: string
    format: email
  avatar_url:
    type: string
    format: uri
```

### Schema response với allOf

```yaml
# components/schemas/ticket/TicketDetailResponse.yaml
type: object
properties:
  id:
    type: integer
    readOnly: true
  status:
    type: string
    enum: [CREATED, IN_PROGRESS, PENDING, CLOSED]
  created_at:
    type: string
    format: date-time
    readOnly: true
  creator:
    $ref: "../common/UserInfo.yaml"
  assignee:
    allOf:
      - $ref: "../common/UserInfo.yaml"
      - type: object
        properties:
          department:
            type: string
            example: "Hỗ trợ Hosting"
```

`assignee` dùng `allOf` để kế thừa `UserInfo` và thêm field `department`.

### Dùng trong path

```yaml
responses:
  "200":
    content:
      application/json:
        schema:
          allOf:
            - $ref: "../../components/schemas/core/StandardSuccess.yaml"
            - type: object
              properties:
                data:
                  $ref: "../../components/schemas/ticket/TicketDetailResponse.yaml"
  "401":
    $ref: "../../components/responses/Unauthorized.yaml"
  "403":
    $ref: "../../components/responses/Forbidden.yaml"
  "404":
    $ref: "../../components/responses/NotFound.yaml"
  "500":
    $ref: "../../components/responses/InternalError.yaml"
```
