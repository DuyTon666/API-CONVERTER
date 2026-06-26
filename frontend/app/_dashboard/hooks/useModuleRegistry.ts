import { useState } from "react";
import { ImportModuleProgress, ModuleListResult } from "../types";
import { apiFetch, formatFetchError } from "../api";

type UseModuleRegistryOptions = {
  onImportDone?: () => void;
};

export function useModuleRegistry(
  backend: string,
  options: UseModuleRegistryOptions = {},
) {

  const [moduleList, setModuleList] = useState<ModuleListResult | null>(null);
  const [modulesLoading, setModulesLoading] = useState(true);
  const [modulesError, setModulesError] = useState("");
  const [activatingModule, setActivatingModule] = useState<string | null>(null);
  const [activateError, setActivateError] = useState("");
  const [deactivatingModule, setDeactivatingModule] = useState<string | null>(null);
  const [deactivateError, setDeactivateError] = useState("");
  const [importRunning, setImportRunning] = useState(false);
  const [importTarget, setImportTarget] = useState<string | null>(null);
  const [importModules, setImportModules] = useState<ImportModuleProgress[]>(
    [],
  );
  const [importDone, setImportDone] = useState(false);
  const [importError, setImportError] = useState("");

  const fetchModules = () => {
    setModulesLoading(true);
    return apiFetch<ModuleListResult>(`${backend}/modules`)
      .then((data) => {
        setModuleList(data);
        setModulesError("");
      })
      .catch((e) => setModulesError(formatFetchError(e)))
      .finally(() => setModulesLoading(false));
  };
  const handleActivate = async (name: string) => {
    setActivatingModule(name);
    setActivateError("");
    try {
      const data = await apiFetch<ModuleListResult>(
        `${backend}/modules/${encodeURIComponent(name)}/activate`,
        { method: "POST" },
      );
      setModuleList(data);
    } catch (e: unknown) {
      setActivateError(formatFetchError(e));
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
      const data = await apiFetch<{ job_id: string }>(url, { method: "POST" });

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
          options.onImportDone?.();
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
      setImportError(formatFetchError(e));
      setImportRunning(false);
    }
  };
  const handleDeactivate = async (name: string) => {
    setDeactivatingModule(name);
    setDeactivateError("");
    try {
      const data = await apiFetch<ModuleListResult>(
        `${backend}/modules/${encodeURIComponent(name)}/deactivate`,
        { method: "POST" },
      );
      setModuleList(data);
    } catch (e: unknown) {
      setDeactivateError(formatFetchError(e));
    } finally {
      setDeactivatingModule(null);
    }
  };

  return {
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
  };
}