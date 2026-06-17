# CI/CD — Pipeline Chi Tiết

---

## 1. Điều Kiện Trigger

### Pull Request → `main` hoặc `develop`

```yaml
on:
  pull_request:
    branches: [main, develop]
```

Chạy:
1. `validate.yaml` — Spectral + Redocly validation
2. `diff.yaml` — Phát hiện API breaking changes

### Push → `main` hoặc `develop`

```yaml
on:
  push:
    branches: [main, develop]
    paths:
      - "dist/**"
      - "scripts/**"
      - "package.json"
```

Chạy:
1. `deploy.yaml` — Build docs + deploy tới GitHub Pages
2. `notify` — Gửi thông báo Slack

---

## 2. Validation Workflow (validate.yaml)

### Bước 1: Checkout Repository

```yaml
- name: Checkout repository
  uses: actions/checkout@v4
```

Clone repository vào workspace của runner.

---

### Bước 2: Setup Node.js

```yaml
- name: Setup NodeJS
  uses: actions/setup-node@v5
  with:
    node-version: 24
    cache: npm
    cache-dependency-path: package-lock.json
```

Cache `node_modules` theo hash của `package-lock.json`. Cache hit giảm thời gian từ ~30s xuống ~5s.

---

### Bước 3: Cài Đặt Dependencies

```yaml
- name: Install dependencies
  run: npm ci
```

`npm ci` xóa `node_modules` và cài từ lockfile → reproducible builds.

**Lỗi:**
```
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json are in sync.
```

**Fix:**
```bash
npm install
git add package-lock.json
git commit -m "chore: update package-lock.json"
git push
```

---

### Bước 4: Chạy Spectral line
```yaml
- name: Run Spectral Rule
  run: npm run lint:spectral
```

### Bước 5: Chạy Redocly Validation

```yaml
- name: Run Redocly Validation
  run: npm run validate:api
```

**Thành công:**
```
Woohoo! Your OpenAPI definition is valid. 🎉
```

**Thất bại:**
```
Referenced schema not found: #/components/schemas/TicketResponse
❌ Validation failed with 1 error.
```

**Fix:**
```bash
ls -la components/schemas/ticket/TicketResponse.yaml
# Nếu thiếu → tạo file
# Nếu có → kiểm tra lại đường dẫn $ref
```

---

## 3. Diff Workflow (diff.yaml)

### Bước 1: Checkout 2 Nhánh

```yaml
- uses: actions/checkout@v5
  with: { path: new }

- uses: actions/checkout@v5
  with: { ref: main, path: old }
```

Checkout PR branch vào `new/`, main branch vào `old/` để so sánh song song.

---

### Bước 2: Cài Đặt oasdiff

```yaml
- name: Install oasdiff
  env:
    VERSION: 1.15.3
  run: |
    curl -fsSL https://github.com/oasdiff/oasdiff/releases/download/v${VERSION}/oasdiff_${VERSION}_linux_amd64.tar.gz | tar -xz
    sudo mv oasdiff /usr/local/bin/
```

---

### Bước 3: Kiểm Tra Changelog

```yaml
- name: Check API changelog
  run: oasdiff changelog old/dist/openapi-bundled.yaml new/dist/openapi-bundled.yaml || true
```

**Kết quả mẫu khi có thay đổi:**
```
### What's New
- POST /v1/users/{user_id}/tickets/{id}/reopen

### What's Modified
- POST /v1/users/{user_id}/tickets
  - Request body property 'files' max items increased from 3 to 5

### Breaking Changes
None
```

`|| true` ngăn fail — bước này chỉ mang tính thông tin.

# 📊 Các mode chính của OASDiff

| Command             | Mục đích                   | Block CI | Độ strict  |
| ------------------- | -------------------------- | -------- | ---------- |
| `oasdiff breaking`  | Kiểm tra breaking changes  | ✅ Có     | Rất cao    |
| `oasdiff changelog` | Hiển thị thay đổi API      | ❌ Không  | Trung bình |
| `oasdiff diff`      | Diff chi tiết toàn bộ spec | ❌ Không  | Verbose    |
| `oasdiff summary`   | Tóm tắt thay đổi           | ❌ Không  | Nhẹ        |

---

# 1️⃣ `oasdiff breaking`

## 📌 Mục đích

Kiểm tra các thay đổi có thể làm client cũ bị lỗi.

Đây là mode strict nhất.

---

## 🔧 Ví dụ

```bash
oasdiff breaking old/dist/openapi-bundled.yaml new/dist/openapi-bundled.yaml
```

---

## ❌ Sẽ FAIL nếu có:

| Thay đổi                  | Có bị coi là breaking? |
| ------------------------- | ---------------------- |
| Xóa endpoint              | ✅                      |
| Đổi request schema        | ✅                      |
| Đổi response schema       | ✅                      |
| Field optional → required | ✅                      |
| Đổi enum                  | ✅                      |
| Đổi authentication        | ✅                      |
| Đổi response body         | ✅                      |

---

## 📌 Ví dụ breaking

### OLD

```yaml
responses:
  "200":
    description: OK
```

### NEW

```yaml
responses:
  "200":
    content:
      application/json:
        schema:
          type: object
```

---

## 📌 Output

```txt
Error: response body changed
```

và:

```txt
exit code 1
```

=> CI fail.

---

## 📌 Khi nào nên dùng?

### ✅ Nên dùng khi:

* API production stable
* Public API
* Có nhiều client đang sử dụng
* Muốn đảm bảo backward compatibility

---

## ⚠️ Không nên dùng khi:

* API còn đang phát triển mạnh
* Governance chưa ổn định
* Error response thường xuyên thay đổi

---

# 2️⃣ `oasdiff changelog`

## 📌 Mục đích

Hiển thị tất cả thay đổi giữa hai version API.

---

## 🔧 Ví dụ

```bash
oasdiff changelog old/dist/openapi-bundled.yaml new/dist/openapi-bundled.yaml
```

---

## 📌 Nó sẽ report:

* endpoint mới
* schema thay đổi
* examples thay đổi
* descriptions thay đổi
* response thay đổi

---

## 📌 Nhưng KHÔNG fail CI

Thường trả:

```txt
exit code 0
```

---

## 📌 Khi nào nên dùng?

### ✅ Rất phù hợp cho:

* Pull Request review
* API governance phase
* Team development
* Internal API

---

## 📌 Workflow phổ biến

```txt
Developer tạo PR
        ↓
OASDiff changelog
        ↓
Comment thay đổi vào PR
        ↓
Reviewer kiểm tra
```

---

# 3️⃣ `oasdiff diff`

## 📌 Mục đích

Hiển thị diff chi tiết nhất.

Giống như:

```txt
git diff cho OpenAPI
```

---

## 🔧 Ví dụ

```bash
oasdiff diff old/dist/openapi-bundled.yaml new/dist/openapi-bundled.yaml
```

---

## 📌 Output

Rất verbose.

Ví dụ:

```txt
response body type changed
schema property removed
enum updated
```

---

## 📌 Dùng khi:

* debug
* investigate issue
* audit API changes

---

# 4️⃣ `oasdiff summary`

## 📌 Mục đích

Hiển thị thống kê tổng quan.

---

## 🔧 Ví dụ

```bash
oasdiff summary old/dist/openapi-bundled.yaml new/dist/openapi-bundled.yaml
```

---

## 📌 Output ví dụ

```txt
Paths Added: 2
Paths Removed: 1
Breaking Changes: 3
```

---

# ⚠️ Một hiểu lầm phổ biến

## ❌ “breaking = sai”

Không đúng.

Ví dụ:

### OLD

```yaml
401:
  description: Unauthorized
```

### NEW

```yaml
401:
  content:
    application/json:
      schema:
        type: object
```

OASDiff sẽ coi là:

```txt
BREAKING CHANGE
```

vì response contract đã thay đổi.

---

## Nhưng thực tế:

* spec mới có thể đúng hơn
* API improved
* client vẫn chạy bình thường

---

# 📌 Vì sao CI bị block dù spec đúng?

Ví dụ:

```txt
response body changed from empty → object
```

Tool coi đây là breaking change.

---

## Đây là behavior đúng của OASDiff.

Nhưng:

```txt
breaking change ≠ bad change
```

---

# 📌 Khuyến nghị thực tế cho CI/CD

## 🚀 Phase 1 — Governance Setup

Khuyến nghị:

```bash
redocly lint
spectral lint
oasdiff changelog
```

### Vì:

* API còn thay đổi nhiều
* Team đang setup governance
* Tránh block PR không cần thiết

---

## 🚀 Phase 2 — Stable API

Khi API ổn định:

```bash
oasdiff breaking
```

để enforce backward compatibility.

---

# 📌 Workflow Production phổ biến

| Check                        | Block PR |
| ---------------------------- | -------- |
| OpenAPI syntax invalid       | ✅        |
| Broken `$ref`                | ✅        |
| Spectral governance fail     | ✅        |
| Response description changed | ❌        |
| Example changed              | ❌        |
| Error response changed       | ❌        |
| Success response breaking    | ✅        |

---

# 📌 Khuyến nghị cho project hiện tại

## ✅ Nên dùng

```bash
oasdiff changelog old/dist/openapi-bundled.yaml new/dist/openapi-bundled.yaml
```

---

## ❌ Chưa nên dùng

```bash
oasdiff breaking
```

vì API vẫn đang evolving.

---

# 📌 Một số option hữu ích

## Ignore response body

```bash
oasdiff breaking \
  --exclude-elements response-body \
  old/dist/openapi-bundled.yaml new/dist/openapi-bundled.yaml
```

---

## Ignore examples

```bash
oasdiff breaking \
  --exclude-elements examples \
  old/dist/openapi-bundled.yaml new/dist/openapi-bundled.yaml
```

---

## Ignore descriptions

```bash
oasdiff breaking \
  --exclude-elements description \
  old/dist/openapi-bundled.yaml new/dist/openapi-bundled.yaml
```

---

# 📌 Pipeline khuyến nghị

```txt
OpenAPI Spec
      ↓
Redocly Validate
      ↓
Spectral Governance
      ↓
OASDiff Changelog
      ↓
Build Docs
      ↓
Deploy
```

---

# ✅ Kết luận

| Command     | Nên dùng khi             |
| ----------- | ------------------------ |
| `breaking`  | API production/stable    |
| `changelog` | Development & governance |
| `diff`      | Debug                    |
| `summary`   | Quick review             |

---

## 4. Deploy Workflow (deploy.yaml)

### Bước 1: Build Documentation

```yaml
- name: Build API Documentation
  run: npm run build:docs
```

Tạo `public/api-docs.html` — single-page documentation với interactive API explorer.

---

### Bước 2: Chuẩn Bị GitHub Pages

```yaml
- name: Prepare Deployment Folder
  run: |
    mkdir -p _site
    cp public/api-docs.html _site/index.html
```

---

### Bước 3: Deploy lên GitHub Pages

```yaml
- name: Upload Pages Artifact
  uses: actions/upload-pages-artifact@v3
  with:
    path: _site

- name: Deploy to GitHub Pages
  uses: actions/deploy-pages@v4
```

Truy cập tại: `https://<username>.github.io/<repo>/`

---

### Bước 4: Thông Báo Slack

```yaml
- name: Gửi thông báo Slack
  run: |
    curl -X POST https://slack.com/api/chat.postMessage \
      -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{...}"
```

**Message mẫu:**
```
✅ Deploy — Passed

Repo:    Dinh-Nhan/CI-CD
Branch:  `main`
Author:  dinhnhan
Commit:  `a3f9c12`

Files changed:
• components/schemas/ticket/ReopenTicketRequest.yaml
• paths/tickets/reopen.yaml
```

**Lỗi 401 Unauthorized:**
```bash
# Kiểm tra GitHub Secrets đã set chưa
# Settings → Secrets and variables → Actions
# Cần: SLACK_BOT_TOKEN, SLACK_CHANNEL_ID
# Slack App → OAuth & Permissions → Scopes: chat:write, chat:write.public
```
