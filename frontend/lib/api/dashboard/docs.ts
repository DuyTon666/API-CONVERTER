import { apiFetch, readErrorDetail } from "@/lib/api/client";
import {
  AiFixResult,
  DocsBuildResult,
  DocsStatus,
  RedoclyIssue,
  SpectralIssue,
} from "@/types/dashboard";

export async function fetchDocsStatus(backend: string): Promise<DocsStatus> {
  return apiFetch<DocsStatus>(`${backend}/docs/status`);
}

export async function buildDocs(backend: string): Promise<DocsBuildResult> {
  return apiFetch<DocsBuildResult>(`${backend}/docs/build`, { method: "POST" });
}

export async function relintDocs(backend: string): Promise<DocsBuildResult> {
  return apiFetch<DocsBuildResult>(`${backend}/docs/relint`, { method: "POST" });
}

export function docsDownloadHtmlUrl(backend: string): string {
  return `${backend}/docs/download-html`;
}

// Ném riêng error này để caller phân biệt "chưa build bundle" (404, cần build
// trước) với lỗi kết nối/server thật sự — xem openBundleEditor trong useDocsBuilder.
export class BundleNotFoundError extends Error {}

export async function fetchBundleContent(backend: string): Promise<string> {
  const res = await fetch(`${backend}/docs/bundle-content`, { cache: "no-store" });
  if (res.status === 404) throw new BundleNotFoundError();
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return res.text();
}

export async function saveBundleContent(backend: string, content: string): Promise<void> {
  const res = await fetch(`${backend}/docs/bundle-content`, {
    method: "PUT",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
    body: content,
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
}

export async function aiFixBundle(
  backend: string,
  content: string,
  spectral: SpectralIssue[],
  redocly: RedoclyIssue[],
): Promise<AiFixResult> {
  const res = await fetch(`${backend}/docs/bundle/ai-fix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, spectral, redocly }),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return res.json();
}
