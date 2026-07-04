import { apiFetch } from "@/lib/api/client";
import { ManualEditConflict, ModuleListResult, ScanResult } from "@/types/dashboard";

export async function scanModules(backend: string): Promise<ScanResult> {
  return apiFetch<ScanResult>(`${backend}/modules/scan`);
}

export async function fetchModules(backend: string): Promise<ModuleListResult> {
  return apiFetch<ModuleListResult>(`${backend}/modules`);
}

export async function activateModule(backend: string, name: string): Promise<ModuleListResult> {
  return apiFetch<ModuleListResult>(
    `${backend}/modules/${encodeURIComponent(name)}/activate`,
    { method: "POST" },
  );
}

export async function deactivateModule(backend: string, name: string): Promise<ModuleListResult> {
  return apiFetch<ModuleListResult>(
    `${backend}/modules/${encodeURIComponent(name)}/deactivate`,
    { method: "POST" },
  );
}

export async function startImport(
  backend: string,
  moduleName: string | null,
): Promise<{ job_id: string }> {
  const url = moduleName
    ? `${backend}/modules/import?module=${encodeURIComponent(moduleName)}`
    : `${backend}/modules/import`;
  return apiFetch<{ job_id: string }>(url, { method: "POST" });
}

export function importStreamUrl(backend: string, jobId: string): string {
  return `${backend}/modules/import/${jobId}/stream`;
}

export async function fetchManualEditConflicts(backend: string): Promise<ManualEditConflict[]> {
  return apiFetch<ManualEditConflict[]>(`${backend}/modules/manual-edit-conflicts`);
}

export async function resolveManualEditConflict(
  backend: string,
  operationId: string,
  field: string,
  choice: "keep_old" | "accept_new",
): Promise<void> {
  await apiFetch(`${backend}/modules/manual-edit-conflicts/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operationId, field, choice }),
  });
}
