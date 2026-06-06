# Frontend — API Converter

## Tổng quan

Giao diện web cho phép người dùng upload tài liệu API (.docx), theo dõi tiến trình xử lý, review/chỉnh sửa YAML output, và xuất tài liệu OpenAPI hoàn chỉnh.

---

## Công nghệ

| Công nghệ | Phiên bản | Vai trò |
|---|---|---|
| **Next.js** | 16.2.6 | Framework React, App Router, SSR/CSR |
| **React** | 19.2.4 | UI library, state management |
| **TypeScript** | ^5 | Type safety cho toàn bộ code |
| **Tailwind CSS** | ^4 | Utility-first CSS, không viết CSS thủ công |
| **Monaco Editor** | @monaco-editor/react ^4.7.0 | Code editor trong trình duyệt (giống VS Code) |
| **ESLint** | ^9 | Kiểm tra lỗi code tĩnh |

### Font
- **Geist Sans** — font chữ thường (Next.js default)
- **Geist Mono** — font monospace cho code/YAML

---

## Cấu trúc thư mục

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout — font, metadata, MonacoErrorSuppressor
│   ├── globals.css             # Import Tailwind, CSS variables (light/dark)
│   ├── MonacoErrorSuppressor.tsx  # Suppress lỗi nội bộ Monaco
│   ├── page.tsx                # Trang chủ — upload file
│   └── jobs/
│       └── [job_id]/
│           ├── page.tsx        # Trang job — progress + review + export
│           └── BundleEditor.tsx  # Monaco editor cho bundle YAML
├── next.config.ts              # Config Next.js
└── package.json
```

---

## Các trang (Pages)

### 1. Trang chủ — `/` (`app/page.tsx`)

**Mục đích:** Upload file .docx để bắt đầu pipeline.

**Chức năng:**
- Drop zone kéo-thả file hoặc click để mở file picker
- Chỉ chấp nhận `.docx` (filter tại `handleFiles`)
- Hiển thị danh sách file đã chọn, có nút xóa từng file
- Nút "Chạy pipeline" — gọi `POST /jobs`, redirect sang `/jobs/{job_id}`
- Hiển thị lỗi kết nối backend nếu có

**State:**
```typescript
files: File[]       // danh sách file đã chọn
loading: boolean    // đang gửi request
error: string       // thông báo lỗi
```

---

### 2. Trang Job — `/jobs/[job_id]` (`app/jobs/[job_id]/page.tsx`)

**Mục đích:** Theo dõi tiến trình xử lý, xem kết quả lint, chỉnh sửa bundle.

#### 2a. Progress tracking

Kết nối SSE (Server-Sent Events) tới `GET /jobs/{job_id}/stream`:
- Mỗi file xử lý xong → backend gửi event → frontend cập nhật status
- Progress bar hiển thị `done / total`
- Status mỗi file: `pending` / `processing` / `done` / `error` / `flagged`

#### 2b. Export & Lint

Nút **"Xuất tài liệu"** → `POST /jobs/{job_id}/export`:
- Backend bundle YAML → chạy Spectral lint → chạy Redocly lint → build Swagger HTML
- Trả về `{ spectral: [...], redocly: [...], html_ready: bool }`

Nút **"Build lại"** (xuất hiện sau lần export đầu): gọi lại cùng endpoint.

#### 2c. Hiển thị kết quả lint

Kết quả được normalize qua `normalizeIssues()`:

```typescript
// Spectral: severity là number (0=error, 1=warn, 2=info)
// Redocly: severity là string ("error" | "warn")
// → gộp thành NormalizedIssue thống nhất
type NormalizedIssue = {
  severity: "error" | "warn" | "info"
  source: "Spectral" | "Redocly"
  code: string       // ruleId hoặc code
  message: string
  location?: string  // path join bằng "."
}
```

Hiển thị dạng **tabs**: Error / Warn / Info, mỗi tab có badge đếm số lỗi.

#### 2d. Bundle Editor

Nút **"Chỉnh sửa bundle"** → mở modal full-screen với Monaco Editor:
- Load nội dung `dist/openapi-bundled.yaml` từ `GET /jobs/{job_id}/bundle-content`
- Hiển thị markers lỗi Spectral + Redocly trực tiếp trong editor (inline highlight)
- Nút **"Lưu"**: `PUT /jobs/{job_id}/bundle-content`
- Nút **"Lưu & Kiểm tra lại"**: lưu rồi gọi `POST /jobs/{job_id}/relint`, cập nhật kết quả lint

**State:**
```typescript
files: FileResult[]        // danh sách file và status
done: boolean              // pipeline hoàn tất
exporting: boolean         // đang export
lintResult: LintResult     // kết quả spectral + redocly
bundleContent: string|null // nội dung bundle đang chỉnh sửa
savingBundle: boolean
relinting: boolean
activeTab: "error"|"warn"|"info"
```

---

### 3. Bundle Editor — `BundleEditor.tsx`

Component Monaco Editor wrapper:

**Props:**
```typescript
content: string             // nội dung YAML
onChange: (val) => void     // callback khi user edit
spectralIssues: SpectralIssue[]
redoclyIssues: RedoclyIssue[]
```

**Chức năng chính:**
- Render Monaco Editor với language `yaml`
- Sau khi editor mount → gọi `applyMarkers()` để đặt error markers từ Spectral + Redocly
- Spectral markers dùng `range.start.line` / `range.end.line` → highlight đúng dòng
- Redocly markers dùng `location[0].line` / `location[0].column` nếu có

**Monaco options:**
```typescript
fontSize: 13
minimap: { enabled: false }
lineNumbers: "on"
wordWrap: "on"
automaticLayout: true   // tự resize khi container thay đổi
```

---

## Giao tiếp với Backend

Base URL: `http://localhost:8000`

| Method | Endpoint | Dùng ở đâu |
|---|---|---|
| `POST` | `/jobs` | Upload file, tạo job |
| `GET` | `/jobs/{id}/stream` | SSE — theo dõi tiến trình |
| `GET` | `/jobs/{id}/flags` | Lấy file flagged (chưa dùng trong UI hiện tại) |
| `GET` | `/jobs/{id}/files/{fid}/yaml` | Đọc YAML của file |
| `PUT` | `/jobs/{id}/files/{fid}/yaml` | Lưu YAML đã chỉnh sửa |
| `POST` | `/jobs/{id}/files/{fid}/approve` | Approve file |
| `POST` | `/jobs/{id}/export` | Bundle + lint + build HTML |
| `GET` | `/jobs/{id}/bundle-content` | Đọc nội dung bundle |
| `PUT` | `/jobs/{id}/bundle-content` | Lưu bundle sau chỉnh sửa |
| `POST` | `/jobs/{id}/relint` | Lint lại từ bundle hiện tại |
| `GET` | `/jobs/{id}/download-html` | Tải file HTML Swagger UI |

---

## Kiểu dữ liệu chính (Types)

```typescript
type FileResult = {
  file_id: string
  filename: string
  status: "pending" | "processing" | "done" | "error" | "flagged"
  error: string
}

type SpectralIssue = {
  severity: number        // 0=error, 1=warn, 2=info
  message: string
  code: string
  path: string[]
  range?: {
    start: { line: number; character: number }
    end:   { line: number; character: number }
  }
}

type RedoclyIssue = {
  severity: string        // "error" | "warn"
  message: string
  ruleId: string
  location?: Array<{
    pointer?: string
    line?: number
    column?: number
  }>
}

type LintResult = {
  bundle_ready: boolean
  html_ready: boolean
  spectral: SpectralIssue[]
  redocly: RedoclyIssue[]
}
```

---

## Workflow UI/UX — Luồng người dùng

```
[Trang chủ /]
    │
    │  Kéo thả hoặc click chọn file .docx
    │  Xóa file không muốn
    │  Click "Chạy pipeline"
    │
    ▼
[POST /jobs] ──── redirect ────▶ [Trang Job /jobs/{id}]
                                      │
                                      │  SSE stream — cập nhật realtime
                                      │  Progress bar tăng dần
                                      │  Mỗi file: pending → processing → done/error
                                      │
                                      ▼
                                 [Tất cả file xong]
                                      │
                                      │  Click "Xuất tài liệu"
                                      │
                                      ▼
                                 [POST /export]
                                      │
                                      ├──▶ Bundle YAML
                                      ├──▶ Spectral lint
                                      ├──▶ Redocly lint
                                      └──▶ Build Swagger HTML
                                      │
                                      ▼
                                 [Kết quả kiểm tra]
                                 Tab Error / Warn / Info
                                      │
                                      ├── Không có lỗi → "Tải HTML"
                                      │
                                      └── Có lỗi → "Chỉnh sửa bundle"
                                                        │
                                                        ▼
                                                  [Modal Monaco Editor]
                                                  Xem inline markers
                                                  Sửa YAML tay
                                                        │
                                                        ▼
                                                  "Lưu & Kiểm tra lại"
                                                  → relint → cập nhật tabs
                                                        │
                                                   (lặp lại cho đến sạch lỗi)
                                                        │
                                                        ▼
                                                  "Tải HTML" ✓
```

---

## Các điểm kỹ thuật đáng chú ý

**SSE thay vì polling** — `EventSource` giữ kết nối mở, backend push event từng file xong, không cần client hỏi liên tục.

**Dynamic import Monaco** — Monaco nặng (~2MB), được lazy load chỉ khi cần:
```typescript
const BundleEditor = dynamic(() => import("./BundleEditor"), { ssr: false })
```
`ssr: false` vì Monaco chỉ chạy được trên browser, không phải server.

**MonacoErrorSuppressor** — Monaco internally dùng Promise và có thể reject với `{ type: "cancelation" }` khi component unmount. Component này suppress những rejection đó để không làm ô nhiễm console.

**CORS** — Backend cho phép `http://localhost:3000`. Nếu chạy frontend ở port khác (3001, 3002...) sẽ bị block.

---

## Thiếu sót hiện tại (Known Gaps)

| Vấn đề | Ghi chú |
|---|---|
| Không có YAML editor per-file | `GET/PUT /jobs/{id}/files/{fid}/yaml` tồn tại ở backend nhưng UI chưa dùng |
| Approve/reject per-file chưa có UI | `POST /approve` có ở backend, không có nút trên UI |
| Spectral/Redocly hiển thị chung 1 tab | Đang plan tách 2 bảng riêng |
| `location` của Redocly không có line/column | Markers Monaco luôn ở dòng 1 với Redocly issues |
| Không có auth | Mọi người đều truy cập được job của nhau nếu biết `job_id` |
| Job chỉ tồn tại trong RAM | Restart backend là mất hết job |
