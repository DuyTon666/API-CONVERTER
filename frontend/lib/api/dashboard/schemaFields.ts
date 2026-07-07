import { apiFetch, readErrorDetail } from "@/lib/api/client";
import { OperationDataSchemas, SchemaFieldUpdate } from "@/types/dashboard";

export async function fetchSchemaFields(
  backend: string,
): Promise<OperationDataSchemas[]> {
  return apiFetch<OperationDataSchemas[]>(`${backend}/docs/schema-fields`);
}

export async function updateSchemaFields(
  backend: string,
  payload: SchemaFieldUpdate[],
): Promise<{ updated: number }> {
  const res = await fetch(`${backend}/docs/schema-fields`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return res.json();
}
