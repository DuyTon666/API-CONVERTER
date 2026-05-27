# API Governance - Quy trình kiểm tra

## 🎯 Mục đích

Đảm bảo tất cả API specs tuân thủ chuẩn OpenAPI 3.0 và conventions của team.

## 🔍 Các rules được kiểm tra

### 1. **No Inline Schema (ERROR)**
Schema trong `paths/` phải dùng `$ref`, không được định nghĩa inline.

❌ **SAI:**
```yaml
# paths/users.yaml
post:
  requestBody:
    content:
      application/json:
        schema:
          type: object  # ← Inline schema
          properties:
            name:
              type: string
```

✅ **ĐÚNG:**
```yaml
# paths/users.yaml
post:
  requestBody:
    content:
      application/json:
        schema:
          $ref: '../components/schemas/CreateUserRequest.yaml'
```

### 2. **operationId Format (ERROR)**
operationId phải theo pattern `verbNoun`.

✅ **Đúng:** `listUsers`, `createOrder`, `deleteItem`, `closeTicket`
❌ **Sai:** `get_users`, `CreateOrder`, `delete-item`

### 3. **readOnly Fields (ERROR)**
Các trường sau phải có `readOnly: true`:
- `id`
- `created_at`
- `updated_at`

### 4. **Error Responses (WARNING)**
Mọi operation nên có:
- `401` (Unauthorized)
- `404` (Not Found) - cho operations với `/{id}`
- `500` (Internal Server Error)

## 🚀 Chạy kiểm tra local

```bash
# Chạy tất cả checks
npm run lint:api

# Chỉ chạy Spectral
npm run lint:spectral

# Chỉ chạy Redocly
npm run validate:api
```

## 🔄 Quy trình CI/CD

### Khi tạo PR:

1. **GitHub Actions tự động chạy**
   - Trigger: PR vào `main` hoặc `develop`
   - Workflow: `.github/workflows/ci.yaml`

2. **Các bước kiểm tra:**
   ```
   ✓ Check inline schema (bash script)
   ✓ Validate với Spectral
   ✓ Validate với Redocly
   ✓ Generate diff
   ✓ Build docs preview
   ```

3. **Kết quả:**
   - ✅ **PASS**: PR có thể merge
   - ❌ **FAIL**: PR bị block, phải sửa lỗi

### Khi merge vào main:

1. **Deploy docs lên GitHub Pages**
2. **Gửi notification Slack**

## 🛠️ Sửa lỗi thường gặp

### Lỗi: "Inline schema found"

**Nguyên nhân:** Schema được định nghĩa trực tiếp trong `paths/`

**Cách sửa:**
1. Tạo schema mới trong `components/schemas/`
2. Dùng `$ref` trong `paths/`

### Lỗi: "operationId sai format"

**Nguyên nhân:** operationId không theo pattern `verbNoun`

**Cách sửa:**
```yaml
# SAI
operationId: get_users

# ĐÚNG
operationId: listUsers
```

### Lỗi: "id phải có readOnly: true"

**Nguyên nhân:** Trường `id` trong schema không có `readOnly: true`

**Cách sửa:**
```yaml
properties:
  id:
    type: string
    format: uuid
    readOnly: true  # ← Thêm dòng này
```

## 📚 Tài liệu tham khảo

- [OpenAPI 3.1 Spec](https://spec.openapis.org/oas/v3.1.0)
- [Spectral Rules](https://meta.stoplight.io/docs/spectral/README.md)
- [Team Conventions](./CONVENTIONS.md)
