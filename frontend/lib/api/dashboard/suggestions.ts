import { apiFetch } from "@/lib/api/client";
import { ApplyResult, SuggestionsResult } from "@/types/dashboard";

export async function fetchSuggestions(backend: string): Promise<SuggestionsResult> {
  return apiFetch<SuggestionsResult>(`${backend}/modules/suggestions`);
}

export async function runSuggest(backend: string): Promise<SuggestionsResult> {
  return apiFetch<SuggestionsResult>(`${backend}/modules/suggest`, { method: "POST" });
}

export async function approveSuggestion(
  backend: string,
  body: { mode: string; module?: string; file?: string; override_module?: string },
): Promise<SuggestionsResult> {
  return apiFetch<SuggestionsResult>(`${backend}/modules/suggestions/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function applySuggestions(backend: string): Promise<ApplyResult> {
  return apiFetch<ApplyResult>(`${backend}/modules/apply`, { method: "POST" });
}
