import { useState } from "react";
import {
  AiFixPatch,
  AiFixResolution,
  AiFixResult,
  AiFixUnresolved,
  DocsBuildResult,
  DocsStatus,
} from "../types";
import { apiFetch, formatFetchError, readErrorDetail } from "../api";

export function useDocsBuilder(backend: string) {
  const [docsBuilding, setDocsBuilding] = useState(false);
  const [docsResult, setDocsResult] = useState<DocsBuildResult | null>(null);
  const [docsError, setDocsError] = useState("");
  const [docsStatus, setDocsStatus] = useState<DocsStatus | null>(null);

  const [bundleContent, setBundleContent] = useState<string | null>(null);
  const [savingBundle, setSavingBundle] = useState(false);
  const [relinting, setRelinting] = useState(false);
  const [aiFixingBundle, setAiFixingBundle] = useState(false);

  const [aiFixPatches, setAiFixPatches] = useState<AiFixPatch[]>([]);
  const [aiFixUnresolved, setAiFixUnresolved] = useState<AiFixUnresolved[]>([]);
  const [aiFixResolutions, setAiFixResolutions] = useState<
    Record<string, AiFixResolution>
  >({});
  const [showAiFixPanel, setShowAiFixPanel] = useState(false);

  // Ghép từng patch vào bundleContent theo lựa chọn của người dùng (giữ bản gốc/
  // bản AI sửa/cả hai) — xử lý từ dòng cuối lên đầu để patch chưa xử lý không bị lệch số dòng.
  // Nhận "editedPatches" từ AiFixPanel (đã đọc đúng nội dung người dùng vừa sửa tay
  // trực tiếp từ editor) thay vì dùng aiFixPatches gốc trong state.
  const applyAiFixResolutions = (editedPatches: AiFixPatch[]) => {
    if (bundleContent === null) return;
    const lines = bundleContent.split("\n");
    const sorted = [...editedPatches].sort((a, b) => b.start_line - a.start_line);

    for (const patch of sorted) {
      const resolution = aiFixResolutions[patch.id] ?? "fixed";
      const replacement =
        resolution === "original"
          ? patch.original_text
          : resolution === "both"
            ? `${patch.original_text}\n${patch.fixed_text}`
            : patch.fixed_text;
      lines.splice(
        patch.start_line,
        patch.end_line - patch.start_line + 1,
        ...replacement.split("\n"),
      );
    }

    setBundleContent(lines.join("\n"));
    closeAiFixPanel();
  };

  // Đóng panel AI fix mà không áp dụng gì, dọn sạch state để lần mở sau không dính dữ liệu cũ.
  const closeAiFixPanel = () => {
    setShowAiFixPanel(false);
    setAiFixPatches([]);
    setAiFixUnresolved([]);
    setAiFixResolutions({});
  };

  // Đổi lựa chọn (giữ gốc/giữ bản sửa/giữ cả hai) cho 1 patch cụ thể.
  const setAiFixResolution = (id: string, resolution: AiFixResolution) => {
    setAiFixResolutions((prev) => ({ ...prev, [id]: resolution }));
  };

  const fetchDocsStatus = () => {
    return apiFetch<DocsStatus>(`${backend}/docs/status`)
      .then((data) => setDocsStatus(data))
      .catch(() => setDocsStatus(null));
  };

  const handleBuildDocs = async () => {
    setDocsError("");
    setDocsBuilding(true);
    try {
      const data = await apiFetch<DocsBuildResult>(`${backend}/docs/build`, {
        method: "POST",
      });
      setDocsResult(data);
    } catch (e: unknown) {
      setDocsError(formatFetchError(e));
    } finally {
      setDocsBuilding(false);
    }
  };

  const handleRelint = async () => {
    setDocsError("");
    setRelinting(true);
    try {
      const data = await apiFetch<DocsBuildResult>(`${backend}/docs/relint`, {
        method: "POST",
      });
      setDocsResult(data);
    } catch (e: unknown) {
      setDocsError(formatFetchError(e));
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
        alert("Lỗi đọc bundle: " + (await readErrorDetail(res)));
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
        alert("Lỗi lưu bundle: " + (await readErrorDetail(res)));
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
        alert("Lỗi lưu bundle: " + (await readErrorDetail(saveRes)));
        return;
      }
      setRelinting(true);
      const res = await fetch(`${backend}/docs/relint`, { method: "POST" });
      if (!res.ok) {
        alert("Lỗi kiểm tra lại: " + (await readErrorDetail(res)));
        return;
      }
      setDocsResult(await res.json());
      setBundleContent(null);
    } finally {
      setSavingBundle(false);
      setRelinting(false);
    }
  };

  const handleAiFixBundle = async () => {
    if (bundleContent === null) return;
    setAiFixingBundle(true);
    try {
      const res = await fetch(`${backend}/docs/bundle/ai-fix`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: bundleContent,
          spectral: docsResult?.spectral ?? [],
          redocly: docsResult?.redocly ?? [],
        }),
      });
      if (!res.ok) {
        alert("Lỗi AI fix: " + (await readErrorDetail(res)));
        return;
      }
      const data: AiFixResult = await res.json();
      if (data.patches.length === 0) {
        alert(
          data.unresolved.length > 0
            ? "AI không xác định được vị trí lỗi nào để sửa — cần sửa tay."
            : "Không có lỗi nào để sửa",
        );
        return;
      }
      setAiFixPatches(data.patches);
      setAiFixUnresolved(data.unresolved);
      setAiFixResolutions(
        Object.fromEntries(
          data.patches.map((p) => [p.id, "fixed" as AiFixResolution]),
        ),
      );
      setShowAiFixPanel(true);
    } finally {
      setAiFixingBundle(false);
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
  };
}
