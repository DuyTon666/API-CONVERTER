import { apiFetch } from "@/lib/api/client";
import { ErrorReviewReport, ErrorApplyResult } from "@/types/dashboard";

export async function fetchErrorEntries(
  backend: string,
  module: string,
): Promise<ErrorReviewReport> {
  return apiFetch<ErrorReviewReport>(`${backend}/errors/${module}`);
}

export async function resolveErrorEntry(
  backend: string,
  module: string,
  code: string,
  decision: string,
  approvedBy: string,
  newCode?: string,
  sourceFile?: string,
): Promise<ErrorReviewReport> {
  return apiFetch<ErrorReviewReport>(`${backend}/errors/${module}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      decision,
      approved_by: approvedBy,
      new_code: newCode,
      source_file: sourceFile,
    }),
  });
}

export async function applyErrorEntries(
  backend: string,
  module: string,
): Promise<ErrorApplyResult> {
  return apiFetch<ErrorApplyResult>(`${backend}/errors/${module}/apply`, {
    method: "POST",
  });
}
