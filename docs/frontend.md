# Frontend — API Converter

## Tổng quan

Dashboard 1 trang (`app/page.tsx`) cho toàn bộ workflow: import tài liệu → scan → gợi ý/duyệt module → import → build tài liệu Swagger → chỉnh sửa nội dung. Toàn bộ state nằm ở component cha, các "card" con chỉ render UI + nhận callback.

> Route `app/jobs/[job_id]/` (upload đơn lẻ, luồng cũ) đã bị **xóa** — không có nơi nào trong UI link tới nó và không có cách tạo job (`POST /jobs` không được gọi từ đâu), nên route này chưa từng truy cập được trong thực tế. Component `BundleEditor.tsx` (Monaco wrapper) đã được di chuyển vào `_dashboard/` vì vẫn được `BundleEditorModal` dùng lại cho tab "YAML thô".

---

## Công nghệ

| Công nghệ                                  | Vai trò                                                                   |
| ------------------------------------------ | ------------------------------------------------------------------------- |
| **Next.js**                                | Framework React, App Router                                               |
| **React**                                  | UI, state management (toàn bộ state ở `page.tsx`, không dùng store ngoài) |
| **TypeScript**                             | Type safety                                                               |
| **Tailwind CSS**                           | Styling                                                                   |
| **Monaco Editor** (`@monaco-editor/react`) | Code editor cho tab "YAML thô" trong Bundle Editor                        |

> Next.js version này có breaking changes — đọc `node_modules/next/dist/docs/` trước khi code (xem `frontend/AGENTS.md`).

---

## Cấu trúc thư mục

```
frontend/
├── app/
│   ├── page.tsx                       # Dashboard chính — toàn bộ state + handler
│   ├── layout.tsx
│   ├── globals.css
│   ├── _dashboard/                    # Các card con của dashboard
│   │   ├── types.ts                   # Type chung: ScanResult, ModuleListResult, SuggestionsResult, ApplyResult, DocsBuildResult, DocsStatus, ImportModuleProgress, SpectralIssue, RedoclyIssue
│   │   ├── format.ts                  # formatDate, formatRelativeTime, formatBytes, SUPPORTED_EXTENSIONS, countLintIssues
│   │   ├── ImportCard.tsx             # Upload file vào 1.docs/source/api_contract/
│   │   ├── ScanCard.tsx               # Hiển thị kết quả /modules/scan
│   │   ├── SuggestCard.tsx            # Gợi ý/duyệt/apply module assignment
│   │   ├── ModuleRegistryCard.tsx     # Bảng module + activate/deactivate + import (SSE)
│   │   ├── SwaggerDocsCard.tsx        # Build/lint/download tài liệu, mở Bundle Editor
│   │   ├── BundleEditorModal.tsx      # Modal full-screen, 2 tab: Form Editor + YAML thô
│   │   ├── BundleEditor.tsx           # Wrapper Monaco Editor (chuyển từ app/jobs/[job_id]/ cũ)
│   │   ├── OperationsFormEditor.tsx   # Tab "Chỉnh sửa nội dung" — sửa summary/description không cần biết YAML
│   │   ├── StatTiles.tsx              # 4 ô số liệu tổng quan trên dashboard
│   │   └── WorkflowStepper.tsx        # Thanh bước scan→suggest→apply→import→docs
│   ├── swagger/
│   │   ├── page.tsx
│   │   └── SwaggerView.tsx            # Render Swagger UI từ bundle, có Fuse.js fuzzy search tích hợp vào opsFilter
│   └── portal/                        # Developer Portal tự build (KHÔNG link từ nav — xem mục riêng)
│       ├── page.tsx                   # Server Component — đọc bundle YAML trực tiếp từ đĩa, resolve $ref
│       ├── PortalSearch.tsx           # Search/filter bằng Fuse.js (client component)
│       ├── EndpointCard.tsx           # Card hiển thị 1 operation trong list
│       ├── EndpointDetailDrawer.tsx   # Drawer chi tiết khi click vào 1 operation
│       └── SchemaViewer.tsx           # Render schema object dạng cây
└── package.json
```

---

## Dashboard chính — `app/page.tsx`

### Bố cục

```
┌─────────────────────────────────────────────┐
│  Nav: API Converter          [Developer Portal] │
├─────────────────────────────────────────────┤
│  WorkflowStepper: Nguồn → Phân loại → Module → Tài liệu │
├─────────────────────────────────────────────┤
│  StatTiles: module active / draft / file chưa gán / suggestion chờ duyệt │
├──────────────────────┬──────────────────────┤
│  Cột trái (7/12)      │  Cột phải (5/12)      │
│  - SuggestCard        │  - ImportCard         │
│  - ModuleRegistryCard │  - ScanCard           │
│                       │  - SwaggerDocsCard    │
└──────────────────────┴──────────────────────┘
```

Trên mobile: thứ tự đảo lại theo `order-N` (ImportCard → ScanCard → SuggestCard → ModuleRegistryCard → SwaggerDocsCard).

### State chính

| State                                                                       | Mô tả                                     |
| --------------------------------------------------------------------------- | ----------------------------------------- |
| `scan` / `scanLoading` / `scanError`                                        | Kết quả `GET /modules/scan`               |
| `moduleList` / `modulesLoading` / `modulesError`                            | Kết quả `GET /modules`                    |
| `uploadFiles` / `uploading`                                                 | File đang chọn để upload qua `ImportCard` |
| `suggestions` / `suggestRunning` / `approving` / `applying` / `applyResult` | Toàn bộ state luồng suggest→approve→apply |
| `activatingModule` / `deactivatingModule`                                   | Đang activate/deactivate module nào       |
| `importRunning` / `importTarget` / `importModules` / `importDone`           | State SSE của `/modules/import`           |
| `docsBuilding` / `docsResult` / `docsStatus`                                | State build/lint tài liệu                 |
| `bundleContent`                                                             | Khi không null → mở `BundleEditorModal`   |

### Các hàm chính

| Hàm                                                                   | Gọi API                                            | Mô tả                                                                                     |
| --------------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `fetchScan` / `fetchModules` / `fetchSuggestions` / `fetchDocsStatus` | `GET`                                              | Chạy 1 lần khi mount (`useEffect([])`)                                                    |
| `handleUpload`                                                        | `POST /source/upload`                              | Upload file thô, không convert ngay                                                       |
| `handleRunSuggest`                                                    | `POST /modules/suggest`                            | Chạy phân tích (30–90s)                                                                   |
| `handleApprove` / `handleApproveSelected`                             | `POST /modules/suggestions/approve`                | Duyệt 1 hoặc nhiều file (mode `file`/`module`/`all`)                                      |
| `handleApply`                                                         | `POST /modules/apply`                              | Copy file đã duyệt vào thư mục module                                                     |
| `handleActivate` / `handleDeactivate`                                 | `POST /modules/{m}/activate                        | deactivate`                                                                               | Đổi trạng thái module |
| `handleImport`                                                        | `POST /modules/import` + SSE                       | Mở `EventSource`, cập nhật `importModules` theo từng event, đóng khi nhận `event: "done"` |
| `handleBuildDocs` / `handleRelint`                                    | `POST /docs/build` / `/docs/relint`                | Build hoặc lint lại                                                                       |
| `openBundleEditor`                                                    | `GET /docs/bundle-content`                         | Mở modal, set `bundleContent`                                                             |
| `saveBundle` / `saveAndRelint`                                        | `PUT /docs/bundle-content` (+ `POST /docs/relint`) | Lưu bundle YAML thô; có check `res.ok` và `alert` nếu lỗi                                 |

---

## `BundleEditorModal.tsx`

Modal full-screen, 2 tab:

```
┌──────────────────────────────────────────┐
│ [Chỉnh sửa nội dung] [YAML thô]      [✕] │
├──────────────────────────────────────────┤
│           nội dung tab đang chọn          │
├──────────────────────────────────────────┤
│  [Lưu] [Lưu & Kiểm tra lại]  ← chỉ tab YAML│
└──────────────────────────────────────────┘
```

- **Tab "Chỉnh sửa nội dung"** (mặc định) → render `OperationsFormEditor`, tự fetch/save, không cần props từ modal
- **Tab "YAML thô"** → render `BundleEditor` (`./BundleEditor`, Monaco), dùng `content`/`onChange`/`onSave`/`onSaveAndRelint` từ props (điều khiển bởi `page.tsx`)
- Footer Lưu/Lưu & Kiểm tra chỉ hiện ở tab YAML — tab Form có nút riêng trong chính nó

---

## `OperationsFormEditor.tsx`

Form editor cho non-dev — không cần biết YAML.

**Luồng:**
```
Mount → GET /docs/operations → list operations
Group theo tags, hiển thị card cho mỗi endpoint:
  - Method badge (màu theo HTTP method) + path (read-only)
  - Input "Tên gọi" (summary)
  - Textarea "Mô tả chi tiết" (description)
Edit → đánh dấu dirty (viền vàng, "● chưa lưu")
[Lưu] → PATCH /docs/operations (chỉ gửi operation đã đổi)
[Lưu & Kiểm tra lại] → Lưu rồi POST /docs/relint, hiện số lỗi
```

**Chỉ cho sửa 2 field:** `summary` + `description`. Method, path, parameters, schema, response codes hiển thị read-only, không có input — không thể vô tình làm hỏng cấu trúc API.

**Search + filter:** theo path/summary (text) và theo tag (dropdown).

---

## `SwaggerDocsCard.tsx`

```
[Build tài liệu Swagger UI]                      ← khi chưa có bundle
hoặc
[Xem / Sửa lỗi bundle] [Kiểm tra lỗi] [Tải HTML] [Tạo lại tài liệu]  ← khi đã có bundle
```

Hiển thị kết quả lint (Spectral + Redocly) dạng list, màu đỏ = error, vàng = warning. Nút "Xem / Sửa lỗi bundle" mở `BundleEditorModal`.

---

## `ModuleRegistryCard.tsx`

Bảng module: tên, status (badge màu: active=xanh, draft=vàng, deprecated=xám), file_count, endpoint_count, last_import (relative time + tooltip absolute).

Nút theo status:
- `draft`/`deprecated` → **Activate**
- `active` → **Import** (riêng module này) + **Deactivate**

Nút "Import tất cả" ở header — disable nếu không có module nào active.

Khi import chạy: hiện progress bar per-module (`importModules` state), % = `(success+failed+skipped)/total`.

---

## `SuggestCard.tsx`

Bảng suggestion với checkbox chọn nhiều, filter tab Chờ duyệt/Đã duyệt/Tất cả. Mỗi dòng hiện endpoint, method, module gợi ý, conflict warning (nếu `service_in_doc` khác `final_module`), input override module. Nút "Duyệt (N) file" duyệt các file đã check, "Apply suggestions" copy file đã duyệt vào thư mục module.

---

## `app/swagger/SwaggerView.tsx`

Trang Developer Portal — render Swagger UI từ `dist/openapi-bundled.yaml`. Tích hợp **Fuse.js** vào search bar mặc định của Swagger UI qua plugin `opsFilter` (không dùng search bar riêng):

```typescript
keys: [
  { name: "operationId", weight: 0.3 },
  { name: "summary", weight: 0.25 },
  { name: "path", weight: 0.2 },
  { name: "tag", weight: 0.1 },
  { name: "description", weight: 0.1 },
]
threshold: 0.4, ignoreLocation: true, useExtendedSearch: true
```

`scripts/build-swagger-ui.js` (build static HTML cho `public/api-docs.html`) dùng cùng approach — plain JS port của plugin này.

---

## `app/portal/` — Developer Portal tự build (⚠ chưa được link tới)

Route `/portal` render 1 giao diện xem API docs **tự thiết kế** (không dùng thư viện Swagger UI), gồm:

```
┌──────────────────────────────────────────────┐
│  Search... [GET][POST][PUT]...  [Tag ▼]      │
├──────────────────────────────────────────────┤
│  EndpointCard: GET /v1/tickets   "Lấy ds..." │
│  EndpointCard: POST /v1/tickets  "Tạo..."    │
├──────────────────────────────────────────────┤
│  Click 1 card → EndpointDetailDrawer mở:     │
│    parameters, request/response schema       │
│    (render qua SchemaViewer dạng cây)         │
└──────────────────────────────────────────────┘
```

**Luồng:** `page.tsx` là Server Component — đọc trực tiếp `dist/openapi-bundled.yaml` bằng `fs.readFileSync` lúc render (không qua backend API), tự resolve `$ref` (`resolveRefs()`, đệ quy tối đa 10 cấp), trích operations rồi truyền cho `PortalSearch` (client component) render + search bằng Fuse.js riêng (keys: `operationId`/`summary`/`path`/`tags`/`description`).

**⚠️ Vấn đề:** không có `href="/portal"` nào trong toàn bộ codebase — route này chỉ truy cập được nếu gõ thẳng URL. Nav hiện tại (`page.tsx`) chỉ link tới `/swagger`. Hai route `/portal` và `/swagger` cùng giải quyết 1 nhu cầu (xem + tìm kiếm API docs) bằng 2 cách implement khác nhau — nhiều khả năng `/portal` là bản dựng trước, bị bỏ lại sau khi chuyển qua dùng Swagger UI chuẩn ở `/swagger`.

---

## Giao tiếp với Backend

Base URL: `process.env.NEXT_PUBLIC_API_URL` (set trong `frontend/.env.local`).

| Nhóm        | Endpoint dùng                                                                                                                          |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Scan/Module | `/modules/scan`, `/modules`, `/modules/{m}/activate`, `/modules/{m}/deactivate`, `/modules/import`, `/modules/import/{id}/stream`      |
| Suggest     | `/modules/suggestions`, `/modules/suggest`, `/modules/suggestions/approve`, `/modules/apply`                                           |
| Source      | `/source/upload`                                                                                                                       |
| Docs        | `/docs/build`, `/docs/status`, `/docs/bundle-content` (GET/PUT), `/docs/relint`, `/docs/download-html`, `/docs/operations` (GET/PATCH) |

Đây là **toàn bộ** endpoint backend hiện có — không còn route `/jobs/*` nào (đã xóa, xem `docs/backend.md` mục Lịch sử thay đổi).

---

## Các điểm kỹ thuật đáng chú ý

**State pattern nhất quán** — mọi async action theo công thức `setLoading(true) → fetch → setX(data)/setError(e) → setLoading(false)`.

**SSE thay vì polling** — `/modules/import/{id}/stream` dùng `EventSource`, đóng khi nhận `event: "done"` hoặc `onerror`.

**Dynamic import Monaco** — lazy load, `ssr: false` vì Monaco chỉ chạy trên browser:
```typescript
const BundleEditor = dynamic(() => import("./BundleEditor"), { ssr: false });
```

**`useMounted()` pattern** — dùng trong `ModuleRegistryCard` và `SuggestCard` để tránh hydration mismatch khi disable button dựa trên state client-only (`suppressHydrationWarning`).

---

## Thiếu sót hiện tại (Known Gaps)

| Vấn đề                                  | Ghi chú                                                                                                     |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Không có nút Publish                    | Chỉ có "Tải HTML" thủ công, chưa có commit+push tự động                                                     |
| `useMounted` gây 2 lint error           | `react-hooks/set-state-in-effect` ở `ModuleRegistryCard.tsx` và `SuggestCard.tsx` — không ảnh hưởng runtime |
| Form Editor chỉ sửa summary/description | Chưa hỗ trợ parameter description, response description                                                     |
| Không có auth                           | Dashboard mở public trong mạng nội bộ                                                                       |
| `app/portal/` không được link từ nav    | Trùng chức năng với `/swagger`, có khả năng là code mồ côi — cần quyết định giữ hay xóa                     |
