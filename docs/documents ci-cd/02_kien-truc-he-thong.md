# CI/CD — Kiến Trúc Hệ Thống

---

## 1. Cài Đặt & Cấu Trúc Hệ Thống

### 1.1 Cấu Trúc Repository

```
.
├── .github/
│   └── workflows/
│       ├── ci.yaml
│       ├── lint.yaml
│       ├── diff.yaml
│       └── deploy.yaml
├── .vscode/
│   └── settings.json
├── dist/
├── functions/
├── openapi/
│   ├── components/
│   ├── paths/
│   └── openapi.yaml
├── public/
├── scripts/
├── .spectral.yaml
├── redocly.yaml
└── package.json
```

### Vai Trò Các Thành Phần Chính

| Thành phần | Vai trò |
|---|---|
| `.github/workflows` | Chứa các workflow CI/CD của GitHub Actions |
| `scripts/` | Chứa script build ui swagger |
| `.spectral.yaml` | File cấu hình custom rule cho Spectral |
| `redocly.yaml` | File cấu hình rule cho Redocly|
| `functions/` | Chứa custom validation function |
| `package.json` | Quản lý dependency và npm scripts |
| `openapi/` | Thư mục chứa toàn bộ file yaml được AI sinh ra |
| `public/` | Nơi build ra file tài liệu để deploy |
| `dist` | Nơi chứ file bundle |

---

## 2. Kiến Trúc Pipeline

### 2.1 Tổng Quan Pipeline

```
┌─────────────────┐
│   MÁY LOCAL     │
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
│    ├─ validate.yaml (Spectral + Redocly)            │
│    └─ diff.yaml (Phát hiện Breaking Changes)        │
│                                                     │
│  Push → main/develop:                               │
│    ├─ deploy.yaml (Build Docs + GitHub Pages)       │
│    └─ notify (Thông báo Slack)                      │
└─────────────────────────────────────────────────────┘
```

### 2.2 Các Tầng Validation

| Tầng | Tool | Phạm vi | Chặn CI |
|---|---|---|---|
| **L1: Spectral Lint** | @stoplight/spectral-cli | Custom rules (operationId, readOnly, 401/403) | ✅ CÓ |
| **L2: Redocly Validate** | @redocly/cli | Tuân thủ OpenAPI 3.1 spec | ✅ CÓ |
| **L3: Breaking Changes** | oasdiff | So sánh API với nhánh main | ⚠️ CẢNH BÁO |

### 2.3 Phiên Bản Tools

```json
{
    "@redocly/cli": "^2.31.2",
    "@stoplight/spectral-cli": "^6.15.1",
    "swagger-ui-dist": "^5.11.0"
}
```

---

## 3. Luồng Hoạt Động

```
Developer
    │
    ├─ Viết schema
    ├─ Chạy Spectral lint local
    └─ Commit và Push
              │
              ▼
    GitHub Actions CI
    ├─ Naming convention check
    ├─ Spectral lint
    ├─ Redocly validate
    └─ Kiểm tra diff thay đổi API
              │
              ▼
    Slack Notification (#api-dev-log)
    └─ Thông báo thành công hoặc thất bại
```

### Mô Tả Quy Trình

1. Developer chỉnh sửa tài liệu OpenAPI (`openapi.yaml`, `components/`, `paths/`)
2. Trước khi push, developer chủ động chạy lint local bằng Spectral và Redocly
3. Sau khi hoàn tất: `git commit` → `git push` → tạo Pull Request
4. GitHub Actions tự động kích hoạt workflow trong `.github/workflows/`
5. Pipeline thực hiện: cài dependency → lint → validate → kiểm tra diff
6. Nếu phát hiện lỗi: pipeline fail, PR bị chặn merge, developer theo dõi và sửa lỗi trong tab Actions và push lên lại.
7. Nếu thành công: PR có thể merge, deploy tài liệu API, Slack gửi thông báo
