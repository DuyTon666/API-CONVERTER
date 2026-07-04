import { useState } from "react";
import { ManualEditConflict } from "@/types/dashboard";
import { formatFetchError } from "@/lib/api/client";
import {
  fetchManualEditConflicts,
  resolveManualEditConflict,
} from "@/lib/api/dashboard/modules";

// Key dùng để biết đúng conflict nào đang được resolve, vì có thể hiện nhiều
// conflict cùng lúc (giống "approving" trong useSuggestions.ts).
function conflictKey(c: ManualEditConflict): string {
  return `${c.operationId}::${c.field}`;
}

export function useManualEditConflicts(backend: string) {
  const [conflicts, setConflicts] = useState<ManualEditConflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [resolving, setResolving] = useState<string | null>(null);
  const [resolveError, setResolveError] = useState("");

  const fetchConflicts = () => {
    setLoading(true);
    return fetchManualEditConflicts(backend)
      .then((data) => {
        setConflicts(data);
        setError("");
      })
      .catch((e) => setError(formatFetchError(e)))
      .finally(() => setLoading(false));
  };

  const handleResolve = async (
    conflict: ManualEditConflict,
    choice: "keep_old" | "accept_new",
  ) => {
    setResolving(conflictKey(conflict));
    setResolveError("");
    try {
      await resolveManualEditConflict(backend, conflict.operationId, conflict.field, choice);
      setConflicts((prev) => prev.filter((c) => conflictKey(c) !== conflictKey(conflict)));
    } catch (e: unknown) {
      setResolveError(formatFetchError(e));
    } finally {
      setResolving(null);
    }
  };

  return {
    conflicts,
    loading,
    error,
    resolving,
    resolveError,
    conflictKey,
    fetchConflicts,
    handleResolve,
  };
}
