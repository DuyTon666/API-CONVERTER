import { DocsBuildResult } from "./types";

export const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"];

export function isSupportedFile(name: string): boolean {
  const lower = name.toLowerCase();
  return SUPPORTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function countLintIssues(result: DocsBuildResult): { error: number; warn: number } {
  const error =
    result.spectral.filter((i) => i.severity === 0).length +
    result.redocly.filter((i) => i.severity === "error").length;
  const warn =
    result.spectral.filter((i) => i.severity === 1).length +
    result.redocly.filter((i) => i.severity !== "error").length;
  return { error, warn };
}

export const approvalIcon: Record<string, string> = {
  approved: "✓",
  rejected: "✗",
  pending: "?",
};

export const approvalColor: Record<string, string> = {
  approved: "text-green-600",
  rejected: "text-red-500",
  pending: "text-gray-400",
};

export const statusIcon: Record<string, string> = {
  active: "●",
  draft: "○",
  deprecated: "✕",
};

export const statusColor: Record<string, string> = {
  active: "text-green-600",
  draft: "text-gray-400",
  deprecated: "text-red-500",
};

export function formatExtensions(byExt: Record<string, number>): string {
  return Object.entries(byExt)
    .map(([ext, count]) => `${ext}: ${count}`)
    .join(", ");
}

export function formatDate(value: string | null): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("vi-VN");
  } catch {
    return value;
  }
}
