"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";

const BundleEditor = dynamic(() => import("./BundleEditor"), { ssr: false });

type FileResult = {
  file_id: string;
  filename: string;
  status: "pending" | "processing" | "done" | "error" | "flagged";
  error: string;
};

type SpectralIssue = {
  severity: number;
  message: string;
  code: string;
  path: string[];
};

type RedoclyIssue = {
  severity: string;
  message: string;
  ruleId: string;
};

type LintResult = {
  bundle_ready: boolean;
  html_ready: boolean;
  spectral: SpectralIssue[];
  redocly: RedoclyIssue[];
};

const statusColor: Record<string, string> = {
  pending: "text-gray-400",
  processing: "text-blue-500",
  done: "text-green-600",
  error: "text-red-500",
  flagged: "text-yellow-500",
};

const statusLabel: Record<string, string> = {
  pending: "Chờ",
  processing: "Đang xử lý...",
  done: "✓ Xong",
  error: "✕ Lỗi",
  flagged: "⚠ Cần review",
};

const spectralColor = (severity: number) => {
  if (severity === 0) return "bg-red-50 text-red-700";
  if (severity === 1) return "bg-yellow-50 text-yellow-700";
  return "bg-blue-50 text-blue-700";
};

const spectralLabel = (severity: number) => {
  if (severity === 0) return "error";
  if (severity === 1) return "warn";
  return "info";
};

export default function JobPage() {
  const { job_id } = useParams<{ job_id: string }>();
  const [files, setFiles] = useState<FileResult[]>([]);
  const [done, setDone] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [lintResult, setLintResult] = useState<LintResult | null>(null);

  // Bundle editor
  const [bundleContent, setBundleContent] = useState<string | null>(null);
  const [savingBundle, setSavingBundle] = useState(false);
  const [relinting, setRelinting] = useState(false);

  // SSE — theo dõi tiến trình
  useEffect(() => {
    const es = new EventSource(`http://localhost:8000/jobs/${job_id}/stream`);
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.event === "done") {
        setDone(true);
        es.close();
        return;
      }
      setFiles((prev) => {
        const exists = prev.find((f) => f.file_id === data.file_id);
        if (exists) return prev.map((f) => (f.file_id === data.file_id ? data : f));
        return [...prev, data];
      });
    };
    return () => es.close();
  }, [job_id]);

  // Export: bundle + lint + build HTML
  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch(`http://localhost:8000/jobs/${job_id}/export`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) { alert("Lỗi export: " + data.detail); return; }
      setLintResult(data);
    } finally {
      setExporting(false);
    }
  };

  // Mở bundle editor
  const openBundleEditor = async () => {
    try {
      const res = await fetch(`http://localhost:8000/jobs/${job_id}/bundle-content`, {
        cache: "no-store",
      });
      if (res.status === 404) { alert("Chưa có bundle, hãy export trước"); return; }
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: res.statusText }));
        alert("Lỗi đọc bundle: " + data.detail);
        return;
      }
      const text = await res.text();
      setBundleContent(text);
    } catch (e) {
      alert("Lỗi kết nối: " + String(e));
    }
  };

  // Lưu bundle
  const saveBundle = async () => {
    if (bundleContent === null) return;
    setSavingBundle(true);
    try {
      await fetch(`http://localhost:8000/jobs/${job_id}/bundle-content`, {
        method: "PUT",
        headers: { "Content-Type": "text/plain; charset=utf-8" },
        body: bundleContent,
      });
    } finally {
      setSavingBundle(false);
    }
  };

  // Lưu bundle rồi lint lại
  const saveAndRelint = async () => {
    if (bundleContent === null) return;
    setSavingBundle(true);
    try {
      await fetch(`http://localhost:8000/jobs/${job_id}/bundle-content`, {
        method: "PUT",
        headers: { "Content-Type": "text/plain; charset=utf-8" },
        body: bundleContent,
      });
      setRelinting(true);
      const res = await fetch(`http://localhost:8000/jobs/${job_id}/relint`, { method: "POST" });
      const data = await res.json();
      setLintResult(data);
      setBundleContent(null);
    } finally {
      setSavingBundle(false);
      setRelinting(false);
    }
  };

  const handleDownloadHtml = () => {
    window.open(`http://localhost:8000/jobs/${job_id}/download-html`, "_blank");
  };

  const doneCount = files.filter((f) => f.status === "done").length;

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center py-16 px-4">
      <div className="w-full max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-800 mb-1">Đang xử lý</h1>
        <p className="text-gray-400 text-sm mb-6">Job: {job_id}</p>

        {/* Progress bar */}
        <div className="mb-2 flex justify-between text-sm text-gray-500">
          <span>{doneCount} / {files.length} file xong</span>
          {done && <span className="text-green-600 font-medium">Hoàn thành</span>}
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
          <div
            className="bg-blue-500 h-2 rounded-full transition-all"
            style={{ width: files.length ? `${(doneCount / files.length) * 100}%` : "0%" }}
          />
        </div>

        {/* Danh sách file */}
        <ul className="space-y-2 mb-6">
          {files.map((f) => (
            <li key={f.file_id} className="flex justify-between items-center bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm">
              <span className="text-gray-700 truncate mr-4">{f.filename}</span>
              <span className={`shrink-0 ${statusColor[f.status]}`}>{statusLabel[f.status]}</span>
            </li>
          ))}
        </ul>

        {/* Nút Xuất / Build lại */}
        {done && (
          <button
            onClick={handleExport}
            disabled={exporting}
            className="w-full py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700 disabled:opacity-40 transition mb-6"
          >
            {exporting ? "Đang build..." : lintResult ? "Build lại" : "Xuất tài liệu"}
          </button>
        )}

        {/* Lint results */}
        {lintResult && (
          <div className="space-y-5">
            {/* Header */}
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-700">Kết quả kiểm tra</h2>
              <div className="flex gap-2">
                <button
                  onClick={openBundleEditor}
                  className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition"
                >
                  Chỉnh sửa bundle
                </button>
                {lintResult.html_ready && (
                  <button
                    onClick={handleDownloadHtml}
                    className="px-4 py-2 bg-green-600 text-white text-sm font-semibold rounded-lg hover:bg-green-700 transition"
                  >
                    Tải HTML
                  </button>
                )}
              </div>
            </div>

            {/* Spectral */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-sm font-semibold text-gray-600">Spectral</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${lintResult.spectral.length === 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                  {lintResult.spectral.length} vấn đề
                </span>
              </div>
              {lintResult.spectral.length === 0 ? (
                <p className="text-green-600 text-sm">Không có lỗi</p>
              ) : (
                <ul className="space-y-1 max-h-64 overflow-auto">
                  {lintResult.spectral.map((issue, i) => (
                    <li key={i} className={`text-xs px-3 py-2 rounded-lg ${spectralColor(issue.severity)}`}>
                      <span className="font-semibold uppercase mr-1">[{spectralLabel(issue.severity)}]</span>
                      <span className="font-mono mr-1">[{issue.code}]</span>
                      {issue.message}
                      {issue.path?.length > 0 && (
                        <span className="opacity-60 ml-1">— {issue.path.join(".")}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Redocly */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-sm font-semibold text-gray-600">Redocly</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${lintResult.redocly.length === 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                  {lintResult.redocly.length} vấn đề
                </span>
              </div>
              {lintResult.redocly.length === 0 ? (
                <p className="text-green-600 text-sm">Không có lỗi</p>
              ) : (
                <ul className="space-y-1 max-h-64 overflow-auto">
                  {lintResult.redocly.map((issue, i) => (
                    <li key={i} className={`text-xs px-3 py-2 rounded-lg ${issue.severity === "error" ? "bg-red-50 text-red-700" : "bg-yellow-50 text-yellow-700"}`}>
                      <span className="font-semibold uppercase mr-1">[{issue.severity}]</span>
                      <span className="font-mono mr-1">[{issue.ruleId}]</span>
                      {issue.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Bundle editor modal */}
      {bundleContent !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl w-full max-w-4xl h-[90vh] flex flex-col overflow-hidden">
            <div className="flex justify-between items-center px-6 py-4 border-b">
              <h2 className="font-semibold text-gray-800">Chỉnh sửa bundle — openapi-bundled.yaml</h2>
              <button onClick={() => setBundleContent(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="flex-1 min-h-[400px]">
              <BundleEditor
                content={bundleContent}
                onChange={setBundleContent}
                spectralIssues={lintResult?.spectral ?? []}
                redoclyIssues={lintResult?.redocly ?? []}
              />
            </div>
            <div className="flex gap-3 px-6 py-4 border-t">
              <button
                onClick={saveBundle}
                disabled={savingBundle}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm transition disabled:opacity-40"
              >
                {savingBundle ? "Đang lưu..." : "Lưu"}
              </button>
              <button
                onClick={saveAndRelint}
                disabled={savingBundle || relinting}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm transition disabled:opacity-40"
              >
                {relinting ? "Đang kiểm tra..." : "Lưu & Kiểm tra lại"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
