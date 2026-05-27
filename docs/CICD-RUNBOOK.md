# CI/CD RUNBOOK — OpenAPI Validation Pipeline

> **Target Audience:** Senior Engineers, DevOps, Backend Developers
> **Last Updated:** 2026-05-19
> **Status:** Production-Ready

---

## TABLE OF CONTENTS

1. [System Architecture](#1-system-architecture)
2. [Local Development Flow](#2-local-development-flow)
3. [Git Workflow](#3-git-workflow)
4. [CI/CD Pipeline](#4-cicd-pipeline)
5. [Failure Scenarios & Debugging](#5-failure-scenarios--debugging)
6. [Real-World Examples](#6-real-world-examples)
7. [Troubleshooting Matrix](#7-troubleshooting-matrix)

---

## 1. SYSTEM ARCHITECTURE

### 1.1 Pipeline Overview

```txt
┌─────────────────┐
│  MÁY LOCAL      │
│                 │
│  1. Clone       │
│  2. Install     │
│  3. Lint        │
│  4. Commit      │
│  5. Push        │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│              GITHUB ACTIONS CI/CD                   │
│                                                     │
│  PR → main/develop:                                 │
│    ├─ validate.yaml (Spectral + Redocly)           │
│    └─ diff.yaml (Phát hiện Breaking Changes)       │
│                                                     │
│  Push → main/develop:                               │
│    ├─ deploy.yaml (Build Docs + GitHub Pages)      │
│    └─ notify (Thông báo Slack)                     │
└─────────────────────────────────────────────────────┘
```

### 1.2 Các Tầng Validation

| Tầng                               | Tool                    | Phạm vi                                       | Chặn CI  |
| ---------------------------------- | ----------------------- | --------------------------------------------- | -------- |
| **L1: Kiểm tra Inline Schema**     | Python script           | Phát hiện inline schemas trong `paths/`       | ✅ CÓ    |
| **L2: Spectral Lint**              | @stoplight/spectral-cli | Custom rules (operationId, readOnly, 401/403) | ✅ CÓ    |
| **L3: Redocly Validate**           | @redocly/cli            | Tuân thủ OpenAPI 3.1 spec                     | ✅ CÓ    |
| **L4: Breaking Changes**           | oasdiff                 | So sánh API với nhánh main                    | ⚠️ CẢNH BÁO |

### 1.3 Tools & Versions

```json
{
  "@stoplight/spectral-cli": "^6.15.1",
  "@redocly/cli": "^2.30.4",
  "oasdiff": "v1.10.27"
}
```

---

## 2. LUỒNG PHÁT TRIỂN LOCAL

### 2.1 Cài Đặt Ban Đầu

#### INPUT
- URL repository Git
- Node.js 20+ đã cài đặt
- Python 3.8+ đã cài đặt

#### COMMAND
```bash
# Clone repository
git clone https://github.com/Dinh-Nhan/CI-CD.git
cd CI-CD

# Cài đặt dependencies
npm ci

# Xác minh cài đặt
npm run lint:api
```

#### OUTPUT (Kỳ vọng)
```
================================================
🔍 Step 1: Checking paths for inline schemas...
================================================

🔍 Checking for inline schemas in paths/...

Checking paths/tickets/create.yaml...
  ✅ OK
Checking paths/tickets/detail.yaml...
  ✅ OK

✅ No inline schemas in paths/
```

#### EXPLANATION
- `npm ci` cài đặt phiên bản chính xác từ `package-lock.json` (reproducible builds)
- `npm run lint:api` thực thi `scripts/lint-all.sh` để chạy:
  1. Python inline schema checker
  2. Spectral lint (không hiển thị trong lần chạy đầu nếu không có lỗi)

#### ERROR CASE
```
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /path/to/package.json
```

#### FIX
```bash
# Xác minh bạn đang ở đúng thư mục
pwd  # Phải hiển thị .../CI-CD

# Kiểm tra package.json có tồn tại
ls -la package.json

# Nếu thiếu, clone lại repository
```

---

### 2.2 Chạy Validation Trên Local

#### 2.2.1 Validation Đầy Đủ

#### INPUT
- Các file OpenAPI đã sửa đổi trong `paths/` hoặc `components/`

#### COMMAND
```bash
npm run lint:api
```

#### OUTPUT (Thành công)
```
================================================
🔍 Step 1: Checking paths for inline schemas...
================================================

✅ No inline schemas in paths/
```

#### OUTPUT (Thất bại)
```
================================================
🔍 Step 1: Checking paths for inline schemas...
================================================

Checking paths/tickets/create.yaml...
  ❌ INLINE SCHEMA FOUND:
     - Found inline schema with type: object at post.requestBody.content.application/json.schema

❌ Inline schema check failed
```

#### EXPLANATION
- Script kiểm tra tất cả file `.yaml` trong thư mục `paths/`
- Thất bại nếu bất kỳ schema nào có `type: object` hoặc `type: array` mà không có `$ref`
- Exit code 1 = thất bại (chặn commit trong pre-commit hooks)

---

#### 2.2.2 Chỉ Chạy Spectral Lint

#### INPUT
- File OpenAPI specification

#### COMMAND
```bash
npm run lint:spectral
```

#### OUTPUT (Thành công)
```
No results with a severity of 'error' or higher found!
```

#### OUTPUT (Thất bại)
```
/home/user/CI-CD/openapi.yaml
  37:7  error  operation-id-verb-noun  operationId "create_ticket" sai format. Phải dùng camelCase — ví dụ: listUsers, createOrder, reopenTicket.  paths./v1/tickets.post.operationId

✖ 1 problem (1 error, 0 warnings, 0 infos, 0 hints)
```

#### EXPLANATION
- Spectral validate theo custom rules trong `.spectral.js`
- Error severity chặn CI/CD pipeline
- Warning severity cho phép merge nhưng yêu cầu fix trước khi production

---

#### 2.2.3 Redocly Validation

#### INPUT
- File OpenAPI specification

#### COMMAND
```bash
npm run validate:api
```

#### OUTPUT (Thành công)
```
validating /home/user/CI-CD/openapi.yaml...

/home/user/CI-CD/openapi.yaml: validated in 142ms

Woohoo! Your OpenAPI definition is valid. 🎉
```

#### OUTPUT (Thất bại)
```
validating /home/user/CI-CD/openapi.yaml...

[1] openapi.yaml:45:7 at #/paths/~1v1~1tickets/post/responses/200/content/application~1json/schema

Property `$ref` is not expected here.

43 |       content:
44 |         application/json:
45 |           schema:
46 |             $ref: "#/components/schemas/NonExistentSchema"
   |             ^^^^
47 |     "401":

Error was generated by the spec rule.

/home/user/CI-CD/openapi.yaml: validated in 156ms

❌ Validation failed with 1 error.
```

#### EXPLANATION
- Redocly kiểm tra tuân thủ OpenAPI 3.1 specification
- Validate `$ref` resolution, cấu trúc schema, các trường bắt buộc
- Phát hiện circular references và invalid references

---

### 2.3 Bundle & Build Documentation

#### INPUT
- OpenAPI specification hợp lệ

#### COMMAND
```bash
# Bundle tất cả $ref vào single file
npm run bundle:api

# Build HTML documentation
npm run build:docs
```

#### OUTPUT
```
Bundling...
📦 Created a bundle for /home/user/CI-CD/openapi.yaml at openapi-bundled.yaml 142ms.

Building documentation...
🎉 bundled successfully in: openapi-bundled.yaml (142ms)
🎉 built successfully in: api-docs.html (1.2s)
```

#### EXPLANATION
- `bundle:api` resolve tất cả `$ref` vào `openapi-bundled.yaml`
- `build:docs` tạo static HTML documentation
- Được sử dụng trong deployment pipeline tới GitHub Pages

#### ERROR CASE
```
Error: Can't resolve reference: #/components/schemas/NonExistentSchema
```

#### FIX
```bash
# Tìm tất cả references tới schema bị thiếu
grep -r "NonExistentSchema" --include="*.yaml" .

# Chọn một trong hai:
# 1. Tạo file schema bị thiếu
# 2. Sửa $ref để trỏ tới schema đúng
```

---


## 3. LUỒNG GIT

### 3.1 Chiến Lược Nhánh

#### INPUT
- Yêu cầu feature/fix

#### COMMAND
```bash
# Luôn tạo nhánh từ develop
git checkout develop
git pull origin develop

# Tạo feature branch
git checkout -b feat/schema-ticket-reopen
```

#### EXPLANATION
- `develop` = nhánh tích hợp
- `main` = nhánh production
- Không bao giờ commit trực tiếp vào `main` hoặc `develop`

#### Quy Ước Đặt Tên Nhánh
| Loại    | Pattern         | Ví dụ                         |
| ------- | --------------- | ----------------------------- |
| Feature | `feat/schema-*` | `feat/schema-ticket-reopen`   |
| Fix     | `fix/schema-*`  | `fix/schema-missing-401`      |
| Chore   | `chore/*`       | `chore/update-spectral-rules` |

---

### 3.2 Format Commit Message

#### INPUT
- Các thay đổi đã staged

#### COMMAND
```bash
git add components/schemas/ticket/ReopenTicketRequest.yaml
git commit -m "feat(schemas): add ReopenTicketRequest schema"
```

#### FORMAT
```
<type>(<scope>): <subject>

type: feat | fix | chore | docs | refactor
scope: schemas | paths | rules | docs
subject: imperative, lowercase, no period
```

#### VÍ DỤ
```bash
# ✅ TỐT
git commit -m "feat(schemas): add CreateTicketRequest schema"
git commit -m "fix(paths): add missing 401 response to /tickets endpoint"
git commit -m "chore(spectral): update operationId validation rule"

# ❌ TỆ
git commit -m "add schema"
git commit -m "Fixed bug"
git commit -m "Update files"
```

#### EXPLANATION
- Conventional commits cho phép tạo changelog tự động
- Scope giúp xác định phần nào của codebase đã thay đổi
- Subject nên hoàn thành câu: "This commit will..."

---

### 3.3 Push & Tạo Pull Request

#### INPUT
- Các thay đổi đã commit trên feature branch

#### COMMAND
```bash
# Push lên remote
git push origin feat/schema-ticket-reopen

# Tạo PR qua GitHub CLI (tùy chọn)
gh pr create \
  --base develop \
  --title "feat(schemas): add ReopenTicketRequest schema" \
  --body "Adds schema for ticket reopen functionality"
```

#### OUTPUT
```
Enumerating objects: 7, done.
Counting objects: 100% (7/7), done.
Delta compression using up to 8 threads
Compressing objects: 100% (4/4), done.
Writing objects: 100% (4/4), 512 bytes | 512.00 KiB/s, done.
Total 4 (delta 3), reused 0 (delta 0), pack-reused 0
remote: Resolving deltas: 100% (3/3), completed with 3 local objects.
To github.com:Dinh-Nhan/CI-CD.git
 * [new branch]      feat/schema-ticket-reopen -> feat/schema-ticket-reopen
```

#### EXPLANATION
- Push tạo remote branch
- PR kích hoạt CI/CD validation pipeline
- PR phải pass tất cả checks trước khi được phép merge

---

### 3.4 Pull Request Template

```markdown
## 📋 Mô Tả
<!-- PR này làm gì? Tại sao cần thiết? -->

Thêm schema `ReopenTicketRequest` để hỗ trợ chức năng mở lại ticket.

## 📁 Files Thay Đổi
- `components/schemas/ticket/ReopenTicketRequest.yaml` (mới)
- `paths/tickets/reopen.yaml` (cập nhật)

## ✅ Checklist Trước Khi Merge
- [x] Đã chạy `npm run lint:api` trên local — không có lỗi
- [x] File schema sử dụng PascalCase naming
- [x] operationId tuân theo format verbNoun
- [x] Response schemas sử dụng `$ref` (không có inline schemas)
- [x] Các trường server-generated có `readOnly: true`
- [x] Tất cả error responses bắt buộc đã có (401, 403, 500)
- [x] Commit message tuân theo conventional format

## 🔗 Liên Kết Liên Quan
- Jira: PROJ-1234
- API Docs: https://example.com/api-docs

## 💬 Ghi Chú Cho Reviewer
<!-- Điều gì reviewer cần chú ý đặc biệt -->

Schema mới tuân theo patterns hiện có. Không có breaking changes.
```

---

## 4. CI/CD PIPELINE

### 4.1 Điều Kiện Trigger

#### Pull Request → `main` hoặc `develop`
```yaml
on:
  pull_request:
    branches: [main, develop]
```

**Chạy:**
1. `validate.yaml` — Spectral + Redocly validation
2. `diff.yaml` — Phát hiện API breaking changes

#### Push → `main` hoặc `develop`
```yaml
on:
  push:
    branches: [main, develop]
    paths:
      - "components/**"
      - "paths/**"
      - "openapi.yaml"
```

**Chạy:**
1. `deploy.yaml` — Build docs + deploy tới GitHub Pages
2. `notify` — Gửi thông báo Slack

---

### 4.2 Validation Workflow (validate.yaml)

#### BƯỚC 1: Checkout Repository

#### INPUT
- GitHub Actions runner (ubuntu-latest)

#### COMMAND
```yaml
- name: Checkout repository
  uses: actions/checkout@v4
```

#### OUTPUT
```
Run actions/checkout@v4
Syncing repository: Dinh-Nhan/CI-CD
Getting Git version info
Initializing the repository
```

#### EXPLANATION
- Clone repository vào workspace của runner
- Sử dụng `actions/checkout@v4` để hỗ trợ Git LFS và submodules

---

#### BƯỚC 2: Setup Node.js

#### INPUT
- Node.js version 20
- `package-lock.json` cho cache key

#### COMMAND
```yaml
- name: Setup NodeJS
  uses: actions/setup-node@v4
  with:
    node-version: 20
    cache: npm
    cache-dependency-path: package-lock.json
```

#### OUTPUT
```
Run actions/setup-node@v4
Attempting to download 20.x...
Extracting Node.js...
Adding to PATH...
Successfully set up Node.js version 20.12.0
```

#### EXPLANATION
- Cài đặt Node.js 20.x (latest stable)
- Cache `node_modules` dựa trên hash của `package-lock.json`
- Cache hit giảm thời gian cài đặt từ ~30s xuống ~5s

---

#### BƯỚC 3: Cài Đặt Dependencies

#### INPUT
- `package.json` và `package-lock.json`

#### COMMAND
```yaml
- name: Install dependencies
  run: npm ci
```

#### OUTPUT
```
Run npm ci
npm WARN deprecated @humanwhocodes/config-array@0.11.14
added 234 packages in 12s
```

#### EXPLANATION
- `npm ci` (clean install) xóa `node_modules` và cài đặt từ lockfile
- Đảm bảo reproducible builds (khác với `npm install`)
- Thất bại nếu `package-lock.json` không đồng bộ với `package.json`

#### ERROR CASE
```
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json are in sync.
```

#### FIX
```bash
# Tạo lại lockfile trên local
npm install
git add package-lock.json
git commit -m "chore: update package-lock.json"
git push
```

---

#### BƯỚC 4: Chạy Spectral Lint

#### INPUT
- `openapi.yaml` và tất cả các file được tham chiếu
- `.spectral.js` ruleset

#### COMMAND
```yaml
- name: Run Spectral Lint
  run: npm run lint:api
```

#### OUTPUT (Thành công)
```
Run npm run lint:api

================================================
🔍 Step 1: Checking paths for inline schemas...
================================================

✅ No inline schemas in paths/
```

#### OUTPUT (Thất bại)
```
Run npm run lint:api

================================================
🔍 Step 1: Checking paths for inline schemas...
================================================

Checking paths/tickets/create.yaml...
  ❌ INLINE SCHEMA FOUND:
     - Found inline schema with type: object at post.requestBody.content.multipart/form-data.schema

❌ Inline schema check failed
Error: Process completed with exit code 1.
```

#### EXPLANATION
- Thực thi `scripts/lint-all.sh` để chạy:
  1. Python inline schema checker
  2. Spectral lint (nếu bước 1 pass)
- Exit code 1 làm workflow thất bại và chặn PR merge

#### ERROR CASE — Inline Schema
```
paths/tickets/create.yaml:15:13
  ❌ INLINE SCHEMA FOUND:
     - Found inline schema with type: object at post.requestBody.content.application/json.schema
```

#### FIX
```yaml
# ❌ TRƯỚC (inline schema)
requestBody:
  content:
    application/json:
      schema:
        type: object
        properties:
          title:
            type: string

# ✅ SAU (dùng $ref)
requestBody:
  content:
    application/json:
      schema:
        $ref: "../../components/schemas/ticket/CreateTicketRequest.yaml"
```

---

#### BƯỚC 5: Chạy Redocly Validation

#### INPUT
- `openapi.yaml` và tất cả các file được tham chiếu
- `.redocly.yaml` configuration

#### COMMAND
```yaml
- name: Run Redocly Validation
  run: npm run validate:api
```

#### OUTPUT (Thành công)
```
Run npm run validate:api

validating /home/runner/work/CI-CD/CI-CD/openapi.yaml...

/home/runner/work/CI-CD/CI-CD/openapi.yaml: validated in 142ms

Woohoo! Your OpenAPI definition is valid. 🎉
```

#### OUTPUT (Thất bại)
```
Run npm run validate:api

validating /home/runner/work/CI-CD/CI-CD/openapi.yaml...

[1] openapi.yaml:45:7 at #/paths/~1v1~1tickets/post/responses/200/content

Referenced schema not found: #/components/schemas/TicketResponse

Error was generated by the spec rule.

❌ Validation failed with 1 error.
Error: Process completed with exit code 1.
```

#### EXPLANATION
- Validate tuân thủ OpenAPI 3.1 specification
- Kiểm tra tất cả `$ref` resolve đúng
- Phát hiện circular references và cấu trúc schema không hợp lệ

#### ERROR CASE — Thiếu $ref
```
Referenced schema not found: #/components/schemas/TicketResponse
```

#### FIX
```bash
# Kiểm tra file có tồn tại
ls -la components/schemas/ticket/TicketResponse.yaml

# Nếu thiếu, tạo file schema
# Nếu tồn tại, kiểm tra đường dẫn $ref có đúng
```

---

### 4.3 Diff Workflow (diff.yaml)

#### BƯỚC 1: Checkout Nhánh Hiện Tại & Nhánh Gốc

#### INPUT
- Nhánh PR hiện tại
- Nhánh gốc (main)

#### COMMAND
```yaml
- uses: actions/checkout@v4
  with: { path: new }

- uses: actions/checkout@v4
  with: { ref: main, path: old }
```

#### OUTPUT
```
Syncing repository: Dinh-Nhan/CI-CD
Checking out ref: main
Successfully checked out main to /home/runner/work/CI-CD/CI-CD/old
```

#### EXPLANATION
- Checkout nhánh PR vào thư mục `new/`
- Checkout nhánh `main` vào thư mục `old/`
- Cho phép so sánh song song

---

#### BƯỚC 2: Cài Đặt oasdiff

#### INPUT
- oasdiff binary v1.10.27

#### COMMAND
```yaml
- name: Install oasdiff
  run: |
    if ! command -v oasdiff &> /dev/null; then
      curl -fsSL https://github.com/oasdiff/oasdiff/releases/download/v1.10.27/oasdiff_1.10.27_linux_amd64.tar.gz | tar -xz
      sudo mv oasdiff /usr/local/bin/
    fi
```

#### OUTPUT
```
Run if ! command -v oasdiff &> /dev/null; then...
Downloading oasdiff v1.10.27...
Installing to /usr/local/bin/oasdiff
```

#### EXPLANATION
- Tải pre-compiled binary từ GitHub releases
- Cache binary để tăng tốc các lần chạy tiếp theo
- `command -v` kiểm tra đã cài đặt chưa

---

#### BƯỚC 3: Kiểm Tra Changelog Changes

#### INPUT
- `old/openapi.yaml` (nhánh main)
- `new/openapi.yaml` (nhánh PR)

#### COMMAND
```yaml
- name: Check changelog changes
  run: |
    oasdiff changelog old/openapi.yaml new/openapi.yaml || true
```

#### OUTPUT (Không Có Thay Đổi)
```
Run oasdiff changelog old/openapi.yaml new/openapi.yaml
No changes detected
```

#### OUTPUT (Phát Hiện Thay Đổi)
```
Run oasdiff changelog old/openapi.yaml new/openapi.yaml

### What's New
- POST /v1/users/{user_id}/tickets/{id}/reopen

### What's Modified
- POST /v1/users/{user_id}/tickets
  - Request body property 'files' max items increased from 3 to 5

### Breaking Changes
None
```

#### EXPLANATION
- So sánh OpenAPI specs và tạo changelog dễ đọc
- `|| true` ngăn thất bại (chỉ mang tính thông tin)
- Phát hiện breaking changes có thể được bật (đã comment trong workflow)

---

### 4.4 Deploy Workflow (deploy.yaml)

#### BƯỚC 1-3: Giống Validation Workflow
(Checkout, Setup Node, Install Dependencies)

---

#### BƯỚC 4: Bundle OpenAPI Specification

#### INPUT
- `openapi.yaml` với tất cả các file `$ref`

#### COMMAND
```yaml
- name: Bundle OpenAPI Specification
  run: npm run bundle:api
```

#### OUTPUT
```
Run npm run bundle:api

Bundling...
📦 Created a bundle for /home/runner/work/CI-CD/CI-CD/openapi.yaml at openapi-bundled.yaml 142ms.
```

#### EXPLANATION
- Resolve tất cả `$ref` vào single file `openapi-bundled.yaml`
- Bắt buộc cho việc tạo documentation
- File đã bundle là self-contained (không có external references)

---

#### BƯỚC 5: Build API Documentation

#### INPUT
- `openapi-bundled.yaml`

#### COMMAND
```yaml
- name: Build API Documentation
  run: npm run build:docs
```

#### OUTPUT
```
Run npm run build:docs

Building documentation...
🎉 bundled successfully in: openapi-bundled.yaml (142ms)
🎉 built successfully in: api-docs.html (1.2s)
```

#### EXPLANATION
- Tạo static HTML documentation sử dụng Redocly
- Output: `api-docs.html` (single-page documentation)
- Bao gồm interactive API explorer

---

#### BƯỚC 6: Chuẩn Bị GitHub Pages Deployment

#### INPUT
- `api-docs.html`

#### COMMAND
```yaml
- name: Prepare Deployment Folder
  run: |
    mkdir -p _site
    cp api-docs.html _site/index.html
```

#### OUTPUT
```
Run mkdir -p _site
Copying api-docs.html to _site/index.html
```

#### EXPLANATION
- GitHub Pages phục vụ từ thư mục `_site/`
- Đổi tên `api-docs.html` thành `index.html` để phục vụ mặc định

---

#### BƯỚC 7: Upload & Deploy tới GitHub Pages

#### INPUT
- Thư mục `_site/`

#### COMMAND
```yaml
- name: Upload Pages Artifact
  uses: actions/upload-pages-artifact@v3
  with:
    path: _site

- name: Deploy to GitHub Pages
  uses: actions/deploy-pages@v4
```

#### OUTPUT
```
Run actions/upload-pages-artifact@v3
Uploading artifact...
Artifact uploaded successfully

Run actions/deploy-pages@v4
Deploying to GitHub Pages...
Deployment successful
URL: https://dinh-nhan.github.io/CI-CD/
```

#### EXPLANATION
- Upload `_site/` dưới dạng GitHub Actions artifact
- Deploy artifact tới GitHub Pages
- Truy cập tại `https://<username>.github.io/<repo>/`

---

#### BƯỚC 8: Gửi Thông Báo Slack

#### INPUT
- Kết quả deployment (success/failure)
- Danh sách files thay đổi
- Metadata commit

#### COMMAND
```yaml
- name: Gửi thông báo Slack
  run: |
    curl -X POST https://slack.com/api/chat.postMessage \
      -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{...}"
```

#### OUTPUT (Slack Message)
```
✅ Deploy — Passed

Repo:     Dinh-Nhan/CI-CD
Branch:   `main`
Author:   dinhnhan
Commit:   `a3f9c12`

Files changed:
• components/schemas/ticket/ReopenTicketRequest.yaml
• paths/tickets/reopen.yaml

[Xem CI Run]
```

#### EXPLANATION
- Gửi message được format tới Slack channel
- Bao gồm trạng thái deployment, metadata, và link tới CI run
- Yêu cầu secrets `SLACK_BOT_TOKEN` và `SLACK_CHANNEL_ID`

#### ERROR CASE
```
curl: (22) The requested URL returned error: 401 Unauthorized
```

#### FIX
```bash
# Xác minh Slack bot token đã được set trong GitHub Secrets
# Settings → Secrets and variables → Actions → Repository secrets
# Thêm: SLACK_BOT_TOKEN, SLACK_CHANNEL_ID
```

---


## 5. CÁC TÌNH HUỐNG LỖI & DEBUGGING

### 5.1 Spectral Lint Failures

#### 5.1.1 Lỗi Format operationId

#### ERROR OUTPUT
```
/home/runner/work/CI-CD/CI-CD/paths/tickets/create.yaml
  5:17  error  operation-id-verb-noun  operationId "create_ticket" sai format. Phải dùng camelCase — ví dụ: listUsers, createOrder, reopenTicket.  post.operationId

✖ 1 problem (1 error, 0 warnings, 0 infos, 0 hints)
```

#### ROOT CAUSE
- operationId sử dụng snake_case thay vì camelCase
- Rule: `operation-id-verb-noun` trong `.spectral.js`
- Pattern: `^[a-z][a-zA-Z0-9]+$`

#### FIX
```yaml
# ❌ TRƯỚC
post:
  operationId: create_ticket

# ✅ SAU
post:
  operationId: createTicket
```

#### VERIFICATION
```bash
npm run lint:spectral
# Phải hiển thị: No results with a severity of 'error' or higher found!
```

---

#### 5.1.2 Thiếu readOnly Trên Server Fields

#### ERROR OUTPUT
```
/home/runner/work/CI-CD/CI-CD/components/schemas/ticket/TicketDetail.yaml
  12:7  error  schema-server-fields-must-be-readonly  Trường "id" phải có readOnly: true  properties.id

✖ 1 problem (1 error, 0 warnings, 0 infos, 0 hints)
```

#### ROOT CAUSE
- Các trường server-generated (`id`, `created_at`, `updated_at`) phải là read-only
- Ngăn clients gửi các trường này trong requests
- Rule: `schema-server-fields-must-be-readonly` trong `.spectral.js`

#### FIX
```yaml
# ❌ TRƯỚC
properties:
  id:
    type: integer
    example: 456
  created_at:
    type: string
    format: date-time

# ✅ SAU
properties:
  id:
    type: integer
    example: 456
    readOnly: true
  created_at:
    type: string
    format: date-time
    readOnly: true
```

#### VERIFICATION
```bash
npm run lint:spectral
```

---

#### 5.1.3 Thiếu 401/403 Trên Private Endpoints

#### ERROR OUTPUT
```
/home/runner/work/CI-CD/CI-CD/paths/tickets/create.yaml
  10:3  error  private-endpoint-must-have-401-403  Endpoint private phải có response 401 (Unauthorized)  post
  10:3  error  private-endpoint-must-have-401-403  Endpoint private phải có response 403 (Forbidden)  post

✖ 2 problems (2 errors, 0 warnings, 0 infos, 0 hints)
```

#### ROOT CAUSE
- Endpoint yêu cầu authentication (`security: [bearerAuth: []]`)
- Phải document 401 (invalid token) và 403 (insufficient permissions)
- Custom function: `functions/private-must-have-401-403.js`

#### FIX
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

#### VERIFICATION
```bash
npm run lint:spectral
```

---

#### 5.1.4 Thiếu 500 Response

#### ERROR OUTPUT
```
/home/runner/work/CI-CD/CI-CD/paths/tickets/create.yaml
  10:3  warning  operation-must-have-500  Operation thiếu response 500 (Internal Server Error).  post

✖ 0 problems (0 errors, 1 warning, 0 infos, 0 hints)
```

#### ROOT CAUSE
- Tất cả operations nên document 500 (server error)
- Warning level (không chặn merge nhưng nên được fix)

#### FIX
```yaml
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

### 5.2 Redocly Validation Failures

#### 5.2.1 Đường Dẫn $ref Không Hợp Lệ

#### ERROR OUTPUT
```
validating /home/runner/work/CI-CD/CI-CD/openapi.yaml...

[1] openapi.yaml:45:7 at #/paths/~1v1~1tickets/post/responses/200/content/application~1json/schema

Property `$ref` is not expected here.

Referenced schema not found: #/components/schemas/TicketResponse

Error was generated by the spec rule.

❌ Validation failed with 1 error.
```

#### ROOT CAUSE
- `$ref` trỏ tới file schema không tồn tại
- Các nguyên nhân có thể:
  1. File không tồn tại
  2. Đường dẫn file không đúng
  3. File đã được đổi tên nhưng `$ref` chưa cập nhật

#### FIX
```bash
# Bước 1: Kiểm tra file có tồn tại
ls -la components/schemas/ticket/TicketResponse.yaml

# Bước 2: Nếu thiếu, tạo file
# Nếu tồn tại, xác minh đường dẫn $ref

# Bước 3: Tìm tất cả references tới schema này
grep -r "TicketResponse" --include="*.yaml" .

# Bước 4: Cập nhật tất cả đường dẫn $ref
```

#### VERIFICATION
```bash
npm run validate:api
# Phải hiển thị: Woohoo! Your OpenAPI definition is valid. 🎉
```

---

#### 5.2.2 Circular Reference

#### ERROR OUTPUT
```
validating /home/runner/work/CI-CD/CI-CD/openapi.yaml...

[1] components/schemas/ticket/TicketDetail.yaml:15:7

Circular reference detected:
  TicketDetail → Conversation → TicketDetail

Error was generated by the spec rule.

❌ Validation failed with 1 error.
```

#### ROOT CAUSE
- Schema A tham chiếu Schema B, Schema B lại tham chiếu Schema A
- Tạo vòng lặp vô hạn trong schema resolution

#### FIX
```yaml
# ❌ TRƯỚC (circular)
# TicketDetail.yaml
properties:
  conversations:
    type: array
    items:
      $ref: "./Conversation.yaml"

# Conversation.yaml
properties:
  ticket:
    $ref: "./TicketDetail.yaml"

# ✅ SAU (phá vòng lặp)
# Conversation.yaml
properties:
  ticket_id:
    type: integer
    description: Reference to ticket ID (tránh circular ref)
```

#### VERIFICATION
```bash
npm run validate:api
```

---

#### 5.2.3 Cú Pháp OpenAPI Không Hợp Lệ

#### ERROR OUTPUT
```
validating /home/runner/work/CI-CD/CI-CD/openapi.yaml...

[1] paths/tickets/create.yaml:10:3

Property `requestbody` is not expected here. Did you mean `requestBody`?

Error was generated by the spec rule.

❌ Validation failed with 1 error.
```

#### ROOT CAUSE
- Lỗi chính tả trong OpenAPI keyword (phân biệt hoa thường)
- Các lỗi phổ biến: `requestbody`, `Responses`, `Content`

#### FIX
```yaml
# ❌ TRƯỚC
post:
  requestbody:  # chữ 'b' thường
    content:
      application/json:
        schema:
          $ref: "..."

# ✅ SAU
post:
  requestBody:  # camelCase
    content:
      application/json:
        schema:
          $ref: "..."
```

---

### 5.3 Inline Schema Check Failures

#### ERROR OUTPUT
```
================================================
🔍 Step 1: Checking paths for inline schemas...
================================================

Checking paths/tickets/create.yaml...
  ❌ INLINE SCHEMA FOUND:
     - Found inline schema with type: object at post.requestBody.content.application/json.schema

❌ Inline schema check failed
```

#### ROOT CAUSE
- Schema được định nghĩa inline trong thư mục `paths/`
- Vi phạm separation of concerns (paths chỉ nên tham chiếu schemas)
- Script: `scripts/check-inline-schema.py`

#### FIX
```yaml
# ❌ TRƯỚC (inline schema trong paths/tickets/create.yaml)
post:
  requestBody:
    content:
      application/json:
        schema:
          type: object
          properties:
            title:
              type: string
            description:
              type: string

# ✅ SAU
# Bước 1: Tạo components/schemas/ticket/CreateTicketRequest.yaml
type: object
properties:
  title:
    type: string
  description:
    type: string

# Bước 2: Tham chiếu trong paths/tickets/create.yaml
post:
  requestBody:
    content:
      application/json:
        schema:
          $ref: "../../components/schemas/ticket/CreateTicketRequest.yaml"
```

#### VERIFICATION
```bash
npm run lint:api
# Phải hiển thị: ✅ No inline schemas in paths/
```

---

### 5.4 GitHub Actions Failures

#### 5.4.1 npm ci Thất Bại

#### ERROR OUTPUT
```
Run npm ci

npm ERR! code EUSAGE
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json are in sync.

Error: Process completed with exit code 1.
```

#### ROOT CAUSE
- `package-lock.json` không đồng bộ với `package.json`
- Thường xảy ra sau khi chỉnh sửa `package.json` thủ công

#### FIX
```bash
# Tạo lại lockfile trên local
rm -rf node_modules package-lock.json
npm install

# Commit lockfile đã cập nhật
git add package-lock.json
git commit -m "chore: regenerate package-lock.json"
git push
```

---

#### 5.4.2 Checkout Thất Bại

#### ERROR OUTPUT
```
Run actions/checkout@v4

Error: fatal: repository 'https://github.com/Dinh-Nhan/CI-CD.git' not found

Error: Process completed with exit code 128.
```

#### ROOT CAUSE
- Repository là private và workflow không có quyền truy cập
- Quyền `GITHUB_TOKEN` không đủ

#### FIX
```yaml
# Thêm vào workflow file
permissions:
  contents: read
  pull-requests: write  # nếu comment trên PRs
```

---

#### 5.4.3 Slack Notification Thất Bại

#### ERROR OUTPUT
```
Run curl -X POST https://slack.com/api/chat.postMessage...

{"ok":false,"error":"invalid_auth"}

Error: Process completed with exit code 22.
```

#### ROOT CAUSE
- Secret `SLACK_BOT_TOKEN` chưa được set hoặc không hợp lệ
- Bot không có quyền post trong channel

#### FIX
```bash
# Bước 1: Xác minh secret đã được set
# GitHub → Settings → Secrets and variables → Actions
# Kiểm tra: SLACK_BOT_TOKEN, SLACK_CHANNEL_ID

# Bước 2: Xác minh quyền bot trong Slack
# Slack App → OAuth & Permissions → Scopes
# Yêu cầu: chat:write, chat:write.public

# Bước 3: Cài đặt lại app vào workspace nếu cần
```

---

### 5.5 Quy Trình Debugging

```
┌─────────────────────────────────────────┐
│  CI/CD Pipeline Thất Bại                │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Bước 1: Xác Định Job Thất Bại          │
│  → GitHub Actions → Click vào run fail  │
│  → Mở rộng step bị lỗi                  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Bước 2: Đọc Error Message              │
│  → Copy toàn bộ error output            │
│  → Ghi chú đường dẫn file và số dòng    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Bước 3: Tái Hiện Trên Local            │
│  → git pull origin <branch>             │
│  → npm ci                                │
│  → npm run lint:api                     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Bước 4: Sửa Lỗi                        │
│  → Sửa file dựa trên error message      │
│  → Chạy validation lại                  │
│  → Lặp lại cho đến khi pass             │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Bước 5: Commit & Push                  │
│  → git add <files>                      │
│  → git commit -m "fix: ..."             │
│  → git push                              │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Bước 6: Xác Minh CI Pass               │
│  → Đợi GitHub Actions hoàn thành        │
│  → Kiểm tra tất cả jobs đều xanh        │
└─────────────────────────────────────────┘
```


## 6. VÍ DỤ THỰC TẾ

### 6.1 Ví Dụ 1: Thêm Endpoint Mới (Đường Thành Công)

#### KỊCH BẢN
Thêm endpoint: `POST /v1/users/{user_id}/tickets/{id}/reopen`

---

#### BƯỚC 1: Tạo Schema File

**INPUT:** Yêu cầu endpoint

**COMMAND:**
```bash
# Tạo schema file
touch components/schemas/ticket/ReopenTicketRequest.yaml
```

**FILE:** `components/schemas/ticket/ReopenTicketRequest.yaml`
```yaml
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

**EXPLANATION:**
- Tên file sử dụng PascalCase: `ReopenTicketRequest.yaml`
- Nằm trong `components/schemas/ticket/` (tổ chức theo domain)
- Không có trường `readOnly` (đây là request schema)

---

#### BƯỚC 2: Tạo Path File

**COMMAND:**
```bash
# Tạo path file
touch paths/tickets/reopen.yaml
```

**FILE:** `paths/tickets/reopen.yaml`
```yaml
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
      description: UID của khách hàng
    - name: id
      in: path
      required: true
      schema:
        type: integer
      description: ID của ticket cần mở lại
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

**EXPLANATION:**
- `operationId: reopenTicket` (camelCase, format verbNoun)
- Sử dụng `$ref` cho tất cả schemas (không inline)
- Bao gồm tất cả error responses bắt buộc (401, 403, 404, 500)
- Path parameters có `required: true`

---

#### BƯỚC 3: Cập Nhật openapi.yaml

**COMMAND:**
```bash
# Chỉnh sửa openapi.yaml
nano openapi.yaml
```

**FILE:** `openapi.yaml` (thêm vào phần paths)
```yaml
paths:
  # ... existing paths ...
  /v1/users/{user_id}/tickets/{id}/reopen:
    $ref: "./paths/tickets/reopen.yaml"
```

---

#### BƯỚC 4: Validate Trên Local

**COMMAND:**
```bash
npm run lint:api
```

**OUTPUT:**
```
================================================
🔍 Step 1: Checking paths for inline schemas...
================================================

🔍 Checking for inline schemas in paths/...

Checking paths/tickets/create.yaml...
  ✅ OK
Checking paths/tickets/reopen.yaml...
  ✅ OK

✅ No inline schemas in paths/
```

**COMMAND:**
```bash
npm run validate:api
```

**OUTPUT:**
```
validating /home/user/CI-CD/openapi.yaml...

/home/user/CI-CD/openapi.yaml: validated in 156ms

Woohoo! Your OpenAPI definition is valid. 🎉
```

---

#### BƯỚC 5: Commit & Push

**COMMAND:**
```bash
git checkout -b feat/schema-ticket-reopen
git add components/schemas/ticket/ReopenTicketRequest.yaml
git add paths/tickets/reopen.yaml
git add openapi.yaml
git commit -m "feat(schemas): add ticket reopen endpoint"
git push origin feat/schema-ticket-reopen
```

**OUTPUT:**
```
[feat/schema-ticket-reopen a3f9c12] feat(schemas): add ticket reopen endpoint
 3 files changed, 67 insertions(+)
 create mode 100644 components/schemas/ticket/ReopenTicketRequest.yaml
 create mode 100644 paths/tickets/reopen.yaml
```

---

#### BƯỚC 6: Tạo Pull Request

**COMMAND:**
```bash
gh pr create \
  --base develop \
  --title "feat(schemas): add ticket reopen endpoint" \
  --body "Adds endpoint for reopening closed tickets"
```

**OUTPUT:**
```
Creating pull request for feat/schema-ticket-reopen into develop in Dinh-Nhan/CI-CD

https://github.com/Dinh-Nhan/CI-CD/pull/42
```

---

#### BƯỚC 7: CI/CD Validation (GitHub Actions)

**GitHub Actions Output:**
```
✅ Validate OpenAPI Specification
  ✅ Checkout repository
  ✅ Setup NodeJS
  ✅ Install dependencies
  ✅ Run Spectral Lint
  ✅ Run Redocly Validation

✅ Check API Differences
  ✅ Checkout repository
  ✅ Install oasdiff
  ✅ Check changelog changes

     ### What's New
     - POST /v1/users/{user_id}/tickets/{id}/reopen
```

---

#### BƯỚC 8: Merge & Deploy

**COMMAND:**
```bash
# Sau khi PR được approve
gh pr merge 42 --squash
```

**GitHub Actions Output (deploy.yaml):**
```
✅ Deploy API Documentation
  ✅ Bundle OpenAPI Specification
  ✅ Build API Documentation
  ✅ Deploy to GitHub Pages

  Deployed to: https://dinh-nhan.github.io/CI-CD/

✅ Notify Slack
  Message sent to #api-dev-log
```

**Slack Notification:**
```
✅ Deploy — Passed

Repo:     Dinh-Nhan/CI-CD
Branch:   `develop`
Author:   dinhnhan
Commit:   `a3f9c12`

Files changed:
• components/schemas/ticket/ReopenTicketRequest.yaml
• paths/tickets/reopen.yaml
• openapi.yaml

[Xem CI Run]
```

---

### 6.2 Ví Dụ 2: Các Lỗi Phổ Biến (Đường Thất Bại)

#### KỊCH BẢN
Developer tạo endpoint với nhiều vi phạm

---

#### LỖI 1: Inline Schema

**FILE:** `paths/tickets/feedback.yaml` (SAI)
```yaml
post:
  operationId: submitFeedback
  requestBody:
    content:
      application/json:
        schema:
          type: object  # ❌ INLINE SCHEMA
          properties:
            rating:
              type: integer
            comment:
              type: string
```

**ERROR OUTPUT:**
```
================================================
🔍 Step 1: Checking paths for inline schemas...
================================================

Checking paths/tickets/feedback.yaml...
  ❌ INLINE SCHEMA FOUND:
     - Found inline schema with type: object at post.requestBody.content.application/json.schema

❌ Inline schema check failed
Error: Process completed with exit code 1.
```

**CÁCH SỬA:**
```bash
# Bước 1: Tạo file schema
cat > components/schemas/ticket/SubmitFeedbackRequest.yaml << 'EOF'
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
EOF

# Bước 2: Cập nhật file path
```

**FILE:** `paths/tickets/feedback.yaml` (ĐÃ SỬA)
```yaml
post:
  operationId: submitFeedback
  requestBody:
    content:
      application/json:
        schema:
          $ref: "../../components/schemas/ticket/SubmitFeedbackRequest.yaml"
```

---

#### LỖI 2: Format operationId Sai

**FILE:** `paths/tickets/feedback.yaml` (SAI)
```yaml
post:
  operationId: submit_feedback  # ❌ snake_case
```

**ERROR OUTPUT:**
```
/home/runner/work/CI-CD/CI-CD/paths/tickets/feedback.yaml
  5:17  error  operation-id-verb-noun  operationId "submit_feedback" sai format. Phải dùng camelCase — ví dụ: listUsers, createOrder, reopenTicket.  post.operationId

✖ 1 problem (1 error, 0 warnings, 0 infos, 0 hints)
```

**CÁCH SỬA:**
```yaml
post:
  operationId: submitFeedback  # ✅ camelCase
```

---

#### LỖI 3: Thiếu 401/403 Responses

**FILE:** `paths/tickets/feedback.yaml` (SAI)
```yaml
post:
  security:
    - bearerAuth: []
  responses:
    "200":
      description: Success
    # ❌ Missing 401, 403
```

**ERROR OUTPUT:**
```
/home/runner/work/CI-CD/CI-CD/paths/tickets/feedback.yaml
  10:3  error  private-endpoint-must-have-401-403  Endpoint private phải có response 401 (Unauthorized)  post
  10:3  error  private-endpoint-must-have-401-403  Endpoint private phải có response 403 (Forbidden)  post

✖ 2 problems (2 errors, 0 warnings, 0 infos, 0 hints)
```

**FIX:**
```yaml
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
    "500":
      $ref: "../../components/responses/InternalError.yaml"
```

---

#### MISTAKE 4: Missing readOnly on Server Fields

**FILE:** `components/schemas/ticket/FeedbackDetail.yaml` (WRONG)
```yaml
type: object
properties:
  id:
    type: integer
    # ❌ Missing readOnly: true
  created_at:
    type: string
    format: date-time
    # ❌ Missing readOnly: true
  rating:
    type: integer
```

**ERROR OUTPUT:**
```
/home/runner/work/CI-CD/CI-CD/components/schemas/ticket/FeedbackDetail.yaml
  4:3   error  schema-server-fields-must-be-readonly  Trường "id" phải có readOnly: true  properties.id
  7:3   error  schema-server-fields-must-be-readonly  Trường "created_at" phải có readOnly: true  properties.created_at

✖ 2 problems (2 errors, 0 warnings, 0 infos, 0 hints)
```

**FIX:**
```yaml
type: object
properties:
  id:
    type: integer
    readOnly: true  # ✅
  created_at:
    type: string
    format: date-time
    readOnly: true  # ✅
  rating:
    type: integer
```

---

#### MISTAKE 5: Invalid $ref Path

**FILE:** `paths/tickets/feedback.yaml` (WRONG)
```yaml
post:
  requestBody:
    content:
      application/json:
        schema:
          $ref: "../../components/schemas/FeedbackRequest.yaml"
          # ❌ Wrong path (missing /ticket/ subdirectory)
```

**ERROR OUTPUT:**
```
validating /home/runner/work/CI-CD/CI-CD/openapi.yaml...

[1] paths/tickets/feedback.yaml:10:11

Referenced schema not found: ../../components/schemas/FeedbackRequest.yaml

Error was generated by the spec rule.

❌ Validation failed with 1 error.
```

**FIX:**
```yaml
post:
  requestBody:
    content:
      application/json:
        schema:
          $ref: "../../components/schemas/ticket/SubmitFeedbackRequest.yaml"
          # ✅ Correct path
```

---

### 6.3 Example 3: Response Schema with Nested Objects

#### SCENARIO
Create response schema with nested user information

---

#### STEP 1: Create Common Schema (Reusable)

**FILE:** `components/schemas/common/UserInfo.yaml`
```yaml
type: object
properties:
  id:
    type: integer
    readOnly: true
    example: 123
  name:
    type: string
    example: "Nguyễn Văn A"
  email:
    type: string
    format: email
    example: "user@example.com"
  avatar_url:
    type: string
    format: uri
    example: "https://cdn.example.com/avatars/123.jpg"
```

---

#### STEP 2: Create Ticket Response Schema

**FILE:** `components/schemas/ticket/TicketDetailResponse.yaml`
```yaml
type: object
properties:
  id:
    type: integer
    readOnly: true
    example: 456
  code:
    type: string
    readOnly: true
    description: Mã ticket hiển thị
    example: "TK-20240601-0001"
  title:
    type: string
    example: "Không truy cập được Hosting"
  description:
    type: string
    example: "Tôi không thể đăng nhập vào tài khoản của mình."
  status:
    type: string
    enum:
      - CREATED
      - IN_PROGRESS
      - PENDING
      - CLOSED
    example: "IN_PROGRESS"
  created_at:
    type: string
    format: date-time
    readOnly: true
    example: "2024-06-01T14:30:00Z"
  updated_at:
    type: string
    format: date-time
    readOnly: true
    example: "2024-06-01T15:45:00Z"
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

**EXPLANATION:**
- Reuses `UserInfo.yaml` for both `creator` and `assignee`
- `assignee` extends `UserInfo` with additional `department` field using `allOf`
- All server-generated fields have `readOnly: true`
- Enum fields have clear values

---

#### STEP 3: Use in Path

**FILE:** `paths/tickets/detail.yaml`
```yaml
get:
  summary: Lấy chi tiết ticket
  operationId: getTicketDetail
  description: Lấy thông tin chi tiết của một ticket
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
  responses:
    "200":
      description: Lấy chi tiết ticket thành công
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

**EXPLANATION:**
- Uses `allOf` to combine `StandardSuccess` wrapper with specific data
- Includes 404 (resource not found) since path has `{id}` parameter
- All error responses properly referenced

---

#### STEP 4: Validate

**COMMAND:**
```bash
npm run lint:api && npm run validate:api
```

**OUTPUT:**
```
================================================
🔍 Step 1: Checking paths for inline schemas...
================================================

✅ No inline schemas in paths/

validating /home/user/CI-CD/openapi.yaml...

/home/user/CI-CD/openapi.yaml: validated in 168ms

Woohoo! Your OpenAPI definition is valid. 🎉
```

---


## 7. MA TRẬN TROUBLESHOOTING

### 7.1 Bảng Tham Chiếu Nhanh

| Triệu chứng                                   | Nguyên nhân gốc              | Cách sửa                                                     | Xác minh                |
| --------------------------------------------- | ---------------------------- | ------------------------------------------------------------ | ----------------------- |
| `❌ Inline schema check failed`                | Schema định nghĩa trong `paths/`   | Chuyển sang `components/schemas/`, dùng `$ref`                    | `npm run lint:api`      |
| `error operation-id-verb-noun`                | operationId không phải camelCase    | Đổi sang format `verbNoun` (vd: `createTicket`)           | `npm run lint:spectral` |
| `error schema-server-fields-must-be-readonly` | Thiếu `readOnly: true`     | Thêm `readOnly: true` vào `id`, `created_at`, `updated_at`     | `npm run lint:spectral` |
| `error private-endpoint-must-have-401-403`    | Thiếu auth error responses | Thêm 401 và 403 responses                                    | `npm run lint:spectral` |
| `Referenced schema not found`                 | Đường dẫn `$ref` không hợp lệ          | Sửa đường dẫn hoặc tạo file thiếu                              | `npm run validate:api`  |
| `Circular reference detected`                 | Schema A → B → A             | Phá vòng lặp bằng ID reference                                | `npm run validate:api`  |
| `npm ci` thất bại                                | Lockfile không đồng bộ         | `rm -rf node_modules package-lock.json && npm install`       | `npm ci`                |
| GitHub Actions checkout thất bại                 | Thiếu permissions          | Thêm `permissions: contents: read` vào workflow                | Re-run workflow         |
| Slack notification thất bại                      | Token/channel không hợp lệ        | Xác minh GitHub Secrets: `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID` | Re-run workflow         |
| `Property not expected here`                  | Lỗi chính tả trong OpenAPI keyword      | Sửa case (vd: `requestBody` không phải `requestbody`)             | `npm run validate:api`  |

---

### 7.2 Tham Chiếu Error Code

#### Spectral Error Codes

| Rule Code                               | Severity | Mô tả                        | Cách sửa                      |
| --------------------------------------- | -------- | ---------------------------------- | ------------------------ |
| `operation-id-verb-noun`                | error    | operationId phải là camelCase      | Dùng format `verbNoun`    |
| `schema-server-fields-must-be-readonly` | error    | Server fields phải là read-only    | Thêm `readOnly: true`     |
| `private-endpoint-must-have-401-403`    | error    | Private endpoints cần auth errors | Thêm 401, 403 responses   |
| `operation-must-have-500`               | warning  | Thiếu 500 response               | Thêm 500 response         |
| `operation-with-id-must-have-404`       | warning  | Path có `{id}` cần 404         | Thêm 404 response         |
| `operation-must-have-summary`           | warning  | Thiếu summary                    | Thêm trường `summary`      |
| `operation-must-have-description`       | warning  | Thiếu description                | Thêm trường `description`  |
| `path-params-must-be-required`          | error    | Path param không có required            | Thêm `required: true`     |
| `path-kebab-case`                       | warning  | Path không phải kebab-case                | Dùng format `/kebab-case` |

---

### 7.3 Command Cheat Sheet

#### Local Development
```bash
# Full validation (khuyến nghị)
npm run lint:api

# Kiểm tra riêng lẻ
npm run lint:spectral          # Chỉ Spectral
npm run validate:api           # Chỉ Redocly
python3 scripts/check-inline-schema.py  # Chỉ kiểm tra inline schema

# Build & bundle
npm run bundle:api             # Tạo openapi-bundled.yaml
npm run build:docs             # Tạo api-docs.html

# Tìm kiếm references
grep -r "SchemaName" --include="*.yaml" .
grep -r "operationId" --include="*.yaml" paths/

# Tìm tất cả inline schemas thủ công
grep -A 5 "type: object" paths/**/*.yaml
grep -A 5 "type: array" paths/**/*.yaml
```

#### Git Operations
```bash
# Quản lý branch
git checkout develop
git pull origin develop
git checkout -b feat/schema-new-feature

# Commit
git add <files>
git commit -m "feat(schemas): description"
git push origin feat/schema-new-feature

# Quản lý PR (GitHub CLI)
gh pr create --base develop --title "..." --body "..."
gh pr view
gh pr merge <number> --squash

# Hoàn tác commit cuối (giữ thay đổi)
git reset --soft HEAD~1

# Hủy thay đổi local
git checkout -- <file>
git restore <file>
```

#### Debugging
```bash
# Kiểm tra file tồn tại
ls -la components/schemas/ticket/TicketDetail.yaml

# Validate cú pháp YAML
python3 -c "import yaml; yaml.safe_load(open('openapi.yaml'))"

# Kiểm tra circular refs thủ công
grep -r "\$ref.*TicketDetail" --include="*.yaml" .

# Xem GitHub Actions logs
gh run list
gh run view <run-id>
gh run view <run-id> --log

# Chạy lại workflow thất bại
gh run rerun <run-id>
```

---

### 7.4 Quy Ước Đặt Tên File

| Loại File       | Vị trí                       | Quy tắc đặt tên                         | Ví dụ                     |
| --------------- | ------------------------------ | ------------------------------ | --------------------------- |
| Request Schema  | `components/schemas/<domain>/` | PascalCase + hậu tố `Request`  | `CreateTicketRequest.yaml`  |
| Response Schema | `components/schemas/<domain>/` | PascalCase + hậu tố `Response` | `TicketDetailResponse.yaml` |
| Entity Schema   | `components/schemas/<domain>/` | PascalCase (tên entity)       | `TicketDetail.yaml`         |
| Common Schema   | `components/schemas/common/`   | PascalCase                     | `UserInfo.yaml`             |
| Core Schema     | `components/schemas/core/`     | PascalCase                     | `StandardError.yaml`        |
| Path File       | `paths/<domain>/`              | kebab-case                     | `create-ticket.yaml`        |
| Response File   | `components/responses/`        | PascalCase                     | `Unauthorized.yaml`         |
| Parameter File  | `components/parameters/`       | PascalCase                     | `PaginationParams.yaml`     |

---

### 7.5 Hướng Dẫn Response Status Code

| Status Code | Khi nào dùng                          | Bắt buộc cho                             |
| ----------- | ------------------------------------ | ---------------------------------------- |
| **200**     | GET, PUT, PATCH, DELETE thành công   | Tất cả read/update operations               |
| **201**     | POST thành công (resource được tạo)   | POST operations (khuyến nghị)            |
| **204**     | DELETE thành công (không có content)       | DELETE operations (tùy chọn)             |
| **400**     | Bad request (cú pháp sai)       | Operations với input phức tạp            |
| **401**     | Unauthorized (token không hợp lệ/thiếu) | **Tất cả private endpoints**                |
| **403**     | Forbidden (không đủ quyền) | **Tất cả private endpoints**                |
| **404**     | Resource không tìm thấy                   | **Tất cả operations có parameter `{id}`** |
| **422**     | Validation error (lỗi semantic)    | Operations có validation rules         |
| **500**     | Internal server error                | **Tất cả operations** (warning nếu thiếu)  |

---

### 7.6 Schema Design Patterns

#### Pattern 1: Request/Response Pair
```yaml
# Request (client → server)
# components/schemas/ticket/CreateTicketRequest.yaml
type: object
required:
  - title
  - description
properties:
  title:
    type: string
  description:
    type: string
  # No readOnly fields in requests

# Response (server → client)
# components/schemas/ticket/CreateTicketResponse.yaml
type: object
properties:
  id:
    type: integer
    readOnly: true  # Server-generated
  title:
    type: string
  description:
    type: string
  created_at:
    type: string
    format: date-time
    readOnly: true  # Server-generated
```

#### Pattern 2: Reusable Common Schemas
```yaml
# components/schemas/common/TimestampFields.yaml
type: object
properties:
  created_at:
    type: string
    format: date-time
    readOnly: true
  updated_at:
    type: string
    format: date-time
    readOnly: true

# Usage in other schemas
# components/schemas/ticket/TicketDetail.yaml
allOf:
  - type: object
    properties:
      id:
        type: integer
        readOnly: true
      title:
        type: string
  - $ref: "../common/TimestampFields.yaml"
```

#### Pattern 3: Enum with Description
```yaml
# ✅ GOOD
status:
  type: string
  description: |
    Trạng thái của ticket:
    - CREATED: Ticket mới tạo, chưa được xử lý
    - IN_PROGRESS: Đang được xử lý bởi support team
    - PENDING: Chờ phản hồi từ khách hàng
    - CLOSED: Đã giải quyết xong
  enum:
    - CREATED
    - IN_PROGRESS
    - PENDING
    - CLOSED
  example: "IN_PROGRESS"
```

#### Pattern 4: Pagination Response
```yaml
# components/schemas/core/PaginatedResponse.yaml
type: object
properties:
  data:
    type: array
    items:
      type: object  # Will be overridden by allOf
  pagination:
    type: object
    properties:
      current_page:
        type: integer
        example: 1
      per_page:
        type: integer
        example: 20
      total:
        type: integer
        example: 150
      total_pages:
        type: integer
        example: 8

# Usage
# paths/tickets/list.yaml
responses:
  "200":
    content:
      application/json:
        schema:
          allOf:
            - $ref: "../../components/schemas/core/PaginatedResponse.yaml"
            - type: object
              properties:
                data:
                  type: array
                  items:
                    $ref: "../../components/schemas/ticket/TicketSummary.yaml"
```

---

### 7.7 CI/CD Performance Optimization

#### Cache Strategy
```yaml
# Optimize npm install with cache
- name: Setup NodeJS
  uses: actions/setup-node@v4
  with:
    node-version: 20
    cache: npm
    cache-dependency-path: package-lock.json
```

**Impact:** Reduces install time from ~30s to ~5s on cache hit

#### Concurrency Control
```yaml
# Prevent multiple runs on same branch
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

**Impact:** Saves CI minutes by canceling outdated runs

#### Conditional Execution
```yaml
# Only run on relevant file changes
on:
  push:
    paths:
      - "components/**"
      - "paths/**"
      - "openapi.yaml"
```

**Impact:** Avoids unnecessary runs on documentation-only changes

---

### 7.8 Security Best Practices

#### 1. Never Commit Secrets
```bash
# ❌ BAD
servers:
  - url: https://api.example.com
    variables:
      apiKey:
        default: "sk_live_abc123xyz"  # Hardcoded secret

# ✅ GOOD
servers:
  - url: https://api.example.com
    description: Production (requires API key in header)

components:
  securitySchemes:
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
```

#### 2. Use GitHub Secrets for CI/CD
```yaml
# Access secrets in workflows
env:
  SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
  SLACK_CHANNEL_ID: ${{ secrets.SLACK_CHANNEL_ID }}
```

#### 3. Minimal Permissions
```yaml
# Grant only necessary permissions
permissions:
  contents: read        # Read repository
  pull-requests: write  # Comment on PRs
  pages: write          # Deploy to GitHub Pages
  id-token: write       # OIDC token for Pages
```

#### 4. Validate Input in Schemas
```yaml
# Use constraints to prevent abuse
properties:
  email:
    type: string
    format: email
    maxLength: 255
  description:
    type: string
    maxLength: 4000
  files:
    type: array
    maxItems: 3
    items:
      type: string
      format: binary
```

---

### 7.9 Monitoring & Observability

#### GitHub Actions Metrics
```bash
# View workflow runs
gh run list --workflow=ci.yaml --limit 10

# View success rate
gh run list --workflow=ci.yaml --json conclusion --jq '[.[] | .conclusion] | group_by(.) | map({conclusion: .[0], count: length})'

# Average run time
gh run list --workflow=ci.yaml --json createdAt,updatedAt --jq '[.[] | ((.updatedAt | fromdateiso8601) - (.createdAt | fromdateiso8601))] | add / length'
```

#### Slack Notification Tracking
- Monitor `#api-dev-log` channel for deployment frequency
- Track failure patterns (time of day, specific files)
- Identify repeat offenders (developers needing training)

#### API Documentation Analytics
- GitHub Pages provides basic analytics
- Track documentation views in GitHub Insights
- Monitor 404s for broken links

---

### 7.10 Rollback Procedures

#### Scenario 1: Bad Merge to Main

**COMMAND:**
```bash
# Option A: Revert commit
git revert <commit-hash>
git push origin main

# Option B: Reset to previous commit (destructive)
git reset --hard <previous-commit-hash>
git push origin main --force
```

**EXPLANATION:**
- `revert` creates new commit that undoes changes (safe)
- `reset --force` rewrites history (use only if no one pulled)

---

#### Scenario 2: Broken GitHub Pages Deployment

**COMMAND:**
```bash
# Re-run deployment from last good commit
gh workflow run deploy.yaml --ref <last-good-commit>

# Or manually trigger from GitHub UI
# Actions → Deploy API Documentation → Run workflow
```

---

#### Scenario 3: Invalid OpenAPI Spec in Production

**IMMEDIATE ACTION:**
```bash
# 1. Identify last good commit
git log --oneline openapi.yaml

# 2. Revert to last good version
git checkout <last-good-commit> -- openapi.yaml
git commit -m "fix: revert openapi.yaml to last good version"
git push origin main

# 3. Verify locally
npm run lint:api && npm run validate:api

# 4. Wait for auto-deployment
```

---

## 8. APPENDIX

### 8.1 Tool Documentation Links

| Tool           | Documentation                           | Version |
| -------------- | --------------------------------------- | ------- |
| Spectral       | https://docs.stoplight.io/docs/spectral | 6.15.1  |
| Redocly        | https://redocly.com/docs/cli/           | 2.30.4  |
| oasdiff        | https://github.com/oasdiff/oasdiff      | 1.10.27 |
| OpenAPI 3.1    | https://spec.openapis.org/oas/v3.1.0    | 3.1.0   |
| GitHub Actions | https://docs.github.com/en/actions      | -       |

---

### 8.2 Custom Spectral Rules Reference

#### Rule: `operation-id-verb-noun`
```javascript
{
  message: 'operationId "{{value}}" sai format. Phải dùng camelCase — ví dụ: listUsers, createOrder, reopenTicket.',
  severity: 'error',
  given: '$.paths[*][*].operationId',
  then: {
    function: pattern,
    functionOptions: { match: '^[a-z][a-zA-Z0-9]+$' }
  }
}
```

**Valid Examples:**
- `createTicket`
- `listUsers`
- `getTicketDetail`
- `updateUserProfile`
- `deleteComment`

**Invalid Examples:**
- `create_ticket` (snake_case)
- `CreateTicket` (PascalCase)
- `create-ticket` (kebab-case)
- `CREATETICKET` (UPPERCASE)

---

#### Rule: `schema-server-fields-must-be-readonly`
```javascript
{
  message: 'Trường "{{property}}" phải có readOnly: true',
  severity: 'error',
  given: [
    '$.components.schemas[*].properties.id',
    '$.components.schemas[*].properties.created_at',
    '$.components.schemas[*].properties.updated_at',
  ],
  then: { field: 'readOnly', function: truthy }
}
```

**Applies to:**
- `id` (primary key)
- `created_at` (creation timestamp)
- `updated_at` (modification timestamp)

---

#### Rule: `private-endpoint-must-have-401-403`
```javascript
{
  message: '{{error}}',
  severity: 'error',
  given: '$.paths[*][*]',
  then: { function: privateEndpoint }
}
```

**Custom Function Logic:**
```javascript
// Checks if endpoint has security requirement
const isPublic = Array.isArray(operation.security) && operation.security.length === 0;

if (isPublic) return; // Skip public endpoints

// Validate 401 and 403 responses exist
if (!operation.responses?.['401']) {
  errors.push({ message: 'Endpoint private phải có response 401 (Unauthorized)' });
}
if (!operation.responses?.['403']) {
  errors.push({ message: 'Endpoint private phải có response 403 (Forbidden)' });
}
```

---

### 8.3 Project Structure Reference

```
CI-CD/
├── .github/
│   └── workflows/
│       ├── ci.yaml           # Main CI orchestrator
│       ├── validate.yaml     # Spectral + Redocly validation
│       ├── diff.yaml         # API breaking changes detection
│       └── deploy.yaml       # Build docs + GitHub Pages deploy
├── components/
│   ├── parameters/           # Reusable parameters
│   │   ├── PaginationParams.yaml
│   │   ├── TicketId.yaml
│   │   └── UserId.yaml
│   ├── responses/            # Reusable responses
│   │   ├── Unauthorized.yaml
│   │   ├── Forbidden.yaml
│   │   ├── NotFound.yaml
│   │   ├── ValidationError.yaml
│   │   └── InternalError.yaml
│   ├── schemas/
│   │   ├── common/           # Cross-domain schemas
│   │   │   ├── UserInfo.yaml
│   │   │   ├── TimestampFields.yaml
│   │   │   └── FileAttachment.yaml
│   │   ├── core/             # Framework schemas
│   │   │   ├── StandardError.yaml
│   │   │   ├── StandardSuccess.yaml
│   │   │   └── Pagination.yaml
│   │   └── ticket/           # Domain-specific schemas
│   │       ├── CreateTicketRequest.yaml
│   │       ├── TicketDetail.yaml
│   │       └── Conversation.yaml
│   └── securitySchemes/
│       └── bearerAuth.yaml
├── paths/
│   ├── tickets/
│   │   ├── create.yaml
│   │   ├── detail.yaml
│   │   ├── close.yaml
│   │   └── reopen.yaml
│   └── departments/
│       └── list.yaml
├── scripts/
│   ├── lint-all.sh           # Main lint orchestrator
│   └── check-inline-schema.py # Python inline schema checker
├── functions/
│   └── private-must-have-401-403.js # Custom Spectral function
├── docs/
│   ├── CICD-RUNBOOK.md       # This document
│   ├── ci-flow.md
│   └── setup-cicd.md
├── .spectral.js              # Spectral configuration
├── .redocly.yaml             # Redocly configuration
├── openapi.yaml              # Main OpenAPI entry point
├── openapi-bundled.yaml      # Generated bundle (gitignored)
├── api-docs.html             # Generated docs (gitignored)
└── package.json              # Node.js dependencies
```

---

### 8.4 Glossary

| Term                | Definition                                                      |
| ------------------- | --------------------------------------------------------------- |
| **OpenAPI**         | Specification for describing REST APIs (formerly Swagger)       |
| **Spectral**        | Linter for OpenAPI/JSON/YAML files with custom rules            |
| **Redocly**         | OpenAPI tooling for validation, bundling, and documentation     |
| **oasdiff**         | Tool for detecting breaking changes between OpenAPI specs       |
| **$ref**            | JSON Reference - pointer to another part of the document        |
| **Inline Schema**   | Schema defined directly in place (anti-pattern in this project) |
| **operationId**     | Unique identifier for an API operation                          |
| **readOnly**        | Property that can only be sent by server, not by client         |
| **allOf**           | JSON Schema keyword for combining multiple schemas              |
| **oneOf**           | JSON Schema keyword for exclusive choice between schemas        |
| **Bundle**          | Single-file OpenAPI spec with all $ref resolved                 |
| **Breaking Change** | API modification that breaks existing clients                   |
| **CI/CD**           | Continuous Integration / Continuous Deployment                  |
| **GitHub Actions**  | GitHub's built-in CI/CD platform                                |
| **GitHub Pages**    | Static site hosting from GitHub repository                      |

---

### 8.5 Contact & Support

| Issue Type              | Contact                                |
| ----------------------- | -------------------------------------- |
| CI/CD Pipeline Issues   | DevOps Team / #devops-support          |
| OpenAPI Spec Questions  | API Team / #api-design                 |
| Spectral Rule Changes   | Architecture Team / #architecture      |
| GitHub Actions Failures | Check logs first, then #devops-support |
| Documentation Bugs      | Create issue in repository             |

---

### 8.6 Changelog

| Date       | Version | Changes                          |
| ---------- | ------- | -------------------------------- |
| 2026-05-19 | 1.0.0   | Initial production-ready runbook |

---

**END OF RUNBOOK**

