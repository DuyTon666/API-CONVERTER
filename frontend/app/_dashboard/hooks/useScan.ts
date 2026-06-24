import { useState } from "react";
import { ScanResult } from "../types";
import { apiFetch, formatFetchError } from "../api";

export function useScan(backend: string) {
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanLoading, setScanLoading] = useState(true);
  const [scanError, setScanError] = useState("");

  const fetchScan = () => {
    setScanLoading(true);
    return apiFetch<ScanResult>(`${backend}/modules/scan`)
      .then((data) => {
        setScan(data);
        setScanError("");
      })
      .catch((e) => setScanError(formatFetchError(e)))
      .finally(() => setScanLoading(false));
  };

  return {
    scan,
    scanLoading,
    scanError,
    fetchScan
  }
}