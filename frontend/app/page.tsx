"use client";

import { useEffect } from "react";
import ImportCard from "./_dashboard/ImportCard";
import ScanCard from "./_dashboard/ScanCard";
import SuggestCard from "./_dashboard/SuggestCard";
import ModuleRegistryCard from "./_dashboard/ModuleRegistryCard";
import SwaggerDocsCard from "./_dashboard/SwaggerDocsCard";
import BundleEditorModal from "./_dashboard/BundleEditorModal";
import AiFixPanel from "./_dashboard/AiFixPanel";
import StatTiles from "./_dashboard/StatTiles";
import WorkflowStepper, { toSteps } from "./_dashboard/WorkflowStepper";
import { useScan } from "./_dashboard/hooks/useScan";
import { useModuleRegistry } from "./_dashboard/hooks/useModuleRegistry";
import { useUpload } from "./_dashboard/hooks/useUpload";
import { useDocsBuilder } from "./_dashboard/hooks/useDocsBuilder";
import { useSuggestions } from "./_dashboard/hooks/useSuggestions";

export default function Home() {
  const backend = process.env.NEXT_PUBLIC_API_URL!;

  const { scan, scanLoading, scanError, fetchScan } = useScan(backend);

  const {
    moduleList,
    modulesLoading,
    modulesError,
    activatingModule,
    activateError,
    handleActivate,
    deactivatingModule,
    deactivateError,
    handleDeactivate,
    importRunning,
    importTarget,
    importModules,
    importDone,
    importError,
    handleImport,
    fetchModules,
  } = useModuleRegistry(backend);

  const {
    uploadFiles,
    uploading,
    uploadError,
    uploadMessage,
    handleSelectFiles,
    handleRemoveUploadFile,
    handleUpload,
  } = useUpload(backend, { onSuccess: fetchScan });

  const {
    docsBuilding,
    docsResult,
    docsError,
    docsStatus,
    bundleContent,
    setBundleContent,
    savingBundle,
    relinting,
    aiFixingBundle,
    aiFixPatches,
    aiFixUnresolved,
    aiFixResolutions,
    showAiFixPanel,
    applyAiFixResolutions,
    setAiFixResolution,
    closeAiFixPanel,
    fetchDocsStatus,
    handleBuildDocs,
    handleRelint,
    handleDownloadDocsHtml,
    openBundleEditor,
    saveBundle,
    saveAndRelint,
    handleAiFixBundle,
  } = useDocsBuilder(backend);

  const {
    suggestions,
    suggestionsLoading,
    suggestionsError,
    suggestRunning,
    approving,
    approvingMulti,
    applying,
    applyResult,
    suggestActionError,
    overrideInputs,
    setOverrideInputs,
    approveSkipped,
    fetchSuggestions,
    handleRunSuggest,
    handleApproveSelected,
    handleApprove,
    handleApply,
  } = useSuggestions(backend, {
    onApplySuccess: () => Promise.all([fetchScan(), fetchModules()]),
  });

  useEffect(() => {
    fetchScan();
    fetchModules();
    fetchSuggestions();
    fetchDocsStatus();
  }, []);

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
            <span className="font-semibold text-gray-900">API Converter</span>
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
              <div className="order-1 scroll-mt-32">
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
                  approveSkipped={approveSkipped}
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
                  deactivatingModule={deactivatingModule}
                  deactivateError={deactivateError}
                  onDeactivate={handleDeactivate}
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
            aiFixing={aiFixingBundle}
            onClose={() => setBundleContent(null)}
            onSave={saveBundle}
            onSaveAndRelint={saveAndRelint}
            onAiFix={handleAiFixBundle}
          />
        )}

        {showAiFixPanel && (
          <AiFixPanel
            patches={aiFixPatches}
            unresolved={aiFixUnresolved}
            resolutions={aiFixResolutions}
            onResolutionChange={setAiFixResolution}
            onApply={applyAiFixResolutions}
            onCancel={closeAiFixPanel}
          />
        )}
      </main>
    </>
  );
}
