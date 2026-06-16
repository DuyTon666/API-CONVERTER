"use client";

import { ImportModuleProgress, ModuleListResult } from "./types";
import { formatDate, formatRelativeTime } from "./format";

type Props = {
  moduleList: ModuleListResult | null;
  loading: boolean;
  error: string;
  activatingModule: string | null;
  activateError: string;
  onActivate: (name: string) => void;
  deactivatingModule: string | null;
  deactivateError: string;
  onDeactivate: (name: string) => void;
  importRunning: boolean;
  importTarget: string | null;
  importModules: ImportModuleProgress[];
  importDone: boolean;
  importError: string;
  onImport: (moduleName: string | null) => void;
};

const statusBadge: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  draft: "bg-amber-100 text-amber-700",
  deprecated: "bg-gray-100 text-gray-500",
};

export default function ModuleRegistryCard({
  moduleList,
  loading,
  error,
  activatingModule,
  activateError,
  onActivate,
  deactivatingModule,
  deactivateError,
  onDeactivate,
  importRunning,
  importTarget,
  importModules,
  importDone,
  importError,
  onImport,
}: Props) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-gray-900">Module Registry</h2>
        <button
          onClick={() => onImport(null)}
          disabled={
            importRunning ||
            loading ||
            !moduleList?.modules.some((m) => m.status === "active")
          }
          className="px-4 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
          title="Chạy pipeline convert tài liệu của tất cả module active thành OpenAPI YAML"
        >
          {importRunning && importTarget === null
            ? "Đang import..."
            : "Import tất cả"}
        </button>
      </div>

      {loading && <p className="text-sm text-gray-400">Đang tải...</p>}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {error}
        </div>
      )}
      {activateError && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {activateError}
        </div>
      )}
      {deactivateError && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {deactivateError}
        </div>
      )}
      {importError && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {importError}
        </div>
      )}

      {moduleList &&
        (moduleList.modules.length === 0 ? (
          <p className="text-sm text-gray-400">
            Chưa có module nào trong registry.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-gray-400 border-b border-gray-200">
                  <th className="py-2 pr-2 font-medium">Module</th>
                  <th className="py-2 pr-2 font-medium">Trạng thái</th>
                  <th className="py-2 pr-2 font-medium">File</th>
                  <th className="py-2 pr-2 font-medium">Endpoint</th>
                  <th className="py-2 pr-2 font-medium">Import gần nhất</th>
                  <th className="py-2 pr-2 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {moduleList.modules.map((m) => (
                  <tr key={m.name} className="hover:bg-gray-50">
                    <td className="py-3 pr-2 font-medium text-gray-900">
                      {m.name}
                    </td>
                    <td className="py-3 pr-2">
                      <span
                        className={`text-xs font-medium px-2 py-1 rounded-full ${
                          statusBadge[m.status] ?? "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {m.status}
                      </span>
                    </td>
                    <td className="py-3 pr-2 text-gray-600">{m.file_count}</td>
                    <td className="py-3 pr-2 text-gray-600">
                      {m.endpoint_count}
                    </td>
                    <td
                      className="py-3 pr-2 text-gray-400"
                      title={
                        m.last_import_at
                          ? `${formatDate(m.last_import_at)}${
                              m.last_import_status
                                ? ` (${m.last_import_status})`
                                : ""
                            }`
                          : undefined
                      }
                    >
                      {formatRelativeTime(m.last_import_at)}
                    </td>
                    <td className="py-3 pr-2 text-right">
                      {m.status === "draft" ? (
                        <button
                          onClick={() => onActivate(m.name)}
                          disabled={activatingModule !== null}
                          className="px-3 py-1 bg-emerald-500 text-white text-xs font-medium rounded-lg hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed transition"
                          title="Chuyển module từ draft sang active để cho phép chạy import"
                        >
                          {activatingModule === m.name
                            ? "Đang kích hoạt..."
                            : "Activate"}
                        </button>
                      ) : m.status === "active" ? (
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={() => onImport(m.name)}
                            disabled={importRunning}
                            className="px-3 py-1 bg-gray-100 text-gray-600 text-xs font-medium rounded-lg hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
                            title="Chạy pipeline convert riêng module này"
                          >
                            {importRunning && importTarget === m.name
                              ? "Đang import..."
                              : "Import"}
                          </button>
                          <button
                            onClick={() => onDeactivate(m.name)}
                            disabled={deactivatingModule !== null || importRunning}
                            className="px-3 py-1 bg-red-50 text-red-600 text-xs font-medium rounded-lg hover:bg-red-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
                            title="Chuyển module về deprecated"
                          >
                            {deactivatingModule === m.name
                              ? "Đang tắt..."
                              : "Deactivate"}
                          </button>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      {importModules.length > 0 && (
        <div className="mt-4 space-y-2">
          {importModules.map((m) => {
            const processed = m.success + m.failed + m.skipped;
            const pct =
              m.total > 0 ? Math.round((processed / m.total) * 100) : 0;
            const isError = m.status === "error";
            return (
              <div
                key={m.name}
                className={`rounded-xl p-4 ${
                  isError
                    ? "bg-red-50 border border-red-100"
                    : "bg-indigo-50 border border-indigo-100"
                }`}
              >
                <div className="flex items-center justify-between text-sm mb-2">
                  <span
                    className={`font-medium ${
                      isError ? "text-red-700" : "text-indigo-700"
                    }`}
                  >
                    {m.status === "running"
                      ? `Đang import module "${m.name}"`
                      : m.status === "done"
                        ? `✓ Import "${m.name}" hoàn thành`
                        : isError
                          ? `✕ Import "${m.name}" thất bại`
                          : `Chờ import "${m.name}"`}
                  </span>
                  <span className={isError ? "text-red-500" : "text-indigo-500"}>
                    {processed}/{m.total} file
                  </span>
                </div>
                <div
                  className={`w-full h-2 rounded-full overflow-hidden ${
                    isError ? "bg-red-100" : "bg-indigo-100"
                  }`}
                >
                  <div
                    className={`h-2 rounded-full transition-all duration-500 ${
                      isError ? "bg-red-500" : "bg-indigo-600"
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                {m.status === "done" &&
                  (m.failed > 0 || m.skipped > 0 || m.needs_review > 0) && (
                    <p className="text-xs text-indigo-500 mt-2">
                      {m.success} thành công
                      {m.failed > 0 && ` · ${m.failed} lỗi`}
                      {m.skipped > 0 && ` · ${m.skipped} bỏ qua`}
                      {m.needs_review > 0 && ` · ${m.needs_review} cần review`}
                    </p>
                  )}
                {isError && m.error && (
                  <p className="text-xs text-red-600 mt-2">{m.error}</p>
                )}
              </div>
            );
          })}
          {importDone && (
            <p className="text-xs text-emerald-600">
              ✓ Toàn bộ import đã hoàn thành
            </p>
          )}
        </div>
      )}
    </section>
  );
}
