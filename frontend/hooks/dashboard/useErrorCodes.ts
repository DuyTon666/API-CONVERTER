import { useState } from "react";
import { toast } from "sonner";
import { ErrorReviewEntry } from "@/types/dashboard";
import { formatFetchError } from "@/lib/api/client";
import {
  fetchErrorEntries,
  resolveErrorEntry,
  applyErrorEntries,
} from "@/lib/api/dashboard/errorCodes";

export function useErrorCodes(backend: string, modules: string[]) {
  const [entriesByModule, setEntriesByModule] = useState<
    Record<string, ErrorReviewEntry[]>
  >({});
  const [loading, setLoading] = useState(false);
  const [resolving, setResolving] = useState<string | null>(null);
  const [applying, setApplying] = useState<string | null>(null);

  // Quét toàn bộ module xem module nào có report đang chờ duyệt. Module chưa
  // từng chạy errors:parse sẽ trả 404 — đó không phải lỗi thật, chỉ là "chưa
  // có gì để review", nên bỏ qua thay vì hiện ErrorAlert.
  const fetchAllErrorEntries = async () => {
    setLoading(true);
    const next: Record<string, ErrorReviewEntry[]> = {};
    await Promise.all(
      modules.map(async (m) => {
        try {
          const report = await fetchErrorEntries(backend, m);
          next[m] = report.entries;
        } catch {
          // không có report cho module này — bỏ qua
        }
      }),
    );
    setEntriesByModule(next);
    setLoading(false);
  };

  const handleResolve = async (
    module: string,
    code: string,
    decision: string,
    approvedBy: string,
    newCode?: string,
    sourceFile?: string,
  ) => {
    setResolving(`${module}:${code}`);
    try {
      const report = await resolveErrorEntry(
        backend,
        module,
        code,
        decision,
        approvedBy,
        newCode,
        sourceFile,
      );
      setEntriesByModule((prev) => ({ ...prev, [module]: report.entries }));
    } catch (e) {
      toast.error(formatFetchError(e));
    } finally {
      setResolving(null);
    }
  };

  const handleApply = async (module: string) => {
    setApplying(module);
    try {
      const result = await applyErrorEntries(backend, module);
      toast.success(
        `Đã áp dụng: ${result.applied} applied · ${result.skipped} skipped · ${result.rejected} rejected`,
      );
      const report = await fetchErrorEntries(backend, module);
      const stillNeedsAction = report.entries.some(
        (e) => !e.resolution && e.status !== "duplicate_ok",
      );
      // report không có cờ "đã apply" để dựa vào — tự suy ra: apply vừa chạy
      // xong mà không còn entry nào cần duyệt nữa thì coi module này đã xong
      // việc, bỏ khỏi danh sách hiển thị (không còn gì để làm với nó nữa,
      // kể cả duplicate_ok cũng chẳng cần xem lại). Còn nếu vẫn còn entry cần
      // duyệt (report vừa được người khác chạy errors:parse lại có mã mới)
      // thì vẫn giữ nguyên để người dùng tiếp tục xử lý.
      setEntriesByModule((prev) => {
        if (stillNeedsAction) return { ...prev, [module]: report.entries };
        const next = { ...prev };
        delete next[module];
        return next;
      });
    } catch (e) {
      toast.error(formatFetchError(e));
    } finally {
      setApplying(null);
    }
  };

  return {
    entriesByModule,
    loading,
    resolving,
    applying,
    fetchAllErrorEntries,
    handleResolve,
    handleApply,
  };
}
