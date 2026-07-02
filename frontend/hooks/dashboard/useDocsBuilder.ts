import { useState } from "react";
import {
  AiFixPatch,
  AiFixResolution,
  AiFixUnresolved,
  DocsBuildResult,
  DocsStatus,
} from "@/types/dashboard";
import { formatFetchError } from "@/lib/api/client";
import {
  BundleNotFoundError,
  aiFixBundle,
  buildDocs,
  fetchBundleContent,
  fetchDocsStatus as fetchDocsStatusApi,
  relintDocs,
  saveBundleContent,
} from "@/lib/api/dashboard/docs";
import { deployDocs } from "@/lib/api/dashboard/deploy";
import { toast } from "sonner";

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

  const [deploying, setDeploying] = useState(false);

  // Ghép từng patch vào bundleContent theo lựa chọn của người dùng (giữ bản gốc/
  // bản AI sửa/cả hai) — xử lý từ dòng cuối lên đầu để patch chưa xử lý không bị lệch số dòng.
  // Nhận "editedPatches" từ AiFixPanel (đã đọc đúng nội dung người dùng vừa sửa tay
  // trực tiếp từ editor) thay vì dùng aiFixPatches gốc trong state.
  // Lưu luôn xuống backend (PUT /docs/bundle-content) ngay sau khi ghép — bấm "Áp dụng"
  // là lưu, không cần bấm "Lưu" riêng (route đó giờ đã đồng bộ cả tầng 2 + tầng 3).
  const applyAiFixResolutions = async (editedPatches: AiFixPatch[]) => {
    if (bundleContent === null) return;
    const lines = bundleContent.split("\n");
    const sorted = [...editedPatches].sort(
      (a, b) => b.start_line - a.start_line,
    );

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

    const merged = lines.join("\n");
    setBundleContent(merged);
    closeAiFixPanel();

    setSavingBundle(true);
    try {
      await putBundleContent(merged);
    } finally {
      setSavingBundle(false);
    }
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
    return fetchDocsStatusApi(backend)
      .then((data) => setDocsStatus(data))
      .catch(() => setDocsStatus(null));
  };

  const handleBuildDocs = async () => {
    setDocsError("");
    setDocsBuilding(true);
    try {
      const data = await buildDocs(backend);
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
      const data = await relintDocs(backend);
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
      const text = await fetchBundleContent(backend);
      setBundleContent(text);
    } catch (e) {
      if (e instanceof BundleNotFoundError) {
        alert("Chưa có bundle, hãy build tài liệu trước");
        return;
      }
      alert("Lỗi đọc bundle: " + formatFetchError(e));
    }
  };

  // Dùng chung cho saveBundle/saveAndRelint/applyAiFixResolutions, tránh 3 nơi tự
  // viết lại cùng 1 đoạn gọi API rồi lệch dần. Trả false khi lưu lỗi (đã alert),
  // để caller tự quyết định có nên tiếp tục (vd saveAndRelint không relint nếu lưu lỗi).
  const putBundleContent = async (content: string): Promise<boolean> => {
    try {
      await saveBundleContent(backend, content);
      return true;
    } catch (e) {
      alert("Lỗi lưu bundle: " + formatFetchError(e));
      return false;
    }
  };

  const saveBundle = async () => {
    if (bundleContent === null) return;
    setSavingBundle(true);
    try {
      await putBundleContent(bundleContent);
    } finally {
      setSavingBundle(false);
    }
  };

  const saveAndRelint = async () => {
    if (bundleContent === null) return;
    setSavingBundle(true);
    try {
      const saved = await putBundleContent(bundleContent);
      if (!saved) return;
      setRelinting(true);
      try {
        const data = await relintDocs(backend);
        setDocsResult(data);
        setBundleContent(null);
      } catch (e) {
        alert("Lỗi kiểm tra lại: " + formatFetchError(e));
      }
    } finally {
      setSavingBundle(false);
      setRelinting(false);
    }
  };

  const handleAiFixBundle = async () => {
    if (bundleContent === null) return;
    setAiFixingBundle(true);
    try {
      const data = await aiFixBundle(
        backend,
        bundleContent,
        docsResult?.spectral ?? [],
        docsResult?.redocly ?? [],
      );
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
    } catch (e) {
      alert("Lỗi AI fix: " + formatFetchError(e));
    } finally {
      setAiFixingBundle(false);
    }
  };

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      const data = await deployDocs("develop");
      if (data.branch) {
        toast.success(data.message ?? "Đã kích hoạt deploy");
      }
    } catch (e: unknown) {
      toast.error(formatFetchError(e));
    } finally {
      setDeploying(false);
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
    deploying,
    handleDeploy,
  };
}
