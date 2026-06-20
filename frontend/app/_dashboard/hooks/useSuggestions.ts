import { useState } from "react";
import { ApplyResult, SuggestionsResult } from "../types";

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

  const fetchSuggestions = () => {
    setSuggestionsLoading(true);
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
      await Promise.all([fetchSuggestions(), options.onApplySuccess?.()]);
    } catch (e: unknown) {
      setSuggestActionError(
        e instanceof Error ? e.message : "Lỗi kết nối backend",
      );
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
    fetchSuggestions,
    handleRunSuggest,
    handleApproveSelected,
    handleApprove,
    handleApply,
  };
}
