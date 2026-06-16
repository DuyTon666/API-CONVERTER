# CI/CD — Git Workflow

---

## 1. Branch Strategy

```bash
# Luôn tạo branch từ develop
git checkout develop
git pull origin develop

git checkout -b feat/schema-ticket-reopen
```

- `develop` = integration branch
- `main` = production branch
- **Không bao giờ commit trực tiếp vào `main` hoặc `develop`** (chặn trong settings github repo)

### Quy Ước Đặt Tên Branch

| Loại | Pattern | Ví dụ |
|---|---|---|
| Feature | `feat/schema-*` | `feat/schema-ticket-reopen` |
| Fix | `fix/schema-*` | `fix/schema-missing-401` |
| Chore | `chore/*` | `chore/update-spectral-rules` |

---

## 2. Commit Message Format

```bash
git add components/schemas/ticket/ReopenTicketRequest.yaml
git commit -m "feat(schemas): add ReopenTicketRequest schema"
```

### Format

```
<type>(<scope>): <subject>

type:    feat | fix | chore | docs | refactor
scope:   schemas | paths | rules | docs
subject: imperative, lowercase, không có dấu chấm cuối
```

### Ví Dụ

```bash
# ✅ ĐÚNG
git commit -m "feat(schemas): add CreateTicketRequest schema"
git commit -m "fix(paths): add missing 401 response to /tickets endpoint"
git commit -m "chore(spectral): update operationId validation rule"

# ❌ SAI
git commit -m "add schema"
git commit -m "Fixed bug"
git commit -m "Update files"
```

Subject nên hoàn chỉnh câu: *"This commit will..."*

---

## 3. Push & Tạo Pull Request

```bash
# Push lên remote
git push origin feat/schema-ticket-reopen

# Tạo PR qua GitHub CLI (tùy chọn)
gh pr create \
  --base develop \
  --title "feat(schemas): add ReopenTicketRequest schema" \
  --body "Adds schema for ticket reopen functionality"
```

- Push tạo remote branch
- PR kích hoạt CI/CD validation pipeline
- PR **phải pass tất cả checks** trước khi được phép merge

---

## 4. Pull Request Template

```markdown
## 📋 Mô Tả
<!-- PR này làm gì? Tại sao cần thiết? -->

## 📁 Files Thay Đổi
- `components/schemas/ticket/ReopenTicketRequest.yaml` (new)
- `paths/tickets/reopen.yaml` (updated)

## ✅ Checklist Trước Khi Merge
- [ ] Đã chạy `npm run lint:inline | lint:spectral | validate:api` local — không có lỗi
- [ ] File schema dùng PascalCase
- [ ] operationId theo format verbNoun
- [ ] Response schemas dùng `$ref` (không inline)
- [ ] Server-generated fields có `readOnly: true`
- [ ] Đủ các error responses bắt buộc (401, 403, 500)
- [ ] Commit message theo Conventional Commits format

## 🔗 Links Liên Quan
- Jira: PROJ-1234
- API Docs: https://example.com/api-docs

## 💬 Ghi Chú Cho Reviewer
Schema mới theo đúng pattern hiện tại. Không có breaking changes.
```
