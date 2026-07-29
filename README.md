# API Converter

Công cụ tự động chuyển đổi tài liệu API (`.docx`, `.pdf`) sang OpenAPI 3.1 YAML. Claude AI enrich mỗi operation với `summary`/`operationId`/`description` tiếng Việt. Đi kèm FastAPI backend + Next.js frontend cho workflow quản lý module và review/duyệt trước khi export.

## 📚 Tài liệu

**Kiến trúc**
- [Kiến trúc Backend](docs/architecture/kien-truc-backend.md)
- [Kiến trúc Frontend](docs/architecture/kien-truc-frontend.md)
- [Đặc tả Use Case](docs/architecture/uc-detail.md)
- [Hướng dẫn đọc sơ đồ](docs/architecture/diagram-guide.md) — [Sequence](docs/architecture/diagrams/sequence/) · [Activity](docs/architecture/diagrams/activity/)

**Quy chuẩn & quy trình**
- [API Governance](docs/guidelines/api-governance.md)
- [Quy tắc Spectral](docs/guidelines/conventions/spectral.md)
- [Quy tắc Redocly](docs/guidelines/conventions/redocly.md)
- [Manual Test Checklist](docs/guidelines/manual-test-checklist.md)

**Triển khai & CI/CD**
- [CI/CD Runbook](docs/devops/cicd-runbook.md)
- [Luồng hoạt động CI](docs/devops/ci-flow.md)
- [Tool OAS-Diff](docs/devops/oas-diff.md)
- [Setup CI/CD](docs/devops/setup-cicd.md)
- [Setup Slack](docs/devops/setup-slack.md)
- [Setup môi trường local](docs/devops/setup-local-dev.md)
- [Tài liệu CI/CD chi tiết](docs/devops/documents-ci-cd/) (tổng quan, kiến trúc, git workflow, pipeline, debugging, ví dụ, troubleshooting)

**Quản lý & báo cáo**
- [Báo cáo đóng góp](docs/management/bao-cao-dong-gop-dinh-nhan.md)
- [Daily report](docs/management/daily-report-dinh-nhan.md)

## Kiến trúc tổng quan

```
Frontend (Next.js)  ──fetch/SSE──▶  Backend (FastAPI)  ──import thẳng──▶  Pipeline (2.pipeline/)
                                            │
                                            ▼
                              Filesystem: 5.openapi/ · dist/ · 4.config/ · 3.build/reports/
```

Backend không chứa business logic pipeline — nó "import thẳng" `2.pipeline/` như 1 thư viện Python (cùng process, không qua network), và là lớp điều phối cho workflow quản lý module + chỉnh sửa/xuất bản tài liệu. Deploy tài liệu (tạo PR) không đi qua Backend — chạy trực tiếp từ 1 Next.js Route Handler gọi GitHub API.

## Cấu trúc thư mục

```
API-CONVERTER/
├── 1.docs/source/api_contract/<module>/   # File .docx/.pdf nguồn theo module
├── 2.pipeline/                            # Pipeline convert (Python) — do teammate khác đảm nhiệm
│   ├── pipeline_API.py                    # Entry point chính (batch, module-aware)
│   ├── run_api_import.py                  # CLI orchestration: scan → suggest → approve → apply → import
│   ├── converters/  enrichers/  generator/  post_process/
│   └── import_flow/                       # Support package (config/scanner)
├── 3.build/reports/                       # Log batch, review queue, version tracking
├── 4.config/                              # Module registry, resolution rules, schema registry
├── 5.openapi/                             # Output YAML (paths/ + components/schemas/)
├── 6.path_stub/                           # Sinh + merge path stub vào openapi.yaml
├── backend/                               # FastAPI server (routers/ → services/ → core/ + api_utils/)
├── frontend/                              # Next.js dashboard (hooks/ + components/dashboard/ + lib/api/)
├── docs/                                  # Tài liệu dự án (xem mục 📚 Tài liệu ở trên)
├── dist/                                  # OpenAPI bundle đã build (openapi-bundled.yaml)
├── public/                                # Swagger UI HTML đã build
├── scripts/                               # Script build docs (build-swagger-ui.js...)
└── requirements.txt / Makefile / package.json
```

## Môi trường & cài đặt

Có **2 venv Python tách biệt** — không dùng lẫn:

| Venv | Dùng cho | Kích hoạt |
|---|---|---|
| `.venv/` (gốc) | Chỉ chạy Pipeline (`anthropic`, `python-docx`, `ruamel.yaml`) | `source .venv/bin/activate` |
| `backend/.venv/` | FastAPI server + các dep parsing mà pipeline dùng trực tiếp | `source backend/.venv/bin/activate` |

```bash
make setup   # Tạo .venv gốc + cài requirements
make check   # Kiểm tra Python env + ANTHROPIC_API_KEY
```

**`frontend/.env.local`** (bắt buộc):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**`backend/.env`** (gitignored — không commit), cần cho tính năng AI-suggest/AI-fix vì project gọi Claude qua gateway nội bộ:
```
ANTHROPIC_BASE_URL=...
ANTHROPIC_AUTH_TOKEN=...
ANTHROPIC_MODEL=cc/claude-sonnet-4-6
ANTHROPIC_API_KEY=...
```

## Chạy dự án

```bash
# Backend
cd backend && make dev          # http://localhost:8000

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
```

## Lệnh Pipeline thường dùng

> ⚠️ `make scan`/`approve`/`run-module`/`run-single`/`run-batch` trong Makefile gốc **đang hỏng** (trỏ tới file đã bị dời). Dùng `run_api_import.py` (hoặc alias npm) thay thế:

```bash
python3 2.pipeline/run_api_import.py scan
python3 2.pipeline/run_api_import.py suggest-root
python3 2.pipeline/run_api_import.py review-suggestions
python3 2.pipeline/run_api_import.py approve-suggestions --all
python3 2.pipeline/run_api_import.py apply-suggestions
python3 2.pipeline/run_api_import.py list-modules
python3 2.pipeline/run_api_import.py activate-module --module <tên>
python3 2.pipeline/run_api_import.py import --module <tên>
```

Alias npm tương ứng: `npm run scan`, `suggest:module`, `review:suggest`, `approve`, `update:registry`, `list:module`, `activate:module`, `convert:api`, `enrich:openapi`, `verify:stats` — xem đầy đủ trong `package.json` (còn có nhóm lệnh xử lý mã lỗi `errors:*`).

## OpenAPI Tooling

```bash
npm run bundle:api      # Redocly bundle → dist/openapi-bundled.yaml
npm run lint:spectral   # Spectral lint
npm run validate:api    # Redocly validate
npm run build:docs      # Build Swagger UI HTML → public/api-docs.html
```

## Luồng làm việc chính (Module Workflow)

```
1.docs/source/api_contract/          ← đặt file PDF/DOCX vào đây
      ↓ suggest-root                  parse → gợi ý module cho từng endpoint
      ↓ approve-suggestions --all
      ↓ apply-suggestions             copy vào 1.docs/source/api_contract/<module>/
      ↓ activate-module --module <n>
      ↓ import                        → 5.openapi/paths/<module>/ + schemas/
```

Toàn bộ luồng trên có thể thao tác qua CLI hoặc qua dashboard Next.js (import → scan → suggest → duyệt → apply → activate → import → build tài liệu → chỉnh sửa/review → deploy).

## Giới hạn hiện tại

- `Makefile` gốc (`scan`/`approve`/`run-module`/`run-single`/`run-batch`) hỏng — dùng `run_api_import.py`.
- `pipeline_PDF.py`/`pipeline_Excel.py` chưa được wire vào backend.
- Upload `.txt`/`.md` chưa hoạt động thật (dead-wiring) — chỉ PDF/DOCX dùng được.
- Chưa có test tự động dù `make test` đã wire pytest.
