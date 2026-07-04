# Refactor deploy-docs/route.ts: bỏ git cục bộ, dùng GitHub Git Data API

## Context

`frontend/app/api/deploy-docs/route.ts` hiện tại chạy `git checkout -b` / `git add` / `git commit` / `git push` bằng `execSync` trên một bản clone local (`REPO_LOCAL_PATH`), đòi hỏi server chạy Next.js phải có sẵn credential push git (SSH key hoặc credential.helper) tồn tại vĩnh viễn trên máy. Đây là rủi ro kiến trúc: credential sống lâu dài trên web server (thay vì token ngắn hạn chỉ dùng trong 1 lần chạy CI), working directory dùng chung dễ bị "kẹt" ở branch tạm (bug đã gặp: `git checkout <baseBranch>` fail sau khi push thành công), và phụ thuộc binary `git` + 1 bản clone ghi được — thứ nhiều nền tảng host Next.js hiện đại (serverless/edge) không hỗ trợ.

Mục tiêu: loại bỏ hoàn toàn nhu cầu credential push + working tree cục bộ, thay bằng các lệnh gọi HTTPS thuần tới GitHub Git Data API (tạo blob → tree → commit → ref) — mỗi lần deploy là 1 chuỗi API call độc lập, không có state cục bộ nào để bị kẹt.

## Quyết định thiết kế

**Bỏ hẳn git khỏi route này (không giữ lại kể cả ở chế độ chỉ-đọc).** Vì `5.openapi/` vốn đã nằm ngay trên ổ đĩa server Next.js (do pipeline Python ghi trực tiếp), route chỉ cần đọc file bằng `fs.readFile` thường — không cần `git status`/`git diff` gì cả. Diff được tính bằng cách so sánh git-blob-SHA của file local với SHA GitHub trả về qua Trees API — không cần binary `git`, không cần `git fetch` định kỳ để tránh stale.

**Giữ nguyên `fetch()` thuần, không thêm `@octokit`** — nhất quán với code hiện tại (`create-doc-pr/route.ts` cũng dùng raw fetch). Ghi chú: nếu sau này logic GitHub API phình to hơn, có thể cân nhắc `@octokit/rest` để đỡ phải tự ghép JSON tay — nhưng không làm trong lần này.

## Các thay đổi cụ thể

### 1. `frontend/app/api/deploy-docs/route.ts` — viết lại toàn bộ phần xử lý git

Header dùng chung:
```ts
const GH_HEADERS = (token: string) => ({
  Accept: "application/vnd.github+json",
  Authorization: `Bearer ${token}`,
  "X-GitHub-Api-Version": "2022-11-28",
});
```

**Bước 1 — Kiểm tra base branch tồn tại + lấy HEAD sha** (thay cho `git rev-parse --verify`):
`GET /repos/{owner}/{repo}/git/ref/heads/{baseBranch}` → 200 lấy `object.sha` làm `baseSha`; 404 → trả 400 y như hiện tại.

**Bước 2 — Tính diff không cần git:**
- `GET /repos/{owner}/{repo}/git/commits/{baseSha}` → lấy `tree.sha` làm `baseTreeSha`.
- `GET /repos/{owner}/{repo}/git/trees/{baseTreeSha}?recursive=1` → lọc entry có `path` bắt đầu bằng `5.openapi/` → map `path → sha`.
- Đọc toàn bộ file local dưới `5.openapi/` (đường dẫn tuyệt đối, xem mục env var bên dưới), tính git-blob-sha từng file bằng:
  ```ts
  import { createHash } from "node:crypto";
  function gitBlobSha(content: Buffer): string {
    const header = Buffer.from(`blob ${content.length}\0`);
    return createHash("sha1").update(Buffer.concat([header, content])).digest("hex");
  }
  ```
- So sánh: không có trong map → **added**; có nhưng sha khác → **modified**; có trong map nhưng không có file local tương ứng → **deleted**.
- Nếu không có gì thay đổi → trả sớm `{ ok: true, message: "Không có thay đổi nào trong 5.openapi/ để deploy." }` y hệt hiện tại, **không gọi thêm bất kỳ API ghi nào**.

**Bước 3 — Tạo blob cho từng file added/modified** (bỏ qua file deleted):
`POST /repos/{owner}/{repo}/git/blobs` với `{ content: base64, encoding: "base64" }`. Đọc file bằng `fs.readFile(path)` (Buffer thô, không qua UTF-8) rồi `.toString("base64")` để tránh lỗi encoding. Chạy song song bằng `Promise.all`. Lỗi bất kỳ blob nào → dừng, trả 500, không tạo tree/commit dở dang.

**Bước 4 — Tạo tree mới:**
`POST /repos/{owner}/{repo}/git/trees` với `base_tree: baseTreeSha` + mảng entry `{ path, mode: "100644", type: "blob", sha }` (file added/modified dùng blob sha vừa tạo; file deleted dùng `sha: null`). Không cần tự dựng cây thư mục cha — GitHub tự xử lý path lồng nhau.

**Bước 5 — Tạo commit:**
`POST /repos/{owner}/{repo}/git/commits` với `{ message, tree: newTreeSha, parents: [baseSha] }`.

**Bước 6 — Tạo branch mới** (thay `git checkout -b` + `git push`):
`POST /repos/{owner}/{repo}/git/refs` với `{ ref: "refs/heads/" + branchName, sha: newCommitSha }`. Thành công → không còn bước "quay lại baseBranch" nào nữa vì không có working tree cục bộ để bị kẹt — xoá hẳn đoạn code `git checkout <baseBranch>` (best-effort) và bug đi kèm nó.

**Bước 7 — Dispatch workflow `create-doc-pr.yaml`: giữ nguyên 100%**, không đổi gì (vẫn cùng 1 request fetch như hiện tại).

**Response shape/status code giữ nguyên hoàn toàn** để `lib/api/dashboard/deploy.ts` và `useDocsBuilder.handleDeploy()` không cần sửa gì:

| Trường hợp | Status | Body |
|---|---|---|
| Thiếu env var | 500 | `{ error }` |
| `baseBranch` không tồn tại | 400 | `{ error }` |
| Không có thay đổi | 200 | `{ ok: true, message }` |
| Lỗi tạo blob/tree/commit/ref | 500 | `{ error }` |
| Dispatch workflow lỗi | 502 | `{ error }` |
| Thành công | 200 | `{ ok: true, message, branch }` |

### 2. Biến môi trường (`frontend/.env.local`, `.env.local.example`)
- **Xoá** `REPO_LOCAL_PATH` — không còn dùng.
- **Thêm** `OPENAPI_DIR` — đường dẫn tuyệt đối tới thư mục `5.openapi/` (không dựa vào `process.cwd()` vì lúc `next dev`/`next start` cwd thường là `frontend/`, dễ sai đường dẫn tương đối).
- `GH_DISPATCH_TOKEN`: cần bổ sung quyền **Contents: Read and write** (fine-grained PAT) hoặc scope `repo` (classic PAT) — thêm bên cạnh quyền dispatch Actions đã có, giữ nguyên tên biến.
- Cập nhật comment đầu file `route.ts` (dòng 4-15 hiện tại) phản ánh: không còn cần git push credential, chỉ cần PAT đủ quyền Git Data API + Actions dispatch.

## Ngoài phạm vi (không đụng vào)
- `frontend/app/api/create-doc-pr/route.ts` (dead code, không dùng).
- `.github/workflows/create-doc-pr.yaml` (không cần đổi — workflow chỉ `checkout` theo `branch_name`, không quan tâm branch đó được tạo bằng cách nào).
- Bất kỳ code pipeline/backend nào.

## Kiểm thử

1. `cd frontend && npx tsc --noEmit && npm run lint` — bắt lỗi kiểu dữ liệu trước khi gọi API thật.
2. Thêm cờ debug nội bộ `dryRun: true` trong body request (không expose ra UI) — chạy bước 1-2 (kiểm tra branch + tính diff), log ra danh sách file sẽ tạo/sửa/xoá mà không gọi các bước ghi (3-7). Dùng để kiểm tra logic diff an toàn trước khi thử ghi thật.
3. Test trên 1 branch nháp — **hiện repo chưa có branch nháp nào, cần tạo mới** (VD `test/deploy-docs-sandbox`, tạo tay trên GitHub trước khi bắt đầu test, không tự động tạo trong code). Gọi trực tiếp bằng `curl` với `baseBranch` trỏ vào branch đó (bỏ qua ràng buộc `"main"|"develop"` ở tầng UI vì đây là gọi thẳng API):
   - Gõ sai tên branch → xác nhận trả 400 đúng.
   - Sửa 1 file trong `5.openapi/`, chạy full flow → xác nhận branch `auto/update-openapi-<ts>` mới xuất hiện trên GitHub, commit chỉ chứa đúng 1 file đó (xem qua GitHub compare view), không đụng file nào khác.
   - Xoá 1 file local, chạy lại → xác nhận commit thể hiện đúng là xoá file, không phải file rỗng.
   - Không sửa gì → xác nhận trả về sớm `{ok:true, message:"Không có thay đổi..."}`, không gọi API ghi nào (có thể tạm dùng token sai để confirm không có lỗi auth nào bắn ra ở nhánh này).
4. Chạy thử dispatch workflow 1 lần trỏ vào branch nháp — xác nhận `create-doc-pr.yaml` chạy bình thường với branch tạo qua API (không phụ thuộc cách tạo branch).
5. Dọn dẹp: xoá branch/PR nháp sinh ra trong lúc test.
6. Cuối cùng chạy thật 1 lần với thay đổi nhỏ, vô hại (sửa 1 dòng comment trong file `5.openapi/`) nhắm vào `develop` thật để xác nhận hoạt động đúng trong môi trường thật, để pipeline PR/validate/auto-merge xử lý tiếp như thiết kế.
