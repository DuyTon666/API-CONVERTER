# Kế hoạch: AI tự fix lỗi YAML — sửa từng vị trí cụ thể + UI giải quyết conflict kiểu GitHub

## Context

Hiện tại nút "✨ AI tự fix lỗi" (`POST /docs/bundle/ai-fix`, `backend/main.py` dòng 516-575) gửi
**toàn bộ** file YAML + danh sách lỗi Spectral/Redocly cho Claude, AI trả về **toàn bộ file đã
sửa lại**, và frontend (`useDocsBuilder.ts` → `handleAiFixBundle`) **thay thế trực tiếp** nội dung
editor — rủi ro cao vì AI có thể hiểu sai và sửa nhầm những phần không liên quan tới lỗi.

Yêu cầu mới: AI chỉ được sửa **đúng những vị trí bị lỗi**, không động tới phần còn lại của file.
Sau khi AI đề xuất sửa, hiển thị so sánh bản gốc vs bản AI sửa **kiểu conflict của Git/GitHub**,
cho người dùng 3 lựa chọn mỗi vị trí: giữ bản gốc / giữ bản AI sửa / giữ cả hai (nối tiếp 2 bản,
không thêm marker `<<<<<<<`, giống "Accept Both Changes" của GitHub/VS Code) — đúng tinh thần dev
tự review trước khi lưu, vốn đã là nguyên tắc thiết kế của tính năng này từ đầu (docstring hiện tại
đã ghi "rủi ro cao... bắt buộc dev tự review").

**Đã xác nhận qua đọc code + chạy lệnh lint thật** (không suy đoán):
- Spectral issue có sẵn `path: string[]` và `range: {start: {line, character}, end: {...}}` — **0-indexed, đã chính xác tới đúng block lỗi**. Test thật trên `dist/openapi-bundled.yaml`: lỗi `license-url` trả `range.start.line=4, range.end.line=5` — khớp 100% với block `license:`/`name: API` thật trong file (dòng 5-6 1-indexed) → **dùng trực tiếp `range`, không cần tự tính**.
- Redocly (`--format json`, dùng cho `validate:api`) chỉ có `location: [{pointer, reportOnKey}]` — JSON Pointer, KHÔNG có line/col. **Nhưng Redocly CLI có thêm format `checkstyle`** (`npx @redocly/cli lint ... --format checkstyle`) trả XML với `line`/`column` **1-indexed trực tiếp** — đã test thật, ra đúng `line="5"` khớp 100% với dòng `license:` thật. → Dùng format này để lấy line/col cho Redocly, **không cần tự resolve JSON Pointer, không cần `ruamel.yaml`**.
- `frontend/app/_dashboard/types.ts` khai báo `SpectralIssue`/`RedoclyIssue` thiếu field `range`/`location` — còn `BundleEditor.tsx` (dòng 6-26) tự khai báo lại bản đầy đủ hơn nhưng vẫn optimistically đọc `location[0].line/.column` (hiện luôn `undefined` vì backend chưa từng cung cấp) — đây là 1 bug có sẵn, sẽ được sửa luôn nhân tiện đợt này.
- `@monaco-editor/react@^4.7.0` (đã cài) có export `DiffEditor` (chưa dùng ở đâu trong code) — đúng công cụ để hiển thị diff 2 bên kiểu conflict.
- Hàm `_parse_ai_json(raw)` (main.py dòng 669-680) đã có sẵn pattern parse JSON từ Claude (kèm regex fallback) — tái dùng được, không viết lại.

## Thiết kế

### 0. Tách logic mới ra file riêng, không dồn thêm vào `main.py`

`backend/main.py` đã ~850 dòng, dồn thêm 5-6 hàm resolver/merge/prompt-builder vào sẽ làm nó phình
to và khó bảo trì. Tạo file mới **`backend/ai_fix.py`** chứa toàn bộ logic mới ở mục 2-5 dưới đây
(`_find_block_end`, `_parse_checkstyle_output`, `_merge_overlapping_ranges`, `_build_batch_prompt`,
và 1 hàm tổng `resolve_and_build_patches(content, spectral, redocly)` trả thẳng `{patches,
unresolved, failed}`). `main.py` chỉ giữ route `@app.post("/docs/bundle/ai-fix")` — import hàm từ
`ai_fix.py`, gọi Claude (vì client AI dùng chung với `ai_suggest_operation` nên việc gọi
`anthropic.Anthropic()` + `_parse_ai_json` vẫn ở `main.py`, truyền `raw` JSON đã parse vào
`ai_fix.py` để xử lý/validate) hoặc để `ai_fix.py` tự gọi AI luôn (gọn hơn, ít truyền qua lại) —
chọn cách 2: `ai_fix.py` tự chứa toàn bộ, `main.py` chỉ còn `return ai_fix.run(content, spectral,
redocly)` + xử lý lỗi qua `http_error`.

### 1. Backend — lấy line/col chính xác cho Redocly (`_bundle_lint_build_docs`, main.py)

Hàm này hiện chạy `redocly lint --format json` 1 lần để lấy `redocly` issue list. Thêm 1 lệnh
chạy song song nữa: `redocly lint --format checkstyle` (cùng input), parse XML bằng
`xml.etree.ElementTree` (built-in, không cần thêm dependency) → list `{ruleId, message, line, column}`
(line/col 1-indexed). Khớp từng issue JSON với issue checkstyle theo cặp `(ruleId, message)` —
nếu trùng nhiều cặp giống nhau, khớp theo thứ tự xuất hiện còn lại — rồi gắn `line: line-1`,
`column: column-1` (đổi về 0-indexed cho đồng nhất với Spectral) vào object issue JSON trước khi
trả cho frontend. **Tác dụng phụ tốt**: mọi nơi đang hiển thị `redocly` issue (danh sách lỗi ở
`SwaggerDocsCard`, marker trong `BundleEditor.tsx`) tự động có line/col đúng — sửa luôn bug có sẵn
nói ở trên.

### 2. Backend — chuẩn hoá Spectral + Redocly thành 1 range duy nhất, tìm điểm kết block cho Redocly

`backend/main.py`, thêm hàm `_find_block_end(lines, start_line)` — chỉ cần dùng cho **Redocly**
(vì checkstyle chỉ cho 1 điểm bắt đầu, không cho biết block dài tới đâu): so **độ thụt lề
(indentation)** — các dòng sau `start_line` có indent lớn hơn dòng start → thuộc block; gặp dòng
indent bằng (và không phải sibling `- ` của sequence) hoặc nhỏ hơn → dừng. Dòng trống/comment bỏ
qua khi so sánh nhưng tạm tính vào block.

Với **Spectral**, dùng trực tiếp `range.start.line`/`range.end.line` đã có sẵn — không cần
`_find_block_end` (range của Spectral đã chính xác tới đúng block, xác nhận qua test thật ở trên).

Kết quả: mỗi issue (Spectral hoặc Redocly) → `{start_line, end_line, original_text}` 0-indexed.

### 3. Gộp các vị trí lỗi chồng lấn

Sau khi resolve mọi issue (Spectral + Redocly) thành range, **sort theo `start_line`**, sweep-merge
các range chồng lấn (`r.start_line <= merged.end_line` → gộp, cộng dồn `issues`) thành 1 patch duy
nhất — đảm bảo không bao giờ có 2 patch độc lập đè lên cùng vùng text (tránh hỏng file khi áp cả 2).
Issue không resolve được (Redocly không có `location`, hoặc checkstyle không khớp được issue nào)
→ đưa vào danh sách `unresolved` riêng, không tạo patch.

### 4. Một lệnh gọi AI duy nhất (không gọi lại cho từng lỗi)

Build 1 prompt chứa toàn bộ patch đã gộp ở bước 2 — mỗi patch là 1 block `original_text` kèm danh
sách message lỗi của nó — cùng các quy ước project (giữ nguyên 4 bullet hiện có trong prompt cũ).
Yêu cầu Claude trả JSON: `{"patches": [{"id": "...", "fixed_text": "..."}]}` — **chỉ đoạn đã sửa
cho từng vị trí, giữ nguyên indentation tương đối** để ghép thẳng lại được. Parse bằng
`_parse_ai_json` có sẵn.

**Validate từng `fixed_text` trước khi trả về client**: thay `lines[start:end+1]` bằng
`fixed_text.split("\n")` trên bản full-document gốc (chỉ trong bộ nhớ, không ghi file), chạy
`_yaml.safe_load()` (PyYAML thường, nhanh) lên **toàn bộ document đã thay** — nếu parse lỗi hoặc
không ra `dict`, loại patch đó khỏi kết quả (đưa vào `failed`), KHÔNG fail cả request.

### 5. Response shape mới — `POST /docs/bundle/ai-fix`

```json
{
  "patches": [
    {
      "id": "loc-0",
      "path_display": "info.license",
      "start_line": 4,
      "end_line": 5,
      "original_text": "  license:\n    name: API",
      "fixed_text": "  license:\n    name: API\n    url: https://example.com/license",
      "issues": [{"source": "spectral", "code": "license-url", "message": "..."}]
    }
  ],
  "unresolved": [{"source": "spectral", "code": "...", "message": "...", "reason": "Lỗi ở cấp gốc tài liệu — cần sửa tay"}],
  "failed": [{"source": "redocly", "code": "...", "message": "...", "reason": "AI không trả về kết quả hợp lệ cho vị trí này"}]
}
```
Không có lỗi nào (spectral+redocly rỗng) → trả `{"patches": [], "unresolved": [], "failed": []}` (giữ HTTP 200, không đổi hành vi nút bị disable hiện tại). Lỗi gọi AI/bundle rỗng vẫn dùng `http_error` + `ErrorCode.AI_CALL_FAILED`/`EMPTY_BUNDLE` như cũ.

### 6. Frontend — state + UI giải quyết conflict

**`types.ts`**: dọn trùng lặp — chuyển khai báo `SpectralIssue`/`RedoclyIssue` đầy đủ (có `range`/`location`) từ `BundleEditor.tsx` về đây làm nguồn duy nhất; `BundleEditor.tsx` import lại từ `./types`. Thêm type mới: `AiFixPatch`, `AiFixUnresolved`, `AiFixResult`, `AiFixResolution = "original" | "fixed" | "both"`.

**`useDocsBuilder.ts`**: thêm state `aiFixPatches`, `aiFixUnresolved`, `aiFixResolutions` (`Record<id, AiFixResolution>`, default mỗi patch = `"fixed"`), `showAiFixPanel`. `handleAiFixBundle` đổi từ `setBundleContent(data.content)` thành lưu `data.patches`/`data.unresolved` + mở panel (không patch nào → alert, không mở panel). Hàm mới `applyAiFixResolutions()`: sort patch theo `start_line` **giảm dần**, `splice` từng patch vào `bundleContent` theo lựa chọn (`original`/`fixed`/`both` = nối `original_text` + `fixed_text`, không marker) — xử lý từ dòng cuối lên đầu để các patch chưa xử lý không bị lệch số dòng.

**`AiFixPanel.tsx`** (file mới): modal hiển thị từng patch bằng `DiffEditor` (`original`/`modified` = `original_text`/`fixed_text`, `language="yaml"`, readOnly, side-by-side) kèm 3 nút chọn lựa dưới mỗi patch, danh sách `unresolved` hiển thị dạng thông báo "cần sửa tay", nút "Áp dụng" gọi `applyAiFixResolutions`. Dynamic import `ssr:false` giống `BundleEditor`.

**`page.tsx`**: destructure state/handler mới từ `useDocsBuilder`, render `<AiFixPanel />` song song với `BundleEditorModal` (không lồng vào trong).

## File bị sửa
- `backend/main.py` — sửa `_bundle_lint_build_docs` (thêm chạy `--format checkstyle` + merge line/col vào Redocly issues, mục 1, vì hàm này phục vụ cả luồng build/lint hiện có nên giữ ở `main.py`); route `ai_fix_bundle` rút gọn lại thành gọi `ai_fix.run(...)`.
- `backend/ai_fix.py` — **file mới** (mục 0): `_parse_checkstyle_output`, `_find_block_end`, `_merge_overlapping_ranges`, `_build_batch_prompt`, hàm tổng `run(content, spectral, redocly)` (tự gọi Claude + `_parse_ai_json` + validate + trả `{patches, unresolved, failed}`).
- `frontend/app/_dashboard/types.ts` — sửa `RedoclyIssue.location` thêm `line`/`column` (số thật, không còn optional-nhưng-luôn-undefined), thêm type `AiFixPatch`, `AiFixUnresolved`, `AiFixResult`, `AiFixResolution`.
- `frontend/app/_dashboard/BundleEditor.tsx` — xoá type trùng lặp, import `SpectralIssue`/`RedoclyIssue` từ `types.ts` (marker Redocly sẽ tự động đúng vị trí nhờ có line/col thật).
- `frontend/app/_dashboard/hooks/useDocsBuilder.ts` — state + `handleAiFixBundle` + `applyAiFixResolutions` mới.
- `frontend/app/_dashboard/AiFixPanel.tsx` — **file mới**.
- `frontend/app/page.tsx` — wire state mới + render `AiFixPanel`.

## Edge case đã tính tới
- Redocly issue thiếu `location`, hoặc checkstyle không khớp được (ruleId+message không trùng) → vào `unresolved`, không tạo patch — không bao giờ vi phạm "không sửa toàn file".
- AI không trả `fixed_text` cho 1 id, hoặc trả nhưng không parse được khi ghép lại → vào `failed`, các patch khác vẫn xử lý bình thường.
- "Giữ cả hai" có thể tạo YAML không hợp lệ (trùng key) — chấp nhận được, vì "Lưu & Kiểm tra lại" sẵn có sẽ bắt lại lỗi này, đúng tinh thần GitHub/VS Code's "Accept Both Changes".

## Verification
1. Backend: dùng 2 lỗi sẵn có thật trong `dist/openapi-bundled.yaml` (`info.license` thiếu `url` — dòng 5; `info.contact`/example data — dòng 1822) — build (`POST /docs/build`) lấy `spectral`/`redocly` (giờ có line/col thật), curl `POST /docs/bundle/ai-fix` với content+issues đó, xác nhận response có 2 patch đúng `start_line`/`end_line`, `unresolved`/`failed` rỗng.
2. Unit-style test `_find_block_end` với input dựng tay: mapping value, sequence item có sibling, scalar 1 dòng, block tới EOF, block có dòng trống ở giữa.
3. Unit-style test `_parse_checkstyle_output` với XML mẫu thật (đã có sẵn ở trên) — xác nhận parse đúng `ruleId`("source" attr)/`message`/`line`/`column`.
4. Browser: Build tài liệu → mở Bundle Editor → tab YAML thô → xác nhận marker Redocly giờ chỉ đúng dòng (trước đây luôn rơi về dòng 1 do thiếu line/col) → "AI tự fix lỗi" → xác nhận panel hiện 2 diff block; chọn "giữ bản đã sửa" cho 1 patch, "giữ bản gốc" cho patch khác → Áp dụng → xác nhận đúng patch được đổi, phần còn lại của file (ví dụ `servers:` ở dưới) không bị lệch dòng/nội dung. Thử thêm 1 lần "giữ cả hai" → Lưu & Kiểm tra lại → xác nhận lint bắt lỗi mới (key trùng) như kỳ vọng.
