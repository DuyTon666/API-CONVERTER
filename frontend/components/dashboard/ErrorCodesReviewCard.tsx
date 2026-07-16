"use client";

import { useState } from "react";
import { ErrorReviewEntry } from "@/types/dashboard";

type Props = {
  modules: string[];
  entriesByModule: Record<string, ErrorReviewEntry[]>;
  loading: boolean;
  resolving: string | null;
  applying: string | null;
  onResolve: (
    module: string,
    code: string,
    decision: string,
    approvedBy: string,
    newCode?: string,
    sourceFile?: string,
  ) => void;
  onApply: (module: string) => void;
};

const DECISION_LABELS: Record<string, string> = {
  keep_existing: "Giữ nguyên map cũ",
  approve_new: "Duyệt là mã mới",
  repair_existing: "Sửa lại message cũ",
  reassign: "Đổi sang mã khác",
};

function statusTone(status: string): string {
  if (status === "conflict") return "bg-red-100 text-red-700";
  if (status === "new") return "bg-blue-100 text-blue-700";
  if (status === "needs_review") return "bg-amber-100 text-amber-700";
  if (status === "duplicate_ok") return "bg-gray-100 text-gray-500";
  return "bg-gray-100 text-gray-600";
}

// Một entry còn "việc cần làm" nếu: chưa từng resolve, HOẶC đã resolve nhưng
// chưa được apply (chưa có applied_at — tức chưa bấm "Xác nhận module" hoặc
// apply chưa chạy tới entry này). duplicate_ok luôn loại trừ, đúng ngữ nghĩa
// hiện có của totalNeedsAction.
function needsAttention(e: ErrorReviewEntry): boolean {
  return e.status !== "duplicate_ok" && (!e.resolution || !e.applied_at);
}

export default function ErrorCodesReviewCard({
  modules,
  entriesByModule,
  loading,
  resolving,
  applying,
  onResolve,
  onApply,
}: Props) {
  const [approvedBy, setApprovedBy] = useState("");
  const [showDuplicateOk, setShowDuplicateOk] = useState(false);
  const [newCodeDrafts, setNewCodeDrafts] = useState<Record<string, string>>(
    {},
  );
  const [selectedModule, setSelectedModule] = useState<string>("");

  // Chỉ những module đã có report (đã chạy errors:parse) mới xuất hiện trong
  // dropdown — module chưa có report trả 404, useErrorCodes đã lọc sẵn.
  const modulesWithReport = modules.filter(
    (m) => (entriesByModule[m]?.length ?? 0) > 0,
  );

  const totalNeedsAction = modulesWithReport.reduce((sum, m) => {
    const moduleEntries = entriesByModule[m] ?? [];
    return (
      sum +
      moduleEntries.filter((e) => !e.resolution && e.status !== "duplicate_ok")
        .length
    );
  }, 0);

  const hasPendingWork = modulesWithReport.some((m) =>
    (entriesByModule[m] ?? []).some(needsAttention),
  );

  // Ẩn card khi không còn gì cần chú ý ở bất kỳ module nào (kể cả trường hợp
  // chưa module nào có report — modulesWithReport rỗng thì .some() tự false).
  // "Cần chú ý" = còn entry chưa resolve, HOẶC đã resolve nhưng chưa apply —
  // tính từ applied_at (dữ liệu thật trên đĩa), không suy đoán, nên card tự
  // hiện lại đúng lúc có entry/conflict mới, không lệch trước/sau reload.
  if (!loading && !hasPendingWork) return null;

  const activeModule =
    selectedModule && modulesWithReport.includes(selectedModule)
      ? selectedModule
      : (modulesWithReport[0] ?? "");

  const entries = (entriesByModule[activeModule] ?? []).filter(
    (e) => showDuplicateOk || e.status !== "duplicate_ok",
  );

  // Bao gồm source_file trong key — cùng 1 code có thể xuất hiện ở nhiều file
  // nguồn khác nhau với status khác nhau (vd 1 code "conflict" ở file này,
  // "duplicate_ok" ở file khác), backend cần source_file để phân biệt đúng
  // entry (xem cmd_resolve_error trong 2.pipeline: nhiều entry trùng code mà
  // thiếu source_file sẽ bị từ chối, không tự đoán entry nào).
  const draftKey = (code: string, sourceFile: string) =>
    `${activeModule}:${code}:${sourceFile}`;

  return (
    <section className="bg-white border border-indigo-200 rounded-2xl shadow-sm p-6">
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-semibold text-gray-900">Review mã lỗi nghiệp vụ</h2>
        {totalNeedsAction > 0 && (
          <span className="text-xs font-semibold px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full">
            {totalNeedsAction} cần duyệt
          </span>
        )}
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Report do <code className="font-mono">errors:parse</code> (2.pipeline)
        sinh ra — chọn quyết định cho từng mã, rồi bấm &quot;Xác nhận
        module&quot; để ghi vào 4.config/errors/.
      </p>


      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select
          value={activeModule}
          onChange={(e) => setSelectedModule(e.target.value)}
          className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm"
        >
          {modulesWithReport.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={approvedBy}
          onChange={(e) => setApprovedBy(e.target.value)}
          placeholder="Tên người duyệt"
          className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm flex-1 min-w-[160px]"
        />

        <label className="flex items-center gap-1.5 text-sm text-gray-500">
          <input
            type="checkbox"
            checked={showDuplicateOk}
            onChange={(e) => setShowDuplicateOk(e.target.checked)}
          />
          Hiện cả duplicate_ok
        </label>

        <button
          onClick={() => onApply(activeModule)}
          disabled={!activeModule || applying === activeModule}
          className="ml-auto px-3 py-1.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {applying === activeModule ? "Đang áp dụng..." : "Xác nhận module"}
        </button>
      </div>

      {loading && entries.length === 0 && (
        <p className="text-sm text-gray-400">Đang tải...</p>
      )}
      {!loading && entries.length === 0 && (
        <p className="text-sm text-gray-400">
          Không còn entry nào cần hiện (bấm &quot;Hiện cả duplicate_ok&quot;
          nếu muốn xem toàn bộ).
        </p>
      )}

      <div className="space-y-3">
        {entries.map((e) => {
          const key = draftKey(e.code, e.source_file);
          const busy = resolving === key;
          const draft = newCodeDrafts[key] ?? "";
          return (
            <div
              key={key}
              className="border border-gray-200 rounded-xl p-4 bg-gray-50/50"
            >
              <div className="flex items-center justify-between mb-2 gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-sm font-semibold text-gray-900">
                    {e.code}
                  </span>
                  <span
                    className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusTone(e.status)}`}
                  >
                    {e.status}
                  </span>
                  {e.resolution && (
                    <span className="text-xs text-emerald-600">
                      đã resolve:{" "}
                      {DECISION_LABELS[e.resolution.decision] ??
                        e.resolution.decision}{" "}
                      (bởi {e.resolution.approved_by})
                    </span>
                  )}
                  {e.applied_at && (
                    <span className="text-xs font-semibold px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                      đã áp dụng
                    </span>
                  )}
                </div>
                <span
                  className="text-xs text-gray-400 truncate max-w-[240px] shrink-0"
                  title={e.source_file}
                >
                  {e.source_file}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3 text-sm">
                <div>
                  <div className="text-xs text-gray-500 mb-1">
                    Nội dung mới (từ tài liệu)
                  </div>
                  <div className="p-2 bg-white border border-gray-200 rounded-lg text-gray-800">
                    {e.incoming.message || (
                      <em className="text-gray-400">(rỗng)</em>
                    )}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">
                    Đã có trong map hiện tại
                  </div>
                  <div className="p-2 bg-white border border-gray-200 rounded-lg text-gray-800">
                    {e.existing_in_map?.message || (
                      <em className="text-gray-400">(chưa có)</em>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {(["keep_existing", "approve_new", "repair_existing"] as const).map(
                  (d) => (
                    <button
                      key={d}
                      onClick={() =>
                        onResolve(
                          activeModule,
                          e.code,
                          d,
                          approvedBy,
                          undefined,
                          e.source_file,
                        )
                      }
                      disabled={busy || !approvedBy.trim()}
                      className="px-3 py-1.5 bg-gray-100 text-gray-700 text-sm font-semibold rounded-lg hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
                    >
                      {busy ? "Đang lưu..." : DECISION_LABELS[d]}
                    </button>
                  ),
                )}
                <input
                  type="text"
                  value={draft}
                  onChange={(ev) =>
                    setNewCodeDrafts((prev) => ({
                      ...prev,
                      [key]: ev.target.value,
                    }))
                  }
                  placeholder="mã mới"
                  className="w-24 px-2 py-1.5 border border-gray-200 rounded-lg text-sm"
                />
                <button
                  onClick={() =>
                    onResolve(
                      activeModule,
                      e.code,
                      "reassign",
                      approvedBy,
                      draft,
                      e.source_file,
                    )
                  }
                  disabled={busy || !approvedBy.trim() || !draft.trim()}
                  className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  {busy ? "Đang lưu..." : DECISION_LABELS.reassign}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
