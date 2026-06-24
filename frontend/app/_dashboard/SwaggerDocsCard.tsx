"use client";

import { DocsBuildResult } from "./types";
import { countLintIssues } from "./format";
import { ErrorAlert } from "./ErrorAlert";

type Props = {
  docsBuilding: boolean;
  docsResult: DocsBuildResult | null;
  docsError: string;
  bundleReady: boolean;
  htmlReady: boolean;
  relinting: boolean;
  onBuildDocs: () => void;
  onRelint: () => void;
  onOpenBundleEditor: () => void;
  onDownloadHtml: () => void;
};

export default function SwaggerDocsCard({
  docsBuilding,
  docsResult,
  docsError,
  bundleReady,
  htmlReady,
  relinting,
  onBuildDocs,
  onRelint,
  onOpenBundleEditor,
  onDownloadHtml,
}: Props) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
      <h2 className="font-semibold text-gray-900 mb-3">Tài liệu Swagger UI</h2>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm mb-4">
        <span className={bundleReady ? "text-emerald-600" : "text-gray-400"}>
          {bundleReady ? "✓ Bundle đã tạo" : "○ Chưa có bundle"}
        </span>
        <span className={htmlReady ? "text-emerald-600" : "text-gray-400"}>
          {htmlReady ? "✓ HTML đã build" : "○ Chưa build HTML"}
        </span>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {bundleReady ? (
          <>
            <button
              onClick={onOpenBundleEditor}
              className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition"
            >
              Xem / Sửa lỗi bundle
            </button>
            <button
              onClick={onRelint}
              disabled={relinting || docsBuilding}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              {relinting ? "Đang kiểm tra..." : "Kiểm tra lỗi"}
            </button>
            {htmlReady && (
              <button
                onClick={onDownloadHtml}
                className="px-3 py-1.5 bg-emerald-500 text-white text-sm font-medium rounded-lg hover:bg-emerald-600 transition"
              >
                Tải HTML
              </button>
            )}
            <button
              onClick={onBuildDocs}
              disabled={docsBuilding || relinting}
              className="px-3 py-1.5 border border-gray-300 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              {docsBuilding ? "Đang build..." : "Tạo lại tài liệu"}
            </button>
          </>
        ) : (
          <button
            onClick={onBuildDocs}
            disabled={docsBuilding}
            className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {docsBuilding ? "Đang build..." : "Build tài liệu Swagger UI"}
          </button>
        )}
      </div>

      {docsError && <ErrorAlert message={docsError} className="mb-4" />}

      {bundleReady && !docsResult && (
        <p className="text-sm text-gray-400">
          Bấm &quot;Kiểm tra lỗi&quot; để chạy Spectral/Redocly trên bundle hiện
          tại, hoặc mở editor để sửa trực tiếp.
        </p>
      )}

      {docsResult &&
        (() => {
          const { error, warn } = countLintIssues(docsResult);
          return (
            <div className="space-y-2 text-sm">
              <p className="text-gray-500">
                Kiểm tra:{" "}
                {error === 0 && warn === 0 ? (
                  <span className="text-emerald-600">Không có vấn đề</span>
                ) : (
                  <>
                    {error > 0 && (
                      <span className="text-red-600 mr-3">{error} lỗi</span>
                    )}
                    {warn > 0 && (
                      <span className="text-amber-600">{warn} cảnh báo</span>
                    )}
                  </>
                )}
              </p>
              {(docsResult.spectral.length > 0 ||
                docsResult.redocly.length > 0) && (
                <ul className="space-y-2 max-h-72 overflow-auto">
                  {docsResult.spectral.map((issue, i) => {
                    const isErr = issue.severity === 0;
                    return (
                      <li
                        key={`spectral-${i}`}
                        className={`flex items-start gap-2 rounded-lg px-3 py-2 border ${
                          isErr
                            ? "bg-red-50 border-red-100"
                            : "bg-amber-50 border-amber-100"
                        }`}
                      >
                        <span
                          className={`text-xs font-semibold rounded px-1.5 py-0.5 mt-0.5 shrink-0 ${
                            isErr
                              ? "text-red-600 bg-red-100"
                              : "text-amber-600 bg-amber-100"
                          }`}
                          title={issue.code}
                        >
                          Spectral
                        </span>
                        <span className="text-gray-700 text-xs leading-5">
                          {issue.message}
                          {issue.path?.length > 0 && (
                            <span className="opacity-60 ml-1">
                              — {issue.path.join(".")}
                            </span>
                          )}
                        </span>
                      </li>
                    );
                  })}
                  {docsResult.redocly.map((issue, i) => {
                    const isErr = issue.severity === "error";
                    return (
                      <li
                        key={`redocly-${i}`}
                        className={`flex items-start gap-2 rounded-lg px-3 py-2 border ${
                          isErr
                            ? "bg-red-50 border-red-100"
                            : "bg-amber-50 border-amber-100"
                        }`}
                      >
                        <span
                          className={`text-xs font-semibold rounded px-1.5 py-0.5 mt-0.5 shrink-0 ${
                            isErr
                              ? "text-red-600 bg-red-100"
                              : "text-amber-600 bg-amber-100"
                          }`}
                          title={issue.ruleId}
                        >
                          Redocly
                        </span>
                        <span className="text-gray-700 text-xs leading-5">
                          {issue.message}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })()}
    </section>
  );
}
