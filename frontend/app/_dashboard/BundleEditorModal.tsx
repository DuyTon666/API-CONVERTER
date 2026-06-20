"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { SpectralIssue, RedoclyIssue } from "./types";
import OperationsFormEditor from "./OperationsFormEditor";

const BundleEditor = dynamic(() => import("./BundleEditor"), { ssr: false });

type Tab = "form" | "yaml";

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
  const [activeTab, setActiveTab] = useState<Tab>("form");

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl w-full max-w-4xl h-[90vh] flex flex-col overflow-hidden">
        {/* Header + tabs */}
        <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
          <div className="flex gap-1">
            <button
              onClick={() => setActiveTab("form")}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
                activeTab === "form"
                  ? "bg-indigo-600 text-white"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
              }`}
            >
              Chỉnh sửa nội dung
            </button>
            <button
              onClick={() => setActiveTab("yaml")}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
                activeTab === "yaml"
                  ? "bg-indigo-600 text-white"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
              }`}
            >
              YAML thô
            </button>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
            title="Đóng"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {activeTab === "form" ? (
            <OperationsFormEditor />
          ) : (
            <BundleEditor
              content={content}
              onChange={onChange}
              spectralIssues={spectralIssues}
              redoclyIssues={redoclyIssues}
            />
          )}
        </div>

        {/* Footer — chỉ hiện cho tab YAML */}
        {activeTab === "yaml" && (
          <div className="flex gap-3 px-6 py-4 border-t shrink-0">
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
        )}
      </div>
    </div>
  );
}
