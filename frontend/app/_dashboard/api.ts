import { resolveErrorMessage } from "./errorMessages";

function parseErrorDetail(data: unknown, fallback: string): { code?: string; message: string } {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail) && "message" in detail) {
    const d = detail as { code?: string; message: string };
    return { code: d.code, message: d.message };
  }
  if (typeof detail === "string") return { message: detail };
  return { message: fallback }; // bao gồm trường hợp 422 validation (detail là list)
}

export async function readErrorDetail(res: Response): Promise<string> {
  const data = await res.json().catch(() => null);
  const { code, message } = parseErrorDetail(data, res.statusText);
  return resolveErrorMessage(code, message);
}

export async function apiFetch<T = unknown>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return res.json();
}

export function formatFetchError(
  e: unknown,
  fallback = "Lỗi kết nối backend",
): string {
  if (e instanceof TypeError) {
    return "Không thể kết nối tới backend, kiểm tra server có đang chạy không";
  }
  return e instanceof Error ? e.message : fallback;
}
