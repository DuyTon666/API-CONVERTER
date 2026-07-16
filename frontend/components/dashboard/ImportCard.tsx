"use client";

import { useRef } from "react";
import { SUPPORTED_EXTENSIONS, formatBytes } from "@/lib/dashboard-format";

type Props = {
  files: File[];
  uploading: boolean;
  onSelectFiles: (selected: FileList | null) => void;
  onRemoveFile: (index: number) => void;
  onUpload: () => void;
};

export default function ImportCard({
  files,
  uploading,
  onSelectFiles,
  onRemoveFile,
  onUpload,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
      <h2 className="font-semibold text-gray-900 mb-4">Import tài liệu</h2>

      <div
        className="border-2 border-dashed border-gray-300 rounded-xl py-8 px-4 text-center text-sm text-gray-400 hover:border-indigo-400 hover:text-indigo-500 transition cursor-pointer"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          onSelectFiles(e.dataTransfer.files);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={SUPPORTED_EXTENSIONS.join(",")}
          multiple
          className="hidden"
          onChange={(e) => onSelectFiles(e.target.files)}
        />
        Kéo thả file {SUPPORTED_EXTENSIONS.join(" / ")} vào đây
      </div>

      {files.length > 0 && (
        <ul className="mt-4 space-y-2 text-sm">
          {files.map((f, i) => (
            <li
              key={i}
              className="group flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2"
            >
              <span className="flex items-center gap-2 truncate mr-4 text-gray-700">
                <svg
                  className="w-4 h-4 shrink-0 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                  />
                </svg>
                <span className="truncate">{f.name}</span>
              </span>
              <span className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-gray-400">
                  {formatBytes(f.size)}
                </span>
                <button
                  onClick={() => onRemoveFile(i)}
                  className="text-gray-300 hover:text-red-400 transition"
                  title="Bỏ file này"
                >
                  ✕
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <button
        onClick={onUpload}
        disabled={files.length === 0 || uploading}
        className="mt-4 w-full bg-indigo-600 text-white text-sm font-medium rounded-lg py-2 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
      >
        {uploading ? "Đang tải lên..." : "Upload"}
      </button>
    </section>
  );
}
