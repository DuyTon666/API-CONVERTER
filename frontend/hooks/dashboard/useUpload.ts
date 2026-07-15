import { useState } from "react";
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
    setUploadFiles((prev) => [...prev, ...Array.from(selected)]);
  };

  const handleRemoveUploadFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, j) => j !== index));
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0) return;
    setUploading(true);
    try {
      const data = await uploadSourceFiles(backend, uploadFiles);
      toast.success(`Đã lưu ${data.total} file vào 1.docs/source/api_contract/`);
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
