# OASDiff Guide for CI/CD OpenAPI Governance

## 📌 OASDiff là gì?

OASDiff là tool dùng để so sánh hai OpenAPI specification.

Repository chính thức:
https://github.com/oasdiff/oasdiff

Nó thường được dùng trong CI/CD để:

* kiểm tra breaking changes
* theo dõi lịch sử thay đổi API
* generate changelog
* review API contract trước khi merge PR

---

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
oasdiff breaking old/openapi.yaml new/openapi.yaml
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
oasdiff changelog old/openapi.yaml new/openapi.yaml
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
oasdiff diff old/openapi.yaml new/openapi.yaml
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
oasdiff summary old/openapi.yaml new/openapi.yaml
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
oasdiff changelog old/openapi.yaml new/openapi.yaml
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
  old/openapi.yaml new/openapi.yaml
```

---

## Ignore examples

```bash
oasdiff breaking \
  --exclude-elements examples \
  old/openapi.yaml new/openapi.yaml
```

---

## Ignore descriptions

```bash
oasdiff breaking \
  --exclude-elements description \
  old/openapi.yaml new/openapi.yaml
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

Hiện tại workflow phù hợp nhất cho project là:

```bash
redocly lint
spectral lint
oasdiff changelog
```
