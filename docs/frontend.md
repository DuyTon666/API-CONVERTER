# Frontend — API Converter

> Cập nhật lần cuối: 16/07/2026 — đối chiếu lại trực tiếp với cây thư mục `frontend/` thật trong repo (trước đó tài liệu này vẫn mô tả layout cũ `app/_dashboard/`, đã bị tách ra từ lâu).

## Tổng quan

Dashboard 1 trang (`app/page.tsx`) cho toàn bộ workflow: import tài liệu → scan → gợi ý/duyệt module → import → build tài liệu Swagger → chỉnh sửa nội dung (form + schema fields) → review mã lỗi nghiệp vụ → review xung đột sửa tay → deploy. State tách thành **9** custom hook (`hooks/dashboard/`), `page.tsx` chỉ compose hook + render layout; các "card" con (`components/dashboard/`) chỉ render UI + nhận callback qua props. Gọi API tách riêng thành `lib/api/dashboard/*.ts`, mỗi file 1 domain.

> Route `app/jobs/[job_id]/` (upload đơn lẻ, luồng cũ) đã bị **xóa** từ lâu — không có nơi nào trong UI link tới nó và không có cách tạo job (`POST /jobs` không tồn tại nữa ở backend).

---

## Công nghệ

| Công nghệ                                  | Vai trò                                                                                                                                                              |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Next.js** (App Router)                   | Framework React — có cả trang client-only (dashboard) lẫn Server Component (`app/portal/page.tsx`) và Route Handler (`app/api/deploy-docs`, `app/api/create-doc-pr`) |
| **React**                                  | UI, state qua custom hook (`hooks/dashboard/`), không dùng store ngoài                                                                                               |
| **TypeScript**                             | Type safety                                                                                                                                                          |
| **Tailwind CSS**                           | Styling                                                                                                                                                              |
| **Monaco Editor** (`@monaco-editor/react`) | `BundleEditor` (tab "YAML thô") dùng editor thường; `AiFixPanel` dùng `DiffEditor` (so sánh gốc/đã sửa, cho sửa tay cả 2 bên)                                        |
| **sonner**                                 | Toast — dùng cho feedback các action async (deploy, resolve/apply mã lỗi...), thay banner inline                                                                     |
| `components/ui/*` (button, select, tabs)   | UI primitive nhỏ kiểu shadcn, dùng trong `OperationsFormEditor`                                                                                                      |

> Next.js version này có breaking changes — đọc `node_modules/next/dist/docs/` trước khi code (xem `frontend/AGENTS.md`).

---

## Cấu trúc thư mục

```
frontend/
├── app/
│   ├── page.tsx                       # Dashboard chính — compose 9 hook + render layout
│   ├── layout.tsx                     # Root layout, mount MonacoErrorSuppressor + Toaster (sonner)
│   ├── MonacoErrorSuppressor.tsx      # Nuốt unhandledrejection "cancelation" nội bộ của Monaco (không phải lỗi thật)
│   ├── globals.css
│   ├── api/
│   │   ├── deploy-docs/route.ts       # POST — commit 5.openapi/** qua GitHub Git Data API + dispatch create-doc-pr.yaml (nút "Deploy tài liệu")
│   │   └── create-doc-pr/route.ts     # ORPHAN — chỉ dispatch workflow, không commit; không có caller nào trong UI
│   ├── swagger/
│   │   ├── page.tsx
│   │   └── SwaggerView.tsx            # Render Swagger UI từ bundle, Fuse.js fuzzy search tích hợp vào opsFilter
│   └── portal/                        # Developer Portal tự build (KHÔNG link từ nav — xem mục riêng)
│       ├── page.tsx                   # Server Component — đọc bundle YAML trực tiếp từ đĩa, resolve $ref
│       ├── PortalSearch.tsx           # Search/filter bằng Fuse.js (client component)
│       ├── EndpointCard.tsx           # Card hiển thị 1 operation trong list
│       ├── EndpointDetailDrawer.tsx   # Drawer chi tiết khi click vào 1 operation
│       ├── SchemaViewer.tsx           # Render schema object dạng cây
│       ├── TryItOut.tsx               # Gọi request thật (fetch trực tiếp từ browser), copy as curl, arm/confirm cho method mutating
│       ├── theme.ts                   # methodTone/statusTone/categoryTone (màu pastel theo HTTP method/status), MUTATING_METHODS
│       └── openapi-utils.ts           # generateExample() — sinh JSON mẫu từ schema (đệ quy, hỗ trợ allOf/anyOf/oneOf) cho ô Request body của TryItOut
├── components/
│   ├── ui/                            # UI primitive nhỏ (button, select, tabs, sonner Toaster wrapper)
│   └── dashboard/
│       ├── ImportCard.tsx             # Upload file vào 1.docs/source/api_contract/
│       ├── ScanCard.tsx                # Hiển thị kết quả /modules/scan
│       ├── SuggestCard.tsx             # Gợi ý/duyệt/apply module assignment
│       ├── ModuleRegistryCard.tsx      # Bảng module + activate/deactivate + import (SSE)
│       ├── ManualEditConflictsCard.tsx # Danh sách field bị conflict giữa sửa tay và import lại
│       ├── ErrorCodesReviewCard.tsx    # Review & xác nhận mã lỗi nghiệp vụ (x-error-responses) trước khi ghi 4.config/errors/
│       ├── SwaggerDocsCard.tsx         # Build/lint/download tài liệu, mở Bundle Editor, nút Deploy
│       ├── BundleEditorModal.tsx       # Modal full-screen, 2 tab: Form Editor + YAML thô
│       ├── BundleEditor.tsx            # Wrapper Monaco Editor thường (tab "YAML thô")
│       ├── AiFixPanel.tsx              # Panel riêng (không nằm trong modal) — DiffEditor per-patch
│       ├── OperationsFormEditor.tsx    # Tab "Chỉnh sửa nội dung" — sửa summary/description + nhúng SchemaFieldsEditor cho request/response
│       ├── SchemaFieldsEditor.tsx      # Renderer đệ quy cho 1 SchemaGroup (request/response của 1 operation) — indent theo depth, schema shared hiện disabled
│       ├── ErrorAlert.tsx              # UI báo lỗi dùng chung
│       ├── StatTiles.tsx               # Ô số liệu tổng quan trên dashboard
│       ├── WorkflowStepper.tsx         # Thanh bước sticky (scan→suggest→apply→import→docs)
│       └── StepSection.tsx             # Timeline dọc giữa trang, cùng ngôn ngữ hình ảnh với WorkflowStepper
├── hooks/dashboard/
│   ├── useMounted.ts                  # Mount-detection — tránh SSR/CSR hydration mismatch
│   ├── useActiveStep.ts               # Scrollspy dùng chung cho WorkflowStepper + StepSection (1 IntersectionObserver)
│   ├── useScan.ts
│   ├── useModuleRegistry.ts
│   ├── useUpload.ts
│   ├── useDocsBuilder.ts              # build/lint/bundle-editor/AI-fix + deploy state
│   ├── useSuggestions.ts
│   ├── useManualEditConflicts.ts
│   └── useErrorCodes.ts               # Review mã lỗi nghiệp vụ — entriesByModule, resolve/apply
├── lib/
│   ├── api/
│   │   ├── client.ts                  # apiFetch/readErrorDetail/formatFetchError dùng chung mọi hook
│   │   ├── errorMessages.ts           # ERROR_MESSAGES override map + resolveErrorMessage()
│   │   └── dashboard/                 # 1 file/domain: docs.ts, modules.ts, operations.ts, schemaFields.ts, suggestions.ts, upload.ts, deploy.ts, errorCodes.ts
│   ├── dashboard-format.ts            # formatDate/formatRelativeTime/formatBytes, SUPPORTED_EXTENSIONS, isSupportedFile, countLintIssues, getDeployBlockedReason
│   └── utils.ts                       # cn() (clsx/tailwind-merge) cho components/ui
├── types/dashboard.ts                 # Toàn bộ type dùng chung: ScanResult, ModuleListResult, DocsBuildResult, ErrorReviewEntry/Report, OperationDataSchemas...
└── package.json
```

---

## Dashboard chính — `app/page.tsx`
### State — 9 custom hook (`hooks/dashboard/`)

`page.tsx` chỉ gọi 9 hook dưới đây và destructure ra props cho card con — không tự giữ state nào
khác ngoài giá trị dẫn xuất (`pendingSuggestions`, `activeModules`, `steps`, `bundleReady`/`htmlReady`...).

| Hook                                           | Owns                                                                                        | Gọi API                                                                                                               |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `useScan(backend)`                             | `scan` / `scanLoading` / `scanError` / `fetchScan`                                          | `GET /modules/scan`                                                                                                   |
| `useManualEditConflicts(backend)`              | `conflicts` / `loading` / `error` / `resolving` / `conflictKey`                             | `GET /modules/manual-edit-conflicts`, `POST /modules/manual-edit-conflicts/resolve`                                   |
| `useModuleRegistry(backend, { onImportDone })` | `moduleList`, activate/deactivate state, import state (SSE)                                 | `GET /modules`, `POST /modules/{m}/activate`/`deactivate`, `POST /modules/import` + `GET /modules/import/{id}/stream` |
| `useUpload(backend, { onSuccess })`            | `uploadFiles` / `uploading`                                                                 | `POST /source/upload`                                                                                                 |
| `useDocsBuilder(backend)`                      | `docsBuilding` / `docsResult` / `docsStatus` / `bundleContent` / `deploying` + AI-fix state | `POST /docs/build`, `/docs/relint`, `/docs/bundle/ai-fix`, `GET`/`PUT /docs/bundle-content`, `POST /api/deploy-docs`  |
| `useSuggestions(backend, { onApplySuccess })`  | `suggestions` / `suggestRunning` / `approving` / `applying` / `applyResult`                 | `GET /modules/suggestions`, `POST /modules/suggest`/`suggestions/approve`/`apply`                                     |
| `useErrorCodes(backend, modules)`              | `entriesByModule` (per module) / `loading` / `resolving` / `applying`                       | `GET /errors/{module}`, `POST /errors/{module}/resolve`/`apply`                                                       |
| `useMounted()`                                 | `mounted: boolean`                                                                          | — (không gọi API, chỉ dùng để gate render đầu tiên ở client khớp SSR)                                                 |
| `useActiveStep(stepIds)`                       | `activeIndex: number`                                                                       | — (chỉ đọc DOM qua `IntersectionObserver`)                                                                            |

`useUpload`, `useSuggestions`, `useModuleRegistry` có phụ thuộc lẫn hook khác — giải quyết bằng
**callback injection** (`onSuccess`/`onApplySuccess`/`onImportDone` truyền từ `page.tsx`), không
hook nào import hook khác. `onImportDone` gọi `fetchConflicts()` — vì import xong là lúc xung đột
sửa tay mới (nếu có) xuất hiện. Nhờ vậy chỉ có đúng 1 instance của mỗi hook, sở hữu bởi `page.tsx`.

Mọi hook gọi API dùng chung `apiFetch`/`readErrorDetail`/`formatFetchError` từ `lib/api/client.ts`
(xem mục **Xử lý lỗi & mã lỗi** phía dưới); mỗi hook import file domain riêng trong `lib/api/dashboard/`
thay vì gọi `fetch` trực tiếp.

### Các hàm chính (nằm trong các hook trên)

| Hàm                                                                                      | Gọi API                                            | Mô tả                                                                                                                                                                                                   |
| ---------------------------------------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fetchScan` / `fetchModules` / `fetchSuggestions` / `fetchDocsStatus` / `fetchConflicts` | `GET`                                              | Chạy 1 lần khi mount (`useEffect([])`)                                                                                                                                                                  |
| `handleUpload`                                                                           | `POST /source/upload`                              | Upload file thô, không convert ngay — `handleSelectFiles` lọc theo `isSupportedFile()` trước khi cho vào danh sách chờ (chặn cả kéo-thả lẫn bypass hộp thoại chọn file)                                 |
| `handleRunSuggest`                                                                       | `POST /modules/suggest`                            | Chạy phân tích (30–90s)                                                                                                                                                                                 |
| `handleApprove` / `handleApproveSelected`                                                | `POST /modules/suggestions/approve`                | Duyệt 1 hoặc nhiều file (mode `file`/`module`/`all`)                                                                                                                                                    |
| `handleApply` (suggestions)                                                              | `POST /modules/apply`                              | Copy file đã duyệt vào thư mục module                                                                                                                                                                   |
| `handleActivate` / `handleDeactivate`                                                    | `POST /modules/{m}/activate` / `deactivate`        | Đổi trạng thái module                                                                                                                                                                                   |
| `handleImport`                                                                           | `POST /modules/import` + SSE                       | Mở `EventSource`, cập nhật `importModules` theo từng event, đóng khi nhận `event: "done"`, gọi `fetchModules()` + `onImportDone()`                                                                      |
| `handleBuildDocs` / `handleRelint`                                                       | `POST /docs/build` / `/docs/relint`                | Build hoặc lint lại                                                                                                                                                                                     |
| `handleDeploy`                                                                           | `POST /api/deploy-docs`                            | Toast kết quả (luôn hiện, không gate theo field tuỳ chọn nào), rồi `setDocsResult(null)` — bắt buộc phải "Kiểm tra lỗi" lại trước khi bấm Deploy lần nữa, tránh bấm liên tiếp tạo nhiều PR/branch trùng |
| `openBundleEditor`                                                                       | `GET /docs/bundle-content`                         | Mở modal, set `bundleContent`                                                                                                                                                                           |
| `saveBundle` / `saveAndRelint`                                                           | `PUT /docs/bundle-content` (+ `POST /docs/relint`) | Lưu bundle YAML thô                                                                                                                                                                                     |
| `handleAiFixBundle`                                                                      | `POST /docs/bundle/ai-fix`                         | Gửi bundle + lỗi lint hiện có, nhận `{patches, unresolved}`, mở `AiFixPanel` (chưa lưu)                                                                                                                 |
| `applyAiFixResolutions`                                                                  | `PUT /docs/bundle-content`                         | Ghép từng patch vào `bundleContent` từ dòng cuối lên đầu (tránh lệch số dòng), lưu ngay xuống backend                                                                                                   |
| `handleResolveConflict`                                                                  | `POST /modules/manual-edit-conflicts/resolve`      | Resolve 1 conflict (`keep_old`/`accept_new`), tự xoá khỏi `conflicts` state khi thành công                                                                                                              |
| `handleResolveErrorEntry` / `handleApplyErrorEntries`                                    | `POST /errors/{m}/resolve` / `/apply`              | Xem mục **`ErrorCodesReviewCard.tsx`** bên dưới                                                                                                                                                         |

---

## `ErrorCodesReviewCard.tsx` — Review mã lỗi nghiệp vụ

1 card duy nhất (không phải 1 card/module) — bên trong có dropdown chọn module đang xem, danh sách entry của module đó, và badge "N cần duyệt" ở header.

**Nguồn dữ liệu:** report do CLI `errors:parse` (2.pipeline, chạy tay bởi người phụ trách 2.pipeline) sinh ra tại `3.build/reports/errors/<module>/error_codes_review.json`. Mỗi entry có `code`, `status` (`new`/`duplicate_ok`/`conflict`/`needs_review`), `incoming` (nội dung từ tài liệu mới), `existing_in_map` (nếu đã có trong catalog), `resolution` (quyết định đã chọn, null nếu chưa), và `applied_at` (thời điểm quyết định thật sự được đẩy vào `4.config/errors/`, lấy từ `review_decisions.yaml` — null nếu đã resolve nhưng chưa apply).

**Quyết định cho từng entry:** giữ nguyên map cũ / duyệt là mã mới / sửa lại message cũ / đổi sang mã khác — gọi `POST /errors/{module}/resolve`, chỉ ghi `resolution` vào report, **chưa** đẩy vào config chính thức.

**"Xác nhận module" (apply):** gọi `POST /errors/{module}/apply` — đẩy toàn bộ entry đã resolve trong report lên `4.config/errors/global_error_map.yaml` hoặc `modules/<module>/error_catalog.yaml`. Entry chưa resolve tự bị bỏ qua (skipped).

**Ẩn/hiện cả card:** card tự ẩn khi không còn entry nào "cần chú ý" ở bất kỳ module nào — định nghĩa 1 entry còn cần chú ý là: chưa có `resolution`, HOẶC đã có `resolution` nhưng chưa có `applied_at` (đã resolve nhưng chưa bấm Apply); `duplicate_ok` luôn loại trừ. Tính lại mỗi lần render/fetch từ dữ liệu thật (`applied_at`), không phải suy đoán/heuristic lưu riêng — nên card **tự hiện lại đúng lúc** khi report được parse lại và có entry/conflict mới (cùng code, message khác → `applied_at` không khớp → tự động cần chú ý lại), và trạng thái trước/sau reload trang luôn nhất quán.

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
- **Tab "YAML thô"** → render `BundleEditor` (Monaco editor thường), dùng `content`/`onChange`/`onSave`/`onSaveAndRelint`/`onAiFix` từ props (điều khiển bởi `page.tsx`)
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

## `OperationsFormEditor.tsx` (+ `SchemaFieldsEditor.tsx`)

Form editor cho non-dev — không cần biết YAML. Mỗi operation collapse thành 1 dòng theo mặc định
(method/path/summary/% hoàn chỉnh, kiểu Swagger UI) — click để mở form đầy đủ.

**Luồng:**

```
Mount → GET /docs/operations + GET /docs/schema-fields (song song) → list operations + data schemas
Group theo tags, hiển thị card cho mỗi endpoint:
  - Method badge (màu theo HTTP method) + path (read-only) + badge "x% hoàn chỉnh"
  - Input "Tên gọi" (summary)
  - Textarea "Mô tả chi tiết" (description)
  - Input mô tả cho từng parameter (nếu operation có parameters)
  - Input mô tả cho từng response (nếu operation có responses không bị $ref)
  - SchemaFieldsEditor cho request (nếu có) và response (nếu có) — mô tả từng field trong business schema
  - Nút "Gợi ý AI" → POST /docs/operations/ai-suggest, chỉ điền field đang trống (cả summary/description lẫn field schema trống, qua dataSchemas payload)
Edit → đánh dấu dirty (viền vàng, "● chưa lưu")
[Lưu] → PATCH /docs/operations (operation level) + PATCH /docs/schema-fields (schema field level, nếu có đổi)
[Lưu & Kiểm tra lại] → Lưu rồi POST /docs/relint, hiện số lỗi
```

**`SchemaFieldsEditor.tsx`** — renderer đệ quy cho 1 `SchemaGroup` (`services/schema_fields.py` phía backend resolve request/response business schema của 1 operation, unwrap `allOf`/`StandardSuccess`, walk `properties` đệ quy). Mỗi field là 1 dòng thụt lề theo độ sâu; schema nào bị dùng chung bởi >1 operation (`shared: true`, ví dụ `UserInfo`) hiện disabled kèm ghi chú — sửa loại schema này chỉ làm được qua tab YAML thô, tránh 1 operation sửa mô tả field làm thay đổi ý nghĩa ở mọi operation khác dùng chung schema đó.

**Chỉ cho sửa field mô tả (human-readable):** `summary`, `description`, `parameters[].description`, `responses[].description`, và `description` của từng field trong schema (không shared). Method, path, parameter name/type, schema type, response codes, và schema `shared: true` hiển thị read-only hoặc bị loại khỏi danh sách sửa.

**Badge % hoàn chỉnh:** tính theo tỉ lệ field có mô tả / tổng field cần điền, cập nhật real-time khi gõ. Màu: xanh (100%), vàng (50-99%), đỏ (<50%).

**Search + filter:** theo path/summary (text) và theo tag (dropdown).

---

## `SwaggerDocsCard.tsx`

```
[Build tài liệu Swagger UI]                                              ← khi chưa có bundle
hoặc
[Xem / Sửa lỗi bundle] [Kiểm tra lỗi] [Tải HTML] [Tạo lại tài liệu]      ← khi đã có bundle
[Deploy tài liệu]                                                        ← luôn hiện, disable theo getDeployBlockedReason()
```

Hiển thị kết quả lint (Spectral + Redocly) dạng list, màu đỏ = error, vàng = warning. Nút "Xem / Sửa lỗi bundle" mở `BundleEditorModal`.

**Nút Deploy** — `getDeployBlockedReason()` (`lib/dashboard-format.ts`) chặn theo thứ tự: chưa có bundle → chưa "Kiểm tra lỗi" lần nào (`docsResult` null) → còn lỗi `error` → đang có thao tác khác chạy. Xem mục **Deploy tài liệu** bên dưới cho luồng đầy đủ, và mục **Hydration mismatch** ở "Các điểm kỹ thuật đáng chú ý" cho lý do `bundleReady`/`htmlReady` phải gate qua `mounted`.

---

## `ModuleRegistryCard.tsx`

Bảng module: tên, status (badge màu: active=xanh, draft=vàng, deprecated=xám), file_count, endpoint_count, last_import (relative time + tooltip absolute).

Nút theo status:

- `draft`/`deprecated` → **Activate**
- `active` → **Import** (riêng module này) + **Deactivate**

Nút "Import tất cả" ở header — disable nếu không có module nào active (gate thêm `!mounted` vì `moduleList` fetch qua effect, xem mục hydration).

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

Resolve xong, entry tự biến mất khỏi danh sách không cần reload trang. Mất kết nối backend giữa lúc
bấm nút → hiện lỗi "Không thể kết nối tới backend...", nút trở lại bấm được ngay, entry **không** bị
xoá khỏi queue.

---

## `SuggestCard.tsx`

Bảng suggestion với checkbox chọn nhiều, filter tab Chờ duyệt/Đã duyệt/Tất cả. Mỗi dòng hiện endpoint, method, module gợi ý, conflict warning (nếu `service_in_doc` khác `final_module`), input override module. Nút "Duyệt (N) file" duyệt các file đã check, "Apply suggestions" copy file đã duyệt vào thư mục module.

---

## `WorkflowStepper.tsx` + `StepSection.tsx` + `useActiveStep`

`WorkflowStepper` là thanh bước sticky ở trên (scan→suggest→apply→import→docs); `StepSection` là timeline dọc bọc quanh từng khối nội dung chính giữa trang. Cả 2 dùng chung 1 `useActiveStep(stepIds)` — 1 `IntersectionObserver` duy nhất theo dõi section nào đang ở đầu viewport (`rootMargin: "-30% 0px -60% 0px"`), tránh 2 nơi tự chạy observer trùng nhau trên cùng tập phần tử, đảm bảo 2 chỗ luôn hiển thị đúng cùng 1 bước "đang active".

---

## `app/swagger/SwaggerView.tsx`

Render Swagger UI từ `dist/openapi-bundled.yaml`. Tích hợp **Fuse.js** vào search bar mặc định của Swagger UI qua plugin `opsFilter` (không dùng search bar riêng):

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

Cũng render bảng `x-error-responses` (mã lỗi nghiệp vụ) lồng vào từng dòng response qua plugin `wrapComponents.response` — đọc `operation.x-error-responses[status]`, chèn `<details>` gấp/mở danh sách mã lỗi ngay dưới response đó.

`scripts/build-swagger-ui.js` (build static HTML cho `public/api-docs.html`, chạy trong `deploy.yaml`/`npm run build:docs`) dùng **cùng approach** cho cả 2 plugin (Fuse.js filter + bảng mã lỗi) — bản JS thuần không qua JSX/React của Next, vì trang static chỉ có React đóng gói sẵn trong `swagger-ui-bundle.js`.

---

## `app/portal/` — Developer Portal tự build (⚠ chưa được link tới)

Route `/portal` render 1 giao diện xem API docs **tự thiết kế** (không dùng thư viện Swagger UI):

```
┌──────────────────────────────────────────────┐
│  Search... [GET][POST][PUT]...  [Tag ▼]      │
├──────────────────────────────────────────────┤
│  EndpointCard: GET /v1/tickets   "Lấy ds..." │
│  EndpointCard: POST /v1/tickets  "Tạo..."    │
├──────────────────────────────────────────────┤
│  Click 1 card → EndpointDetailDrawer mở:     │
│    parameters, request/response schema        │
│    (SchemaViewer dạng cây) + panel Try it out │
└──────────────────────────────────────────────┘
```

**Luồng:** `page.tsx` là Server Component — đọc trực tiếp `dist/openapi-bundled.yaml` bằng `fs.readFileSync` lúc render (không qua backend API), tự resolve `$ref` (đệ quy tối đa 10 cấp), trích operations rồi truyền cho `PortalSearch` (client component) render + search bằng Fuse.js riêng.

**`TryItOut.tsx`** — panel gọi request thật ngay trong trình duyệt (`fetch()` trực tiếp tới `baseUrl` lấy từ spec `servers`), không qua backend Next.js nào cả:
- Build URL từ path/query param, header param nhập tay.
- Method mutating (`POST`/`PUT`/`PATCH`/`DELETE`, theo `MUTATING_METHODS` trong `theme.ts`) phải bấm **2 lần** ("Gửi request" → "Xác nhận gửi (production)") mới thật sự gửi — tránh bấm nhầm gây side-effect thật trên server production.
- Ô Request body tự sinh JSON mẫu từ schema qua `generateExample()` (`openapi-utils.ts`, đệ quy, hỗ trợ `allOf`/`anyOf`/`oneOf`, format `date-time`, giới hạn độ sâu 5 cấp tránh đệ quy vô hạn khi schema tự tham chiếu).
- Nút "Copy as curl" — build lại đúng command từ url/headers/body hiện tại.
- Lỗi mạng/CORS hiện thông báo riêng, không phải lỗi kỹ thuật thô của `fetch`.

---

## Deploy tài liệu (`app/api/deploy-docs/route.ts`)

Nút "Deploy tài liệu" (`SwaggerDocsCard`) → `useDocsBuilder`'s `handleDeploy()` → `deployDocs()` (`lib/api/dashboard/deploy.ts`) → `POST /api/deploy-docs` (Next.js Route Handler, **không** đi qua backend Python).

Route cần 4 biến môi trường (`OPENAPI_DIR`, `GH_DISPATCH_TOKEN`, `GH_OWNER`, `GH_REPO` — xem `docs/setup-local-dev.md`). Luồng: lấy HEAD commit/tree của `baseBranch` ("main"/"develop", mặc định "develop") qua GitHub Git Data API → tính git-blob-SHA1 từng file local trong `OPENAPI_DIR` (chỉ đọc, không phải git checkout) → diff với blob SHA đã có trên remote để tìm file added/modified/deleted dưới `5.openapi/` → nếu không có gì đổi, trả `{ok: true, message: "Không có thay đổi..."}` (không tạo gì cả) → nếu có, tạo blob/tree/commit/ref mới (`auto/update-openapi-<timestamp>`) → dispatch workflow `create-doc-pr.yaml` (bundle lại + mở PR + auto-merge nếu validate pass).

**Toast luôn hiện cho cả 2 nhánh thành công** (`handleDeploy` gọi `toast.success(data.message)` không điều kiện, không gate theo field `branch` tuỳ chọn — sửa lại từ 1 bug cũ khiến nhánh "không có thay đổi" không hiện gì cả). Toast "đã kích hoạt PR" chỉ xác nhận **request gửi thành công** (GitHub nhận dispatch, trả `204`) — không đảm bảo PR đã thật sự tạo/merge, phải tự vào tab Actions/PR trên GitHub để biết kết quả cuối.

**`app/api/create-doc-pr/route.ts`** — route khác, đơn giản hơn (chỉ dispatch workflow, không tự commit) — **không có caller nào trong UI** (orphan), cũng có 1 lỗi nhỏ ở header `Accept` (`application/vn.github+json`, thiếu chữ `d`) — vô hại vì route không dùng tới, nhưng nên sửa nếu sau này hồi sinh route này.

---

## Giao tiếp với Backend

Base URL: `process.env.NEXT_PUBLIC_API_URL` (set trong `frontend/.env.local`).

| Nhóm                                      | Endpoint dùng                                                                                                                                                                                                                   |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scan/Module                               | `/modules/scan`, `/modules`, `/modules/{m}/activate`, `/modules/{m}/deactivate`, `/modules/import`, `/modules/import/{id}/stream`                                                                                               |
| Suggest                                   | `/modules/suggestions`, `/modules/suggest`, `/modules/suggestions/approve`, `/modules/apply`                                                                                                                                    |
| Source                                    | `/source/upload`                                                                                                                                                                                                                |
| Docs                                      | `/docs/build`, `/docs/status`, `/docs/bundle-content` (GET/PUT), `/docs/relint`, `/docs/download-html`, `/docs/operations` (GET/PATCH), `/docs/operations/ai-suggest`, `/docs/bundle/ai-fix`, `/docs/schema-fields` (GET/PATCH) |
| Manual edit conflicts                     | `/modules/manual-edit-conflicts` (GET), `/modules/manual-edit-conflicts/resolve` (POST)                                                                                                                                         |
| Mã lỗi nghiệp vụ                          | `/errors/{module}` (GET), `/errors/{module}/resolve` (POST), `/errors/{module}/apply` (POST)                                                                                                                                    |
| Deploy (Next.js route, không qua backend) | `/api/deploy-docs` (POST) — gọi thẳng GitHub API                                                                                                                                                                                |

Đây là **toàn bộ** endpoint backend hiện có — không còn route `/jobs/*` nào.

---

## Xử lý lỗi & mã lỗi

`lib/api/client.ts` là điểm tập trung duy nhất cho fetch + parse lỗi, dùng bởi mọi hook và
`OperationsFormEditor.tsx`:

```typescript
export async function readErrorDetail(res: Response): Promise<string>; // đọc + map lỗi → chuỗi hiển thị
export async function apiFetch<T>(url, init?): Promise<T>; // fetch + throw new Error(readErrorDetail) nếu !res.ok
export function formatFetchError(e: unknown, fallback?): string; // dùng trong catch (e), không phải trong fetch
```

**Backend trả `detail: {code, message}`** (xem `docs/backend.md` mục Hệ thống mã lỗi).
`readErrorDetail` đọc `code` + `message` từ đó, đưa qua `resolveErrorMessage(code, message)`
(`lib/api/errorMessages.ts`) — nếu `code` có trong `ERROR_MESSAGES` thì hiển thị chữ override, không thì
fallback về `message` gốc của backend. Lỗi 422 validation của FastAPI (`detail` là `list`) và lỗi
không parse được JSON đều fallback về `res.statusText`.

**Tự override chữ hiển thị cho 1 mã lỗi** — chỉ cần sửa `lib/api/errorMessages.ts`, không
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

**Dynamic import Monaco** — lazy load, `ssr: false` vì Monaco chỉ chạy trên browser:

```typescript
const BundleEditor = dynamic(() => import("./BundleEditor"), { ssr: false });
const DiffEditor = dynamic(() => import("@monaco-editor/react").then((m) => m.DiffEditor), { ssr: false });
```

**Hydration mismatch — pattern `useMounted()` + `!mounted ||`**: bất kỳ giá trị nào ảnh hưởng tới thuộc tính render (đặc biệt `disabled`) mà phụ thuộc dữ liệu fetch qua `useEffect` (chỉ chạy ở client, sau mount) đều có nguy cơ SSR render khác với client — vì server không biết trước kết quả fetch đó, còn client (nếu fetch xong đủ nhanh, ví dụ backend chạy local) có thể đã cập nhật state ngay trước khi React kịp so khớp hydration. React **không tự sửa lại DOM** khi phát hiện mismatch này ("won't be patched up", chỉ cảnh báo Console) — DOM giữ nguyên giá trị server đã render cho tới khi có re-render khác đụng tới, gây hiện tượng nút "trông có vẻ enable" dù logic đã tính disable.

Cách xử lý dùng nhất quán trong dự án: gate giá trị phụ thuộc fetch bằng `mounted` (từ `useMounted()`) sao cho **lần render đầu tiên ở client luôn khớp SSR** (ép về `false`/giá trị mặc định), giá trị thật chỉ áp dụng sau khi mount xong — lúc đó là re-render bình thường (không phải hydration-match), DOM được patch đúng qua reconciliation thường. Áp dụng ở 2 mức tuỳ tình huống:
- **Gate ngay tại điểm tính giá trị dùng chung nhiều nơi** — ví dụ `bundleReady`/`htmlReady` (`page.tsx`) chỉ có đúng 1 nguồn tính nhưng dùng ở 3+ chỗ trong `SwaggerDocsCard` (badge trạng thái, nhánh chọn nút build, điều kiện disable nút Deploy) → gate 1 lần ở `page.tsx` (`mounted && (...)`), tự đúng cho mọi nơi dùng.
- **Gate trực tiếp tại `disabled={...}` của từng nút** (kèm `suppressHydrationWarning`) — dùng khi giá trị chỉ ảnh hưởng đúng 1 nút, ví dụ `ModuleRegistryCard`/`SuggestCard` (`!mounted || <điều kiện khác>`).

**`MonacoErrorSuppressor`** (`app/MonacoErrorSuppressor.tsx`, mount trong `layout.tsx` ở root) — nuốt
`unhandledrejection` có `reason.type === "cancelation"`, lỗi nội bộ vô hại của Monaco khi 1 thao tác
bị huỷ giữa chừng (vd đóng editor khi đang gõ), không phải lỗi thật cần báo console.

**`ErrorAlert`** (`components/dashboard/ErrorAlert.tsx`) — UI báo lỗi dùng chung, thay nhiều chỗ `<div>` trùng lặp trước đây; nhận `message` + `className` tuỳ chọn để giữ margin riêng của từng nơi gọi.

---

## Muốn thêm 1 card mới thì làm sao

Toàn bộ 9 hook + card hiện có đều theo đúng 1 khuôn — thêm tính năng mới nên theo lại khuôn này thay vì tự nghĩ cách khác. Ví dụ mẫu cụ thể: `useErrorCodes` → `ErrorCodesReviewCard` (feature "Review mã lỗi nghiệp vụ").

1. **Type** (`types/dashboard.ts`) — định nghĩa shape dữ liệu API trả về/nhận vào, ví dụ `ErrorReviewEntry`, `ErrorReviewReport`.
2. **API wrapper** (`lib/api/dashboard/<tên-domain>.ts`, file mới) — chỉ chứa hàm fetch mỏng, dùng lại `apiFetch`/`readErrorDetail` từ `lib/api/client.ts` — không tự viết `fetch()` thô lại từ đầu. Xem `lib/api/dashboard/errorCodes.ts` làm mẫu (3 hàm: `fetchErrorEntries`/`resolveErrorEntry`/`applyErrorEntries`, mỗi hàm map thẳng 1 endpoint).
3. **Hook** (`hooks/dashboard/use<TênDomain>.ts`, file mới) — giữ state (`useState`) + các hàm `handleXxx` gọi vào API wrapper ở bước 2, trả ra object `{state..., handleXxx}`. Không tự gọi `fetch` trực tiếp trong hook — luôn qua file ở bước 2.
4. **Component** (`components/dashboard/<TênDomain>Card.tsx`, file mới) — **chỉ nhận props**, không tự gọi API, không tự giữ state ngoài UI cục bộ thuần render (input đang gõ, checkbox filter...). Toàn bộ state/handler nghiệp vụ đến từ hook ở bước 3 qua props.
5. **Đăng ký vào `page.tsx`** — gọi hook mới, destructure biến cần, truyền xuống component ở bước 4 qua props, render trong JSX (thường bọc trong `StepSection` nếu nó là 1 bước trong timeline chính, xem cách các `StepSection` hiện có được dùng).

**Nếu card mới cần dữ liệu từ hook khác** (ví dụ cần `moduleNames` từ `useModuleRegistry`) — **không** import hook kia vào hook mới. Chỉ `page.tsx` được gọi tất cả hook; hook nào cần phối hợp thì nhận qua **callback injection** (`onXxx` truyền từ `page.tsx` vào lúc gọi hook, xem cách `useUpload`/`useSuggestions`/`useModuleRegistry` nhận `onSuccess`/`onApplySuccess`/`onImportDone`). Cách này giữ đúng 1 instance của mỗi hook, tránh 2 nơi tự giữ 2 bản state lệch nhau.

---

## Thiếu sót hiện tại (Known Gaps)

| Vấn đề                                                  | Ghi chú                                                                                                                             |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Không có auth                                           | Dashboard mở public trong mạng nội bộ                                                                                               |
| `app/portal/` không được link từ nav                    | Trùng chức năng với `/swagger`, vẫn muốn giữ lại (đã có thêm Try it out) để sau này muốn thay đổi dùng giao diện khác thì gọi nó ra |
| `app/api/create-doc-pr/route.ts` orphan                 | Không caller nào trong UI, header `Accept` sai chính tả (`vn.github+json`) — an toàn để xoá hoặc sửa nếu hồi sinh                   |
| `ManualEditConflictsCard` flash "Đang tải..." lúc mount | UX rough edge nhỏ, chưa fix                                                                                                         |
| Deploy chỉ xác nhận "request gửi thành công"            | Không poll lại workflow run/PR để biết kết quả cuối cùng — phải tự kiểm tra trên GitHub                                             |
| Chất lượng AI-fix khi batch nhiều operation             | Không phải bug frontend — xem `docs/backend.md` mục AI-fix breadcrumb/parent context + `docs/manual-test-checklist.md` DEF-04       |
