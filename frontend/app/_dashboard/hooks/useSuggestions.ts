import { useState } from "react";
import { ApplyResult, SkippedApproval, SuggestionsResult } from "../types";
import { apiFetch, formatFetchError } from "../api";

type UseSuggestionsOptions = {
  onApplySuccess?: () => void;
};

export function useSuggestions(backend: string, options: UseSuggestionsOptions = {}) {
  const [suggestions, setSuggestions] = useState<SuggestionsResult | null>(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const [suggestionsError, setSuggestionsError] = useState("");
  const [suggestRunning, setSuggestRunning] = useState(false);
  const [approving, setApproving] = useState<string | null>(null);
  const [approvingMulti, setApprovingMulti] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);
  const [suggestActionError, setSuggestActionError] = useState("");
  const [overrideInputs, setOverrideInputs] = useState<Record<string, string>>({});
  const [approveSkipped, setApproveSkipped] = useState<SkippedApproval[]>([]);

  const fetchSuggestions = () => {
    setSuggestionsLoading(true);
    return apiFetch<SuggestionsResult>(`${backend}/modules/suggestions`)
      .then((data) => {
        setSuggestions(data);
        setSuggestionsError("");
      })
      .catch((e) => setSuggestionsError(formatFetchError(e)))
      .finally(() => setSuggestionsLoading(false));
  };

  const handleRunSuggest = async () => {
    setSuggestRunning(true);
    setSuggestActionError("");
    try {
      const data = await apiFetch<SuggestionsResult>(
        `${backend}/modules/suggest`,
        { method: "POST" },
      );
      setSuggestions(data);
    } catch (e: unknown) {
      setSuggestActionError(formatFetchError(e));
    } finally {
      setSuggestRunning(false);
    }
  };

  const handleApproveSelected = async (
    items: Array<{ file: string; override_module?: string }>,
  ) => {
    setApprovingMulti(true);
    setSuggestActionError("");
    setApproveSkipped([]);
    try {
      let latestData = suggestions;
      // Gọi riêng từng file (mode "file") nên cộng dồn "skipped" qua từng lần gọi —
      // mỗi response chỉ biết file của chính lần gọi đó có bị bỏ qua hay không.
      const skipped: SkippedApproval[] = [];
      for (const item of items) {
        latestData = await apiFetch<SuggestionsResult>(
          `${backend}/modules/suggestions/approve`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              mode: "file",
              file: item.file,
              override_module: item.override_module,
            }),
          },
        );
        if (latestData.skipped) skipped.push(...latestData.skipped);
      }
      if (latestData) setSuggestions(latestData);
      setApproveSkipped(skipped);
    } catch (e: unknown) {
      setSuggestActionError(formatFetchError(e));
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
      const data = await apiFetch<SuggestionsResult>(
        `${backend}/modules/suggestions/approve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      setSuggestions(data);
    } catch (e: unknown) {
      setSuggestActionError(formatFetchError(e));
    } finally {
      setApproving(null);
    }
  };

  const handleApply = async () => {
    setApplying(true);
    setSuggestActionError("");
    try {
      const data = await apiFetch<ApplyResult>(`${backend}/modules/apply`, {
        method: "POST",
      });
      setApplyResult(data);
      await Promise.all([fetchSuggestions(), options.onApplySuccess?.()]);
    } catch (e: unknown) {
      setSuggestActionError(formatFetchError(e));
    } finally {
      setApplying(false);
    }
  };

  return {
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
  };
}
