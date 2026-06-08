"use client";

import { ApplyResult, SuggestionsResult } from "./types";
import { approvalColor, approvalIcon } from "./format";

type ApproveBody = { mode: string; module?: string; file?: string; override_module?: string };

type Props = {
  suggestions: SuggestionsResult | null;
  loading: boolean;
  error: string;
  actionError: string;
  suggestRunning: boolean;
  approving: string | null;
  applying: boolean;
  applyResult: ApplyResult | null;
  overrideInputs: Record<string, string>;
  onOverrideChange: (file: string, value: string) => void;
  onRunSuggest: () => void;
  onApprove: (body: ApproveBody, key: string) => void;
  onApply: () => void;
};

export default function SuggestCard({
  suggestions,
  loading,
  error,
  actionError,
  suggestRunning,
  approving,
  applying,
  applyResult,
  overrideInputs,
  onOverrideChange,
  onRunSuggest,
  onApprove,
  onApply,
}: Props) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-700 mb-3">Gợi ý &amp; duyệt module</h2>

      <div className="flex flex-wrap gap-3 mb-4">
        <button
          onClick={onRunSuggest}
          disabled={suggestRunning}
          className="px-4 py-2 bg-indigo-100 text-indigo-700 text-sm font-semibold rounded-lg hover:bg-indigo-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {suggestRunning ? "Đang chạy suggest-root..." : "Chạy suggest-root"}
        </button>
        <button
          onClick={() => onApprove({ mode: "all" }, "all")}
          disabled={!suggestions?.exists || suggestions.items.length === 0 || approving !== null}
          className="px-4 py-2 bg-slate-100 text-slate-600 text-sm font-semibold rounded-lg hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {approving === "all" ? "Đang duyệt..." : "Approve tất cả"}
        </button>
        <button
          onClick={onApply}
          disabled={!suggestions?.exists || suggestions.items.length === 0 || applying}
          className="px-4 py-2 bg-emerald-100 text-emerald-700 text-sm font-semibold rounded-lg hover:bg-emerald-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {applying ? "Đang apply..." : "Apply suggestions"}
        </button>
      </div>

      {actionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{actionError}</div>
      )}

      {loading && <p className="text-sm text-gray-400">Đang tải suggestions...</p>}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{error}</div>
      )}

      {suggestions && !suggestions.exists && (
        <p className="text-sm text-gray-400">Chưa có suggestions — hãy chạy &quot;Chạy suggest-root&quot;.</p>
      )}

      {suggestions && suggestions.exists && (
        suggestions.items.length === 0 ? (
          <p className="text-sm text-gray-400">Không có suggestion nào.</p>
        ) : (
          <div className="space-y-3">
            <div className="overflow-x-auto bg-white border border-gray-200 rounded-lg">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-200">
                    <th className="px-4 py-2 font-medium">File</th>
                    <th className="px-4 py-2 font-medium">Endpoint</th>
                    <th className="px-4 py-2 font-medium">Module gợi ý</th>
                    <th className="px-4 py-2 font-medium">Độ tin cậy</th>
                    <th className="px-4 py-2 font-medium">Trạng thái</th>
                    <th className="px-4 py-2 font-medium">Override &amp; duyệt</th>
                  </tr>
                </thead>
                <tbody>
                  {suggestions.items.map((item) => (
                    <tr key={item.file} className="border-b border-gray-100 last:border-0 align-top">
                      <td className="px-4 py-2 text-gray-700 font-medium max-w-[180px] truncate">{item.file}</td>
                      <td className="px-4 py-2 text-gray-500 font-mono text-xs">
                        {item.method ? `${item.method} ` : ""}
                        {item.endpoint ?? "-"}
                      </td>
                      <td className="px-4 py-2 text-gray-600">
                        {item.final_module ?? item.suggested_module ?? "-"}
                        {item.approved_module && item.approved_module !== item.suggested_module && (
                          <span className="text-gray-400"> (duyệt: {item.approved_module})</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-gray-500">
                        {item.confidence_label ?? "-"}
                        {typeof item.confidence_score === "number" ? ` (${item.confidence_score.toFixed(2)})` : ""}
                      </td>
                      <td className={`px-4 py-2 font-medium ${approvalColor[item.approval_status] ?? "text-gray-400"}`}>
                        {approvalIcon[item.approval_status] ?? "?"} {item.approval_status}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex gap-2 items-center">
                          <input
                            type="text"
                            placeholder={item.suggested_module ?? "module"}
                            value={overrideInputs[item.file] ?? ""}
                            onChange={(e) => onOverrideChange(item.file, e.target.value)}
                            className="w-28 px-2 py-1 border border-gray-200 rounded text-xs text-gray-700"
                          />
                          <button
                            onClick={() =>
                              onApprove(
                                {
                                  mode: "file",
                                  file: item.file,
                                  override_module: overrideInputs[item.file]?.trim() || undefined,
                                },
                                item.file
                              )
                            }
                            disabled={approving !== null}
                            className="px-3 py-1 bg-indigo-50 text-indigo-600 text-xs font-medium rounded hover:bg-indigo-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
                          >
                            {approving === item.file ? "..." : "Duyệt"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-sm text-gray-400">
              Tổng: {suggestions.total ?? suggestions.items.length} (
              {Object.entries(suggestions.summary)
                .map(([s, c]) => `${s}=${c}`)
                .join(", ")}
              )
            </p>
          </div>
        )
      )}

      {applyResult && (
        <div className="mt-4 space-y-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-600 mb-2">
              Đã apply ({applyResult.applied.length})
            </h3>
            {applyResult.applied.length === 0 ? (
              <p className="text-sm text-gray-400">Không có file nào được apply.</p>
            ) : (
              <ul className="space-y-1 max-h-48 overflow-auto">
                {applyResult.applied.map((a, i) => (
                  <li key={i} className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-700 flex justify-between">
                    <span className="truncate mr-4">{a.file}</span>
                    <span className="text-gray-400 shrink-0">{a.module} · {a.action}</span>
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
                  <li key={i} className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-700 flex justify-between">
                    <span className="truncate mr-4">{s.file}</span>
                    <span className="text-gray-400 shrink-0">{s.skip_reason}</span>
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
