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
import {
  buildDefaultAiFixResolutions,
  buildEmptyAiFixMessage,
  mergeAiFixPatches,
} from "@/lib/dashboard-ai-fix";
import { toast } from "sonner";

export function useDocsBuilder(backend: string) {
  const [docsBuilding, setDocsBuilding] = useState(false);
  const [docsResult, setDocsResult] = useState<DocsBuildResult | null>(null);
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
  // Lưu + relint ngay xuống backend sau khi ghép — bấm "Áp dụng" là lưu, không cần bấm
  // "Lưu" riêng. Relint là bắt buộc (không chỉ lưu): patch AI sửa thường lệch số dòng so
  // với đoạn gốc, nên docsResult.spectral/redocly (line/range) cũ sẽ trỏ sai vị trí trong
  // nội dung mới. Nếu không relint, lần "AI tự fix lỗi" kế tiếp sẽ cắt nhầm đoạn YAML theo
  // range cũ → AI sửa sai chỗ → sinh lỗi mới, lặp vài lần thì mọi patch đều hỏng YAML và bị
  // validate loại hết, trông như "gọi lại không sửa được gì".
  const applyAiFixResolutions = async (editedPatches: AiFixPatch[]) => {
    if (bundleContent === null) return;
    const merged = mergeAiFixPatches(
      bundleContent,
      editedPatches,
      aiFixResolutions,
    );
    setBundleContent(merged);
    closeAiFixPanel();

    setSavingBundle(true);
    try {
      await saveThenRelint(merged);
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
    setDocsBuilding(true);
    try {
      const data = await buildDocs(backend);
      setDocsResult(data);
    } catch (e: unknown) {
      toast.error(formatFetchError(e));
    } finally {
      setDocsBuilding(false);
    }
  };

  const handleRelint = async () => {
    setRelinting(true);
    try {
      const data = await relintDocs(backend);
      setDocsResult(data);
    } catch (e: unknown) {
      toast.error(formatFetchError(e));
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

  // Lưu content rồi relint ngay, cập nhật docsResult — dùng chung cho saveAndRelint và
  // applyAiFixResolutions (xem lý do bắt buộc relint sau khi áp AI-fix ở comment trên
  // applyAiFixResolutions). Trả false khi lưu hoặc relint lỗi (đã alert).
  const saveThenRelint = async (content: string): Promise<boolean> => {
    const saved = await putBundleContent(content);
    if (!saved) return false;
    setRelinting(true);
    try {
      const data = await relintDocs(backend);
      setDocsResult(data);
      return true;
    } catch (e) {
      alert("Lỗi kiểm tra lại: " + formatFetchError(e));
      return false;
    } finally {
      setRelinting(false);
    }
  };

  const saveAndRelint = async () => {
    if (bundleContent === null) return;
    setSavingBundle(true);
    try {
      const ok = await saveThenRelint(bundleContent);
      if (ok) setBundleContent(null);
    } finally {
      setSavingBundle(false);
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
      const emptyMessage = buildEmptyAiFixMessage(
        data.patches,
        data.unresolved,
      );
      if (emptyMessage) {
        toast.error(emptyMessage);
        return;
      }
      setAiFixPatches(data.patches);
      setAiFixUnresolved(data.unresolved);
      setAiFixResolutions(buildDefaultAiFixResolutions(data.patches));
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
