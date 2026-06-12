"use client";

import { useEffect, useState } from "react";
import ImportCard from "./_dashboard/ImportCard";
import ScanCard from "./_dashboard/ScanCard";
import SuggestCard from "./_dashboard/SuggestCard";
import ModuleRegistryCard from "./_dashboard/ModuleRegistryCard";
import SwaggerDocsCard from "./_dashboard/SwaggerDocsCard";
import BundleEditorModal from "./_dashboard/BundleEditorModal";
import StatTiles from "./_dashboard/StatTiles";
import WorkflowStepper, { toSteps } from "./_dashboard/WorkflowStepper";
import { isSupportedFile } from "./_dashboard/format";
import {
  ApplyResult,
  DocsBuildResult,
  DocsStatus,
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

  const [suggestions, setSuggestions] = useState<SuggestionsResult | null>(
    null,
  );
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const [suggestionsError, setSuggestionsError] = useState("");
  const [suggestRunning, setSuggestRunning] = useState(false);
  const [approving, setApproving] = useState<string | null>(null);
  const [approvingMulti, setApprovingMulti] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);
  const [suggestActionError, setSuggestActionError] = useState("");
  const [overrideInputs, setOverrideInputs] = useState<Record<string, string>>(
    {},
  );

  const [activatingModule, setActivatingModule] = useState<string | null>(null);
  const [activateError, setActivateError] = useState("");

  const [importRunning, setImportRunning] = useState(false);
  const [importTarget, setImportTarget] = useState<string | null>(null);
  const [importModules, setImportModules] = useState<ImportModuleProgress[]>(
    [],
  );
  const [importDone, setImportDone] = useState(false);
  const [importError, setImportError] = useState("");

  const [docsBuilding, setDocsBuilding] = useState(false);
  const [docsResult, setDocsResult] = useState<DocsBuildResult | null>(null);
  const [docsError, setDocsError] = useState("");
  const [docsStatus, setDocsStatus] = useState<DocsStatus | null>(null);

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
      .catch((e) =>
        setScanError(e instanceof Error ? e.message : "Lỗi kết nối backend"),
      )
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
      .catch((e) =>
        setModulesError(e instanceof Error ? e.message : "Lỗi kết nối backend"),
      )
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
      .catch((e) =>
        setSuggestionsError(
          e instanceof Error ? e.message : "Lỗi kết nối backend",
        ),
      )
      .finally(() => setSuggestionsLoading(false));
  };

  const fetchDocsStatus = () => {
    return fetch(`${backend}/docs/status`)
      .then((res) => {
        if (!res.ok) throw new Error("Không thể tải trạng thái tài liệu");
        return res.json();
      })
      .then((data) => setDocsStatus(data))
      .catch(() => setDocsStatus(null));
  };

  useEffect(() => {
    fetchScan();
    fetchModules();
    fetchSuggestions();
    fetchDocsStatus();
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
      setUploadMessage(
        `Đã lưu ${data.total} file vào 1.docs/source/api_contract/`,
      );
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
      setSuggestActionError(
        e instanceof Error ? e.message : "Lỗi kết nối backend",
      );
    } finally {
      setSuggestRunning(false);
    }
  };

  const handleApproveSelected = async (
    items: Array<{ file: string; override_module?: string }>,
  ) => {
    setApprovingMulti(true);
    setSuggestActionError("");
    try {
      let latestData = suggestions;
      for (const item of items) {
        const res = await fetch(`${backend}/modules/suggestions/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode: "file",
            file: item.file,
            override_module: item.override_module,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail ?? "Lỗi duyệt suggestion");
        latestData = data;
      }
      if (latestData) setSuggestions(latestData);
    } catch (e: unknown) {
      setSuggestActionError(
        e instanceof Error ? e.message : "Lỗi kết nối backend",
      );
    } finally {
      setApprovingMulti(false);
    }
  };

  const handleApprove = async (
    body: {
      mode: string;
      module?: string;
      file?: string;
      override_module?: string;
    },
    key: string,
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
      setSuggestActionError(
        e instanceof Error ? e.message : "Lỗi kết nối backend",
      );
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
      setSuggestActionError(
        e instanceof Error ? e.message : "Lỗi kết nối backend",
      );
    } finally {
      setApplying(false);
    }
  };

  const handleActivate = async (name: string) => {
    setActivatingModule(name);
    setActivateError("");
    try {
      const res = await fetch(
        `${backend}/modules/${encodeURIComponent(name)}/activate`,
        {
          method: "POST",
        },
      );
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

      const es = new EventSource(
        `${backend}/modules/import/${data.job_id}/stream`,
      );
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
          if (exists)
            return prev.map((m) => (m.name === payload.name ? payload : m));
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

  const handleRelint = async () => {
    setDocsError("");
    setRelinting(true);
    try {
      const res = await fetch(`${backend}/docs/relint`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Lỗi kiểm tra bundle");
      setDocsResult(data);
    } catch (e: unknown) {
      setDocsError(e instanceof Error ? e.message : "Lỗi kết nối backend");
    } finally {
      setRelinting(false);
    }
  };

  const handleDownloadDocsHtml = () => {
    window.open(`${backend}/docs/download-html`, "_blank");
  };

  const openBundleEditor = async () => {
    try {
      const res = await fetch(`${backend}/docs/bundle-content`, {
        cache: "no-store",
      });
      if (res.status === 404) {
        alert("Chưa có bundle, hãy build tài liệu trước");
        return;
      }
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
      if (!res.ok) {
        alert("Lỗi kiểm tra lại: " + data.detail);
        return;
      }
      setDocsResult(data);
      setBundleContent(null);
    } finally {
      setSavingBundle(false);
      setRelinting(false);
    }
  };

  const pendingSuggestions =
    suggestions?.items.filter((i) => i.approval_status === "pending").length ??
    0;
  const activeModules = moduleList?.summary.by_status["active"] ?? 0;
  const draftModules = moduleList?.summary.by_status["draft"] ?? 0;
  const unassignedFiles = scan?.unassigned.length ?? 0;

  const hasSourceFiles =
    scan !== null && (scan.modules.length > 0 || scan.unassigned.length > 0);

  const bundleReady =
    docsResult?.bundle_ready ?? docsStatus?.bundle_ready ?? false;
  const htmlReady = docsResult?.html_ready ?? docsStatus?.html_ready ?? false;

  const steps = toSteps([
    { id: "card-import", label: "Nguồn", done: hasSourceFiles },
    {
      id: "card-suggest",
      label: "Phân loại",
      done: hasSourceFiles && unassignedFiles === 0 && pendingSuggestions === 0,
    },
    {
      id: "card-modules",
      label: "Module",
      done:
        activeModules > 0 &&
        draftModules === 0 &&
        (moduleList?.modules.every(
          (m) => m.status !== "active" || m.last_import_at !== null,
        ) ??
          false),
    },
    {
      id: "card-docs",
      label: "Tài liệu",
      done: bundleReady && htmlReady,
    },
  ]);

  return (
    <>
      <nav className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-gray-100 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="font-semibold text-gray-900">
              API Converter
            </span>
          </div>
          <a
            href="/swagger"
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-2 px-4 py-1.5 text-sm font-medium bg-indigo-600 text-white rounded-full hover:bg-indigo-700 transition-all duration-200"
          >
            Developer Portal
            <svg
              className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform duration-200"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M14 5l7 7m0 0l-7 7m7-7H3"
              />
            </svg>
          </a>
        </div>
      </nav>
      <div className="sticky top-14 z-40 bg-gray-50/90 backdrop-blur border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 lg:px-8 py-3">
          <WorkflowStepper steps={steps} />
        </div>
      </div>
      <main className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 lg:px-8 py-6 space-y-6">

          <StatTiles
            stats={[
              {
                label: "Module active",
                value: activeModules,
                tone: "success",
                loading: modulesLoading,
              },
              {
                label: "Module draft",
                value: draftModules,
                tone: draftModules > 0 ? "warning" : "default",
                loading: modulesLoading,
              },
              {
                label: "File chưa gán module",
                value: unassignedFiles,
                tone: unassignedFiles > 0 ? "warning" : "default",
                loading: scanLoading,
              },
              {
                label: "Suggestion chờ duyệt",
                value: pendingSuggestions,
                tone: pendingSuggestions > 0 ? "danger" : "default",
                loading: suggestionsLoading,
              },
            ]}
          />

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Cột phụ trợ — bên phải trên desktop; mobile xen kẽ theo order */}
            <div className="contents lg:block lg:order-2 lg:col-span-5 lg:space-y-6">
              <div id="card-import" className="order-1 scroll-mt-32">
                <ImportCard
                  files={uploadFiles}
                  uploading={uploading}
                  error={uploadError}
                  message={uploadMessage}
                  onSelectFiles={handleSelectFiles}
                  onRemoveFile={handleRemoveUploadFile}
                  onUpload={handleUpload}
                />
              </div>

              <div className="order-2">
                <ScanCard scan={scan} loading={scanLoading} error={scanError} />
              </div>

              <div id="card-docs" className="order-5 scroll-mt-32">
                <SwaggerDocsCard
                  docsBuilding={docsBuilding}
                  docsResult={docsResult}
                  docsError={docsError}
                  bundleReady={bundleReady}
                  htmlReady={htmlReady}
                  relinting={relinting}
                  onBuildDocs={handleBuildDocs}
                  onRelint={handleRelint}
                  onOpenBundleEditor={openBundleEditor}
                  onDownloadHtml={handleDownloadDocsHtml}
                />
              </div>
            </div>

            {/* Cột thao tác chính — bên trái trên desktop */}
            <div className="contents lg:block lg:order-1 lg:col-span-7 lg:space-y-6">
              <div id="card-suggest" className="order-3 scroll-mt-32">
            <SuggestCard
              suggestions={suggestions}
              loading={suggestionsLoading}
              error={suggestionsError}
              actionError={suggestActionError}
              suggestRunning={suggestRunning}
              approving={approving}
              approvingMulti={approvingMulti}
              applying={applying}
              applyResult={applyResult}
              overrideInputs={overrideInputs}
              onOverrideChange={(file, value) =>
                setOverrideInputs((prev) => ({ ...prev, [file]: value }))
              }
              onRunSuggest={handleRunSuggest}
              onApprove={handleApprove}
              onApproveSelected={handleApproveSelected}
              onApply={handleApply}
            />
              </div>

              <div id="card-modules" className="order-4 scroll-mt-32">
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
              </div>
            </div>
          </div>
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
    </>
  );
}
