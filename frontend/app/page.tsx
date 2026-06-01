"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const handleFiles = (selected: FileList | null) => {
    if (!selected) return;
    const docx = Array.from(selected).filter((f) => f.name.endsWith(".docx"));
    setFiles((prev) => [...prev, ...docx]);
  };

  const handleRun = async () => {
    if (files.length === 0) return;
    setLoading(true);
    setError("");
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    try {
      const res = await fetch("http://localhost:8000/jobs", {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      router.push(`/jobs/${data.job_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Lỗi kết nối backend");
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center py-16 px-4">
      <div className="w-full max-w-2xl">
        <h1 className="text-3xl font-bold text-gray-800 mb-1">API Converter</h1>
        <p className="text-gray-400 mb-8">Upload tài liệu .docx để chuyển đổi sang OpenAPI</p>

        {/* Drop zone */}
        <div
          className="border-2 border-dashed border-gray-300 rounded-xl p-10 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".docx"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <p className="text-gray-400 text-lg">Kéo thả hoặc click để chọn file</p>
          <p className="text-gray-300 text-sm mt-1">Hỗ trợ nhiều file .docx cùng lúc</p>
        </div>

        {/* Danh sách file đã chọn */}
        {files.length > 0 && (
          <ul className="mt-4 space-y-2">
            {files.map((f, i) => (
              <li key={i} className="flex justify-between items-center bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm">
                <span className="text-gray-700">{f.name}</span>
                <button
                  onClick={() => setFiles(files.filter((_, j) => j !== i))}
                  className="text-gray-300 hover:text-red-400 transition"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
            {error}
          </div>
        )}

        <button
          onClick={handleRun}
          disabled={files.length === 0 || loading}
          className="mt-6 w-full py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {loading ? "Đang gửi..." : `Chạy pipeline (${files.length} file)`}
        </button>
      </div>
    </main>
  );
}
