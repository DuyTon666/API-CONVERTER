## 📚 Tài liệu

- [API-GOVERNANCE](docs/api-governance.md)
- [Luồng hoạt động CI](docs/ci-flow.md)
- [Tool OAS-Diff](docs/oas-diff.md)
- [Setup CI](docs/setup-cicd.md)
- [Setup Slack](docs/setup-slack.md)


# API-CONVERTER_V2

Công cụ chuyển đổi tài liệu API (.docx) sang OpenAPI YAML tự động, sử dụng Claude (Anthropic) để sinh `summary` và `operationId`.

## Cấu trúc thư mục

```
API-CONVERTER_V2/
├── 1.docs/source/<module>/     # File .docx đầu vào theo module
├── 2.pipeline/                 # Source code pipeline (Python)
│   ├── pipeline_Ticket.py      # Entry point chính
│   ├── converters/             # Đọc + parse docx/pdf/excel
│   ├── enrichers/              # Gọi LLM (Anthropic)
│   ├── generator/              # Sinh YAML output
│   ├── merger/                 # Gộp nhiều source
│   ├── post_process/           # Tag readOnly, thay $ref
│   ├── validators/             # Validate YAML output
│   └── utils/                  # Module registry, pluralizer
├── 3.build/reports/            # Log batch, review queue, version
├── 4.config/                   # Config hệ thống + module registry
├── 5.openapi/                  # Output YAML (paths + schemas)
├── requirements.txt
└── Makefile
```

## Yêu cầu

- Python 3.10+
- `ANTHROPIC_API_KEY` hợp lệ

## Cài đặt lần đầu

```bash
# 1. Clone repo
git clone <repo-url>
cd API-CONVERTER_V2

# 2. Tạo venv và cài thư viện
make setup

# 3. Set API key (thêm vào ~/.bashrc hoặc ~/.zshrc để dùng lâu dài)
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Kiểm tra môi trường
make check
```

## Luồng sử dụng chuẩn

### Bước 1 — Scan module mới

Đặt thư mục tài liệu vào `1.docs/source/<tên-module>/`, rồi chạy:

```bash
make scan
```

Hệ thống phát hiện module chưa đăng ký, đề xuất đường dẫn, hỏi confirm rồi đăng ký với status `draft`.

### Bước 2 — Approve module

```bash
make approve m=ticket by="nguyen-van-a"
```

Chuyển module từ `draft` → `active`.

### Bước 3 — Chạy convert

```bash
# Chạy module đã active (strict)
make run-module m=ticket

# Chạy module draft (bootstrap, output cần review)
make run-module m=ticket mode=bootstrap
```

Output YAML ghi vào `5.openapi/paths/<module>/`, schemas vào `5.openapi/components/schemas/<module>/`.

## Các lệnh khác

```bash
# Chạy batch thủ công (không qua module registry)
make run-batch in=1.docs/source/ticket out=5.openapi/paths/tickets

# Chạy 1 file đơn lẻ
make run-single in=1.docs/source/ticket/create.docx out=5.openapi/paths/tickets/create.yaml

# Chạy test
make test

# Xoá venv + cache
make clean
```

## Output sau mỗi lần chạy

| File | Mô tả |
|------|-------|
| `3.build/reports/batch_log.json` | Tổng kết: success/fail/skip |
| `3.build/reports/human_review_queue.json` | Các file cần review thủ công |
| `3.build/reports/file_version.json` | Version tracking, tránh convert lại file không đổi |

## Lưu ý

- File `.docx` phải có **method** (`GET`/`POST`/...) và **path** (`/v1/...`) rõ ràng trong nội dung.
- File đã convert cùng version sẽ bị **SKIP** tự động (kiểm tra `file_version.json`).
- Nếu LLM không điền được `summary`/`operationId`, file sẽ vào `human_review_queue.json`.
- Không commit `ANTHROPIC_API_KEY` vào source code hay `.env` tracked bởi git.

# Lần đầu
make setup
export ANTHROPIC_API_KEY="sk-ant-..."
make check

# Mỗi lần dùng
make scan
make approve m=<module>
make run-module m=<module>