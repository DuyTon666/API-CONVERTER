import { useState } from "react";
import { DocsBuildResult, DocsStatus } from "../types";

export function useDocsBuilder(backend: string) {
  const [docsBuilding, setDocsBuilding] = useState(false);
  const [docsResult, setDocsResult] = useState<DocsBuildResult | null>(null);
  const [docsError, setDocsError] = useState("");
  const [docsStatus, setDocsStatus] = useState<DocsStatus | null>(null);

  const [bundleContent, setBundleContent] = useState<string | null>(null);
  const [savingBundle, setSavingBundle] = useState(false);
  const [relinting, setRelinting] = useState(false);

  const fetchDocsStatus = () => {
    return fetch(`${backend}/docs/status`)
      .then((res) => {
        if (!res.ok) throw new Error("Không thể tải trạng thái tài liệu");
        return res.json();
      })
      .then((data) => setDocsStatus(data))
      .catch(() => setDocsStatus(null));
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
      const res = await fetch(`${backend}/docs/bundle-content`, {
        method: "PUT",
        headers: { "Content-Type": "text/plain; charset=utf-8" },
        body: bundleContent,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: res.statusText }));
        alert("Lỗi lưu bundle: " + data.detail);
      }
    } finally {
      setSavingBundle(false);
    }
  };

  const saveAndRelint = async () => {
    if (bundleContent === null) return;
    setSavingBundle(true);
    try {
      const saveRes = await fetch(`${backend}/docs/bundle-content`, {
        method: "PUT",
        headers: { "Content-Type": "text/plain; charset=utf-8" },
        body: bundleContent,
      });
      if (!saveRes.ok) {
        const data = await saveRes.json().catch(() => ({ detail: saveRes.statusText }));
        alert("Lỗi lưu bundle: " + data.detail);
        return;
      }
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

  return {
    docsBuilding,
    docsResult,
    docsError,
    docsStatus,
    bundleContent,
    setBundleContent,
    savingBundle,
    relinting,
    fetchDocsStatus,
    handleBuildDocs,
    handleRelint,
    handleDownloadDocsHtml,
    openBundleEditor,
    saveBundle,
    saveAndRelint,
  };
}
