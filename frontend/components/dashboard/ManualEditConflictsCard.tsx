"use client";

import { ManualEditConflict } from "@/types/dashboard";
import { ErrorAlert } from "./ErrorAlert";

type Props = {
  conflicts: ManualEditConflict[];
  loading: boolean;
  error: string;
  resolving: string | null;
  resolveError: string;
  conflictKey: (c: ManualEditConflict) => string;
  onResolve: (
    conflict: ManualEditConflict,
    choice: "keep_old" | "accept_new",
  ) => void;
};

export default function ManualEditConflictsCard({
  conflicts,
  loading,
  error,
  resolving,
  resolveError,
  conflictKey,
  onResolve,
}: Props) {
  // Ẩn card khi không có gì cần duyệt — không làm rối UI lúc bình thường.
  if (!loading && conflicts.length === 0 && !error) return null;

  return (
    <section className="bg-white border border-amber-200 rounded-2xl shadow-sm p-6">
      <h2 className="font-semibold text-gray-900 mb-1">
        Xung đột sửa tay khi import lại
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        Các field này đã từng được sửa tay trong Form Editor, nhưng tài liệu
        nguồn vừa được cập nhật và pipeline sinh ra giá trị khác. Chọn giữ bản
        sửa tay hoặc lấy bản pipeline mới sinh.
      </p>

      {error && <ErrorAlert message={error} className="mb-4" />}
      {resolveError && <ErrorAlert message={resolveError} className="mb-4" />}

      {loading && conflicts.length === 0 && (
        <p className="text-sm text-gray-400">Đang tải...</p>
      )}

      <div className="space-y-3">
        {conflicts.map((c) => {
          const key = conflictKey(c);
          const busy = resolving === key;
          return (
            <div
              key={key}
              className="border border-gray-200 rounded-xl p-4 bg-amber-50/40"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-sm font-semibold text-gray-900">
                  {c.entityId}
                </span>
                <span className="text-xs text-gray-500">
                  {c.module} · {c.kind === "schema" ? "schema" : "operation"} ·{" "}
                  {c.field}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3 text-sm">
                <div>
                  <div className="text-xs text-gray-500 mb-1">
                    Bản sửa tay (cũ)
                  </div>
                  <div className="p-2 bg-white border border-gray-200 rounded-lg text-gray-800 whitespace-pre-wrap">
                    {c.old_value || <em className="text-gray-400">(rỗng)</em>}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">
                    Bản pipeline vừa sinh (mới)
                  </div>
                  <div className="p-2 bg-white border border-gray-200 rounded-lg text-gray-800 whitespace-pre-wrap">
                    {c.new_value || <em className="text-gray-400">(rỗng)</em>}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => onResolve(c, "keep_old")}
                  disabled={busy}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 text-sm font-semibold rounded-lg hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  {busy ? "Đang lưu..." : "Giữ bản cũ"}
                </button>
                <button
                  onClick={() => onResolve(c, "accept_new")}
                  disabled={busy}
                  className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  {busy ? "Đang lưu..." : "Lấy bản mới"}
                </button>
                <span className="text-xs text-gray-400 ml-auto">
                  Phát hiện lúc {c.detected_at}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
