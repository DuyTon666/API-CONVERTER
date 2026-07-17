# Kiến trúc Frontend — API Converter

> Đọc trực tiếp code trong `frontend/` để viết lại — không dựa vào bản `.tex` cũ vì đã phát hiện vài chỗ sai (số component, thiếu 1 hook). Mục tiêu giống file kiến trúc Backend: đọc xong hình dung được toàn bộ bức tranh Frontend, không chỉ thuộc bảng.

## 1. Frontend trong bức tranh tổng thể

Khác với nhiều app có nhiều trang, Frontend ở đây gần như chỉ là **1 trang dashboard duy nhất** (`app/page.tsx`) — người dùng làm toàn bộ luồng nghiệp vụ (từ upload tài liệu tới deploy) mà không rời trang, không có điều hướng multi-step qua nhiều URL. 2 trang còn lại (`/swagger`, `/portal`) là nơi *xem* tài liệu đã build, tách biệt hoàn toàn khỏi dashboard.

Frontend nói chuyện với 2 phía khác nhau, qua 2 cơ chế khác nhau — dễ nhầm là 1 nếu không để ý:

```
┌─────────────────────────┐
│   Dashboard (page.tsx)  │
└───────────┬──────────────┘
            │ fetch() thuần, qua NEXT_PUBLIC_API_URL
            ▼
   ┌──────────────────┐
   │  Backend FastAPI   │   (convert, sửa nội dung, build/lint)
   └──────────────────┘

┌─────────────────────────┐
│  SwaggerDocsCard: nút    │
│  "Deploy tài liệu"       │
└───────────┬──────────────┘
            │ fetch() tới route Next.js của CHÍNH mình
            ▼
   ┌──────────────────────────┐
   │ app/api/deploy-docs/       │  (route.ts — chạy trên
   │ route.ts                    │   Next.js server, gọi
   └──────────────────────────┘   thẳng GitHub REST API)
```

Nút Deploy KHÔNG gọi Backend FastAPI — nó gọi 1 route server riêng nằm ngay trong Next.js (`app/api/deploy-docs/route.ts`), route này tự gọi GitHub REST API. Đây chính là điểm đã ghi trong file kiến trúc Backend: logic nghiệp vụ chia làm 2 nơi độc lập.

## 2. Cấu trúc thư mục — tách theo trách nhiệm, không theo trang

```
frontend/
├── app/
│   ├── page.tsx              trang dashboard duy nhất — chỉ compose hook + render layout
│   ├── swagger/               trang xem Swagger UI (đọc file trực tiếp, không qua Backend)
│   ├── portal/                trang portal riêng — mồ côi, không có link nào trỏ tới (mục 3)
│   └── api/                   2 route server-side (deploy-docs, create-doc-pr)
├── hooks/dashboard/           8 file — MỌI state của dashboard nằm ở đây
├── components/dashboard/      15 file — chỉ nhận props + render, không tự gọi API
└── lib/api/dashboard/         7 file — 1 file mỏng bọc fetch cho mỗi domain
```

Nguyên tắc: **`page.tsx` không tự giữ state, không tự gọi API** — nó chỉ gọi các hook rồi truyền dữ liệu xuống component qua props. Muốn biết 1 hành động (vd "bấm Activate") làm gì, chỉ cần tìm đúng 1 hook sở hữu nó — không phải lục cả `page.tsx` dài 366 dòng.

## 3. Route thực tế — chỉ có 3 trang + 2 API route

| Route | File | Có link trỏ tới từ đâu trong app? |
|---|---|---|
| `/` | `app/page.tsx` | Trang gốc |
| `/swagger` | `app/swagger/page.tsx` | Nút "Developer Portal" trên thanh nav của `/` |
| `/portal` | `app/portal/page.tsx` | **Không có** — mồ côi, chỉ vào được nếu gõ thẳng URL |
| `/api/deploy-docs` | `app/api/deploy-docs/route.ts` | Nút "Deploy tài liệu" trong `SwaggerDocsCard` |
| `/api/create-doc-pr` | `app/api/create-doc-pr/route.ts` | **Không có** — không nơi nào trong frontend gọi route này |

Chú ý: nút ghi chữ "Developer Portal" trên thanh nav thực chất trỏ `href="/swagger"` — mở Swagger UI, không phải trang `/portal` thật (trang card riêng, tìm kiếm bằng Fuse.js). `/portal` tồn tại đầy đủ code nhưng không route nào trong app dẫn tới, phải gõ URL tay mới vào được.

## 4. 8 custom hook — mỗi hook sở hữu đúng 1 mảng chức năng

| Hook | Sở hữu | Số dòng |
|---|---|---|
| `useScan` | Kết quả scan + `fetchScan` | 28 |
| `useUpload` | State chọn file + upload, nhận callback `onSuccess` | 52 |
| `useModuleRegistry` | Danh sách module, activate/deactivate, import (SSE), nhận callback `onImportDone` | 126 |
| `useSuggestions` | Suggest/approve/apply, nhận callback `onApplySuccess` | 134 |
| `useManualEditConflicts` | Fetch/resolve xung đột sửa tay | 66 |
| `useDocsBuilder` | Build/lint/bundle-editor/AI-fix/Deploy — hook nặng nhất | 276 |
| `useActiveStep` | Scrollspy dùng chung `WorkflowStepper` + `StepSection` (1 `IntersectionObserver` duy nhất) | 37 |
| `useMounted` | Tránh hydration mismatch (SSR) | 9 |

Mỗi hook tự quản lý state loading/error/data bằng `useState` — không có hook nào import hook khác trực tiếp.

### Cách các hook phối hợp: callback injection

3 hook cần biết khi hook khác vừa xong việc để tự làm mới dữ liệu — nhưng thay vì import lẫn nhau, chúng **nhận callback qua tham số**, và `page.tsx` là nơi nối các callback đó lại:

```ts
useUpload(backend, { onSuccess: fetchScan })
// upload xong → tự fetchScan() để cập nhật danh sách file mới

useModuleRegistry(backend, { onImportDone: fetchConflicts })
// import xong → tự fetchConflicts() vì import có thể sinh xung đột sửa tay mới

useSuggestions(backend, {
  onApplySuccess: () => Promise.all([fetchScan(), fetchModules()])
})
// apply suggestion xong → cả scan lẫn module list đều có thể đổi, refresh cả 2
```

Lý do làm vậy thay vì để hook A gọi thẳng hook B: mỗi hook chỉ có **đúng 1 instance state** sống trong `page.tsx`, không nhân đôi state nếu 2 nơi cùng gọi 1 hook.

## 5. Bố cục trang — cuộn dọc 4 bước, không phải wizard nhảy bước

Dashboard hiển thị 4 khối tương ứng 4 bước nghiệp vụ, xếp dọc trong 1 trang dài — không phải modal/wizard chuyển qua lại:

```
[Nav sticky: logo + nút "Developer Portal"]
[WorkflowStepper sticky: 4 chấm bước — bấm để scroll tới section]
[StatTiles: 4 số tổng quan]
[ManualEditConflictsCard — nếu có xung đột, hiện ngay đầu trang]

① Nguồn      → ImportCard + ScanCard
② Phân loại  → SuggestCard
③ Module     → ModuleRegistryCard
④ Tài liệu   → SwaggerDocsCard

[BundleEditorModal — hiện đè lên khi mở, không nằm trong luồng 4 bước]
[AiFixPanel — tương tự, hiện đè lên khi có patch AI đề xuất]
```

`WorkflowStepper` (thanh sticky trên cùng) và `StepSection` (khối từng bước, có cột số bên trái) **dùng chung đúng 1 `useActiveStep`** — hook này chạy 1 `IntersectionObserver` duy nhất theo dõi section nào đang ở đầu viewport, rồi cả 2 nơi tô màu theo cùng 1 `activeIndex`. Thiết kế vậy để tránh 2 observer riêng chạy trùng trên cùng tập phần tử.

`BundleEditorModal` và `AiFixPanel` không thuộc 4 `StepSection` — chúng render ở cuối `page.tsx`, hiện/ẩn dựa trên state (`bundleContent !== null`, `showAiFixPanel`), giống overlay đè lên toàn trang.

## 6. Lớp gọi API

`fetch()` thuần — không dùng axios/SWR/React Query. Bọc qua 1 helper mỏng duy nhất, `lib/api/client.ts`'s `apiFetch<T>(url, init)`:

```ts
export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return res.json();
}
```

`readErrorDetail()` đọc đúng khớp shape lỗi backend trả về (`{ detail: { code, message } }`) rồi map qua `resolveErrorMessage()` để đổi câu tiếng Việt thân thiện hơn nếu có trong bảng override (hiện bảng này rỗng).

Không có cache layer, không retry tự động, không dedupe request trùng — mỗi hook tự `setLoading(true) → fetch → setLoading(false)`. Vì không qua SWR/React Query nên không có revalidate nền — dữ liệu chỉ mới lại khi có hành động tường minh gọi lại `fetchX()`.

Lệnh gọi API được tổ chức theo domain trong `lib/api/dashboard/` — 1 file cho mỗi hook tương ứng:

| File | Hook dùng |
|---|---|
| `modules.ts` | `useScan`, `useModuleRegistry`, `useManualEditConflicts` |
| `upload.ts` | `useUpload` |
| `suggestions.ts` | `useSuggestions` |
| `docs.ts` | `useDocsBuilder` (build/lint/bundle-content/ai-fix) |
| `operations.ts`, `schemaFields.ts` | dùng trong `OperationsFormEditor`/`SchemaFieldsEditor` |
| `deploy.ts` | `useDocsBuilder`'s `handleDeploy()` |

## 7. Vòng đời SSE phía client

Chỉ 1 nơi dùng `EventSource` — `useModuleRegistry.ts`'s `handleImport()`:

- **Mở:** ngay sau khi `POST /modules/import` trả `job_id`.
- **Đóng do xong việc:** nhận message `payload.event === "done"` → `es.close()`.
- **Đóng do lỗi:** `es.onerror` → `es.close()` ngay + báo lỗi. `EventSource` có cơ chế tự reconnect theo spec trình duyệt, nhưng vì code chủ động `close()` ngay trong `onerror`, cơ chế tự-reconnect đó không bao giờ có cơ hội chạy — mất kết nối 1 lần là dừng hẳn, người dùng phải tự bấm Import lại.
- **Cleanup khi unmount:** **không có** — biến `es` chỉ sống trong closure của `handleImport`, không có `useEffect` nào giữ nó để đóng khi component unmount.

## 8. Cơ chế thông báo lỗi — thực ra có 3 kiểu khác nhau, không phải 1

Đây là điểm dễ hiểu lầm nếu chỉ đọc lướt — soát kỹ `useDocsBuilder.ts` phát hiện **3 kiểu hiển thị lỗi cùng tồn tại**, không nhất quán:

**Kiểu 1 — Inline qua `ErrorAlert`** (phổ biến nhất): mỗi hook giữ 1 state lỗi dạng string (`modulesError`, `activateError`, `importError`, `docsError`...), component cha render qua `ErrorAlert.tsx` — 1 khối đỏ nhạt nằm ngay tại vị trí action gây lỗi, không tự mất. Dùng cho scan, upload, activate/deactivate, import, suggestions, build/relint.

**Kiểu 2 — `alert()` gốc của trình duyệt** (chặn UI, phải bấm OK mới đóng): xuất hiện đúng **6 lần**, toàn bộ đều nằm trong `useDocsBuilder.ts`, gắn với luồng Bundle Editor Modal — mở bundle lỗi, lưu bundle lỗi, lưu-rồi-relint lỗi, AI-fix lỗi/không tìm được lỗi để sửa. Đây là kiểu lỗi thời, không đồng bộ giao diện với phần còn lại của app.

**Kiểu 3 — `sonner` toast**: chỉ dùng đúng 2 chỗ (`toast.success()`/`toast.error()`), cả hai đều trong `handleDeploy()` — tức toast chỉ phục vụ riêng action Deploy, không phải cơ chế chung toàn app như tên thư viện có thể khiến người đọc nghĩ.

Nói cách khác: **cùng 1 hook (`useDocsBuilder`) dùng cả 3 kiểu thông báo lỗi cho 3 nhóm hành động khác nhau của chính nó** — build/relint dùng kiểu 1, thao tác trong Bundle Editor dùng kiểu 2, riêng Deploy dùng kiểu 3. Đây là điểm đáng cân nhắc chuẩn hóa lại nếu có thời gian.

## 9. Validate YAML phía client — không có

`BundleEditor.tsx` dùng Monaco với `defaultLanguage="yaml"` (chỉ bật highlight cú pháp cơ bản, không phải parser YAML đầy đủ như package `monaco-yaml` riêng). Các marker đỏ/vàng hiển thị trong editor lấy hoàn toàn từ props `spectralIssues`/`redoclyIssues` — tức kết quả lint cũ nhất đã fetch trước đó, không phải parse lại YAML mỗi lần gõ phím. Không có `onValidate`, không parse thử YAML trước khi cho bấm "Lưu".

Hệ quả: gõ sai cú pháp YAML rồi bấm Lưu ngay (chưa relint lại) thì lỗi chỉ lộ ra khi backend nhận `PUT /docs/bundle-content`, trả `400 BUNDLE_INVALID_YAML` — lúc đó hiển thị qua `alert()` (kiểu 2 ở mục 8), không phải marker trong editor.

## 10. 15 component con — vai trò từng cái

| Component | Vai trò |
|---|---|
| `ScanCard` | Hiện kết quả scan, file chưa gán module |
| `ImportCard` | Vùng kéo-thả upload file nguồn |
| `SuggestCard` | Chạy gợi ý module, xem/duyệt/apply — component lớn nhất sau `OperationsFormEditor` (465 dòng) |
| `ModuleRegistryCard` | Bảng module + trạng thái + nút Activate/Deactivate/Import, hiện tiến trình SSE |
| `ManualEditConflictsCard` | Danh sách xung đột sửa tay khi import lại, nút Giữ bản cũ/Lấy bản mới |
| `SwaggerDocsCard` | Nhóm nút Build/Relint/Download HTML/Deploy, hiện tổng số lỗi lint |
| `BundleEditorModal` | Modal 2 tab: "Chỉnh sửa nội dung" (`OperationsFormEditor`) và "YAML thô" (`BundleEditor`) |
| `BundleEditor` | Monaco Editor cho tab YAML thô, hiện marker lint (mục 9) |
| `OperationsFormEditor` | Form sửa summary/description/parameter/response — component lớn nhất (845 dòng) |
| `SchemaFieldsEditor` | Renderer đệ quy cho 1 cây `SchemaGroup` (schema request/response của 1 operation) |
| `AiFixPanel` | Diff 2 cột (gốc/AI sửa) cho từng lỗi lint, chọn giữ bản nào trước khi áp dụng |
| `StatTiles` | 4 ô số tổng quan (module active/draft, file chưa gán, suggestion chờ duyệt) |
| `WorkflowStepper` | Thanh 4 bước sticky trên cùng, bấm để scroll tới section (mục 5) |
| `StepSection` | Khối 1 bước trong timeline dọc, cột số/tick bên trái (mục 5) |
| `ErrorAlert` | Khối hiển thị lỗi inline dùng chung — kiểu 1 ở mục 8 |

Toàn bộ chỉ nhận props + render — không component nào tự gọi `fetch`/`apiFetch`, mọi lời gọi API đều đi qua hook ở `page.tsx` rồi truyền hàm xuống qua props (`onActivate`, `onImport`...).

## 11. State pattern chung

Mọi hành động không đồng bộ đều theo đúng 1 khuôn: `setLoading(true) → await fetch → setLoading(false)`, kèm 1 state lỗi string song song. SSE là ngoại lệ duy nhất — `EventSource` mở trong hàm xử lý, đóng khi nhận `done` hoặc `onerror` (không reconnect, không cleanup unmount — mục 7).

## 12. Tổng hợp giới hạn đáng lưu ý

- Nút "Developer Portal" gây hiểu lầm — trỏ `/swagger` chứ không phải trang `/portal` thật; `/portal` tồn tại đầy đủ nhưng mồ côi hoàn toàn.
- `EventSource` của import không cleanup lúc unmount, và tự đóng vĩnh viễn ngay lần lỗi đầu tiên (không tận dụng cơ chế reconnect có sẵn của trình duyệt).
- **3 kiểu thông báo lỗi khác nhau cùng tồn tại trong cùng 1 hook** (`ErrorAlert` / `alert()` / `toast`) — không nhất quán trải nghiệm, đặc biệt `alert()` chặn UI kiểu cũ chỉ dùng riêng cho luồng Bundle Editor.
- Không validate YAML phía client — mọi lỗi cú pháp chỉ phát hiện được sau khi gọi backend.
- Không cache/revalidate (không SWR/React Query) — dữ liệu có thể cũ nếu người dùng không chủ động refresh, không có cơ chế tự đồng bộ nền.
