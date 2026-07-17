# Setup môi trường local — API Converter

> Tài liệu này gom lại toàn bộ bước cần làm để chạy được dự án lần đầu trên máy mới: cài đặt, các file `.env`, và cấu hình phía GitHub (secrets, Pages). Không lặp lại nội dung đã có ở `setup-cicd.md` (quy tắc PR/commit) hay `setup-slack.md` (chi tiết tạo Slack App) — 2 file đó vẫn là nguồn tham khảo chính cho phần của nó.

---

## Yêu cầu hệ thống

| Công cụ | Version     | Ghi chú                                                                                                                             |
| ------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Node.js | 24          | Khớp với version dùng trong CI (`.github/workflows/*.yaml`) — nên dùng đúng version này ở máy local để tránh lệch hành vi so với CI |
| Python  | 3.10+       | Dùng cho cả 2 venv (root pipeline + backend)                                                                                        |
| npm     | đi kèm Node |                                                                                                                                     |

---

## 1. Clone & cài dependencies gốc

```bash
git clone <repo-url>
cd "API CONVERTER"
npm install
```

`npm install` ở gốc cài các tool OpenAPI (Redocly, Spectral) dùng cho `npm run bundle:api` / `lint:spectral` / `validate:api` / `build:docs`.

---

## 2. Python venv — Pipeline (`2.pipeline/`)

```bash
make setup   # tạo .venv/ ở gốc, cài 2.pipeline/requirements.txt
```

Pipeline **không đọc file `.env`** (không có `load_dotenv()` nào trong `2.pipeline/`) — bắt buộc phải `export` biến môi trường thật sự trong shell (hoặc thêm vào `~/.bashrc`/`~/.zshrc` để khỏi export lại mỗi lần mở terminal mới):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Kiểm tra lại:
```bash
make check
```
In ra Python version, version các package chính (`anthropic`, `python-docx`, `ruamel.yaml`, `chardet`), và xác nhận `ANTHROPIC_API_KEY` đã set chưa.

> **Lưu ý:** `make scan`/`approve`/`run-module`/`run-single`/`run-batch` hiện đang **broken** — các target đó gọi `2.pipeline/pipeline_DOCX.py`, file này đã được chuyển sang `3.build/orphans/` và không còn tồn tại ở path cũ. Dùng `python3 2.pipeline/run_api_import.py <lệnh>` (hoặc alias npm tương ứng, xem README/CLAUDE.md phần Commands) thay thế.

---

## 3. Python venv — Backend (`backend/`)

Venv **riêng biệt** với venv ở bước 2 — không dùng chung:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Tạo `backend/.env`

File này **gitignored** — không commit. Copy từ `backend/.env.example` rồi điền giá trị thật:

```bash
cp .env.example .env
```

Nội dung cần có:

```bash
ANTHROPIC_BASE_URL=...       # gateway nội bộ của công ty, không phải api.anthropic.com
ANTHROPIC_AUTH_TOKEN=...     # token gateway — đây mới là cơ chế auth thật sự đang dùng
ANTHROPIC_MODEL=cc/claude-sonnet-4-6
ANTHROPIC_API_KEY=...
```

Backend gọi `anthropic.Anthropic()` **không truyền tham số nào** (`backend/services/ai_fix.py`, `backend/services/operations.py`) — SDK tự đọc 3 biến `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_API_KEY` từ biến môi trường tiến trình (được `load_dotenv()` trong `main.py` bơm vào). Riêng `model` thật ra **đang bị hardcode thẳng trong code** (`model="cc/claude-sonnet-4-6"`) — biến `ANTHROPIC_MODEL` trong `.env` hiện không được đọc ở đâu cả, giữ lại phục vụ cho tương lai chứ chưa có tác dụng thật.

Thiếu file này (hoặc thiếu `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_BASE_URL`) → `POST /docs/operations/ai-suggest` và `POST /docs/bundle/ai-fix` trả lỗi 502, các phần khác của backend vẫn chạy bình thường.

### Chạy thử

```bash
cd backend && make dev
```
(tương đương `./.venv/bin/uvicorn main:app --reload --port 8000`)

Kiểm tra: `curl http://localhost:8000/health` → phải trả về OK.

---

## 4. Frontend

```bash
cd frontend
npm install
```

### Tạo `frontend/.env.local`

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Chỉ cần đúng 1 dòng này là đủ để chạy dashboard chính (scan/suggest/import/build docs...). 4 biến dưới đây **chỉ cần nếu muốn dùng nút "Deploy tài liệu"** (`POST /api/deploy-docs`, gọi thẳng GitHub Git Data API, không qua backend Python):

```bash
OPENAPI_DIR=/duong/dan/tuyet/doi/toi/thu/muc/5.openapi   # route chỉ ĐỌC từ đây, không phải git checkout, không push gì từ local
GH_DISPATCH_TOKEN=ghp_...    # PAT có quyền đủ để đọc/ghi git data + dispatch workflow trên repo này
GH_OWNER=<tên-owner-hoặc-org>
GH_REPO=<tên-repo>
```

Thiếu 1 trong 4 biến trên → bấm Deploy sẽ báo lỗi rõ ràng ("Thiếu các biến môi trường trong .env.local"), không crash gì, các tính năng khác của dashboard không bị ảnh hưởng.

### Chạy thử

```bash
npm run dev
```
Mở `http://localhost:3000`.

> **Next.js version note:** dự án đang dùng version có breaking changes so với các bản cũ hơn — trước khi sửa code frontend, đọc `node_modules/next/dist/docs/` để xác nhận hành vi hiện tại thay vì suy đoán theo kiến thức cũ (xem `frontend/AGENTS.md`).

CORS ở backend (`backend/main.py`) chỉ cho phép `http://localhost:3000` — nếu chạy frontend ở port khác, phải tự sửa `allow_origins` trong `backend/main.py`.

---

## 5. Cấu hình phía GitHub

### 5.1 Repo Secrets (Settings → Secrets and variables → Actions)

| Secret                                | Bắt buộc?                    | Dùng ở đâu                                          | Ghi chú                                                                                                                                                                                                                                                                      |
| ------------------------------------- | ---------------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GITHUB_TOKEN`                        | Không cần tạo                | `deploy.yaml`                                       | GitHub tự cấp sẵn cho mọi workflow, không phải tạo tay                                                                                                                                                                                                                       |
| `KEY_DEPLOY`                          | Có, nếu muốn dùng nút Deploy | `create-doc-pr.yaml`                                | Personal Access Token (PAT) tạo tay — **bắt buộc phải là PAT thật**, không dùng `GITHUB_TOKEN` mặc định được, vì workflow mở PR bằng `GITHUB_TOKEN` của chính nó sẽ **không** tự kích hoạt được `ci.yaml` (giới hạn bảo mật của GitHub, tránh workflow tự gọi đệ quy vô hạn) |
| `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID` | Tùy chọn                     | Job `notify` (đang comment-out trong `deploy.yaml`) | Xem chi tiết cách tạo ở [`setup-slack.md`](./setup-slack.md)                                                                                                                                                                                                                 |

Tạo `KEY_DEPLOY`: vào GitHub → **Settings** (cá nhân) → **Developer settings** → **Personal access tokens** → tạo token có quyền `repo` (và `workflow` nếu dùng fine-grained token) → paste vào repo Secrets với tên `KEY_DEPLOY`.

### 5.2 GitHub Pages

`deploy.yaml` build xong sẽ tự push vào 1 trong 2 nhánh, chọn theo nhánh vừa push code:
- Push lên `main` → ghi vào nhánh `gh-page`
- Push lên `develop` (hoặc nhánh khác) → ghi vào nhánh `gh-page-dev`

GitHub Pages chỉ phục vụ **1 nhánh tại 1 thời điểm** — vào **Settings → Pages → Source** chọn nhánh muốn hiển thị công khai (thường là `gh-page-dev` trong giai đoạn dev, đổi sang `gh-page` khi lên production). Đổi nhánh nguồn ở đây **không tự động** theo nhánh code đang active — phải tự vào đổi tay khi cần.

---

## 6. Checklist xác nhận setup đúng

- [ ] `make check` (root) báo `ANTHROPIC_API_KEY` đã set
- [ ] `curl http://localhost:8000/health` trả OK (backend chạy được)
- [ ] Dashboard mở được ở `http://localhost:3000`, không có lỗi CORS trong Console
- [ ] `POST /docs/operations/ai-suggest` (nút "AI gợi ý" trong Form Editor) không trả 502 → xác nhận `backend/.env` đúng
- [ ] (Nếu cần) bấm "Deploy tài liệu" không báo "Thiếu các biến môi trường" → xác nhận `frontend/.env.local` đủ 4 biến GitHub
- [ ] `npm run lint:spectral` và `npm run validate:api` (root) chạy được, không lỗi thiếu tool
