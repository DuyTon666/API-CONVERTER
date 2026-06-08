"use client";

import { DocsBuildResult } from "./types";
import { countLintIssues } from "./format";

type Props = {
  docsBuilding: boolean;
  docsResult: DocsBuildResult | null;
  docsError: string;
  onBuildDocs: () => void;
  onOpenBundleEditor: () => void;
  onDownloadHtml: () => void;
};

export default function SwaggerDocsCard({
  docsBuilding,
  docsResult,
  docsError,
  onBuildDocs,
  onOpenBundleEditor,
  onDownloadHtml,
}: Props) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-700 mb-3">Tài liệu Swagger UI</h2>
      <p className="text-sm text-gray-400 mb-3">
        Bundle 5.openapi/ → kiểm tra Spectral/Redocly → build giao diện Swagger UI tĩnh.
      </p>

      <div className="flex gap-3 mb-3">
        <button
          onClick={onBuildDocs}
          disabled={docsBuilding}
          className="px-5 py-2.5 bg-indigo-100 text-indigo-700 text-sm font-semibold rounded-lg hover:bg-indigo-200 disabled:opacity-40 transition"
        >
          {docsBuilding ? "Đang build..." : "Build tài liệu Swagger UI"}
        </button>
        {docsResult?.bundle_ready && (
          <button
            onClick={onOpenBundleEditor}
            className="px-5 py-2.5 bg-slate-100 text-slate-600 text-sm font-semibold rounded-lg hover:bg-slate-200 transition"
          >
            Xem / Chỉnh sửa bundle
          </button>
        )}
        {docsResult?.html_ready && (
          <button
            onClick={onDownloadHtml}
            className="px-5 py-2.5 bg-emerald-100 text-emerald-700 text-sm font-semibold rounded-lg hover:bg-emerald-200 transition"
          >
            Tải HTML
          </button>
        )}
      </div>

      {docsError && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{docsError}</div>
      )}

      {docsResult && (() => {
        const { error, warn } = countLintIssues(docsResult);
        return (
          <div className="space-y-2 text-sm">
            <p className="text-gray-600">
              {docsResult.bundle_ready ? "✓ Bundle đã tạo" : "Chưa có bundle"}
              {" · "}
              {docsResult.html_ready ? "✓ HTML đã build" : "Chưa build được HTML"}
            </p>
            <p>
              Kiểm tra: {error === 0 && warn === 0 ? (
                <span className="text-green-600">Không có vấn đề</span>
              ) : (
                <>
                  {error > 0 && <span className="text-red-600 mr-3">{error} lỗi</span>}
                  {warn > 0 && <span className="text-yellow-600">{warn} cảnh báo</span>}
                </>
              )}
            </p>
            {(docsResult.spectral.length > 0 || docsResult.redocly.length > 0) && (
              <ul className="space-y-1 max-h-72 overflow-auto">
                {docsResult.spectral.map((issue, i) => (
                  <li
                    key={`spectral-${i}`}
                    className={`text-xs px-3 py-2 rounded-lg ${
                      issue.severity === 0
                        ? "bg-red-50 text-red-700"
                        : issue.severity === 1
                        ? "bg-yellow-50 text-yellow-700"
                        : "bg-blue-50 text-blue-700"
                    }`}
                  >
                    <span className="font-semibold mr-1">[Spectral]</span>
                    <span className="font-mono mr-1">[{issue.code}]</span>
                    {issue.message}
                    {issue.path?.length > 0 && <span className="opacity-60 ml-1">— {issue.path.join(".")}</span>}
                  </li>
                ))}
                {docsResult.redocly.map((issue, i) => (
                  <li
                    key={`redocly-${i}`}
                    className={`text-xs px-3 py-2 rounded-lg ${
                      issue.severity === "error" ? "bg-red-50 text-red-700" : "bg-yellow-50 text-yellow-700"
                    }`}
                  >
                    <span className="font-semibold mr-1">[Redocly]</span>
                    <span className="font-mono mr-1">[{issue.ruleId}]</span>
                    {issue.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })()}
    </section>
  );
}
