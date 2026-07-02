import { NextRequest, NextResponse } from "next/server";
import { execSync } from "child_process";

// ─────────────────────────────────────────────────────────────
// ENV cần thiết (.env.local, server-side only):
//
//   REPO_LOCAL_PATH    = đường dẫn tuyệt đối tới thư mục repo git
//                         trên server (nơi UI đang ghi file 5.openapi/)
//   GH_DISPATCH_TOKEN  = PAT có quyền Actions: write
//   GH_OWNER           = owner/org của repo
//   GH_REPO            = tên repo
//
// LƯU Ý: server này phải có sẵn quyền `git push` lên remote (SSH key
// hoặc credential.helper cấu hình sẵn) — nếu không bước push sẽ lỗi.
// ─────────────────────────────────────────────────────────────

const WORKFLOW_FILE = "create-doc-pr.yaml";

function run(cmd: string, cwd: string) {
  return execSync(cmd, { cwd, stdio: "pipe" }).toString().trim();
}

export async function POST(req: NextRequest) {
  const repoDir = process.env.REPO_LOCAL_PATH;
  const token = process.env.GH_DISPATCH_TOKEN;
  const owner = process.env.GH_OWNER;
  const repo = process.env.GH_REPO;

  if (!repoDir || !token || !owner || !repo) {
    return NextResponse.json(
      {
        error:
          "Thiếu REPO_LOCAL_PATH / GH_DISPATCH_TOKEN / GH_OWNER / GH_REPO trên server.",
      },
      { status: 500 },
    );
  }

  let baseBranch: "main" | "develop" = "develop";
  try {
    const body = await req.json();
    if (body?.baseBranch === "main" || body?.baseBranch === "develop") {
      baseBranch = body.baseBranch;
    }
  } catch {
    // dùng mặc định "develop"
  }

  // 1. Kiểm tra có thay đổi thật trong 5.openapi/ chưa
  let status = "";
  try {
    status = run("git status --porcelain -- 5.openapi", repoDir);
  } catch (e) {
    return NextResponse.json(
      { error: `Không đọc được trạng thái git: ${(e as Error).message}` },
      { status: 500 },
    );
  }

  if (!status) {
    return NextResponse.json({
      ok: true,
      message: "Không có thay đổi nào trong 5.openapi/ để deploy.",
    });
  }

  const branchName = `auto/update-openapi-${Date.now()}`;

  // 2. Tạo branch mới, commit, push — rồi LUÔN quay lại base_branch
  //    cho dù thành công hay lỗi, để UI không bị kẹt ở branch tạm.
  try {
    run(`git checkout -b ${branchName}`, repoDir);
    run("git add 5.openapi", repoDir);
    run(
      `git commit -m "docs(openapi): cập nhật từ giao diện kiểm tra tài liệu"`,
      repoDir,
    );
    run(`git push origin ${branchName}`, repoDir);
  } catch (e) {
    try {
      run(`git checkout ${baseBranch}`, repoDir);
    } catch {
      // best-effort, không che lỗi gốc
    }
    return NextResponse.json(
      { error: `Lỗi khi commit/push local: ${(e as Error).message}` },
      { status: 500 },
    );
  }

  try {
    run(`git checkout ${baseBranch}`, repoDir);
  } catch (e) {
    // Branch đã push thành công lên remote rồi, chỉ là working dir local
    // chưa quay lại được base_branch — không chặn response, chỉ cảnh báo.
    console.error("Không quay lại được base_branch:", e);
  }

  // 3. Kích hoạt workflow: bundle lại + mở PR từ branch vừa push + auto-merge
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({
      ref: "main",
      inputs: { base_branch: baseBranch, branch_name: branchName },
    }),
  });

  if (res.status === 204) {
    return NextResponse.json({
      ok: true,
      message: `Đã push "${branchName}" và kích hoạt PR tự động. Sẽ tự merge nếu validate pass.`,
      branch: branchName,
    });
  }

  const errorText = await res.text();
  return NextResponse.json(
    { error: `GitHub API lỗi (${res.status}): ${errorText}` },
    { status: 502 },
  );
}
