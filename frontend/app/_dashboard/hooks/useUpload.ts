import { useState } from "react";
import { apiFetch, formatFetchError } from "../api";

type UseUploadOptions = {
  onSuccess?: () => void;
};

export function useUpload(backend: string, options: UseUploadOptions = {}) {
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadMessage, setUploadMessage] = useState("");

  const handleSelectFiles = (selected: FileList | null) => {
    if (!selected) return;
    setUploadFiles((prev) => [...prev, ...Array.from(selected)]);
    setUploadMessage("");
    setUploadError("");
  };

  const handleRemoveUploadFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, j) => j !== index));
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0) return;
    setUploading(true);
    setUploadError("");
    setUploadMessage("");
    const form = new FormData();
    uploadFiles.forEach((f) => form.append("files", f));
    try {
      const data = await apiFetch<{ total: number }>(`${backend}/source/upload`, {
        method: "POST",
        body: form,
      });
      setUploadMessage(`Đã lưu ${data.total} file vào 1.docs/source/api_contract/`);
      setUploadFiles([]);
      options.onSuccess?.();
    } catch (e: unknown) {
      setUploadError(formatFetchError(e));
    } finally {
      setUploading(false);
    }
  };

  return {
    uploadFiles,
    uploading,
    uploadError,
    uploadMessage,
    handleSelectFiles,
    handleRemoveUploadFile,
    handleUpload,
  };
}
