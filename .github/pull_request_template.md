## PR template

**Tiêu đề:** `feat(schemas): <mô tả ngắn gọn>`

### 📋 Mô tả thay đổi

<!-- Giải thích ngắn gọn bạn thêm/sửa gì và tại sao -->

### 📁 Files thay đổi

<!-- Liệt kê các file schema liên quan -->

- `components/schemas/.../XxxYyy.yaml`
- `paths/.../*.yaml`

### ✅ Checklist trước khi request review

- [ ] Đã chạy `npm run lint:inline | lint:spectral | validate:api` local — không còn lỗi `error`
- [ ] Tên file schema đúng **PascalCase**
- [ ] Tên thư mục đúng `components/schemas/<domain>/`
- [ ] `operationId` đúng format **verbNoun** (`createTicket`, `listUsers`…)
- [ ] Response schema dùng `$ref`, không inline
- [ ] Các field server-generated (`id`, `created_at`…) có `readOnly: true`
- [ ] Đủ error responses: `400`, `401`, `500` (và `404` nếu path có `{id}`)
- [ ] Commit message đúng format `feat(scope): mô tả`
- [ ] Đã cập nhật tất cả `$ref` nếu có đổi tên file

### 🔗 Liên kết liên quan

<!-- Ticket Jira / Linear, tài liệu API, PR liên quan nếu có -->

- Ticket:
- Tài liệu:

### 💬 Ghi chú cho reviewer

<!-- Điểm cần review kỹ, context đặc biệt, hoặc trade-off nếu có -->
