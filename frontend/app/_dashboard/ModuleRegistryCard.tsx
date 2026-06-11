"use client";

import { ImportModuleProgress, ModuleListResult } from "./types";
import { formatDate, statusColor, statusIcon } from "./format";

type Props = {
  moduleList: ModuleListResult | null;
  loading: boolean;
  error: string;
  activatingModule: string | null;
  activateError: string;
  onActivate: (name: string) => void;
  importRunning: boolean;
  importTarget: string | null;
  importModules: ImportModuleProgress[];
  importDone: boolean;
  importError: string;
  onImport: (moduleName: string | null) => void;
};

export default function ModuleRegistryCard({
  moduleList,
  loading,
  error,
  activatingModule,
  activateError,
  onActivate,
  importRunning,
  importTarget,
  importModules,
  importDone,
  importError,
  onImport,
}: Props) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-semibold text-gray-700">Module registry</h2>
        <button
          onClick={() => onImport(null)}
          disabled={importRunning || loading || !moduleList?.modules.some((m) => m.status === "active")}
          className="px-4 py-2 bg-emerald-100 text-emerald-700 text-sm font-semibold rounded-lg hover:bg-emerald-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {importRunning && importTarget === null ? "Đang import..." : "Import tất cả module active"}
        </button>
      </div>
      <p className="text-xs text-gray-400 mb-4">
        <span className="font-medium text-indigo-500">Activate</span>: chuyển module draft → active để cho phép chạy import.{" "}
        <span className="font-medium text-emerald-600">Import</span>: chạy pipeline convert tài liệu thành OpenAPI YAML.
      </p>

      {loading && <p className="text-sm text-gray-400">Đang tải...</p>}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{error}</div>
      )}
      {activateError && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{activateError}</div>
      )}
      {importError && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{importError}</div>
      )}

      {moduleList && (
        moduleList.modules.length === 0 ? (
          <p className="text-sm text-gray-400">Chưa có module nào trong registry.</p>
        ) : (
          <div className="space-y-3">
            <div className="overflow-x-auto bg-white border border-gray-200 rounded-lg">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-200">
                    <th className="px-4 py-2 font-medium">Module</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium text-right">Files</th>
                    <th className="px-4 py-2 font-medium text-right">Endpoints</th>
                    <th className="px-4 py-2 font-medium">Last import</th>
                    <th className="px-4 py-2 font-medium">Created</th>
                    <th className="px-4 py-2 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {moduleList.modules.map((m) => (
                    <tr key={m.name} className="border-b border-gray-100 last:border-0">
                      <td className="px-4 py-2 text-gray-700 font-medium">{m.name}</td>
                      <td className={`px-4 py-2 ${statusColor[m.status] ?? "text-gray-400"}`}>
                        {statusIcon[m.status] ?? "?"} {m.status}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-600">{m.file_count}</td>
                      <td className="px-4 py-2 text-right text-gray-600">{m.endpoint_count}</td>
                      <td className="px-4 py-2 text-gray-500">
                        {formatDate(m.last_import_at)}
                        {m.last_import_status ? ` (${m.last_import_status})` : ""}
                      </td>
                      <td className="px-4 py-2 text-gray-500">{formatDate(m.created_at)}</td>
                      <td className="px-4 py-2">
                        {m.status === "draft" ? (
                          <button
                            onClick={() => onActivate(m.name)}
                            disabled={activatingModule !== null}
                            className="px-3 py-1 bg-indigo-50 text-indigo-600 text-xs font-medium rounded hover:bg-indigo-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
                            title="Chuyển module từ trạng thái draft sang active, sau đó mới có thể chạy Import"
                          >
                            {activatingModule === m.name ? "Đang kích hoạt..." : "Activate"}
                          </button>
                        ) : m.status === "active" ? (
                          <button
                            onClick={() => onImport(m.name)}
                            disabled={importRunning}
                            className="px-3 py-1 bg-emerald-50 text-emerald-600 text-xs font-medium rounded hover:bg-emerald-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
                            title="Chạy pipeline convert tài liệu trong module thành OpenAPI YAML"
                          >
                            {importRunning && importTarget === m.name ? "Đang import..." : "Import"}
                          </button>
                        ) : (
                          <span className="text-gray-300 text-xs">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-sm text-gray-400">
              Total: {moduleList.summary.total} (
              {Object.entries(moduleList.summary.by_status)
                .map(([s, c]) => `${s}=${c}`)
                .join(", ")}
              )
            </p>
          </div>
        )
      )}

      {(importRunning || importDone || importModules.length > 0) && (
        <div className="mt-4 space-y-2">
          <h3 className="text-sm font-semibold text-gray-600">
            Import {importTarget ? `module "${importTarget}"` : "tất cả module active"}
            {importRunning && <span className="ml-2 font-normal text-blue-500">đang chạy...</span>}
            {importDone && <span className="ml-2 font-normal text-green-600">hoàn thành</span>}
          </h3>
          <ul className="space-y-1">
            {importModules.map((m) => (
              <li
                key={m.name}
                className="flex justify-between items-center bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm"
              >
                <span className="text-gray-700 font-medium">{m.name}</span>
                {m.status === "done" ? (
                  <span className="text-green-600">
                    ✓ {m.success}/{m.total} thành công
                    {m.failed > 0 && `, ${m.failed} lỗi`}
                    {m.skipped > 0 && `, ${m.skipped} bỏ qua`}
                    {m.needs_review > 0 && `, ${m.needs_review} cần review`}
                  </span>
                ) : m.status === "error" ? (
                  <span className="text-red-500">✕ {m.error}</span>
                ) : (
                  <span className="text-gray-400">đang xử lý...</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
