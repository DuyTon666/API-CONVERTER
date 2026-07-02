import { NextRequest, NextResponse } from "next/server";

const WORKFLOW_FILE = "create-doc-pr.yaml";

export async function POST(req: NextRequest) {
  const token = process.env.GH_DISPATCH_TOKEN;
  const owner = process.env.GH_OWNER;
  const repo = process.env.GH_REPO;

  if (!token || !owner || !repo) {
    return NextResponse.json(
      {
        error:
          "Thiếu cấu hình GH_DISPATCH_TOKEN / GH_OWNER / GH_REPO trên server.",
      },
      { status: 500 },
    );
  }

  let baseBranch = "develop";
  try {
    const body = await req.json();
    if (body?.baseBranch === "main" || body?.baseBranch === "develop") {
      baseBranch = body.baseBranch;
    }
  } catch {
    // không có body dùng mặc định develop
  }

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vn.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({
      ref: "main",
      inputs: { base_branch: baseBranch },
    }),
  });

  if (res.status === 204) {
    return NextResponse.json({
      ok: true,
      message:
        "Đã kích hoạt workflow tạo PR. Kiểm tra tab Actions hoặc Pull requests sau vài giây.",
      actionsUrl: `https://github.com/${owner}/${repo}/actions/workflows/${WORKFLOW_FILE}`,
    });
  }

  const errorText = await res.text();
  return NextResponse.json(
    { error: `GitHub API lỗi (${res.status}): ${errorText}` },
    { status: 502 },
  );
}
