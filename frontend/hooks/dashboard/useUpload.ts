import { useState } from "react";
import { isSupportedFile, SUPPORTED_EXTENSIONS } from "@/lib/dashboard-format";
import { toast } from "sonner";
import { formatFetchError } from "@/lib/api/client";
import { uploadSourceFiles } from "@/lib/api/dashboard/upload";

type UseUploadOptions = {
  onSuccess?: () => void;
};

export function useUpload(backend: string, options: UseUploadOptions = {}) {
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);

  const handleSelectFiles = (selected: FileList | null) => {
    if (!selected) return;

    const incoming = Array.from(selected);
    const supported = incoming.filter((f) => isSupportedFile(f.name));
    const rejected = incoming.filter((f) => !isSupportedFile(f.name));

    if (rejected.length > 0) {
      toast.error(`Bỏ qua ${rejected.length} file sai định dạng (chỉ nhân ${SUPPORTED_EXTENSIONS.join("/")}):
      ${rejected.map((f) => f.name).join(", ")}`);
    }
    if (supported.length > 0) {
      setUploadFiles((prev) => [...prev, ...supported]);
    }
  };

  const handleRemoveUploadFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, j) => j !== index));
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0) return;
    setUploading(true);
    try {
      const data = await uploadSourceFiles(backend, uploadFiles);
      toast.success(
        `Đã lưu ${data.total} file vào 1.docs/source/api_contract/`,
      );
      setUploadFiles([]);
      options.onSuccess?.();
    } catch (e: unknown) {
      toast.error(formatFetchError(e));
    } finally {
      setUploading(false);
    }
  };

  return {
    uploadFiles,
    uploading,
    handleSelectFiles,
    handleRemoveUploadFile,
    handleUpload,
  };
}
