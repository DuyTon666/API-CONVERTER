# CI/CD — Ma Trận Troubleshooting & Tham Chiếu
> Được cập nhật lần cuối vào ngày 09/06/2026

## 1. Bảng Tham Chiếu Nhanh

| Triệu chứng                                      | Nguyên nhân                         | Fix                                                              | Verify                  |
| ------------------------------------------------ | ----------------------------------- | ---------------------------------------------------------------- | ----------------------- |
| `error operation-id-verb-noun`                   | operationId không phải camelCase    | Đổi sang format `verbNoun` (vd: `createTicket`)                  | `npm run lint:spectral` |
| `error server-id-must-be-readonly`               | `id` thiếu `readOnly: true` trong response 200 | Thêm `readOnly: true` vào field `id` của response schema | `npm run lint:spectral` |
| `error client-id-must-not-be-readonly`           | `id` có `readOnly: true` trong requestBody | Xóa `readOnly` khỏi request schema                         | `npm run lint:spectral` |
| `error private-endpoint-must-have-401-403`       | Thiếu auth error responses          | Thêm 401 và 403 responses với `$ref`                             | `npm run lint:spectral` |
| `error has-request-body-must-have-400`           | Có requestBody nhưng thiếu 400      | Thêm `$ref` đến BadRequest response                              | `npm run lint:spectral` |
| `error enum-has-description`                     | Enum property thiếu description     | Thêm `description` mô tả từng giá trị enum                      | `npm run lint:spectral` |
| `Referenced schema not found`                    | Đường dẫn `$ref` không hợp lệ       | Sửa đường dẫn hoặc tạo file thiếu trong `5.openapi/`             | `npm run validate:api`  |
| `Circular reference detected`                    | Schema A → B → A                    | Phá vòng lặp bằng ID reference                                   | `npm run validate:api`  |
| `Property not expected here`                     | Lỗi chính tả OpenAPI keyword        | Sửa case (vd: `requestBody` không phải `requestbody`)            | `npm run validate:api`  |
| `npm ci` thất bại                                | Lockfile không đồng bộ              | `rm -rf node_modules package-lock.json && npm install`           | `npm ci`                |
| GitHub Actions checkout thất bại                 | Thiếu permissions                   | Thêm `permissions: contents: read` vào workflow                  | Re-run workflow         |
| Slack notification thất bại                      | Token/channel không hợp lệ          | Kiểm tra `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID` trong Secrets     | Re-run workflow         |

---

## 2. Spectral Rules — Danh Sách Đầy Đủ

Tất cả rules định nghĩa trong `.spectral.yaml`. Spectral chạy trên `dist/openapi-bundled.yaml`.

| Rule Code                               | Severity | Mô tả                                                   | Fix                                                         |
| --------------------------------------- | -------- | ------------------------------------------------------- | ----------------------------------------------------------- |
| `operation-id-verb-noun`                | error    | operationId phải camelCase bắt đầu bằng động từ         | Dùng format `verbNoun` (vd: `listTickets`, `createOrder`)   |
| `server-id-must-be-readonly`            | error    | Field `id` trong response 200 phải có `readOnly: true`  | Thêm `readOnly: true` vào field `id` của response schema    |
| `client-id-must-not-be-readonly`        | error    | Field `id` trong requestBody không được có `readOnly`   | Xóa `readOnly: true` khỏi request schema                   |
| `private-endpoint-must-have-401-403`    | error    | Private endpoint phải có response 401 và 403            | Thêm `$ref` đến Unauthorized và Forbidden                   |
| `has-request-body-must-have-400`        | error    | Endpoint có requestBody phải có response 400            | Thêm `$ref` đến BadRequest                                  |
| `enum-has-description`                  | error    | Property có `enum` phải có `description` mô tả giá trị | Thêm `description` liệt kê ý nghĩa từng giá trị            |
| `property-must-have-description`        | warning  | Property trong schema phải có `description`             | Thêm `description` cho từng field                           |
| `operation-must-have-description`       | warning  | Operation phải có `description`                         | Thêm trường `description`                                   |
| `operation-with-id-must-have-404`       | warning  | Endpoint có path parameter phải có response 404         | Thêm `$ref` đến NotFound                                    |
| `operation-must-have-tags`              | warning  | Operation phải có ít nhất 1 tag                         | Thêm tag để group trong documentation                       |
| `path-kebab-case`                       | warning  | Path phải dùng kebab-case                               | Dùng format `/kebab-case`                                   |
| `post-must-have-2xx`                    | warning  | POST phải có ít nhất response 200                       | Thêm response 200                                           |
| `delete-must-have-204`                  | warning  | DELETE nên có response 204 No Content                   | Thêm response 204                                           |
| `info-must-have-contact`                | info     | API phải có thông tin contact                           | Thêm `info.contact` vào root spec                           |

> **Lưu ý:** Không có rule tự động kiểm tra response 500. Việc thêm 500 là convention (xem Section 5).

---

## 3. Command Cheat Sheet

### Validation

```bash
# Thứ tự đúng: bundle trước, lint/validate sau
npm run bundle:api       # tạo dist/openapi-bundled.yaml từ 5.openapi/openapi.yaml
npm run lint:spectral    # Spectral custom rules
npm run validate:api     # Redocly OpenAPI 3.1 spec
npm run build:docs       # tạo public/api-docs.html (Swagger UI)
npm run build:docs:redocly  # tạo public/api-docs-redocly.html (Redocly UI)
```

### Tìm kiếm trong OpenAPI files

```bash
# Tìm tên schema
grep -r "TicketResponse" --include="*.yaml" 5.openapi/

# Tìm tất cả operationId
grep -r "operationId" --include="*.yaml" 5.openapi/paths/

# Phát hiện inline schemas thủ công
grep -rn "type: object" 5.openapi/paths/ --include="*.yaml"
grep -rn "type: array" 5.openapi/paths/ --include="*.yaml"

# Kiểm tra $ref có bị broken
grep -rn "\$ref" 5.openapi/paths/ --include="*.yaml"
```

### Bonus: Những Option grep đáng nhớ

| Option              | Ý nghĩa                      |
| ------------------- | ---------------------------- |
| `-r`                | recursive (tìm trong thư mục) |
| `-n`                | hiện số dòng                 |
| `-i`                | ignore case                  |
| `-A 5`              | hiện 5 dòng sau match        |
| `-B 5`              | hiện 5 dòng trước match      |
| `-C 5`              | hiện cả trước + sau          |
| `--include="*.yaml"` | chỉ search file yaml         |

### Git Operations

```bash
# Branch
git checkout develop && git pull origin develop
git checkout -b feat/schema-new-feature

# Commit & push
git add <files>
git commit -m "feat(schemas): description"
git push origin feat/schema-new-feature

# PR (GitHub CLI)
gh pr create --base develop --title "..." --body "..."
gh pr merge <number> --squash

# Undo
git reset --soft HEAD~1      # Hoàn tác commit (giữ thay đổi)
git restore <file>           # Hủy thay đổi local
```

### Debugging

```bash
# Kiểm tra file tồn tại
ls -la 5.openapi/components/schemas/ticket/TicketDetail.yaml

# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('5.openapi/openapi.yaml'))"

# Xem GitHub Actions logs
gh run list
gh run view <run-id> --log
gh run rerun <run-id>
```

---

## 4. Cấu Trúc Thư Mục OpenAPI

```
5.openapi/
├── openapi.yaml                    ← entry point (root spec)
├── components/
│   ├── responses/                  ← response refs dùng chung
│   │   ├── Unauthorized.yaml       → 401
│   │   ├── Forbidden.yaml          → 403
│   │   ├── NotFound.yaml           → 404
│   │   ├── BadRequest.yaml         → 400
│   │   ├── ValidationError.yaml    → 422
│   │   └── InternalError.yaml      → 500
│   ├── schemas/
│   │   ├── common/                 ← schema dùng chung nhiều module
│   │   ├── ticket/                 ← schemas của module ticket
│   │   ├── service/
│   │   ├── department/
│   │   ├── statistic/
│   │   └── ticket_custom/
│   └── parameters/
│       ├── PaginationParams.yaml
│       ├── TicketId.yaml
│       ├── UserId.yaml
│       └── XRequestId.yaml
└── paths/
    ├── ticket/
    ├── tickets/
    ├── service/
    ├── department/
    ├── statistic/
    └── ticket_custom/

dist/
└── openapi-bundled.yaml            ← bundle output (generated, committed)
```

---

## 5. Quy Ước Đặt Tên File

| Loại File        | Vị trí                                      | Quy tắc                        | Ví dụ                       |
| ---------------- | ------------------------------------------- | ------------------------------ | --------------------------- |
| Request Schema   | `5.openapi/components/schemas/<domain>/`    | PascalCase + hậu tố `Request`  | `CreateTicketRequest.yaml`  |
| Response Schema  | `5.openapi/components/schemas/<domain>/`    | PascalCase + hậu tố `Response` | `TicketDetailResponse.yaml` |
| Entity Schema    | `5.openapi/components/schemas/<domain>/`    | PascalCase                     | `TicketDetail.yaml`         |
| Common Schema    | `5.openapi/components/schemas/common/`      | PascalCase                     | `StandardError.yaml`        |
| Path File        | `5.openapi/paths/<domain>/`                 | kebab-case                     | `create-ticket.yaml`        |
| Response File    | `5.openapi/components/responses/`           | PascalCase                     | `Unauthorized.yaml`         |
| Parameter File   | `5.openapi/components/parameters/`          | PascalCase                     | `PaginationParams.yaml`     |

**$ref path convention** — từ `5.openapi/paths/<module>/file.yaml`:
```yaml
$ref: "../../components/responses/Unauthorized.yaml"    # response
$ref: "../../components/schemas/ticket/TicketDetail.yaml"  # schema
$ref: "../../components/parameters/PaginationParams.yaml"  # parameter
```

---

## 6. Hướng Dẫn Response Status Code

| Status  | Khi nào dùng                        | Bắt buộc cho                                           |
| ------- | ----------------------------------- | ------------------------------------------------------ |
| **200** | GET, PUT, PATCH, DELETE thành công  | Tất cả read/update operations                          |
| **201** | POST thành công (resource được tạo) | POST operations (khuyến nghị)                          |
| **204** | DELETE thành công, không có content | DELETE (khuyến nghị)                                   |
| **400** | Bad request, input không hợp lệ     | **Bắt buộc** khi operation có `requestBody`            |
| **401** | Token không hợp lệ/thiếu            | **Tất cả private endpoints** (có `security`)           |
| **403** | Không đủ quyền                      | **Tất cả private endpoints** (có `security`)           |
| **404** | Resource không tìm thấy             | **Tất cả operations có path parameter** (`{id}`)       |
| **422** | Validation error (lỗi semantic)     | Operations có validation rules phức tạp                |
| **500** | Internal server error               | Tất cả operations (convention, không có rule tự động)  |

> **Lưu ý 400:** Chỉ bắt buộc khi operation có `requestBody`. Các action endpoints không nhận body (`POST /logout`, `POST /activate`) không cần 400.
>
> **Lưu ý 500:** Không có Spectral rule kiểm tra. Thêm vào theo convention để documentation đầy đủ.

---

## 7. Schema Design Patterns

### Pattern 1: Request/Response Pair

```yaml
# Request — không có readOnly, không có id/created_at/updated_at
# Pipeline tự xóa created_at và updated_at khỏi request schema
type: object
required: [title, description]
properties:
  title:
    type: string
  description:
    type: string

# Response — server fields có readOnly: true
type: object
properties:
  id:
    type: integer
    readOnly: true
  title:
    type: string
  created_at:
    type: string
    format: date-time
    readOnly: true
  updated_at:
    type: string
    format: date-time
    readOnly: true
```

### Pattern 2: Enum Có Mô Tả

```yaml
status:
  type: string
  description: |
    Trạng thái của ticket:
    - CREATED: Ticket mới tạo, chưa được xử lý
    - IN_PROGRESS: Đang được xử lý bởi support team
    - PENDING: Chờ phản hồi từ khách hàng
    - CLOSED: Đã giải quyết xong
  enum: [CREATED, IN_PROGRESS, PENDING, CLOSED]
  example: "IN_PROGRESS"
```

### Pattern 3: Pagination Response

```yaml
responses:
  "200":
    content:
      application/json:
        schema:
          allOf:
            - $ref: "../../components/schemas/common/PaginatedResponse.yaml"
            - type: object
              properties:
                data:
                  type: array
                  items:
                    $ref: "../../components/schemas/ticket/TicketSummary.yaml"
```

### Pattern 4: Endpoint Đầy Đủ (Best Practice)

```yaml
get:
  summary: Lấy chi tiết ticket
  operationId: getTicketDetail
  description: Lấy thông tin chi tiết của một ticket theo ID.
  tags: [Ticket]
  security:
    - bearerAuth: []
  parameters:
    - $ref: "../../components/parameters/UserId.yaml"
    - $ref: "../../components/parameters/TicketId.yaml"
  responses:
    "200":
      description: Lấy thành công
      content:
        application/json:
          schema:
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

---

## 8. Security Best Practices

```yaml
# ❌ KHÔNG commit secrets
apiKey:
  default: "sk_live_abc123xyz"

# ✅ Dùng GitHub Secrets
env:
  SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
  SLACK_CHANNEL_ID: ${{ secrets.SLACK_CHANNEL_ID }}

# ✅ Minimal permissions trong workflow
permissions:
  contents: read
  pages: write
  id-token: write

# ✅ Validate input để tránh abuse
properties:
  email:
    type: string
    format: email
    maxLength: 255
  files:
    type: array
    maxItems: 3
```

---

## 9. Rollback Procedures

### Hoàn tác merge vào main

```bash
# An toàn (tạo commit mới)
git revert <commit-hash>
git push origin main

# Nguy hiểm (rewrite history — chỉ dùng khi chưa ai pull)
git reset --hard <previous-commit-hash>
git push origin main --force
```

### OpenAPI spec bị lỗi trên production

```bash
# 1. Tìm commit tốt cuối cùng
git log --oneline 5.openapi/openapi.yaml

# 2. Revert về version đó
git checkout <last-good-commit> -- 5.openapi/
git commit -m "fix: revert openapi spec to last good version"
git push origin main

# 3. Verify local
npm run bundle:api && npm run lint:spectral && npm run validate:api
```

---

## 10. CI/CD Performance Optimization

```yaml
# Cache npm để tăng tốc install (~30s → ~5s)
- name: Setup NodeJS
  uses: actions/setup-node@v5
  with:
    node-version: 24
    cache: npm
    cache-dependency-path: package-lock.json

# Tránh chạy nhiều lần trên cùng branch
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

# Deploy chỉ trigger khi file liên quan thay đổi
on:
  push:
    paths:
      - "5.openapi/**"
      - "scripts/**"
      - "package.json"
```

---

## 11. Tài Liệu Tham Khảo

| Tool           | Tài liệu                                  | Phiên bản |
| -------------- | ----------------------------------------- | --------- |
| Spectral       | <https://docs.stoplight.io/docs/spectral> | ^6.15.1   |
| Redocly CLI    | <https://redocly.com/docs/cli/>           | ^2.31.2   |
| oasdiff        | <https://github.com/oasdiff/oasdiff>      | v1.15.3   |
| OpenAPI 3.1    | <https://spec.openapis.org/oas/v3.1.0>    | 3.1.0     |
| GitHub Actions | <https://docs.github.com/en/actions>      | —         |

---

## 12. Glossary

| Thuật ngữ           | Định nghĩa                                                          |
| ------------------- | ------------------------------------------------------------------- |
| **OpenAPI**         | Đặc tả để mô tả REST APIs (trước đây là Swagger)                    |
| **Spectral**        | Linter cho OpenAPI/JSON/YAML với custom rules                       |
| **Redocly**         | Bộ công cụ OpenAPI: validation, bundling, documentation             |
| **oasdiff**         | Tool phát hiện breaking changes giữa hai OpenAPI specs              |
| **$ref**            | JSON Reference — con trỏ tới phần khác của tài liệu                 |
| **Inline Schema**   | Schema định nghĩa trực tiếp tại chỗ (anti-pattern trong dự án này) |
| **operationId**     | Định danh duy nhất cho một API operation                            |
| **readOnly**        | Property chỉ server gửi, client không được gửi                      |
| **allOf**           | JSON Schema keyword để kết hợp nhiều schemas                        |
| **Bundle**          | OpenAPI spec single-file với tất cả `$ref` đã resolve               |
| **Breaking Change** | Thay đổi API làm hỏng client hiện tại                               |
| **pipeline**        | Luồng chuyển đổi DOCX/PDF → OpenAPI YAML (xem `2.pipeline/`)       |
