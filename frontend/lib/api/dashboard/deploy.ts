export type DeploydocsResult = {
  ok: boolean;
  message?: string;
  branch?: string;
};

export async function deployDocs(
  baseBranch: "main" | "develop" = "develop",
): Promise<DeploydocsResult> {
  const res = await fetch("/api/deploy-docs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ baseBranch }),
  });

  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error ?? "Lỗi deploy tài liệu");
  }
  return data;
}
