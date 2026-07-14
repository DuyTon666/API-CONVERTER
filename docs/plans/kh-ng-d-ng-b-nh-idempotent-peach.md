# Mã lỗi nghiệp vụ (x-error-responses): hiển thị + review/xác nhận

Gồm 2 phần độc lập, làm tuần tự: **Phần 1 — Hiển thị** (frontend thuần, đã sẵn sàng thực hiện) và **Phần 2 — Review/xác nhận** (phác thảo trước, làm sau khi Phần 1 xong).

---

## Phần 1 — Hiển thị x-error-responses trong Swagger UI docs

### Context

Chuỗi lệnh `2.pipeline` (`errors:parse → resolve → apply → build-map → enrich`) ghi ra field `x-error-responses` rất chi tiết cho từng operation (mã lỗi nghiệp vụ, category, message, nhóm theo HTTP status) — nhưng hiện tại **không nơi nào hiển thị field này cho người đọc tài liệu**: `backend/services/operations.py` (Form Editor) không đụng tới nó, và cả 2 trang docs (`public/api-docs.html`, `/swagger`) đều dùng Swagger UI mặc định — Swagger UI tự động bỏ qua mọi field `x-*` nó không biết. Dữ liệu chỉ xem được nếu mở raw YAML.

Mục tiêu: chèn thêm phần hiển thị `x-error-responses` vào đúng trang docs người dùng thật sự xem, merge trực tiếp vào từng dòng HTTP status trong bảng Responses có sẵn (không tách khối riêng, không lặp lại số status) — đặt ngay dưới khối "Example Value | Schema" JSON mà Swagger UI đã tự sinh sẵn. Hướng thiết kế đã chốt qua mockup (xem Artifact đã duyệt trong hội thoại): mỗi status có mã lỗi thì dòng đó tự bung ra (badge số + mũi tên), dòng không có thì giữ nguyên bình thường; mỗi mã lỗi có chip màu theo `category`.

**Không nằm trong phạm vi lần này:** chỉnh sửa/review `x-error-responses` qua Form Editor — chỉ làm phần hiển thị (đọc), như đã thống nhất với user.

### Kết quả research (Explore agent đã xác nhận)

- **Trang thật sự tới tay người dùng:** `public/api-docs.html` (build bởi `scripts/build-swagger-ui.js`, deploy lên GitHub Pages qua `.github/workflows/deploy.yaml`) — đây là bản public. Song song có `/swagger` (`frontend/app/swagger/page.tsx` + `SwaggerView.tsx`) — bản preview trong dashboard nội bộ. Cả 2 đều dùng `swagger-ui-dist`/`SwaggerUIBundle` với cùng 1 plugin có sẵn (`fuseFilterPlugin`, đã bị **lặp y hệt** giữa 2 file — tiền lệ có sẵn trong repo cho việc 1 file build script thuần JS + 1 component React không share được module, nên lần này viết plugin mới cũng theo đúng tiền lệ đó, lặp có chủ đích).
- `build:docs:redocly` (`public/api-docs-redocly.html`) — script mồ côi, không ai gọi, không nằm trong CI/deploy — **bỏ qua, không cần đụng tới**.
- Cơ chế chèn: `swagger-ui-dist` hỗ trợ `wrapComponents.responses` (component cha, nhận được `props.operation` — Immutable Map chứa toàn bộ operation kể cả field `x-*`, giống cách `fuseFilterPlugin` đang dùng `.getIn([...])`). Đây là hook để inject — cần 1 bước dựng thử (spike) nhỏ đầu tiên để xác nhận chính xác cách lấy dữ liệu status-row con và chèn đúng vị trí (dưới JSON example, không đè lên).
- `x-error-responses` **sống sót qua bundle** — xác nhận có 54 chỗ trong `dist/openapi-bundled.yaml` hiện tại, cấu trúc nguyên vẹn. Không cần đổi gì ở bước bundle.
- Danh sách `category` thật đang dùng (grep toàn bộ `5.openapi/paths/**/*.yaml`): `Auth, Business, Compat, Concurrency, Config, Contact, Data, Format, Idempotency, Immutable, Input, Input validation, Insert data, Internal, Not Found, Provider, Rate Limit, Re-auth, Routing, State, Unique, Upstream, Validation` (24 giá trị, có vài tên gần giống nhau do dữ liệu viết tay không chuẩn hoá triệt để — không sửa data ở đây, chỉ cần palette đủ rộng + fallback).

### Thiết kế

#### 1. Spike xác nhận hook (làm trước tiên, trước khi viết plugin đầy đủ)

Dựng thử 1 bản tối giản `wrapComponents.responses` trong `frontend/app/swagger/SwaggerView.tsx` (sửa nhanh ở môi trường dev, có hot-reload, dễ kiểm chứng hơn sửa static HTML), log ra `props.operation.getIn(['x-error-responses'])` để xác nhận đọc được đúng dữ liệu và biết chính xác shape props nhận được, trước khi viết logic render đầy đủ. Nếu `wrapComponents.responses` không đưa đủ ngữ cảnh per-status cần thiết, thử `wrapComponents.response` (số ít) như phương án 2 — agent research đã note khả năng này.

#### 2. Viết plugin `errorCodesPlugin` (vanilla JS, không phụ thuộc framework)

Input: `operation` (Immutable Map, có sẵn trong props khi wrap), status code hiện tại đang render.
Logic:
- Đọc `operation.getIn(['x-error-responses', code])` → mảng `{code, category, message}` hoặc `undefined`.
- Không có → trả nguyên `<Original {...props} />`, không render gì thêm (dòng status giữ nguyên bình thường, đúng như mockup — vd `200`, `429`, `500`, `502`).
- Có → render `<Original {...props} />` rồi nối thêm markup mới: 1 `<details>` thu gọn mặc định (trừ khi tổng operation chỉ có 1 status có lỗi — logic tương tự mockup có sẵn), tiêu đề dạng "N mã lỗi", mở ra là bảng `code | category (chip màu) | message`.

Palette category: dùng đúng bộ màu đã duyệt trong mockup cho các category phổ biến (Auth, Input, Business, State, Validation, Not Found), các category còn lại (Compat, Concurrency, Config, Contact, Data, Format, Idempotency, Immutable, Input validation, Insert data, Internal, Provider, Rate Limit, Re-auth, Routing, Unique, Upstream) dùng 1 màu chip trung tính (xám) duy nhất — không bịa thêm 24 màu riêng biệt, tránh loãng, giữ đúng tinh thần "màu chip chỉ để mắt quét nhanh nhóm phổ biến", còn category hiếm thì đọc chữ trực tiếp.

CSS: tái dùng nguyên style đã duyệt ở mockup (biến `--err-*`, `.chip.*`, `.errtable`...) — inject 1 lần bằng `<style>` chèn vào `document.head` khi plugin khởi tạo (không phải per-row, tránh trùng lặp thẻ style).

#### 3. Áp dụng plugin vào cả 2 nơi tiêu thụ (lặp có chủ đích, theo đúng tiền lệ `fuseFilterPlugin`)

- `frontend/app/swagger/SwaggerView.tsx`: thêm `errorCodesPlugin` vào mảng `plugins: [fuseFilterPlugin]` → `plugins: [fuseFilterPlugin, errorCodesPlugin]`.
- `scripts/build-swagger-ui.js`: thêm hàm `errorCodesPlugin` (bản JS thuần, không TS) vào script inline, thêm vào mảng `plugins`.

#### 4. Không đổi gì ở backend/pipeline

`x-error-responses` đã có sẵn trong bundle, không cần route mới, không cần sửa `operations.py`/`schema_fields.py`. Đây là thay đổi thuần frontend/build-script.

### Verification (Phần 1)

1. `npm run bundle:api` (đảm bảo `dist/openapi-bundled.yaml` mới nhất, đã có `x-error-responses`).
2. Chạy `frontend`: `npm run dev`, mở `/swagger`, tìm 1 operation biết chắc có nhiều status kèm lỗi (vd `submitCsrForOrder`, `/v1/orders/{id}/submit-csr` — đã biết cụ thể 400/401/403/409/422 đều có mã, 200/429/500/502 không có) — đối chiếu từng dòng đúng như mockup đã duyệt: dòng có lỗi bung được, dòng không có lỗi giữ nguyên, đếm đúng số lượng mã mỗi status.
3. Kiểm tra 1 operation gần như không có `x-error-responses` nào cả (nếu có) — xác nhận Responses table hiện y hệt Swagger UI mặc định, không vỡ layout, không có `<details>` rỗng.
4. `npm run build:docs` → mở `public/api-docs.html` trực tiếp bằng trình duyệt (file local, không cần server) — xác nhận bản static hoạt động giống hệt bản React.
5. Test cả 2 theme sáng/tối nếu Swagger UI trang này có hỗ trợ dark mode (kiểm tra trước khi giả định).
6. Đối chiếu lại với đúng dữ liệu thật trong `5.openapi/paths/order/submit_csr_for_order.yaml` (không chỉ tin mockup) để tránh lặp lại sai sót đã gặp lúc làm mockup (lúc đó liệt kê thiếu 401/403/409/400 vẫn có mã lỗi).

---

## Phần 2 — Review & xác nhận mã lỗi (PHÁC THẢO — làm sau khi Phần 1 xong)

### Context

Dữ liệu mã lỗi nằm ở 2 tầng, đã xác nhận qua thảo luận với người phụ trách `2.pipeline` + đọc code thật:

- **`3.build/`** = khu vực nháp/đang review. `errors:parse` (CLI, teammate chạy) ghi ra `3.build/reports/errors/<module>/error_codes_review.json` — danh sách entry, mỗi entry có `status` (new/duplicate_ok/conflict/...). Entry nào cần người quyết định thì chưa có field `resolution`.
- **`4.config/`** = đã chốt chính thức (`error_code_map.yaml` global + `error_catalog.yaml`/`review_decisions.yaml` riêng module) — chỉ được ghi khi chạy `errors:apply`.

Mục tiêu Phần 2: thay vì phải gõ tay từng lệnh CLI `resolve --module --code --decision ...` rồi `apply-errors`, làm 1 màn hình review — liệt kê entry cần quyết định, mỗi dòng chọn quyết định (giống hệt tinh thần `ManualEditConflictsCard` đã có), rồi 1 nút "Xác nhận" gọi `apply-errors` để đẩy lên `4.config`.

**Lưu ý phạm vi:** Phần 2 KHÔNG bao gồm trigger `errors:parse`/`errors:build-map`/`errors:enrich` (những bước đó vẫn do người phụ trách `2.pipeline` chạy tay, hoặc bàn riêng sau) — chỉ làm đúng 2 bước **resolve** (quyết định) và **apply** (xác nhận/commit), đúng như user mô tả.

### Kết quả research (Explore agent đã xác nhận)

- **`resolve`** (`2.pipeline/run_api_import.py` → `cmd_resolve_error` trong `contract_profile/run_error_parser.py:258-322`): nhận `module`, `code`, `decision` (chỉ 1 trong 4 giá trị: `reassign`/`keep_existing`/`approve_new`/`repair_existing`), `new_code` (bắt buộc nếu `reassign`), `approved_by`, `source_file` (tuỳ chọn, để phân biệt khi 1 code trùng ở nhiều file). Hàm này **chỉ sửa report JSON** (tìm đúng entry theo code, ghi field `resolution = {decision, approved_by, approved_at, new_code?}`), validate hợp lệ trước khi ghi (vd `reassign` phải kiểm tra `new_code` chưa tồn tại) — **không đụng `4.config`**. Không gọi AI — an toàn wrap trực tiếp vào backend, không cần lo credentials.
- **`apply-errors`** (`cmd_apply_errors` → `apply_decisions()` trong `contract_profile/apply_review_decisions.py:263-393`): duyệt toàn bộ entries trong report, entry nào **chưa có `resolution`** thì tự bỏ qua (không lỗi, không bắt buộc phải resolve hết 100% mới apply được) — ghi vào `error_code_map.yaml` (nếu global) hoặc `error_catalog.yaml` (nếu module), cộng thêm `review_decisions.yaml`. Không gọi AI.
- Cả 2 hàm đã tách sẵn khỏi argparse (giống các hàm `cmd_*` khác đã thấy) — backend import gọi thẳng được, không cần subprocess.

### Thiết kế

#### 1. Backend — service mới `backend/services/error_codes.py`

- `list_error_entries(module: str) -> dict` — đọc thẳng `3.build/reports/errors/<module>/error_codes_review.json` (không gọi `cmd_parse_errors` lại — dữ liệu do teammate chạy `errors:parse` sinh sẵn), trả nguyên `entries` + `summary`. Tương tự cách `manual_edit_conflicts.py::list_conflicts()` đọc thẳng file JSON có sẵn.
- `resolve_error_entry(module, code, decision, approved_by, new_code=None, source_file=None) -> dict` — import gọi thẳng `cmd_resolve_error(...)` (từ `2.pipeline/contract_profile/run_error_parser.py`, cần thêm `2.pipeline` vào `sys.path` — xem cách `core/config.py` đã làm cho `generator.emitter`). Trả lại kết quả bằng cách đọc lại report sau khi gọi (theo đúng pattern "gọi hàm rồi đọc lại file" đã thống nhất, không cần hàm trả return).
- `apply_error_entries(module) -> dict` — tương tự, gọi `cmd_apply_errors(...)`, đọc lại kết quả (report sau apply, hoặc trả thẳng số lượng applied/skipped nếu hàm gốc có return — cần xác nhận lúc code thật, hàm `apply_decisions` có vẻ đã tính sẵn `applied`/`skipped`/`rejected`, tận dụng luôn nếu có).

Cần xác nhận thêm lúc code thật: `approved_by` lấy từ đâu — app hiện không có hệt thống đăng nhập/user — có thể dùng ô nhập tên tự do trên UI (giống `review_decisions.yaml` đang ghi tên "Duy" thủ công), hoặc 1 giá trị cấu hình cố định. Cần hỏi lại user khi bắt tay code phần này.

#### 2. Backend — router mới `backend/routers/error_codes.py`

- `GET /errors/{module}` → `list_error_entries`
- `POST /errors/{module}/resolve` → `resolve_error_entry` (body: `code`, `decision`, `new_code?`, `approved_by`, `source_file?`)
- `POST /errors/{module}/apply` → `apply_error_entries`

Đăng ký router trong `main.py` theo đúng pattern các router khác.

#### 3. Frontend — card mới, dựng theo khuôn `ManualEditConflictsCard.tsx`

- **Vị trí hiển thị (đã chốt):** card **luôn nằm sẵn trên dashboard chính** (`app/page.tsx`), y hệt cách `ManualEditConflictsCard` đang hoạt động — không phải trang/tab riêng phải chủ động vào xem. Lý do: app không có hệ thống đăng nhập/thông báo nên không thể "đẩy" thông báo chủ động tới người dùng; dữ liệu lại được sinh ra ngoài web app (teammate chạy CLI `errors:parse`) nên web không biết khi nào có gì mới — cách khả thi nhất là card tự fetch mỗi lần dashboard load, có entry cần xử lý (status khác `duplicate_ok`) thì tự hiện badge số lượng + bảng, không có thì tự ẩn gọn/im lặng.
- Chọn module (dropdown, tái dùng danh sách module đã có ở `ModuleRegistryCard`).
- Bảng entries: hiển thị `code`, `status` (badge màu theo new/conflict/duplicate_ok), `incoming_message` vs `existing_message` (so sánh cạnh nhau, giống cách `ManualEditConflictsCard` hiện so `old_value`/`new_value`), 4 nút quyết định (keep_existing/reassign+ô nhập mã mới/approve_new/repair_existing) — bấm là gọi `resolve` ngay cho entry đó (2 bước tách biệt: resolve từng dòng, rồi mới apply cả module). Người dùng luôn phải tự bấm chọn — không có nút nào tự động pre-select/tự tin cậy gợi ý máy, vì `error_review_policy.suggest_decision()` (công cụ gợi ý có sẵn trong `2.pipeline`) dùng ngưỡng cứng (0.55 global / 0.72 module similarity), không có độ tin cậy, dễ sai case biên — chỉ dùng làm dòng gợi ý tham khảo nhỏ cạnh mỗi entry (không bắt buộc, có thể làm sau), không dùng để tự chọn quyết định thay người dùng.
- Nút "Xác nhận" cấp module — gọi `apply`, hiện kết quả (bao nhiêu applied/skipped).

### Việc cần làm rõ trước khi code (để hỏi lại user)

1. `approved_by` lấy từ đâu — ô nhập tay hay cố định.
2. Entry `status: duplicate_ok` (không phải conflict thật) có cần hiện trong UI để resolve không, hay chỉ hiện `conflict`/`new` (cần người quyết định thật sự)? (Mockup hiện tại đã làm theo hướng: mặc định ẩn `duplicate_ok`, có checkbox bật lại nếu cần xem.)
3. ~~Có cần nút trigger `errors:parse` ngay trong UI này luôn không~~ — đã chốt: không, giữ nguyên ngoài phạm vi Phần 2 (xem Context).
4. Vị trí/cơ chế hiện card — đã chốt: luôn nằm sẵn trên dashboard, tự ẩn/hiện theo dữ liệu, không phải trang riêng (xem mục 3 Thiết kế phía trên).

### Verification (Phần 2 — khi thực hiện)

1. Test qua `resolve_error_entry`/`apply_error_entries` bằng script Python độc lập trước (giống cách đã test `bundle_sync.py` — dựng thư mục `3.build`/`4.config` giả trong `/tmp`, không đụng file thật) để xác nhận gọi đúng, không lỗi.
2. Test tình huống thật trên 1 module nhỏ (vd `csr`, chỉ 1 file) — resolve xong đối chiếu report JSON có đúng field `resolution`, apply xong đối chiếu `error_code_map.yaml`/`error_catalog.yaml` có đúng entry mới.
3. Test entry `reassign` với `new_code` trùng mã đã tồn tại — xác nhận bị từ chối đúng như validate của `cmd_resolve_error`, không phải tự viết lại validate ở backend.
