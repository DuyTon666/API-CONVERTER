import { useState } from "react";
import {ScanResult} from "../types";

export function useScan(backend: string) {
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanLoading, setScanLoading] = useState(true);
  const [scanError, setScanError] = useState("");


  const fetchScan = () => {
    setScanLoading(true);
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

  return {
    scan,
    scanLoading,
    scanError,
    fetchScan
  }
}