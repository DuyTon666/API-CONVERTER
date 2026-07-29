import { ImportModuleProgress } from "@/types/dashboard";

// Gộp 1 sự kiện tiến trình import (SSE) vào danh sách hiện có theo tên module —
// dùng trong setState updater của useModuleRegistry.ts nên không được mutate "prev".
export function mergeImportProgress(
  prev: ImportModuleProgress[],
  incoming: ImportModuleProgress,
): ImportModuleProgress[] {
  const exists = prev.find((m) => m.name === incoming.name);
  if (exists)
    return prev.map((m) => (m.name === incoming.name ? incoming : m));
  return [...prev, incoming];
}
