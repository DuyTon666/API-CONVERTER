import { DocsBuildResult } from "@/types/dashboard";

export const SUPPORTED_EXTENSIONS = [".pdf", ".docx"];

export function isSupportedFile(name: string): boolean {
  const lower = name.toLowerCase();
  return SUPPORTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

// Tách file hợp lệ/không hợp lệ khi chọn/kéo-thả upload — dùng chung bởi useUpload.ts.
export function partitionFiles<T extends { name: string }>(
  files: T[],
): { supported: T[]; rejected: T[]; rejectedMessage: string | null } {
  const supported = files.filter((f) => isSupportedFile(f.name));
  const rejected = files.filter((f) => !isSupportedFile(f.name));
  const rejectedMessage =
    rejected.length > 0
      ? `Bỏ qua ${rejected.length} file sai định dạng (chỉ nhân ${SUPPORTED_EXTENSIONS.join("/")}):
      ${rejected.map((f) => f.name).join(", ")}`
      : null;
  return { supported, rejected, rejectedMessage };
}

export function countLintIssues(result: DocsBuildResult): {
  error: number;
  warn: number;
} {
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

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(value: string | null): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("vi-VN");
  } catch {
    return value;
  }
}

export function formatRelativeTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (isNaN(date.getTime())) return value;
  const minutes = Math.floor((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "vừa xong";
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} ngày trước`;
  return date.toLocaleDateString("vi-VN");
}

// Business rule: khi nào cho bấm "Deploy tài liệu" — xem SwaggerDocsCard.
export function getDeployBlockedReason(params: {
  bundleReady: boolean;
  docsResult: DocsBuildResult | null;
  busy: boolean;
}): string | null {
  const { bundleReady, docsResult, busy } = params;
  if (!bundleReady) return "Chưa có bundle — hãy build tài liệu trước";
  if (!docsResult) return 'Hãy "Kiểm tra lỗi" ít nhất 1 lần trước khi deploy';
  const { error } = countLintIssues(docsResult);
  if (error > 0)
    return `Bundle đang có ${error} lỗi lint — sửa hết lỗi trước khi deploy`;
  if (busy) return "Đang có thao tác khác chạy, đợi xong đã";
  return null;
}
