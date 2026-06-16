"use client";

import dynamic from "next/dynamic";
import { SpectralIssue, RedoclyIssue } from "./types";

const BundleEditor = dynamic(() => import("../jobs/[job_id]/BundleEditor"), { ssr: false });

type Props = {
  content: string;
  onChange: (value: string) => void;
  spectralIssues: SpectralIssue[];
  redoclyIssues: RedoclyIssue[];
  saving: boolean;
  relinting: boolean;
  onClose: () => void;
  onSave: () => void;
  onSaveAndRelint: () => void;
};

export default function BundleEditorModal({
  content,
  onChange,
  spectralIssues,
  redoclyIssues,
  saving,
  relinting,
  onClose,
  onSave,
  onSaveAndRelint,
}: Props) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl w-full max-w-4xl h-[90vh] flex flex-col overflow-hidden">
        <div className="flex justify-between items-center px-6 py-4 border-b">
          <h2 className="font-semibold text-gray-800">Chỉnh sửa bundle — openapi-bundled.yaml</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>
        <div className="flex-1 min-h-[400px]">
          <BundleEditor
            content={content}
            onChange={onChange}
            spectralIssues={spectralIssues}
            redoclyIssues={redoclyIssues}
          />
        </div>
        <div className="flex gap-3 px-6 py-4 border-t">
          <button
            onClick={onSave}
            disabled={saving}
            className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 text-sm transition disabled:opacity-40"
          >
            {saving ? "Đang lưu..." : "Lưu"}
          </button>
          <button
            onClick={onSaveAndRelint}
            disabled={saving || relinting}
            className="px-4 py-2 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 text-sm transition disabled:opacity-40"
          >
            {relinting ? "Đang kiểm tra..." : "Lưu & Kiểm tra lại"}
          </button>
        </div>
      </div>
    </div>
  );
}
