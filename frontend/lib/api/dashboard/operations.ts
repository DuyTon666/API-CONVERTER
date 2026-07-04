import { apiFetch, readErrorDetail } from "@/lib/api/client";
import {
  Operation,
  OperationAiSuggestPayload,
  OperationAiSuggestResult,
  OperationUpdatePayload,
} from "@/types/dashboard";

export async function fetchOperations(backend: string): Promise<Operation[]> {
  return apiFetch<Operation[]>(`${backend}/docs/operations`);
}

export async function aiSuggestOperation(
  backend: string,
  payload: OperationAiSuggestPayload,
): Promise<OperationAiSuggestResult> {
  const res = await fetch(`${backend}/docs/operations/ai-suggest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return res.json();
}

export async function updateOperations(
  backend: string,
  payload: OperationUpdatePayload[],
): Promise<{ updated: number }> {
  const res = await fetch(`${backend}/docs/operations`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return res.json();
}
