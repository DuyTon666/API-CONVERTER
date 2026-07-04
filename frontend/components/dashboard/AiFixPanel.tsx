"use client";

import dynamic from "next/dynamic";
import { AiFixPatch, AiFixResolution, AiFixUnresolved } from "@/types/dashboard";
import { useRef } from "react";

// DiffEditor cần chạy ở browser (Monaco không hỗ trợ SSR) — import dynamic giống
// cách BundleEditorModal import BundleEditor.
const DiffEditor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.DiffEditor),
  { ssr: false },
);

// 1 trong 2 editor con (original/modified) bên trong DiffEditor — chỉ cần đọc
// nội dung hiện tại lúc bấm Áp dụng, không lắng nghe từng lần gõ (xem lý do ở
// dưới, tại detachAllModels/handleApply).
type StandaloneEditor = {
  getValue: () => string;
};

// Lưu instance editor của từng patch để có thể tự gỡ model trước khi unmount —
// tránh Monaco log lỗi "TextModel got disposed before DiffEditorWidget model got reset"
// khi nhiều DiffEditor bị huỷ cùng lúc lúc đóng panel. Cũng dùng để lấy editor con
// (getOriginalEditor/getModifiedEditor) cho phép sửa tay cả 2 bên.
type DiffEditorInstance = {
  setModel: (model: null) => void;
  getOriginalEditor: () => StandaloneEditor;
  getModifiedEditor: () => StandaloneEditor;
};

type Props = {
  patches: AiFixPatch[];
  unresolved: AiFixUnresolved[];
  resolutions: Record<string, AiFixResolution>;
  onResolutionChange: (id: string, choice: AiFixResolution) => void;
  onApply: (editedPatches: AiFixPatch[]) => void;
  onCancel: () => void;
};

const RESOLUTION_OPTIONS: { value: AiFixResolution; label: string }[] = [
  { value: "original", label: "Giữ bản gốc" },
  { value: "fixed", label: "Giữ bản AI đã sửa" },
  { value: "both", label: "Giữ cả hai" },
];

// Hiển thị danh sách lỗi gắn với 1 patch dưới dạng badge nhỏ.
function IssueBadges({ issues }: { issues: AiFixPatch["issues"] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {issues.map((issue, i) => (
        <span
          key={i}
          className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200"
          title={issue.message}
        >
          [{issue.source}] {issue.code}
        </span>
      ))}
    </div>
  );
}

export default function AiFixPanel({
  patches,
  unresolved,
  resolutions,
  onResolutionChange,
  onApply,
  onCancel,
}: Props) {
  const editorsRef = useRef(new Map<string, DiffEditorInstance>());

  const detachAllModels = () => {
    editorsRef.current.forEach((editor) => editor.setModel(null));
    editorsRef.current.clear();
  };

  // Đọc nội dung mới nhất trực tiếp từ editor (không qua state React) rồi mới
  // gỡ model — props "original"/"modified" của DiffEditor giữ cố định từ lúc AI
  // trả kết quả, không cập nhật theo từng phím gõ, vì DiffEditor là controlled
  // component: đổi prop mỗi keystroke khiến Monaco tạo lại model và nhảy con trỏ
  // về đầu dòng (đã thấy lỗi này khi test tay — gõ bị đảo/lẫn ký tự).
  const handleApply = () => {
    const edited = patches.map((p) => {
      const editor = editorsRef.current.get(p.id);
      if (!editor) return p;
      return {
        ...p,
        original_text: editor.getOriginalEditor().getValue(),
        fixed_text: editor.getModifiedEditor().getValue(),
      };
    });
    detachAllModels();
    onApply(edited);
  };

  const handleCancel = () => {
    detachAllModels();
    onCancel();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl w-full max-w-5xl h-[90vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
          <h2 className="font-semibold text-gray-900">
            ✨ AI tự fix lỗi — chọn cách giải quyết từng vị trí
          </h2>
          <button
            onClick={handleCancel}
            className="text-gray-400 hover:text-gray-600 transition"
            title="Đóng"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4 space-y-6">
          {patches.map((patch, idx) => (
            <div
              key={patch.id}
              className="border border-gray-200 rounded-lg overflow-hidden"
            >
              <div className="flex items-center justify-between gap-3 px-4 py-2 bg-gray-50 border-b">
                <div className="space-y-1">
                  <div className="text-xs text-gray-500">
                    Vị trí #{idx + 1} — dòng {patch.start_line + 1}–
                    {patch.end_line + 1}
                  </div>
                  <IssueBadges issues={patch.issues} />
                </div>
              </div>

              <DiffEditor
                height="220px"
                language="yaml"
                original={patch.original_text}
                modified={patch.fixed_text}
                onMount={(editor) => {
                  editorsRef.current.set(patch.id, editor);
                }}
                options={{
                  readOnly: false,
                  originalEditable: true,
                  renderSideBySide: true,
                  minimap: { enabled: false },
                  fontSize: 12,
                  scrollBeyondLastLine: false,
                }}
              />

              <div className="flex gap-2 px-4 py-3 bg-gray-50 border-t">
                {RESOLUTION_OPTIONS.map((opt) => {
                  const active =
                    (resolutions[patch.id] ?? "fixed") === opt.value;
                  return (
                    <button
                      key={opt.value}
                      onClick={() => onResolutionChange(patch.id, opt.value)}
                      className={`px-3 py-1.5 rounded-lg text-sm transition ${
                        active
                          ? "bg-indigo-600 text-white"
                          : "bg-white text-gray-600 border border-gray-300 hover:bg-gray-100"
                      }`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          {unresolved.length > 0 && (
            <div className="border border-rose-200 rounded-lg overflow-hidden">
              <div className="px-4 py-2 bg-rose-50 text-rose-700 text-sm font-medium border-b border-rose-200">
                Cần sửa tay — AI không tự xác định/sửa được {unresolved.length}{" "}
                lỗi
              </div>
              <ul className="divide-y divide-rose-100">
                {unresolved.map((u, i) => (
                  <li key={i} className="px-4 py-2 text-sm text-gray-700">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 mr-2">
                      [{u.source}] {u.code}
                    </span>
                    {u.message}
                    <span className="text-gray-400"> — {u.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex gap-3 px-6 py-4 border-t shrink-0">
          <button
            onClick={handleApply}
            disabled={patches.length === 0}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm transition disabled:opacity-40"
          >
            Áp dụng
          </button>
          <button
            onClick={handleCancel}
            className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 text-sm transition"
          >
            Hủy
          </button>
        </div>
      </div>
    </div>
  );
}
