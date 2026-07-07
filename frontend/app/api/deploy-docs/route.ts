import { NextRequest, NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const WORKFLOW_FILE = "create-doc-pr.yaml";
const OPENAPI_REPO_PREFIX = "5.openapi/";

function ghHeaders(token: string) {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token}`,
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function gitBlobSha(content: Buffer): string {
  const header = Buffer.from(`blob ${content.length}\0`);
  return createHash("sha1")
    .update(Buffer.concat([header, content]))
    .digest("hex");
}

async function listFilesRecursive(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const full = path.join(dir, entry.name);
      return entry.isDirectory() ? listFilesRecursive(full) : [full];
    }),
  );
  return files.flat();
}

type TreeEntry = { path: string; sha: string; type: string };

type FileChange =
  | {
      status: "added" | "modified";
      repoPath: string;
      absPath: string;
    }
  | { status: "deleted"; repoPath: string };

export async function POST(req: NextRequest) {
  const openapiDir = process.env.OPENAPI_DIR;
  const token = process.env.GH_DISPATCH_TOKEN;
  const owner = process.env.GH_OWNER;
  const repo = process.env.GH_REPO;

  if (!openapiDir || !token || !owner || !repo) {
    return NextResponse.json(
      {
        error: "Thiếu các biến môi trường trong .env.local",
      },
      {
        status: 500,
      },
    );
  }

  let baseBranch: "main" | "develop" = "develop";
  try {
    const body = await req.json();
    if (body?.baseBranch === "main" || body?.baseBranch === "develop") {
      baseBranch = body.baseBranch;
    }
  } catch {}

  const headers = ghHeaders(token);
  const apiBase = `https://api.github.com/repos/${owner}/${repo}`;

  // 1. Kiểm tra base branch tồn tại + láy HEAD sha
  const refRes = await fetch(`${apiBase}/git/ref/heads/${baseBranch}`, {
    headers,
  });
  if (refRes.status === 404) {
    return NextResponse.json(
      {
        error: `Branch "${baseBranch}" chưa tồn tại trên remote. Hãy tạo branch này trước khi deploy.`,
      },
      {
        status: 400,
      },
    );
  }

  if (!refRes.ok) {
    return NextResponse.json(
      {
        error: `GitHub API lỗi khi lấy rè (${refRes.status}): ${await refRes.text()}`,
      },
      {
        status: 500,
      },
    );
  }

  const refData = await refRes.json();
  const baseSha: string = refData.object.sha;

  // 2. Tính diff không cần git - so git-blob-sha local vs sha trên GitHub
  const commitRes = await fetch(`${apiBase}/git/commits/${baseSha}`, {
    headers,
  });
  if (!commitRes.ok) {
    return NextResponse.json(
      {
        error: `GitHub API lỗi khi lấy commit (${commitRes.status}: ${await commitRes.text()})`,
      },
      { status: 500 },
    );
  }

  const commitData = await commitRes.json();
  const baseTreeSha: string = commitData.tree.sha;

  const treeRes = await fetch(
    `${apiBase}/git/trees/${baseTreeSha}?recursive=1`,
    { headers },
  );

  if (!treeRes.ok) {
    return NextResponse.json(
      {
        error: `GitHub API lỗi khi lấy tree (${treeRes.status}): ${await treeRes.text()}`,
      },
      { status: 500 },
    );
  }

  const treeData = await treeRes.json();

  const remoteShaByPath = new Map<string, string>();
  for (const entry of treeData.tree as TreeEntry[]) {
    if (entry.type === "blob" && entry.path.startsWith(OPENAPI_REPO_PREFIX)) {
      remoteShaByPath.set(entry.path, entry.sha);
    }
  }

  let localFiles: string[];
  try {
    localFiles = await listFilesRecursive(openapiDir);
  } catch (e) {
    return NextResponse.json(
      { error: `Khong đọc được thư mục OPENAPI_DIR ${(e as Error).message}` },
      { status: 500 },
    );
  }

  const localShaByPath = new Map<string, { absPath: string; sha: string }>();
  for (const absPath of localFiles) {
    const relPath = path
      .relative(openapiDir, absPath)
      .split(path.sep)
      .join("/");
    const repoPath = OPENAPI_REPO_PREFIX + relPath;
    const content = await readFile(absPath);
    localShaByPath.set(repoPath, { absPath, sha: gitBlobSha(content) });
  }
  const changes: FileChange[] = [];
  for (const [repoPath, { absPath, sha }] of localShaByPath) {
    const remoteSha = remoteShaByPath.get(repoPath);
    if (!remoteSha) {
      changes.push({ status: "added", repoPath, absPath });
    } else if (remoteSha !== sha) {
      changes.push({ status: "modified", repoPath, absPath });
    }
  }
  for (const repoPath of remoteShaByPath.keys()) {
    if (!localShaByPath.has(repoPath)) {
      changes.push({ status: "deleted", repoPath });
    }
  }

  if (changes.length === 0) {
    return NextResponse.json({
      ok: true,
      message: "Không có thay đổi nào trong 5.openapi/ để deploy.",
    });
  }

  // 3. Tạo blob cho từng file added/modified
  const blobShaByPath = new Map<string, string>();
  try {
    await Promise.all(
      changes
        .filter(
          (c): c is Extract<FileChange, { status: "added" | "modified" }> =>
            c.status !== "deleted",
        )
        .map(async (change) => {
          const content = await readFile(change.absPath);
          const blobRes = await fetch(`${apiBase}/git/blobs`, {
            method: "POST",
            headers,
            body: JSON.stringify({
              content: content.toString("base64"),
              encoding: "base64",
            }),
          });
          if (!blobRes.ok) {
            throw new Error(
              `Tạo blob lỗi cho ${change.repoPath}: ${await blobRes.text()}`,
            );
          }
          const blobData = await blobRes.json();
          blobShaByPath.set(change.repoPath, blobData.sha);
        }),
    );
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }

  // 4. Tạo tree mới
  const treeEntries = changes.map((change) =>
    change.status === "deleted"
      ? { path: change.repoPath, mode: "100644", type: "blob", sha: null }
      : {
          path: change.repoPath,
          mode: "100644",
          type: "blob",
          sha: blobShaByPath.get(change.repoPath),
        },
  );

  const newTreeRes = await fetch(`${apiBase}/git/trees`, {
    method: "POST",
    headers,
    body: JSON.stringify({ base_tree: baseTreeSha, tree: treeEntries }),
  });
  if (!newTreeRes.ok) {
    return NextResponse.json(
      {
        error: `Tạo tree lỗi (${newTreeRes.status}): ${await newTreeRes.text()}`,
      },
      { status: 500 },
    );
  }
  const newTreeData = await newTreeRes.json();

  // 5. Tạo commit mới
  const newCommitRes = await fetch(`${apiBase}/git/commits`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message: "docs(openapi): cập nhật từ giao diện kiểm tra tài liệu",
      tree: newTreeData.sha,
      parents: [baseSha],
    }),
  });
  if (!newCommitRes.ok) {
    return NextResponse.json(
      {
        error: `Tạo commit lỗi (${newCommitRes.status}): ${await newCommitRes.text()}`,
      },
      { status: 500 },
    );
  }
  const newCommitData = await newCommitRes.json();

  // 6. Tạo branch mới trỏ tới commit vừa tạo
  const branchName = `auto/update-openapi-${Date.now()}`;
  const newRefRes = await fetch(`${apiBase}/git/refs`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      ref: `refs/heads/${branchName}`,
      sha: newCommitData.sha,
    }),
  });
  if (!newRefRes.ok) {
    return NextResponse.json(
      {
        error: `Tạo branch lỗi (${newRefRes.status}): ${await newRefRes.text()}`,
      },
      { status: 500 },
    );
  }

  // 7. Kích hoạt workflow: bundle lại + mở PR từ branch vừa tạo + auto-merge
  const dispatchUrl = `${apiBase}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
  const dispatchRes = await fetch(dispatchUrl, {
    method: "POST",
    headers,
    body: JSON.stringify({
      ref: baseBranch,
      inputs: { base_branch: baseBranch, branch_name: branchName },
    }),
  });

  if (dispatchRes.status === 204) {
    return NextResponse.json({
      ok: true,
      message: `Đã tạo "${branchName}" và kích hoạt PR tự động. Sẽ tự merge nếu validate pass.`,
      branch: branchName,
    });
  }

  const errorText = await dispatchRes.text();
  return NextResponse.json(
    { error: `GitHub API lỗi (${dispatchRes.status}): ${errorText}` },
    { status: 502 },
  );
}
