"use client";

import { useEffect } from "react";
import ImportCard from "@/components/dashboard/ImportCard";
import ScanCard from "@/components/dashboard/ScanCard";
import SuggestCard from "@/components/dashboard/SuggestCard";
import ManualEditConflictsCard from "@/components/dashboard/ManualEditConflictsCard";
import ErrorCodesReviewCard from "@/components/dashboard/ErrorCodesReviewCard";
import ModuleRegistryCard from "@/components/dashboard/ModuleRegistryCard";
import SwaggerDocsCard from "@/components/dashboard/SwaggerDocsCard";
import BundleEditorModal from "@/components/dashboard/BundleEditorModal";
import AiFixPanel from "@/components/dashboard/AiFixPanel";
import StatTiles from "@/components/dashboard/StatTiles";
import WorkflowStepper, {
  toSteps,
} from "@/components/dashboard/WorkflowStepper";
import StepSection, { StepStatus } from "@/components/dashboard/StepSection";
import { useActiveStep } from "@/hooks/dashboard/useActiveStep";
import { useScan } from "@/hooks/dashboard/useScan";
import { useModuleRegistry } from "@/hooks/dashboard/useModuleRegistry";
import { useUpload } from "@/hooks/dashboard/useUpload";
import { useDocsBuilder } from "@/hooks/dashboard/useDocsBuilder";
import { useSuggestions } from "@/hooks/dashboard/useSuggestions";
import { useManualEditConflicts } from "@/hooks/dashboard/useManualEditConflicts";
import { useErrorCodes } from "@/hooks/dashboard/useErrorCodes";

export default function Home() {
  const backend = process.env.NEXT_PUBLIC_API_URL!;

  const { scan, scanLoading, scanError, fetchScan } = useScan(backend);

  const {
    conflicts,
    loading: conflictsLoading,
    error: conflictsError,
    resolving: conflictResolving,
    conflictKey,
    fetchConflicts,
    handleResolve: handleResolveConflict,
  } = useManualEditConflicts(backend);

  const {
    moduleList,
    modulesLoading,
    modulesError,
    activatingModule,
    handleActivate,
    deactivatingModule,
    handleDeactivate,
    importRunning,
    importTarget,
    importModules,
    importDone,
    handleImport,
    fetchModules,
  } = useModuleRegistry(backend, { onImportDone: fetchConflicts });

  const moduleNames = moduleList?.modules.map((m) => m.name) ?? [];

  const {
    entriesByModule: errorEntriesByModule,
    loading: errorEntriesLoading,
    resolving: errorResolving,
    applying: errorApplying,
    fetchAllErrorEntries,
    handleResolve: handleResolveErrorEntry,
    handleApply: handleApplyErrorEntries,
  } = useErrorCodes(backend, moduleNames);

  const {
    uploadFiles,
    uploading,
    handleSelectFiles,
    handleRemoveUploadFile,
    handleUpload,
  } = useUpload(backend, { onSuccess: fetchScan });

  const {
    docsBuilding,
    docsResult,
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
    deploying,
    handleDeploy,
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
    fetchConflicts();
  }, []);

  // moduleList chỉ có sau khi fetchModules() ở effect trên tải xong (bất đồng
  // bộ) — không thể gọi fetchAllErrorEntries ngay trong effect đó vì lúc đó
  // moduleNames vẫn rỗng. Effect riêng này chạy lại mỗi khi moduleList đổi.
  useEffect(() => {
    if (moduleList) fetchAllErrorEntries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moduleList]);

  const pendingSuggestions =
    suggestions?.items.filter((i) => i.approval_status === "pending").length ??
    0;
  const activeModules = moduleList?.summary.by_status["active"] ?? 0;
  const draftModules = moduleList?.summary.by_status["draft"] ?? 0;
  const unassignedFiles = scan?.unassigned.length ?? 0;

  const bundleReady =
    docsResult?.bundle_ready ?? docsStatus?.bundle_ready ?? false;
  const htmlReady = docsResult?.html_ready ?? docsStatus?.html_ready ?? false;

  const steps = toSteps([
    { id: "card-import", label: "Nguồn" },
    {
      id: "card-suggest",
      label: "Phân loại",
    },
    {
      id: "card-modules",
      label: "Module",
    },
    {
      id: "card-docs",
      label: "Tài liệu",
    },
  ]);
  const activeIndex = useActiveStep(steps.map((s) => s.id));
  const stepStatus = (i: number): StepStatus =>
    i < activeIndex ? "done" : i === activeIndex ? "current" : "upcoming";

  return (
    <>
      <nav className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-gray-100 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="font-semibold text-gray-900">API Converter</span>
          </div>
          <a
            href="/portal"
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
          <WorkflowStepper steps={steps} activeIndex={activeIndex} />
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

          <ManualEditConflictsCard
            conflicts={conflicts}
            loading={conflictsLoading}
            error={conflictsError}
            resolving={conflictResolving}
            conflictKey={conflictKey}
            onResolve={handleResolveConflict}
          />

          <ErrorCodesReviewCard
            modules={moduleNames}
            entriesByModule={errorEntriesByModule}
            loading={errorEntriesLoading}
            resolving={errorResolving}
            applying={errorApplying}
            onResolve={handleResolveErrorEntry}
            onApply={handleApplyErrorEntries}
          />

          <div>
            <StepSection
              id="card-import"
              number={1}
              label="Nguồn"
              status={stepStatus(0)}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <ImportCard
                  files={uploadFiles}
                  uploading={uploading}
                  onSelectFiles={handleSelectFiles}
                  onRemoveFile={handleRemoveUploadFile}
                  onUpload={handleUpload}
                />
                <ScanCard scan={scan} loading={scanLoading} error={scanError} />
              </div>
            </StepSection>

            <StepSection
              id="card-suggest"
              number={2}
              label="Phân loại"
              status={stepStatus(1)}
            >
              <SuggestCard
                suggestions={suggestions}
                loading={suggestionsLoading}
                error={suggestionsError}
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
            </StepSection>

            <StepSection
              id="card-modules"
              number={3}
              label="Module"
              status={stepStatus(2)}
            >
              <ModuleRegistryCard
                moduleList={moduleList}
                loading={modulesLoading}
                error={modulesError}
                activatingModule={activatingModule}
                onActivate={handleActivate}
                deactivatingModule={deactivatingModule}
                onDeactivate={handleDeactivate}
                importRunning={importRunning}
                importTarget={importTarget}
                importModules={importModules}
                importDone={importDone}
                onImport={handleImport}
              />
            </StepSection>

            <StepSection
              id="card-docs"
              number={4}
              label="Tài liệu"
              status={stepStatus(3)}
              isLast
            >
              <SwaggerDocsCard
                docsBuilding={docsBuilding}
                docsResult={docsResult}
                bundleReady={bundleReady}
                htmlReady={htmlReady}
                relinting={relinting}
                deploying={deploying}
                onDeploy={handleDeploy}
                onBuildDocs={handleBuildDocs}
                onRelint={handleRelint}
                onOpenBundleEditor={openBundleEditor}
                onDownloadHtml={handleDownloadDocsHtml}
              />
            </StepSection>
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
