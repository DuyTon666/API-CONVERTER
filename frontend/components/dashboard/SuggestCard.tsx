"use client";

import {
  ApplyResult,
  SkippedApproval,
  SuggestionsResult,
} from "@/types/dashboard";
import { useEffect, useState } from "react";
import { useMounted } from "@/hooks/dashboard/useMounted";
import { ErrorAlert } from "./ErrorAlert";

type ApproveBody = {
  mode: string;
  module?: string;
  file?: string;
  override_module?: string;
};

type ApproveItem = {
  file: string;
  override_module?: string;
};

type Props = {
  suggestions: SuggestionsResult | null;
  loading: boolean;
  error: string;
  suggestRunning: boolean;
  approving: string | null;
  approvingMulti: boolean;
  applying: boolean;
  applyResult: ApplyResult | null;
  approveSkipped: SkippedApproval[];
  overrideInputs: Record<string, string>;
  onApproveSelected: (items: ApproveItem[]) => void;
  onOverrideChange: (file: string, value: string) => void;
  onRunSuggest: () => void;
  onApprove: (body: ApproveBody, key: string) => void;
  onApply: () => void;
};

// Rút gọn cột "Lý do gợi ý" thành 1 dòng (method + endpoint + trạng thái khớp
// service) — chi tiết đầy đủ xem qua title/hover.
function reasonDetail(item: SuggestionsResult["items"][number]): string {
  const lines = [`${item.method ?? ""} ${item.endpoint ?? "-"}`.trim()];
  if (item.service_in_doc) {
    lines.push(
      item.conflict
        ? `service: ${item.service_in_doc} ≠ ${item.final_module ?? item.suggested_module}`
        : `service: ${item.service_in_doc} ✓`,
    );
  } else {
    lines.push("service không xác định");
  }
  return lines.join("\n");
}

function ElapsedTimer() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  return <>({elapsed}s)</>;
}

export default function SuggestCard({
  suggestions,
  loading,
  error,
  suggestRunning,
  approving,
  approvingMulti,
  applying,
  applyResult,
  approveSkipped,
  overrideInputs,
  onOverrideChange,
  onRunSuggest,
  onApproveSelected,
  onApply,
}: Props) {
  const mounted = useMounted();
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState<
    "pending" | "approved" | "all"
  >("pending");

  const visibleItems = (suggestions?.items ?? []).filter(
    (i) => statusFilter === "all" || i.approval_status === statusFilter,
  );

  // Chỉ hàng pending mới chọn được — duyệt lại item đã duyệt là no-op phía backend
  const selectableFiles = visibleItems
    .filter((i) => i.approval_status === "pending")
    .map((i) => i.file);
  const allSelected =
    selectableFiles.length > 0 &&
    selectableFiles.every((f) => selectedFiles.has(f));

  const toggleAll = () =>
    setSelectedFiles(allSelected ? new Set() : new Set(selectableFiles));

  const changeFilter = (f: "pending" | "approved" | "all") => {
    setStatusFilter(f);
    setSelectedFiles(new Set());
  };

  const toggleFile = (file: string) =>
    setSelectedFiles((prev) => {
      const next = new Set(prev);
      next.has(file) ? next.delete(file) : next.add(file);
      return next;
    });

  const busy = approving !== null || approvingMulti;

  const handleApproveSelected = () => {
    const items = Array.from(selectedFiles).map((file) => ({
      file,
      override_module: overrideInputs[file]?.trim() || undefined,
    }));
    onApproveSelected(items);
    setSelectedFiles(new Set());
  };

  return (
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
      <h2 className="font-semibold text-gray-900 mb-4">
        Gợi ý &amp; duyệt module
      </h2>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button
          onClick={onRunSuggest}
          disabled={suggestRunning}
          className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-semibold rounded-lg hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-2"
        >
          {suggestRunning ? (
            <>
              <svg
                className="animate-spin h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v8H4z"
                />
              </svg>
              Đang phân tích...
              <ElapsedTimer />
            </>
          ) : (
            "Gợi ý module"
          )}
        </button>

        <button
          onClick={handleApproveSelected}
          disabled={
            !mounted ||
            busy ||
            loading ||
            !selectedFiles ||
            selectedFiles.size === 0
          }
          suppressHydrationWarning
          className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-semibold rounded-lg hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {approvingMulti
            ? "Đang duyệt..."
            : `Duyệt (${selectedFiles ? selectedFiles.size : 0}) file`}
        </button>

        <button
          onClick={onApply}
          disabled={
            !mounted ||
            applying ||
            loading ||
            (suggestions?.summary?.approved ?? 0) === 0
          }
          suppressHydrationWarning
          className="px-4 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {applying ? "Đang apply..." : "Apply suggestions"}
        </button>
      </div>

      {suggestRunning && (
        <p className="text-xs text-gray-400 mb-3">
          Quá trình phân tích tài liệu thường mất 30–90 giây, vui lòng chờ...
        </p>
      )}

      {approveSkipped.length > 0 && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-sm space-y-1">
          <p className="font-medium">
            {approveSkipped.length} file bị bỏ qua khi duyệt:
          </p>
          <ul className="space-y-0.5">
            {approveSkipped.map((s, i) => (
              <li key={i}>
                <span className="font-medium">{s.file}</span> — {s.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      {loading && (
        <p className="text-sm text-gray-400">Đang tải suggestions...</p>
      )}
      {error && <ErrorAlert message={error} className="mb-4" />}

      {suggestions && !suggestions.exists && (
        <p className="text-sm text-gray-400">
          Chưa có suggestions — hãy chạy &quot;Gợi ý module&quot;.
        </p>
      )}

      {suggestions &&
        suggestions.exists &&
        (suggestions.items.length === 0 ? (
          <p className="text-sm text-gray-400">Không có suggestion nào.</p>
        ) : (
          <div className="space-y-3">
            <div className="flex gap-1 border-b border-gray-200">
              {(
                [
                  [
                    "pending",
                    `Chờ duyệt (${suggestions.summary.pending ?? 0})`,
                  ],
                  [
                    "approved",
                    `Đã duyệt (${suggestions.summary.approved ?? 0})`,
                  ],
                  ["all", "Tất cả"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => changeFilter(key)}
                  className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition ${
                    statusFilter === key
                      ? "border-indigo-600 text-indigo-600"
                      : "border-transparent text-gray-400 hover:text-gray-600"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="overflow-auto max-h-100 border border-gray-100 rounded-lg">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-gray-400">
                    <th className="sticky top-0 z-10 bg-gray-50 px-3 py-1.5 border-b border-gray-200">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={toggleAll}
                        disabled={selectableFiles.length === 0}
                        className="accent-indigo-600 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Chọn tất cả file chờ duyệt"
                      />
                    </th>
                    <th className="sticky top-0 z-10 bg-gray-50 px-3 py-1.5 font-medium border-b border-gray-200">
                      File
                    </th>
                    <th className="sticky top-0 z-10 bg-gray-50 px-3 py-1.5 font-medium border-b border-gray-200">
                      Module gợi ý
                    </th>
                    <th className="sticky top-0 z-10 bg-gray-50 px-3 py-1.5 font-medium border-b border-gray-200">
                      Lý do gợi ý
                    </th>
                    <th className="sticky top-0 z-10 bg-gray-50 px-3 py-1.5 font-medium border-b border-gray-200">
                      Trạng thái
                    </th>
                    <th className="sticky top-0 z-10 bg-gray-50 px-3 py-1.5 font-medium border-b border-gray-200">
                      Override
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {visibleItems.length === 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-4 py-6 text-center text-sm text-gray-400"
                      >
                        {statusFilter === "pending"
                          ? "Không còn item chờ duyệt 🎉"
                          : "Không có item nào."}
                      </td>
                    </tr>
                  )}
                  {visibleItems.map((item) => (
                    <tr
                      key={item.file}
                      className="border-b border-gray-100 last:border-0 align-top transition hover:bg-gray-50"
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={selectedFiles.has(item.file)}
                          onChange={() => toggleFile(item.file)}
                          disabled={item.approval_status !== "pending"}
                          className="accent-indigo-600 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                          title={
                            item.approval_status !== "pending"
                              ? "Đã duyệt — không cần duyệt lại"
                              : undefined
                          }
                        />
                      </td>
                      <td className="px-4 py-2 text-gray-700 font-medium max-w-45 truncate">
                        {item.file}
                      </td>
                      <td className="px-4 py-2">
                        <span className="font-medium text-gray-700">
                          {item.final_module ?? item.suggested_module ?? "-"}
                        </span>
                        {item.approved_module &&
                          item.approved_module !== item.suggested_module && (
                            <span className="text-gray-400 text-xs ml-1">
                              (duyệt: {item.approved_module})
                            </span>
                          )}
                      </td>
                      <td className="px-3 py-1.5 max-w-50">
                        <div
                          className="truncate text-xs text-gray-500 flex items-center gap-1"
                          title={reasonDetail(item)}
                        >
                          {item.method && (
                            <span className="text-indigo-500 font-medium">
                              {item.method}
                            </span>
                          )}
                          <code className="text-gray-600">
                            {item.endpoint ?? "-"}
                          </code>
                          {item.service_in_doc ? (
                            item.conflict ? (
                              <span className="text-amber-500">⚠</span>
                            ) : (
                              <span className="text-emerald-500">✓</span>
                            )
                          ) : (
                            <span className="text-gray-400">?</span>
                          )}
                        </div>
                      </td>

                      <td className="px-4 py-2">
                        <span
                          className={`inline-flex whitespace-nowrap px-2 py-0.5 rounded-full text-xs font-medium ${
                            item.approval_status === "approved"
                              ? "bg-emerald-100 text-emerald-700"
                              : item.approval_status === "pending"
                                ? "bg-amber-100 text-amber-600"
                                : "bg-gray-100 text-gray-500"
                          }`}
                        >
                          {item.approval_status === "approved"
                            ? "Đã duyệt"
                            : item.approval_status === "pending"
                              ? "Chờ duyệt"
                              : item.approval_status}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          placeholder={item.suggested_module ?? "module"}
                          value={overrideInputs[item.file] ?? ""}
                          onChange={(e) =>
                            onOverrideChange(item.file, e.target.value)
                          }
                          disabled={item.approval_status !== "pending"}
                          title={
                            item.approval_status !== "pending"
                              ? "Đã duyệt — override không còn tác dụng"
                              : undefined
                          }
                          className="w-28 px-2 py-1 border border-gray-200 rounded text-xs text-gray-700 disabled:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}

      {applyResult && (
        <div className="mt-4 space-y-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-600 mb-2">
              Đã apply ({applyResult.applied.length})
            </h3>
            {applyResult.applied.length === 0 ? (
              <p className="text-sm text-gray-400">
                Không có file nào được apply.
              </p>
            ) : (
              <ul className="space-y-1 max-h-48 overflow-auto">
                {applyResult.applied.map((a, i) => (
                  <li
                    key={i}
                    className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-700 flex justify-between"
                  >
                    <span className="truncate mr-4">{a.file}</span>
                    <span className="text-gray-400 shrink-0">
                      {a.module} · {a.action}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {applyResult.skipped.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-600 mb-2">
                Bỏ qua ({applyResult.skipped.length})
              </h3>
              <ul className="space-y-1 max-h-48 overflow-auto">
                {applyResult.skipped.map((s, i) => (
                  <li
                    key={i}
                    className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-700 flex justify-between"
                  >
                    <span className="truncate mr-4">{s.file}</span>
                    <span className="text-gray-400 shrink-0">
                      {s.skip_reason}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
