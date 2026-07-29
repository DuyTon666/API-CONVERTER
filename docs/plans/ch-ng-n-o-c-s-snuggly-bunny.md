# Viết test Vitest cho frontend/

## Context

Backend đã có 51+ test tự động (pytest); frontend chỉ có đúng 1 file test (`frontend/lib/dashboard-format.test.ts`, phủ 2/7 hàm). Đây là việc còn dang dở từ kế hoạch ngày 23/07 ("viết test cho frontend" — sau khi đã xong phần backend cho tính năng AI tự sửa lỗi và gắn CI chạy test backend mỗi PR).

Mục tiêu: nâng độ phủ test frontend theo đúng convention đã có sẵn trong repo (tách hàm thuần → test bằng Vitest, không mock khi không cần), và mở rộng convention đó sang phần logic hiện đang "mắc kẹt" trong các custom hook (`hooks/dashboard/`) — cụ thể là 3 khối logic rủi ro cao nhất: merge patch AI-fix, gộp tiến trình import qua SSE, và phân loại file upload. Đã xác nhận với người dùng: phạm vi lần này **bao gồm** việc tách các khối logic đó ra hàm thuần đứng riêng rồi mới viết test (refactor thuần, không đổi hành vi UI).

**Hạ tầng hiện có** (`frontend/vitest.config.ts`): chỉ có alias `@`, KHÔNG có `jsdom`/`@testing-library/react` → chỉ test được hàm thuần TS/JS, không render component/hook React. Không cần cài thêm gì (không có `msw`/`nock`; dùng `Response`/`fetch` toàn cục của Node cho phần cần mock).

**Convention quan sát được** (từ `dashboard-format.test.ts` — file test duy nhất hiện có): `describe("tênHàm", () => { test("mô tả hành vi bằng tiếng Việt", () => {...}) })`, assertion đơn giản (`toBe`/`toEqual`), comment tiếng Việt giải thích fixture, không mock khi không cần.

## Phạm vi

**Nhóm A — bổ sung test cho hàm thuần đã có sẵn, không sửa code nguồn:**
1. `frontend/lib/dashboard-format.ts` — 5 hàm chưa test: `isSupportedFile`, `formatExtensions`, `formatBytes`, `formatDate`, `formatRelativeTime`.
2. `frontend/lib/api/errorMessages.ts` — `resolveErrorMessage`.
3. `frontend/lib/api/client.ts` — `formatFetchError` (ưu tiên cao nhất, giống hệt convention có sẵn), `readErrorDetail` (test qua entry point public này, không export `parseErrorDetail` nội bộ), `apiFetch` (stretch, cần `vi.stubGlobal`).

**Nhóm B — thêm `export`, không refactor logic:**
4. `frontend/hooks/dashboard/useManualEditConflicts.ts` — export `conflictKey` (dòng 12) để test trực tiếp. Đây là lần đầu 1 file `hooks/dashboard/*.ts` được import thẳng vào Vitest trong repo — làm sớm để xác nhận môi trường `node` (không jsdom) import được file hook bình thường (file chỉ có 1 hàm module-scope không đụng DOM), trước khi đầu tư vào nhóm C.

**Nhóm C — tách hàm thuần khỏi hook (refactor thuần, hành vi UI giữ nguyên), rồi test:**
5. `useUpload.ts` → tách `partitionFiles` vào `dashboard-format.ts` (không tạo file mới — dùng chung `isSupportedFile`/`SUPPORTED_EXTENSIONS` đã có sẵn cùng file).
6. `useModuleRegistry.ts` → tách `mergeImportProgress` vào file mới `frontend/lib/dashboard-import-progress.ts`.
7. `useDocsBuilder.ts` → tách 3 hàm vào file mới `frontend/lib/dashboard-ai-fix.ts`: `mergeAiFixPatches`, `buildEmptyAiFixMessage`, `buildDefaultAiFixResolutions`.

## Chi tiết từng phần

### 1. `dashboard-format.ts` — thêm `describe` block vào `dashboard-format.test.ts`

- `isSupportedFile`: `.pdf`/`.docx` → true; hoa/thường không phân biệt; `.zip` → false; `"notes.pdf.txt"` → false (bẫy nếu ai đổi sang `includes`); `".docx"` (chỉ có phần mở rộng) → true.
- `formatExtensions`: `{".pdf":3,".docx":2}` → `".pdf: 3, .docx: 2"`; `{}` → `""`.
- `formatBytes`: `0`→`"0 B"`; `1023`→`"1023 B"`; `1024`→`"1 KB"`; `1536`→`"2 KB"` (test làm tròn); `1048575`→`"1024 KB"` (không tự cuộn lên MB — hành vi thật, lock lại bằng test, không phải bug cần sửa); `1048576`→`"1.0 MB"`; `2621440`→`"2.5 MB"`.
- `formatDate`: `null`→`"-"` (hyphen thường); tính `expected` động bằng `new Date(v).toLocaleString("vi-VN")` trong chính test (tránh phụ thuộc timezone máy chạy); input `"not-a-date"` → `new Date("not-a-date").toLocaleString("vi-VN")` cho ra `"Invalid Date"` chứ không throw — nhánh `catch` trong code gần như dead code với input dạng string, ghi chú rõ trong test.
- `formatRelativeTime`: dùng `vi.useFakeTimers()` + `vi.setSystemTime(...)` (kỹ thuật mới, thêm `beforeEach`/`afterEach` riêng cho block này). `null`→`"—"` (em dash, khác ký tự với `formatDate`, copy nguyên từ source đừng gõ tay). Test đủ biên: vừa xong (30s trước), 59 phút, đúng 1 phút (biên dưới), đúng 60 phút = 1 giờ (biên chuyển), 23 giờ, đúng 24 giờ = 1 ngày (biên chuyển), 29 ngày, đúng 30 ngày (chuyển sang `toLocaleDateString`, tính `expected` động). `"not-a-date"` → trả về **chính giá trị gốc** (khác `formatDate`!) vì có guard `isNaN` tường minh — viết 1 test đối chiếu trực tiếp 2 hàm để làm rõ khác biệt.

### 2. `errorMessages.test.ts` (file mới)

`ERROR_MESSAGES` hiện là object rỗng, không freeze — mutate tạm trong test (`try/finally` hoặc `afterEach` dọn lại) để phủ nhánh có override, không cần sửa production code. Case: `code=undefined`→fallback; `code=""`→fallback (falsy); code không có trong map→fallback; có override→trả override; override bằng chuỗi rỗng→vẫn fallback (falsy, dễ gây bất ngờ khi map có dữ liệu thật sau này).

### 3. `client.test.ts` (file mới)

- `formatFetchError`: `TypeError` bất kỳ → message cố định; `Error`/`RangeError` thường → `.message`; giá trị không phải `Error` (`"boom"`, `undefined`) → fallback (mặc định hoặc tuỳ biến).
- `readErrorDetail`: dùng `new Response(JSON.stringify(body), {status, statusText})` (Response thật của Node, không cần mock `fetch`). Case: `detail` object có `message` → lấy message đó; `detail` string → dùng thẳng; `detail` là mảng (giả lập lỗi 422 validation) → rơi về fallback = statusText; `detail` object thiếu `message` → fallback = statusText; body không phải JSON hợp lệ → fallback = statusText (verify `.catch(() => null)` hoạt động đúng).
- `apiFetch` (stretch, ưu tiên thấp hơn): `vi.stubGlobal("fetch", ...)` + `afterEach(() => vi.unstubAllGlobals())`. Case: response ok → resolve JSON; response not-ok → reject với đúng message từ `readErrorDetail`; `fetch` reject thẳng bằng `TypeError` → không bị nuốt/bọc lại (không có try/catch trong hàm).

### 4. `useManualEditConflicts.ts` — export `conflictKey`

Sửa dòng 12: thêm `export` trước `function conflictKey`. File test mới `useManualEditConflicts.test.ts`, import `{ conflictKey } from "./useManualEditConflicts"`. Case: đổi `kind` (giữ `entityId`/`field`) → key khác; đổi `entityId` → key khác; đổi `field` → key khác; 1 case verify format chính xác (`"schema:User.email::description"`). Fixture phải điền đủ mọi field bắt buộc của type `ManualEditConflict` dù hàm chỉ đọc 3 field.

**Chạy `npm run test` ngay sau bước này** để xác nhận sớm giả định "import file hook vào Vitest môi trường node không vỡ gì" trước khi làm nhóm C.

### 5. `useUpload.ts` → `partitionFiles` (thêm vào `dashboard-format.ts`)

Chữ ký: `partitionFiles<T extends {name: string}>(files: T[]): {supported: T[]; rejected: T[]; rejectedMessage: string | null}`. Copy nguyên văn logic dòng 19-24 của `useUpload.ts` — **giữ nguyên lỗi chính tả "chỉ nhân"** (không phải "chỉ nhận") và đúng thụt lề 6 dấu cách của template literal đa dòng gốc, vì đây là refactor thuần, message hiển thị UI phải giữ byte-for-byte.

Hook sau khi sửa (thay dòng 15-29):
```ts
const handleSelectFiles = (selected: FileList | null) => {
  if (!selected) return;
  const incoming = Array.from(selected);
  const { supported, rejectedMessage } = partitionFiles(incoming);
  if (rejectedMessage) toast.error(rejectedMessage);
  if (supported.length > 0) setUploadFiles((prev) => [...prev, ...supported]);
};
```
Import dòng 2 đổi thành `import { partitionFiles } from "@/lib/dashboard-format";` (bỏ `isSupportedFile`/`SUPPORTED_EXTENSIONS` không còn dùng trực tiếp, tránh lint lỗi unused-import).

Test case: toàn bộ hợp lệ (rejectedMessage null); toàn bộ không hợp lệ (message đúng số lượng + đúng nội dung, so bằng template literal y hệt gốc); hỗn hợp (giữ đúng thứ tự tương đối 2 nhóm); danh sách rỗng.

### 6. `useModuleRegistry.ts` → `mergeImportProgress` (file mới `dashboard-import-progress.ts`)

```ts
export function mergeImportProgress(
  prev: ImportModuleProgress[],
  incoming: ImportModuleProgress,
): ImportModuleProgress[] {
  const exists = prev.find((m) => m.name === incoming.name);
  if (exists) return prev.map((m) => (m.name === incoming.name ? incoming : m));
  return [...prev, incoming];
}
```
Hook sau khi sửa (thay dòng 74-79 trong `handleImport`, xử lý payload SSE):
```ts
setImportModules((prev) => mergeImportProgress(prev, payload as ImportModuleProgress));
```
Lưu ý: nhánh `payload.event === "done"` (dòng 66-73) xử lý riêng TRƯỚC, không đi qua `mergeImportProgress` — hàm mới chỉ cần lo phần merge theo `name`, không cần biết về event "done".

Test case: module chưa có → append cuối, giữ nguyên phần tử cũ; module đã có → thay đúng vị trí, không đổi thứ tự các phần tử khác; `prev=[]` → `[incoming]`; không mutate mảng `prev` gốc (so sánh snapshot trước/sau khi gọi — quan trọng vì dùng trong `setState` updater).

### 7. `useDocsBuilder.ts` → 3 hàm (file mới `dashboard-ai-fix.ts`)

```ts
export function mergeAiFixPatches(
  bundleContent: string,
  patches: AiFixPatch[],
  resolutions: Record<string, AiFixResolution>,
): string {
  const lines = bundleContent.split("\n");
  const sorted = [...patches].sort((a, b) => b.start_line - a.start_line);
  for (const patch of sorted) {
    const resolution = resolutions[patch.id] ?? "fixed";
    const replacement =
      resolution === "original" ? patch.original_text
      : resolution === "both" ? `${patch.original_text}\n${patch.fixed_text}`
      : patch.fixed_text;
    lines.splice(patch.start_line, patch.end_line - patch.start_line + 1, ...replacement.split("\n"));
  }
  return lines.join("\n");
}

export function buildEmptyAiFixMessage(patches: AiFixPatch[], unresolved: AiFixUnresolved[]): string | null {
  if (patches.length > 0) return null;
  return unresolved.length > 0
    ? "AI không xác định được vị trí lỗi nào để sửa — cần sửa tay."
    : "Không có lỗi nào để sửa";
}

export function buildDefaultAiFixResolutions(patches: AiFixPatch[]): Record<string, AiFixResolution> {
  return Object.fromEntries(patches.map((p) => [p.id, "fixed" as AiFixResolution]));
}
```
Fixture `AiFixPatch` cần điền đủ field bắt buộc kể cả `issues: []` (type có field `issues: AiFixIssueRef[]`).

Hook sau khi sửa — thay thân `applyAiFixResolutions` (dòng 51-83), **giữ nguyên** comment nghiệp vụ phía trên (dòng 41-50):
```ts
const applyAiFixResolutions = async (editedPatches: AiFixPatch[]) => {
  if (bundleContent === null) return;
  const merged = mergeAiFixPatches(bundleContent, editedPatches, aiFixResolutions);
  setBundleContent(merged);
  closeAiFixPanel();
  setSavingBundle(true);
  try {
    await saveThenRelint(merged);
  } finally {
    setSavingBundle(false);
  }
};
```
Thay khối dòng 208-222 trong `handleAiFixBundle`:
```ts
const emptyMessage = buildEmptyAiFixMessage(data.patches, data.unresolved);
if (emptyMessage) {
  alert(emptyMessage);
  return;
}
setAiFixPatches(data.patches);
setAiFixUnresolved(data.unresolved);
setAiFixResolutions(buildDefaultAiFixResolutions(data.patches));
setShowAiFixPanel(true);
```

Test case cho `mergeAiFixPatches` (giá trị đã verify bằng cách chạy thật thuật toán):
- **Sort + lệch dòng**: bundle 5 dòng (`L0..L4`), truyền patch theo thứ tự KHÔNG sort để tự verify hàm sort bên trong — patch tại dòng 1 (1→2 dòng) và patch tại dòng 3 (1→1 dòng) → kết quả `"L0\nX1\nX2\nL2\nY3\nL4"`.
- **3 nhánh resolution** (3 test riêng, patch đơn dòng): `"original"` → giữ nguyên gốc; `"both"` → gốc + `\n` + sửa; `"fixed"` → chỉ bản sửa.
- **Fallback thiếu resolution**: patch có `id` không có trong `resolutions` (`{}`) → coi như `"fixed"`.
- **Patch nhiều dòng gộp 1 dòng**: patch `start_line:1, end_line:3` (3 dòng gốc) → 1 dòng thay thế, verify `deleteCount` tính đúng.
- **Patch chồng phạm vi (overlapping)** — hành vi thật hiện tại, không có validation chống overlap, đây là regression-guard chứ không phải fix bug: 2 patch chồng nhau (A: dòng 0-2, B: dòng 1-3), xử lý B trước (start_line lớn hơn) rồi A — do mảng đã co lại sau bước xử lý B, `deleteCount` của A (tính trên toạ độ gốc) xoá lố sang cả phần tử ngoài phạm vi khai báo ban đầu. Kết quả cụ thể và cách trace: xem báo cáo Plan agent ở trên (đã verify bằng Node) — implementer tự chạy lại đoạn code để lấy đúng string kỳ vọng trước khi viết `expect`, đừng chép tay.

Test case `buildEmptyAiFixMessage`: `patches` có phần tử → `null` (bất kể `unresolved`); `patches=[]` + `unresolved=[]` → "Không có lỗi nào để sửa"; `patches=[]` + `unresolved` có phần tử → thông báo "cần sửa tay".

Test case `buildDefaultAiFixResolutions`: map nhiều patch → mỗi `id` đều `"fixed"`; `patches=[]` → `{}`.

## Thứ tự thực hiện

1. Nhóm A (mục 1-3) — độc lập, không refactor, làm trước để thiết lập pattern mới (fake timers ở mục 1, `Response` thật ở mục 3).
2. Nhóm B (mục 4) — spike xác nhận import hook file vào Vitest an toàn. **Chạy `npm run test` ngay sau bước này.**
3. Nhóm C theo thứ tự đơn giản → phức tạp: mục 5 (`partitionFiles`) → mục 6 (`mergeImportProgress`) → mục 7 (`mergeAiFixPatches` + 2 hàm nhỏ, phức tạp nhất vì case overlapping). Mỗi bước: viết hàm thuần + test trước, sau đó mới sửa hook gọi qua hàm mới (không viết lại logic, chỉ chuyển vị trí).

Không có phụ thuộc chéo giữa mục 5/6/7 — độc lập, có thể đổi thứ tự nếu cần.

## Verification

- Sau mỗi bước ở nhóm C: `cd frontend && npm run test` (toàn bộ suite phải pass) và `npm run lint` (bắt unused-import ở 3 hook vừa sửa).
- Sau khi xong toàn bộ: chạy lại `npm run test` lần cuối, xác nhận số lượng test tăng đúng như kỳ vọng (từ 1 file/vài test lên nhiều file, phủ đủ 7 hàm nhóm A + 1 hàm nhóm B + 4 hàm nhóm C).
- Test thủ công nhanh trên UI (theo đúng thói quen dự án — tắt server ngay sau khi test xong): mở Form Editor, thử tab "AI tự fix lỗi" với 1-2 lỗi thật, bấm "Áp dụng" — xác nhận hành vi merge patch không đổi so với trước refactor (vì `mergeAiFixPatches` chỉ là logic gốc được chuyển vị trí, không viết lại).

## Critical Files

- `frontend/lib/dashboard-format.ts`, `frontend/lib/dashboard-format.test.ts`
- `frontend/lib/api/client.ts`, `frontend/lib/api/errorMessages.ts`
- `frontend/hooks/dashboard/useDocsBuilder.ts`
- `frontend/hooks/dashboard/useModuleRegistry.ts`
- `frontend/hooks/dashboard/useUpload.ts`
- `frontend/hooks/dashboard/useManualEditConflicts.ts`
- `frontend/types/dashboard.ts` (tham chiếu type, không sửa)
