# Frontend — API Converter

## Tổng quan

Dashboard 1 trang (`app/page.tsx`) cho toàn bộ workflow: import tài liệu → scan → gợi ý/duyệt module → import → build tài liệu Swagger → chỉnh sửa nội dung → review xung đột sửa tay. State được tách thành **6** custom hook (`app/_dashboard/hooks/`), `page.tsx` chỉ compose hook + render layout; các "card" con chỉ render UI + nhận callback qua props.

> Route `app/jobs/[job_id]/` (upload đơn lẻ, luồng cũ) đã bị **xóa** từ lâu — không có nơi nào trong UI link tới nó và không có cách tạo job (`POST /jobs` không tồn tại nữa ở backend).

---

## Công nghệ

| Công nghệ                                  | Vai trò                                                                                                                       |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| **Next.js**                                | Framework React, App Router                                                                                                   |
| **React**                                  | UI, state management qua custom hook (`app/_dashboard/hooks/`), không dùng store ngoài                                        |
| **TypeScript**                             | Type safety                                                                                                                   |
| **Tailwind CSS**                           | Styling                                                                                                                       |
| **Monaco Editor** (`@monaco-editor/react`) | `BundleEditor` (tab "YAML thô") dùng editor thường; `AiFixPanel` dùng `DiffEditor` (so sánh gốc/đã sửa, cho sửa tay cả 2 bên) |

> Next.js version này có breaking changes — đọc `node_modules/next/dist/docs/` trước khi code (xem `frontend/AGENTS.md`).

---

## Cấu trúc thư mục

```
frontend/
├── app/
│   ├── page.tsx                       # Dashboard chính — compose 6 hook + render layout
│   ├── layout.tsx                     # Root layout, mount MonacoErrorSuppressor
│   ├── MonacoErrorSuppressor.tsx      # Nuốt unhandledrejection "cancelation" nội bộ của Monaco (không phải lỗi thật)
│   ├── globals.css
│   ├── _dashboard/                    # Các card con của dashboard
│   │   ├── types.ts                   # Type chung: ScanResult, ModuleListResult, SuggestionsResult, ApplyResult, DocsBuildResult, DocsStatus, ImportModuleProgress, SpectralIssue, RedoclyIssue, ManualEditConflict, AiFixPatch/AiFixUnresolved/AiFixResult/AiFixResolution
│   │   ├── format.ts                  # formatDate, formatRelativeTime, formatBytes, SUPPORTED_EXTENSIONS, countLintIssues
│   │   ├── api.ts                     # apiFetch/readErrorDetail/formatFetchError dùng chung cho mọi hook + OperationsFormEditor
│   │   ├── errorMessages.ts           # ERROR_MESSAGES map (code → chữ hiển thị tuỳ chỉnh) + resolveErrorMessage()
│   │   ├── ErrorAlert.tsx             # UI báo lỗi dùng chung (thay 9 chỗ <div> trùng lặp)
│   │   ├── hooks/
│   │   │   ├── useMounted.ts          # Mount-detection, tránh hydration mismatch
│   │   │   ├── useScan.ts             # scan result + fetchScan
│   │   │   ├── useModuleRegistry.ts   # module list, activate/deactivate, import (SSE), nhận onImportDone callback
│   │   │   ├── useUpload.ts           # upload state, nhận onSuccess callback
│   │   │   ├── useDocsBuilder.ts      # build/lint/bundle-editor/AI-fix state
│   │   │   ├── useSuggestions.ts      # suggest/approve/apply, nhận onApplySuccess callback
│   │   │   └── useManualEditConflicts.ts  # list/resolve xung đột sửa tay khi import lại
│   │   ├── ImportCard.tsx             # Upload file vào 1.docs/source/api_contract/
│   │   ├── ScanCard.tsx               # Hiển thị kết quả /modules/scan
│   │   ├── SuggestCard.tsx            # Gợi ý/duyệt/apply module assignment
│   │   ├── ModuleRegistryCard.tsx     # Bảng module + activate/deactivate + import (SSE)
│   │   ├── ManualEditConflictsCard.tsx # Danh sách field bị conflict giữa sửa tay và import lại, nút "Giữ bản cũ"/"Lấy bản mới"
│   │   ├── SwaggerDocsCard.tsx        # Build/lint/download tài liệu, mở Bundle Editor
│   │   ├── BundleEditorModal.tsx      # Modal full-screen, 2 tab: Form Editor + YAML thô
│   │   ├── BundleEditor.tsx           # Wrapper Monaco Editor thường (tab "YAML thô")
│   │   ├── AiFixPanel.tsx             # Panel riêng (không nằm trong modal) — DiffEditor per-patch, chọn giữ gốc/giữ bản sửa/giữ cả hai, nút "Áp dụng"
│   │   ├── OperationsFormEditor.tsx   # Tab "Chỉnh sửa nội dung" — sửa summary/description/parameter & response description, có nút AI gợi ý
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
### State — 6 custom hook (`app/_dashboard/hooks/`)

`page.tsx` chỉ gọi 6 hook dưới đây và destructure ra props cho card con — không tự giữ state nào
khác ngoài giá trị dẫn xuất (`pendingSuggestions`, `activeModules`, `steps`...).

| Hook                                           | Owns                                                                                      | Gọi API                                                                                                               |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `useScan(backend)`                             | `scan` / `scanLoading` / `scanError` / `fetchScan`                                        | `GET /modules/scan`                                                                                                   |
| `useManualEditConflicts(backend)`              | `conflicts` / `loading` / `error` / `resolving` / `resolveError` / `conflictKey`          | `GET /modules/manual-edit-conflicts`, `POST /modules/manual-edit-conflicts/resolve`                                   |
| `useModuleRegistry(backend, { onImportDone })` | `moduleList`, activate/deactivate state, import state (SSE)                               | `GET /modules`, `POST /modules/{m}/activate`/`deactivate`, `POST /modules/import` + `GET /modules/import/{id}/stream` |
| `useUpload(backend, { onSuccess })`            | `uploadFiles` / `uploading` / `uploadError` / `uploadMessage`                             | `POST /source/upload`                                                                                                 |
| `useDocsBuilder(backend)`                      | `docsBuilding` / `docsResult` / `docsStatus` / `bundleContent` + save/relint/AI-fix state | `POST /docs/build`, `/docs/relint`, `/docs/bundle/ai-fix`, `GET`/`PUT /docs/bundle-content`                           |
| `useSuggestions(backend, { onApplySuccess })`  | `suggestions` / `suggestRunning` / `approving` / `applying` / `applyResult`               | `GET /modules/suggestions`, `POST /modules/suggest`/`suggestions/approve`/`apply`                                     |

`useUpload`, `useSuggestions`, `useModuleRegistry` có phụ thuộc lẫn hook khác — giải quyết bằng
**callback injection** (`onSuccess`/`onApplySuccess`/`onImportDone` truyền từ `page.tsx`), không
hook nào import hook khác. `onImportDone` gọi `fetchConflicts()` — vì import xong là lúc xung đột
sửa tay mới (nếu có) xuất hiện. Nhờ vậy chỉ có đúng 1 instance của mỗi hook, sở hữu bởi `page.tsx`.

Cả 6 hook + `OperationsFormEditor.tsx` dùng chung `apiFetch`/`readErrorDetail`/`formatFetchError`
từ `app/_dashboard/api.ts` (xem mục **Xử lý lỗi & mã lỗi** phía dưới).

### Các hàm chính (nằm trong các hook trên)

| Hàm                                                                                      | Gọi API                                             | Mô tả                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fetchScan` / `fetchModules` / `fetchSuggestions` / `fetchDocsStatus` / `fetchConflicts` | `GET`                                               | Chạy 1 lần khi mount (`useEffect([])`)                                                                                                                                                                   |
| `handleUpload`                                                                           | `POST /source/upload`                               | Upload file thô, không convert ngay                                                                                                                                                                      |
| `handleRunSuggest`                                                                       | `POST /modules/suggest`                             | Chạy phân tích (30–90s)                                                                                                                                                                                  |
| `handleApprove` / `handleApproveSelected`                                                | `POST /modules/suggestions/approve`                 | Duyệt 1 hoặc nhiều file (mode `file`/`module`/`all`)                                                                                                                                                     |
| `handleApply`                                                                            | `POST /modules/apply`                               | Copy file đã duyệt vào thư mục module                                                                                                                                                                    |
| `handleActivate` / `handleDeactivate`                                                    | `POST /modules/{m}/activate` / `deactivate`         | Đổi trạng thái module                                                                                                                                                                                    |
| `handleImport`                                                                           | `POST /modules/import` + SSE                        | Mở `EventSource`, cập nhật `importModules` theo từng event, đóng khi nhận `event: "done"`, gọi `fetchModules()` + `onImportDone()`                                                                       |
| `handleBuildDocs` / `handleRelint`                                                       | `POST /docs/build` / `/docs/relint`                 | Build hoặc lint lại                                                                                                                                                                                      |
| `openBundleEditor`                                                                       | `GET /docs/bundle-content`                          | Mở modal, set `bundleContent`                                                                                                                                                                            |
| `saveBundle` / `saveAndRelint`                                                           | `PUT /docs/bundle-content` (+ `POST /docs/relint`)  | Lưu bundle YAML thô qua `putBundleContent()` dùng chung; có check `res.ok` và `alert` nếu lỗi                                                                                                            |
| `handleAiFixBundle`                                                                      | `POST /docs/bundle/ai-fix`                          | Gửi bundle + lỗi lint hiện có, nhận `{patches, unresolved}`, mở `AiFixPanel` (chưa lưu)                                                                                                                  |
| `applyAiFixResolutions`                                                                  | `PUT /docs/bundle-content` (qua `putBundleContent`) | Ghép từng patch (theo lựa chọn original/fixed/both) vào `bundleContent` từ dòng cuối lên đầu (tránh lệch số dòng), rồi **lưu ngay xuống backend** — bấm "Áp dụng" là lưu luôn, không cần bấm "Lưu" riêng |
| `handleResolveConflict`                                                                  | `POST /modules/manual-edit-conflicts/resolve`       | Resolve 1 conflict (`keep_old`/`accept_new`), tự xoá khỏi `conflicts` state khi thành công                                                                                                               |

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
- **Tab "YAML thô"** → render `BundleEditor` (`./BundleEditor`, Monaco editor thường), dùng `content`/`onChange`/`onSave`/`onSaveAndRelint`/`onAiFix` từ props (điều khiển bởi `page.tsx`)
- Footer Lưu/Lưu & Kiểm tra/AI tự fix lỗi chỉ hiện ở tab YAML — tab Form có nút riêng trong chính nó

---

## `AiFixPanel.tsx` — panel riêng, không lồng trong modal

Render ở `page.tsx` top-level (`{showAiFixPanel && <AiFixPanel ... />}`), **độc lập** với
`BundleEditorModal` — mở từ nút "AI tự fix lỗi" trong tab YAML thô nhưng hiện full-screen đè lên
trên, không phải 1 tab/section của modal.

**Luồng:**

```
Bấm "AI tự fix lỗi" → handleAiFixBundle (POST /docs/bundle/ai-fix) → mở AiFixPanel
Mỗi patch hiện 1 DiffEditor (Monaco, gốc/sửa cạnh nhau, originalEditable: true — sửa tay được cả 2 bên)
  + badge danh sách issue + 3 nút chọn: "Giữ bản gốc" / "Giữ bản AI đã sửa" / "Giữ cả hai"
Bấm "Áp dụng" → đọc nội dung MỚI NHẤT trực tiếp từ từng Monaco editor (không qua React state,
  vì props original/modified của DiffEditor cố định từ lúc AI trả kết quả — đổi prop mỗi keystroke
  sẽ làm Monaco tạo lại model và nhảy con trỏ) → gỡ model (detachAllModels, tránh lỗi Monaco log
  "TextModel got disposed...") → applyAiFixResolutions() ghép patch vào bundleContent + PUT lưu ngay
Bấm "Hủy" → gỡ model, đóng panel, không đổi gì
```

`unresolved` (lỗi AI không xác định được vị trí để sửa) hiện riêng 1 khối cảnh báo, không có
DiffEditor — chỉ liệt kê để dev tự sửa tay.

---

## `OperationsFormEditor.tsx`

Form editor cho non-dev — không cần biết YAML.

**Luồng:**

```
Mount → GET /docs/operations → list operations
Group theo tags, hiển thị card cho mỗi endpoint:
  - Method badge (màu theo HTTP method) + path (read-only) + badge "x% hoàn chỉnh"
  - Input "Tên gọi" (summary)
  - Textarea "Mô tả chi tiết" (description)
  - Input mô tả cho từng parameter (nếu operation có parameters)
  - Input mô tả cho từng response (nếu operation có responses không bị $ref)
  - Nút "Gợi ý AI" → POST /docs/operations/ai-suggest, chỉ điền field đang trống
Edit → đánh dấu dirty (viền vàng, "● chưa lưu")
[Lưu] → PATCH /docs/operations (chỉ gửi operation đã đổi, kèm parameters/responses)
[Lưu & Kiểm tra lại] → Lưu rồi POST /docs/relint, hiện số lỗi
```

**Chỉ cho sửa field mô tả (human-readable):** `summary`, `description`, `parameters[].description`, `responses[].description`. Method, path, parameter name/type, schema, response codes, và response dùng `$ref` chung (400/401/404...) hiển thị read-only hoặc bị loại khỏi danh sách sửa — tránh vô tình làm hỏng cấu trúc API hoặc sửa 1 operation làm ảnh hưởng operation khác dùng chung `$ref`.

**Badge % hoàn chỉnh:** tính theo tỉ lệ field có mô tả / tổng field cần điền (`2 + số parameters + số responses`), cập nhật real-time khi gõ. Màu: xanh (100%), vàng (50-99%), đỏ (<50%).

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

## `ManualEditConflictsCard.tsx`

Hiện khi có ít nhất 1 field bị xung đột giữa giá trị sửa tay (Form Editor/YAML thô/AI-fix) và giá trị
mới do `run_batch()` ghi đè trong lần import gần nhất (xem `docs/backend.md` mục **Persist sửa tay qua
tầng 2**). Component tự `return null` khi `!loading && conflicts.length === 0 && !error` — kèm 1
lượt "Đang tải..." chớp nhanh lúc trang vừa mount, trước khi fetch xong (rough edge nhỏ, chưa fix).

Mỗi entry hiện `operationId` + tên field + giá trị cũ/mới (chuỗi rỗng hiện `<em>(rỗng)</em>` thay vì
khoảng trắng), 2 nút:

- **"Giữ bản cũ"** → `POST .../resolve` với `choice: "keep_old"` — ghi giá trị cũ lại tầng 2 + tầng 3.
- **"Lấy bản mới"** → `choice: "accept_new"` — không đổi gì, chỉ xoá khỏi queue.

Resolve xong, entry tự biến mất khỏi danh sách không cần reload trang (cập nhật state local sau khi
API trả OK, theo `conflictKey = operationId::field` để biết đúng entry nào đang xử lý — cho phép
nhiều entry resolve song song không lẫn nhau). Mất kết nối backend giữa lúc bấm nút → hiện lỗi
"Không thể kết nối tới backend...", nút trở lại bấm được ngay, entry **không** bị xoá khỏi queue.

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

---

## Giao tiếp với Backend

Base URL: `process.env.NEXT_PUBLIC_API_URL` (set trong `frontend/.env.local`).

| Nhóm                  | Endpoint dùng                                                                                                                                                                                |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scan/Module           | `/modules/scan`, `/modules`, `/modules/{m}/activate`, `/modules/{m}/deactivate`, `/modules/import`, `/modules/import/{id}/stream`                                                            |
| Suggest               | `/modules/suggestions`, `/modules/suggest`, `/modules/suggestions/approve`, `/modules/apply`                                                                                                 |
| Source                | `/source/upload`                                                                                                                                                                             |
| Docs                  | `/docs/build`, `/docs/status`, `/docs/bundle-content` (GET/PUT), `/docs/relint`, `/docs/download-html`, `/docs/operations` (GET/PATCH), `/docs/operations/ai-suggest`, `/docs/bundle/ai-fix` |
| Manual edit conflicts | `/modules/manual-edit-conflicts` (GET), `/modules/manual-edit-conflicts/resolve` (POST)                                                                                                      |

Đây là **toàn bộ** endpoint backend hiện có — không còn route `/jobs/*` nào.

---

## Xử lý lỗi & mã lỗi

`app/_dashboard/api.ts` là điểm tập trung duy nhất cho fetch + parse lỗi, dùng bởi cả 6 hook và
`OperationsFormEditor.tsx`:

```typescript
export async function readErrorDetail(res: Response): Promise<string>; // đọc + map lỗi → chuỗi hiển thị
export async function apiFetch<T>(url, init?): Promise<T>; // fetch + throw new Error(readErrorDetail) nếu !res.ok
export function formatFetchError(e: unknown, fallback?): string; // dùng trong catch (e), không phải trong fetch
```

**Backend trả `detail: {code, message}`** (xem `docs/backend.md` mục Hệ thống mã lỗi).
`readErrorDetail` đọc `code` + `message` từ đó, đưa qua `resolveErrorMessage(code, message)`
(`errorMessages.ts`) — nếu `code` có trong `ERROR_MESSAGES` thì hiển thị chữ override, không thì
fallback về `message` gốc của backend. Lỗi 422 validation của FastAPI (`detail` là `list`) và lỗi
không parse được JSON đều fallback về `res.statusText`.

**Tự override chữ hiển thị cho 1 mã lỗi** — chỉ cần sửa `app/_dashboard/errorMessages.ts`, không
cần đụng tới hook hay component nào khác:

```typescript
export const ERROR_MESSAGES: Record<string, string> = {
  BUNDLE_NOT_FOUND: 'Chưa có tài liệu — bấm "Build tài liệu" trước nhé',
};
```

Hiện để trống — chưa override mã nào, mọi lỗi đang hiển thị đúng `message` gốc từ backend.

**`formatFetchError` phân biệt `TypeError`** — khi `fetch()` tự throw vì mất kết nối hẳn tới
backend (server tắt, sai URL), lỗi là `TypeError` ("Failed to fetch"/"NetworkError..."), xảy ra
**trước khi có `Response`** nên không có `code`. Nhánh riêng cho `TypeError` hiện chữ "Không thể
kết nối tới backend, kiểm tra server có đang chạy không" thay vì message kỹ thuật thô của browser.

---

## Các điểm kỹ thuật đáng chú ý

**State pattern nhất quán** — mọi async action theo công thức `setLoading(true) → fetch → setX(data)/setError(e) → setLoading(false)`.

**SSE thay vì polling** — `/modules/import/{id}/stream` dùng `EventSource`, đóng khi nhận `event: "done"` hoặc `onerror`.

**Dynamic import Monaco** — lazy load, `ssr: false` vì Monaco chỉ chạy trên browser, dùng ở cả `BundleEditor.tsx` (editor thường) và `AiFixPanel.tsx` (`DiffEditor`):

```typescript
const BundleEditor = dynamic(() => import("./BundleEditor"), { ssr: false });
const DiffEditor = dynamic(() => import("@monaco-editor/react").then((m) => m.DiffEditor), { ssr: false });
```

**`MonacoErrorSuppressor`** (`app/MonacoErrorSuppressor.tsx`, mount trong `layout.tsx` ở root) — nuốt
`unhandledrejection` có `reason.type === "cancelation"`, lỗi nội bộ vô hại của Monaco khi 1 thao tác
bị huỷ giữa chừng (vd đóng editor khi đang gõ), không phải lỗi thật cần báo console.

**`useMounted()` pattern** (`app/_dashboard/hooks/useMounted.ts`) — dùng trong `ModuleRegistryCard` và `SuggestCard` để tránh hydration mismatch khi disable button dựa trên state client-only (`suppressHydrationWarning`).

**`ErrorAlert`** (`app/_dashboard/ErrorAlert.tsx`) — UI báo lỗi dùng chung, thay 9 chỗ `<div>` trùng lặp trước đây; nhận `message` + `className` tuỳ chọn để giữ margin riêng của từng nơi gọi.

---

## Thiếu sót hiện tại (Known Gaps)

| Vấn đề                                                  | Ghi chú                                                                                                                       |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Không có nút Publish                                    | Chỉ có "Tải HTML" thủ công, chưa có commit+push tự động                                                                       |
| Không có auth                                           | Dashboard mở public trong mạng nội bộ                                                                                         |
| `app/portal/` không được link từ nav                    | Trùng chức năng với `/swagger`, vẫn muốn giữ lại để sau này muốn thay đổi dùng giao diện khác swagger thì gọi nó ra.          |
| `ManualEditConflictsCard` flash "Đang tải..." lúc mount | UX rough edge nhỏ, chưa fix — xem mục riêng phía trên                                                                         |
| Chất lượng AI-fix khi batch nhiều operation             | Không phải bug frontend — xem `docs/backend.md` mục AI-fix breadcrumb/parent context + `docs/manual-test-checklist.md` DEF-04 |
