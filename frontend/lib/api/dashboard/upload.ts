import { apiFetch } from "@/lib/api/client";

export async function uploadSourceFiles(
  backend: string,
  files: File[],
): Promise<{ total: number }> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return apiFetch<{ total: number }>(`${backend}/source/upload`, {
    method: "POST",
    body: form,
  });
}
