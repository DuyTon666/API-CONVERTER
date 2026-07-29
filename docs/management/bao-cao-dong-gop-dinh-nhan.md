# Báo cáo đóng góp — Đinh Nhân

> Phạm vi: toàn bộ thời gian tham gia dự án API Converter. Đội ngũ gồm 2 thành viên chính (Em và Duy Tôn bạn phụ trách phần `2.pipeline/`), báo cáo này chỉ liệt kê phần việc do em trực tiếp thực hiện.

## 1. Tóm tắt vai trò

Phụ trách toàn bộ phần **ứng dụng** của dự án — **Backend (FastAPI)**, **Frontend (Next.js)** (dashboard + Developer Portal/search), cấu hình lint **Spectral/Redocly**, toàn bộ **CI/CD** (`.github/workflows/`), và tính năng **Deploy** tài liệu lên GitHub Pages. Không đụng tới các thư mục pipeline (`1.docs/`, `2.pipeline/`, `3.build/`, `4.config/`, `5.openapi/`, `6.path_stub/`) — phần convert tài liệu → YAML, sinh output, và cấu hình module đó do bạn Duy Tôn phụ trách; backend của em chỉ *gọi vào* pipeline đó (import trực tiếp `pipeline_API.py`) và *đọc/ghi output* của nó (`5.openapi/`, `3.build/reports/`), không viết logic bên trong.

## 2. Bảng tổng hợp theo hạng mục

| Hạng mục                 | Số việc chính                            | Ghi chú                                                                                                                                                                                                             |
| ------------------------ | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tính năng mới xây từ đầu | 7                                        | Dashboard UI, Developer Portal (search), Form Editor non-dev, AI Suggest/AI Fix, Manual-edit-conflict, Deploy tài liệu, Error Code review                                                                           |
| Cấu hình lint OpenAPI    | 6/7 rule Spectral + toàn bộ redocly.yaml | Tự viết 6/7 custom function rule trong `functions/`, migrate `.spectral.js` → `.spectral.yaml`                                                                                                                      |
| Tái cấu trúc (refactor)  | 3                                        | Tách hooks frontend, tách router/service backend, đổi cấu trúc thư mục frontend                                                                                                                                     |
| Bug/lỗi bảo mật đã vá    | 4                                        | Lỗi Monaco raw-YAML editor, mất commit khi deploy, workflow không tự trigger, command injection trong CI                                                                                                            |
| Tài liệu kỹ thuật        | 11                                       | uc-detail.md + activity/sequence diagram, docs/architecture/kien-truc-backend.md, docs/architecture/kien-truc-frontend.md, setup-local-dev.md, setup-slack.md, setup-cicd.md, conventions/redocly.md, conventions/spectral.md, oas-diff.md, manual-test-checklist.md |


## 3. Chi tiết theo từng giai đoạn

### Giai đoạn 1 — Khởi tạo dự án, nền CI/CD & bộ rule Spectral/Redocly (27/05 – 02/06)

- Gộp 2 phần việc rời rạc (pipeline convert tài liệu + phần CI/CD) thành 1 repo thống nhất: đưa vào `.github/workflows/` (`ci.yaml`, `deploy.yaml`, `diff.yaml`, `validate.yaml`), `.github/pull_request_template.md`, và tài liệu `docs/devops/cicd-runbook.md` (~2800 dòng, quy trình vận hành CI/CD chi tiết). Đây là nền tảng cho toàn bộ pipeline kiểm tra chất lượng OpenAPI spec chạy tự động trên mọi PR trong suốt dự án (Spectral lint + Redocly validate + OAS-diff).
- Viết ban đầu `.spectral.js` (rule lint OpenAPI riêng cho dự án, 178 dòng), sau đó migrate toàn bộ sang `.spectral.yaml` (đúng định dạng chuẩn Spectral khuyến nghị), rồi tinh gọn lại (bỏ ~61 dòng lặp) thành bản hiện tại (126 dòng, kế thừa `spectral:oas` ở mức `all` + 14 rule tự viết riêng cho dự án).
- Tự viết **6/7 custom function rule** trong `functions/` — mỗi rule là 1 file JS kiểm tra 1 quy ước riêng của dự án, không có sẵn trong bộ chuẩn Spectral: `client-id-must-not-be-readonly.js`, `enum-has-description.js`, `has-request-body-must-have-400.js`, `private-must-have-401-403.js`, `property-must-have-description.js`, `server-id-must-be-readonly.js` (rule thứ 7, `has-2xx-response.js`, do bạn Duy bổ sung sau vào 07/07).
- Viết mới hoàn toàn `redocly.yaml` (23 dòng) — cấu hình validate riêng biệt với Spectral, chạy trên cùng bundle `dist/openapi-bundled.yaml`.

### Giai đoạn 2 — Xây dựng Dashboard UI (01/06 – 12/06)

- Dựng từ đầu giao diện dashboard Next.js: trang chủ (`app/page.tsx`), các card nghiệp vụ (scan tài liệu, quản lý module, import, build/lint tài liệu).
- Nhiều vòng lặp chỉnh sửa UI liên tục trong 2 tuần (6 commit "xây dựng/update ui") để bám sát luồng nghiệp vụ: scan → suggest → apply → import → docs, phản ánh đúng `WorkflowStepper` hiện tại của dashboard.
- Vá lỗi cấu hình biến môi trường (`fix bug env`) — nguyên nhân do frontend/backend cần 2 file `.env` riêng biệt (`NEXT_PUBLIC_API_URL` phía frontend, `ANTHROPIC_*`/CORS phía backend).

### Giai đoạn 3 — Developer Portal (09/06)

- Xây tính năng mới: `frontend/app/portal/` — 1 trang tra cứu API độc lập với dashboard, gồm `PortalSearch.tsx` (tìm kiếm endpoint bằng Fuse.js), `EndpointCard.tsx`, `EndpointDetailDrawer.tsx` (drawer xem chi tiết endpoint), `SchemaViewer.tsx` (hiển thị schema request/response).
- Thêm bộ component UI dùng chung dựa trên shadcn/ui (`components.json`, `components/ui/button.tsx`, `components/ui/tabs.tsx`) — nền tảng style cho các tính năng UI sau này.
- Quy mô: ~5400 dòng thay đổi trong 1 commit, phần lớn là trang portal mới hoàn toàn.

### Giai đoạn 4 — Tài liệu hoá Use Case & sơ đồ luồng (15/06 – 16/06)

- Viết `docs/architecture/uc-detail.md` (đặc tả chi tiết use case, ~500 dòng) và 9 sơ đồ activity (`docs/architecture/diagrams/activity/UC01..09_activity.puml`) mô tả luồng xử lý từng use case chính của hệ thống.
- Bổ sung tiếp 8 sơ đồ sequence (`docs/architecture/diagrams/sequence/UC01..08_sequence.puml`) và `docs/architecture/diagram-guide.md` hướng dẫn cách đọc/tạo sơ đồ — dùng làm tài liệu tham chiếu khi cần giải thích luồng xử lý cho người ngoài team.

### Giai đoạn 5 — Form Editor cho người dùng không rành kỹ thuật (18/06)

- Xây tính năng "Form Editor" (`OperationsFormEditor.tsx`, ~310 dòng) — cho phép chỉnh `summary`/`description` của từng operation OpenAPI qua form thông thường, không cần biết cú pháp YAML.
- Backend bổ sung route tương ứng để đọc/ghi field này trực tiếp vào bundle YAML (tiền thân của route `/docs/operations` hiện tại).
- Mở rộng `scripts/build-swagger-ui.js` (+116 dòng) để build HTML Swagger UI phản ánh đúng nội dung đã chỉnh.

### Giai đoạn 6 — Tái cấu trúc Frontend: tách hooks (20/06)

- Tách toàn bộ state/logic từng nằm dồn trong `app/page.tsx` (474 dòng logic bị cắt giảm) ra 5 custom hook riêng: `useScan`, `useModuleRegistry`, `useSuggestions`, `useDocsBuilder`, `useUpload` — mỗi hook chỉ quản lý đúng 1 mảng nghiệp vụ.
- Dọn luôn route cũ không còn ai gọi tới (`app/jobs/[job_id]/page.tsx`, 347 dòng) — hệ quả của việc hệ thống job upload cũ được thay bằng luồng module import.
- Mục đích: giữ `page.tsx` chỉ còn vai trò compose hook + render layout, dễ bảo trì hơn khi số lượng tính năng tăng lên.

### Giai đoạn 7 — AI Suggest & tái cấu trúc Backend thành routers/services (24/06 – 25/06)

- Thêm tính năng gợi ý nội dung tự động ngay trong Monaco Editor (raw YAML tab) và cơ chế AI Fix (`backend/ai_fix.py`, 242 dòng) — gọi Claude để đề xuất sửa lỗi Spectral/Redocly, trả về patch để người dùng tự chọn accept/reject thay vì ghi đè trực tiếp.
- Tái cấu trúc backend từ 1 file `main.py` gần 630 dòng thành cấu trúc phân lớp: `routers/` (chỉ chứa route handler), `config.py`, `errors.py` (sau này tiếp tục tách thành `core/config.py`, `core/errors.py`) — đặt nền cho quy ước "router mỏng, logic nằm ở service" áp dụng xuyên suốt phần backend còn lại của dự án.

### Giai đoạn 8 — Phát hiện & xử lý xung đột chỉnh sửa thủ công (26/06)

- Xây tính năng "manual-edit-conflict": phát hiện trường hợp người dùng sửa tay trực tiếp trên file YAML trong `5.openapi/` (ngoài quy trình qua UI), rồi pipeline import ghi đè lại — có thể làm mất nội dung đã sửa tay mà không ai biết.
- Thêm `ManualEditConflictsCard.tsx` + hook `useManualEditConflicts` ở frontend, cùng route quét/so sánh tương ứng ở backend (đặt nền cho `services/manual_edit_conflicts.py` hiện tại).

### Giai đoạn 9 — Vá lỗi chỉnh sửa YAML thô & xây dựng cơ chế đồng bộ 2 tầng (29/06)

- Sửa lỗi ở tab "YAML thô" (Monaco) trong Bundle Editor.
- Xây `backend/bundle_sync.py` (240 dòng) — cơ chế đồng bộ khi 1 field bị sửa cả ở tầng 2 (`5.openapi/paths|components`) lẫn tầng 3 (`dist/openapi-bundled.yaml`), tránh 2 tầng lệch nhau sau khi build lại. Đây là tiền thân của `services/bundle_sync.py` hiện đang được cả `operations.py`, `schema_fields.py`, `bundle_content.py`, `manual_edit_conflicts.py` dùng chung.
- Thêm `backend/field_paths.py` (mini-language địa chỉ hoá field theo path, ví dụ `paths./tickets.get.responses.200...`) làm cú pháp chung cho mọi service cần trỏ tới 1 field cụ thể trong cấu trúc OpenAPI lồng nhau.

### Giai đoạn 10 — Deploy tài liệu qua GitHub API (01/07)

- Xây tính năng "Deploy tài liệu": nút bấm trên `SwaggerDocsCard` → route Next.js server-side (`app/api/deploy-docs/route.ts`) → gọi thẳng GitHub REST Git Data API (không cần git binary cục bộ, không cần checkout repo) để tạo blob/tree/commit/branch cho các file thay đổi dưới `5.openapi/**`, sau đó dispatch workflow `create-doc-pr.yaml` để tự bundle + mở PR + auto-merge.
- Thêm workflow `.github/workflows/create-doc-pr.yaml` (111 dòng, `workflow_dispatch` nhận `base_branch`/`branch_name`).
- Đổi tên `backend/utils/` → `backend/api_utils/` để tách rõ "helper domain-agnostic" khỏi phần business logic khi số lượng service tăng lên.

### Giai đoạn 11 — Tái cấu trúc cấu trúc thư mục Frontend & xử lý xung đột merge (02/07 – 05/07)

- Đổi cấu trúc thư mục frontend sang dạng hiện tại (`hooks/dashboard/`, `components/dashboard/`, `lib/api/dashboard/`), tách khỏi cách tổ chức co-located `app/_dashboard/` trước đó.
- Xử lý xung đột merge phát sinh khi gộp nhánh song song với phần việc CI/CD (`docs/devops/cicd-runbook.md`, `backend/pyrightconfig.json`).

### Giai đoạn 12 — Vá 3 lỗi trong pipeline CI/CD deploy (06/07)

Đây là giai đoạn phát hiện và vá lỗi có tác động lớn nhất, phát hiện qua test thủ công nhiều lần thất bại liên tiếp:

1. **Mất commit thật khi deploy** — action `peter-evans/create-pull-request` chỉ nhận diện file "dirty" tại thời điểm nó chạy; do route deploy-docs đã tự commit `5.openapi/**` qua Git Data API từ trước khi dispatch workflow, action không thấy gì mới ở path đó nên tự reset branch về base và chỉ giữ lại phần dist bundle vừa regenerate — xác minh bằng test thủ công: PR merge cuối cùng thiếu hẳn `5.openapi/**`, chỉ còn `dist/openapi-bundled.yaml`. Khắc phục: tự `git commit` phần bundle lên đúng branch đã có sẵn (không để action reset lịch sử), mở PR bằng `gh` CLI thay vì để action tự dựng lại nội dung branch.
2. **Workflow không tự trigger** — GitHub chặn cứng: sự kiện phát sinh (PR opened, push từ merge) do chính `GITHUB_TOKEN` mặc định của 1 workflow tạo ra sẽ không kích hoạt được workflow khác (cơ chế chống vòng lặp vô hạn), trừ `workflow_dispatch`/`repository_dispatch`. Xác nhận bằng dữ liệu thật: `ci.yaml` và `deploy.yaml` chưa từng chạy sau 4 lần test PR/merge liên tiếp dùng `GITHUB_TOKEN` mặc định. Khắc phục: đổi sang PAT riêng (secret `KEY_DEPLOY`, scope `repo`+`workflow`) ở bước tạo PR và bước bật auto-merge.
3. **Command injection trong CI** — nhét text nhiều dòng qua `${{ steps.x.outputs.y }}` dán thẳng vào script bash bước sau; nếu body chứa backtick literal, bash hiểu nhầm thành command substitution và tự chạy lại lệnh khác (`npm run bundle:api`) ngay trong câu lệnh `gh pr create --body`, vỡ cú pháp. Khắc phục: ghi body ra file riêng, dùng `--body-file` thay vì truyền `--body` qua biến output.
4. Thêm `chore(deploy): giữ lịch sử gh-page (force_orphan: false)` — tránh deploy GitHub Pages xoá sạch lịch sử commit của nhánh `gh-page` mỗi lần deploy.

### Giai đoạn 13 — Cập nhật Portal & hoàn thiện UI (07/07)

- Tiếp tục hoàn thiện `app/portal/` và điều chỉnh UI dashboard theo phản hồi thực tế sau khi dùng thử.

### Giai đoạn 14 — Tài liệu kiến trúc & tài liệu vận hành (09/07 – 17/07)

- Viết `docs/devops/setup-cicd.md`, cập nhật `docs/architecture/kien-truc-backend.md`/`docs/architecture/kien-truc-frontend.md` theo đúng cấu trúc code hiện tại (sau các đợt tái cấu trúc ở giai đoạn 7, 10, 11).
- Viết `docs/guidelines/conventions/spectral.md` và `docs/guidelines/conventions/redocly.md` — giải thích chi tiết từng rule đang cấu hình (14 rule tự viết trong `.spectral.yaml`, cấu hình `redocly.yaml`), rule đó check gì, khi nào fail, cách sửa — dùng làm tài liệu tham chiếu khi cần chỉnh sửa hoặc thêm rule mới sau này.
- Chuẩn bị tài liệu phục vụ báo cáo/bàn giao.

### Giai đoạn 15 — Tính năng Error Code Review (15/07 – 16/07)

- Xây tính năng mới "Error Code Review": route `backend/routers/error_codes.py` + `backend/services/error_codes.py` (165 dòng) đọc kết quả rà soát mã lỗi (`3.build/reports/errors/<module>/error_codes_review.json`) và quyết định resolve (`4.config/errors/modules/<module>/review_decisions.yaml`) do pipeline sinh ra, phục vụ UI review.
- Frontend: `ErrorCodesReviewCard.tsx` (293 dòng) — card mới trên dashboard để xem/duyệt mã lỗi theo từng module.
- Cập nhật hiển thị mã lỗi ở cả 2 nơi hiển thị tài liệu đã build: `frontend/app/portal/EndpointDetailDrawer.tsx` và `frontend/app/swagger/SwaggerView.tsx`.
- 2 PR: #22 (tính năng chính) và #23 (fix bug phát sinh sau review — "fix bug error code").

## 4. Tổng kết đóng góp

- **49 commit nội dung** (55 nếu tính cả merge commit) trên nhánh `develop`/các nhánh feature (không tính commit của Duy Tôn hay bot tự động), trải dài 7.5 tuần liên tục, không đứt quãng quá 3-4 ngày ở bất kỳ giai đoạn nào
- **7 tính năng** được xây dựng từ đầu (Dashboard UI, Developer Portal, Form Editor non-dev, AI Suggest/AI Fix, Manual-edit-conflict, Deploy tài liệu qua GitHub API, Error Code Review), phủ toàn bộ vòng đời sử dụng của hệ thống — từ nhập liệu, chỉnh sửa nội dung, kiểm tra chất lượng, đến xuất bản tài liệu.
- **3 lần tái cấu trúc lớn** (hooks frontend, routers/services backend, cấu trúc thư mục frontend) giúp codebase giữ được khả năng mở rộng khi số lượng tính năng tăng dần qua từng tuần, thay vì dồn hết logic vào 1-2 file.
- **4 lỗi/lỗ hổng đã tự phát hiện và vá**, trong đó có 1 lỗ hổng bảo mật (command injection trong CI) và 2 lỗi làm hỏng hoàn toàn luồng deploy tự động (mất commit, workflow không trigger) — cả 3 đều được xác minh bằng test thủ công thực tế trước khi kết luận nguyên nhân, không suy đoán.
- **Toàn bộ cấu hình kiểm tra chất lượng OpenAPI** (Spectral + Redocly) là tự viết: 6/7 custom rule trong `functions/`, migrate `.spectral.js` → `.spectral.yaml`, viết mới `redocly.yaml` — đây là lớp chặn lỗi tự động chạy trên mọi PR trong suốt dự án, không phải phần việc phụ.
- **Tài liệu kỹ thuật**: 9 sơ đồ activity + 8 sơ đồ sequence + đặc tả use case chi tiết, tài liệu kiến trúc backend/frontend luôn được cập nhật theo đúng code sau mỗi đợt tái cấu trúc, cùng 2 tài liệu giải thích rule Spectral/Redocly.
- **Phạm vi rõ ràng**: không bao gồm phần việc trong `1.docs/`, `2.pipeline/`, `3.build/`, `4.config/`, `5.openapi/`, `6.path_stub/` — các thư mục này do bạn Duy phụ trách.
