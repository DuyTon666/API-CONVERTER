import { useState } from "react";
import { ScanResult } from "@/types/dashboard";
import { formatFetchError } from "@/lib/api/client";
import { scanModules } from "@/lib/api/dashboard/modules";

export function useScan(backend: string) {
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanLoading, setScanLoading] = useState(true);
  const [scanError, setScanError] = useState("");

  const fetchScan = () => {
    setScanLoading(true);
    return scanModules(backend)
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
