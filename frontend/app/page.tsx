"use client";

import { useEffect, useState } from "react";
import ImportCard from "./_dashboard/ImportCard";
import ScanCard from "./_dashboard/ScanCard";
import SuggestCard from "./_dashboard/SuggestCard";
import ModuleRegistryCard from "./_dashboard/ModuleRegistryCard";
import SwaggerDocsCard from "./_dashboard/SwaggerDocsCard";
import BundleEditorModal from "./_dashboard/BundleEditorModal";
import { isSupportedFile } from "./_dashboard/format";
import {
  ApplyResult,
  DocsBuildResult,
  ImportModuleProgress,
  ModuleListResult,
  ScanResult,
  SuggestionsResult,
} from "./_dashboard/types";

export default function Home() {
  const backend = process.env.NEXT_PUBLIC_API_URL;

  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanLoading, setScanLoading] = useState(true);
  const [scanError, setScanError] = useState("");

  const [moduleList, setModuleList] = useState<ModuleListResult | null>(null);
  const [modulesLoading, setModulesLoading] = useState(true);
  const [modulesError, setModulesError] = useState("");

  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadMessage, setUploadMessage] = useState("");

  const [suggestions, setSuggestions] = useState<SuggestionsResult | null>(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const [suggestionsError, setSuggestionsError] = useState("");
  const [suggestRunning, setSuggestRunning] = useState(false);
  const [approving, setApproving] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);
  const [suggestActionError, setSuggestActionError] = useState("");
  const [overrideInputs, setOverrideInputs] = useState<Record<string, string>>({});

  const [activatingModule, setActivatingModule] = useState<string | null>(null);
  const [activateError, setActivateError] = useState("");

  const [importRunning, setImportRunning] = useState(false);
  const [importTarget, setImportTarget] = useState<string | null>(null);
  const [importModules, setImportModules] = useState<ImportModuleProgress[]>([]);
  const [importDone, setImportDone] = useState(false);
  const [importError, setImportError] = useState("");

  const [docsBuilding, setDocsBuilding] = useState(false);
  const [docsResult, setDocsResult] = useState<DocsBuildResult | null>(null);
  const [docsError, setDocsError] = useState("");

  const [bundleContent, setBundleContent] = useState<string | null>(null);
  const [savingBundle, setSavingBundle] = useState(false);
  const [relinting, setRelinting] = useState(false);

  const fetchScan = () => {
    return fetch(`${backend}/modules/scan`)
      .then((res) => {
        if (!res.ok) throw new Error("Không thể tải dữ liệu scan");
        return res.json();
      })
      .then((data) => {
        setScan(data);
        setScanError("");
      })
      .catch((e) => setScanError(e instanceof Error ? e.message : "Lỗi kết nối backend"))
      .finally(() => setScanLoading(false));
  };

  const fetchModules = () => {
    return fetch(`${backend}/modules`)
      .then((res) => {
        if (!res.ok) throw new Error("Không thể tải danh sách module");
        return res.json();
      })
      .then((data) => {
        setModuleList(data);
        setModulesError("");
      })
      .catch((e) => setModulesError(e instanceof Error ? e.message : "Lỗi kết nối backend"))
      .finally(() => setModulesLoading(false));
  };

  const fetchSuggestions = () => {
    return fetch(`${backend}/modules/suggestions`)
      .then((res) => {
        if (!res.ok) throw new Error("Không thể tải suggestions");
        return res.json();
      })
      .then((data) => {
        setSuggestions(data);
        setSuggestionsError("");
      })
      .catch((e) => setSuggestionsError(e instanceof Error ? e.message : "Lỗi kết nối backend"))
      .finally(() => setSuggestionsLoading(false));
  };

  useEffect(() => {
    fetchScan();
    fetchModules();
    fetchSuggestions();
  }, []);

  const handleSelectFiles = (selected: FileList | null) => {
    if (!selected) return;
    const valid = Array.from(selected).filter((f) => isSupportedFile(f.name));
    setUploadFiles((prev) => [...prev, ...valid]);
    setUploadMessage("");
    setUploadError("");
  };

  const handleRemoveUploadFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, j) => j !== index));
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0) return;
    setUploading(true);
    setUploadError("");
    setUploadMessage("");
    const form = new FormData();
    uploadFiles.forEach((f) => form.append("files", f));
    try {
      const res = await fetch(`${backend}/source/upload`, {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Lỗi upload");
      setUploadMessage(`Đã lưu ${data.total} file vào 1.docs/source/api_contract/`);
      setUploadFiles([]);
      setScanLoading(true);
      fetchScan();
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Lỗi kết nối backend");
    } finally {
      setUploading(false);
    }
  };

  const handleRunSuggest = async () => {
    setSuggestRunning(true);
    setSuggestActionError("");
    try {
      const res = await fetch(`${backend}/modules/suggest`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Lỗi chạy suggest-root");
      setSuggestions(data);
    } catch (e: unknown) {
      setSuggestActionError(e instanceof Error ? e.message : "Lỗi kết nối backend");
    } finally {
      setSuggestRunning(false);
    }
  };

  const handleApprove = async (
    body: { mode: string; module?: string; file?: string; override_module?: string },
    key: string
  ) => {
    setApproving(key);
    setSuggestActionError("");
    try {
      const res = await fetch(`${backend}/modules/suggestions/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Lỗi duyệt suggestion");
      setSuggestions(data);
    } catch (e: unknown) {
      setSuggestActionError(e instanceof Error ? e.message : "Lỗi kết nối backend");
    } finally {
      setApproving(null);
    }
  };

  const handleApply = async () => {
    setApplying(true);
    setSuggestActionError("");
    try {
      const res = await fetch(`${backend}/modules/apply`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Lỗi apply suggestions");
      setApplyResult(data);
      setScanLoading(true);
      setModulesLoading(true);
      await Promise.all([fetchScan(), fetchModules(), fetchSuggestions()]);
    } catch (e: unknown) {
      setSuggestActionError(e instanceof Error ? e.message : "Lỗi kết nối backend");
    } finally {
      setApplying(false);
    }
  };

  const handleActivate = async (name: string) => {
    setActivatingModule(name);
    setActivateError("");
    try {
      const res = await fetch(`${backend}/modules/${encodeURIComponent(name)}/activate`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Lỗi activate module");
      setModuleList(data);
    } catch (e: unknown) {
      setActivateError(e instanceof Error ? e.message : "Lỗi kết nối backend");
    } finally {
      setActivatingModule(null);
    }
  };

  const handleImport = async (moduleName: string | null) => {
    setImportError("");
    setImportModules([]);
    setImportDone(false);
    setImportRunning(true);
    setImportTarget(moduleName);
    try {
      const url = moduleName
        ? `${backend}/modules/import?module=${encodeURIComponent(moduleName)}`
        : `${backend}/modules/import`;
      const res = await fetch(url, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Lỗi khởi chạy import");

      const es = new EventSource(`${backend}/modules/import/${data.job_id}/stream`);
      es.onmessage = (e) => {
        const payload = JSON.parse(e.data);
        if (payload.event === "done") {
          setImportDone(true);
          setImportRunning(false);
          es.close();
          fetchModules();
          return;
        }
        setImportModules((prev) => {
          const exists = prev.find((m) => m.name === payload.name);
          if (exists) return prev.map((m) => (m.name === payload.name ? payload : m));
          return [...prev, payload];
        });
      };
      es.onerror = () => {
        es.close();
        setImportRunning(false);
        setImportError("Mất kết nối stream import");
      };
    } catch (e: unknown) {
      setImportError(e instanceof Error ? e.message : "Lỗi kết nối backend");
      setImportRunning(false);
    }
  };

  const handleBuildDocs = async () => {
    setDocsError("");
    setDocsBuilding(true);
    try {
      const res = await fetch(`${backend}/docs/build`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Lỗi build tài liệu");
      setDocsResult(data);
    } catch (e: unknown) {
      setDocsError(e instanceof Error ? e.message : "Lỗi kết nối backend");
    } finally {
      setDocsBuilding(false);
    }
  };

  const handleDownloadDocsHtml = () => {
    window.open(`${backend}/docs/download-html`, "_blank");
  };

  const openBundleEditor = async () => {
    try {
      const res = await fetch(`${backend}/docs/bundle-content`, { cache: "no-store" });
      if (res.status === 404) { alert("Chưa có bundle, hãy build tài liệu trước"); return; }
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

  const saveBundle = async () => {
    if (bundleContent === null) return;
    setSavingBundle(true);
    try {
      await fetch(`${backend}/docs/bundle-content`, {
        method: "PUT",
        headers: { "Content-Type": "text/plain; charset=utf-8" },
        body: bundleContent,
      });
    } finally {
      setSavingBundle(false);
    }
  };

  const saveAndRelint = async () => {
    if (bundleContent === null) return;
    setSavingBundle(true);
    try {
      await fetch(`${backend}/docs/bundle-content`, {
        method: "PUT",
        headers: { "Content-Type": "text/plain; charset=utf-8" },
        body: bundleContent,
      });
      setRelinting(true);
      const res = await fetch(`${backend}/docs/relint`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) { alert("Lỗi kiểm tra lại: " + data.detail); return; }
      setDocsResult(data);
      setBundleContent(null);
    } finally {
      setSavingBundle(false);
      setRelinting(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center py-16 px-4">
      <div className="w-full max-w-3xl space-y-10">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 mb-1">API Converter</h1>
          <p className="text-gray-400">Theo dõi luồng import module từ 1.docs/source/api_contract/</p>
        </div>

        <ImportCard
          files={uploadFiles}
          uploading={uploading}
          error={uploadError}
          message={uploadMessage}
          onSelectFiles={handleSelectFiles}
          onRemoveFile={handleRemoveUploadFile}
          onUpload={handleUpload}
        />

        <ScanCard scan={scan} loading={scanLoading} error={scanError} />

        <SuggestCard
          suggestions={suggestions}
          loading={suggestionsLoading}
          error={suggestionsError}
          actionError={suggestActionError}
          suggestRunning={suggestRunning}
          approving={approving}
          applying={applying}
          applyResult={applyResult}
          overrideInputs={overrideInputs}
          onOverrideChange={(file, value) => setOverrideInputs((prev) => ({ ...prev, [file]: value }))}
          onRunSuggest={handleRunSuggest}
          onApprove={handleApprove}
          onApply={handleApply}
        />

        <ModuleRegistryCard
          moduleList={moduleList}
          loading={modulesLoading}
          error={modulesError}
          activatingModule={activatingModule}
          activateError={activateError}
          onActivate={handleActivate}
          importRunning={importRunning}
          importTarget={importTarget}
          importModules={importModules}
          importDone={importDone}
          importError={importError}
          onImport={handleImport}
        />

        <SwaggerDocsCard
          docsBuilding={docsBuilding}
          docsResult={docsResult}
          docsError={docsError}
          onBuildDocs={handleBuildDocs}
          onOpenBundleEditor={openBundleEditor}
          onDownloadHtml={handleDownloadDocsHtml}
        />
      </div>

      {bundleContent !== null && (
        <BundleEditorModal
          content={bundleContent}
          onChange={setBundleContent}
          spectralIssues={docsResult?.spectral ?? []}
          redoclyIssues={docsResult?.redocly ?? []}
          saving={savingBundle}
          relinting={relinting}
          onClose={() => setBundleContent(null)}
          onSave={saveBundle}
          onSaveAndRelint={saveAndRelint}
        />
      )}
    </main>
  );
}
