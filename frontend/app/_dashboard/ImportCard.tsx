"use client";

import { useRef } from "react";
import { SUPPORTED_EXTENSIONS } from "./format";

type Props = {
  files: File[];
  uploading: boolean;
  error: string;
  message: string;
  onSelectFiles: (selected: FileList | null) => void;
  onRemoveFile: (index: number) => void;
  onUpload: () => void;
};

export default function ImportCard({
  files,
  uploading,
  error,
  message,
  onSelectFiles,
  onRemoveFile,
  onUpload,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-700 mb-3">Import file vào api_contract</h2>

      <div
        className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-indigo-300 hover:bg-indigo-50 transition"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); onSelectFiles(e.dataTransfer.files); }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={SUPPORTED_EXTENSIONS.join(",")}
          multiple
          className="hidden"
          onChange={(e) => onSelectFiles(e.target.files)}
        />
        <p className="text-gray-400">Kéo thả hoặc click để chọn file ({SUPPORTED_EXTENSIONS.join(", ")})</p>
        <p className="text-gray-300 text-sm mt-1">File sẽ được lưu vào 1.docs/source/api_contract/</p>
      </div>

      {files.length > 0 && (
        <ul className="mt-3 space-y-2">
          {files.map((f, i) => (
            <li key={i} className="flex justify-between items-center bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm">
              <span className="text-gray-700 truncate mr-4">{f.name}</span>
              <button
                onClick={() => onRemoveFile(i)}
                className="text-gray-300 hover:text-red-400 transition"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{error}</div>
      )}
      {message && (
        <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">{message}</div>
      )}

      <button
        onClick={onUpload}
        disabled={files.length === 0 || uploading}
        className="mt-3 px-5 py-2.5 bg-indigo-100 text-indigo-700 text-sm font-semibold rounded-lg hover:bg-indigo-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
      >
        {uploading ? "Đang tải lên..." : `Import (${files.length} file)`}
      </button>
    </section>
  );
}
