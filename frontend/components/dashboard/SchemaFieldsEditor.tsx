"use client";

import { useState } from "react";
import { SchemaGroup } from "@/types/dashboard";

type Props = {
  group: SchemaGroup;
  editedValues: Record<string, string>;
  onChange: (schemaName: string, path: string, value: string) => void;
};

// Đệ quy render 1 SchemaGroup: header bấm để thu gọn/mở rộng riêng khối này
// (mặc định mở — operation cha đã được chủ động mở ra rồi), field đã làm phẳng
// sẵn (kèm "depth" để thụt lề) thành input mô tả, rồi đệ quy tiếp vào "nested"
// (schema con qua $ref) — shared=true hiện dạng chỉ đọc kèm ghi chú, không cho
// sửa (tránh sửa nhầm schema dùng chung nhiều operation, vd UserInfo dùng bởi
// cả getTicketDetail và createTicketConversation).
export default function SchemaFieldsEditor({
  group,
  editedValues,
  onChange,
}: Props) {
  const [collapsed, setCollapsed] = useState(true);

  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center gap-2 px-3 py-1.5 bg-gray-50 text-xs font-semibold text-gray-500 hover:bg-gray-100 transition"
      >
        <span className="text-gray-400 w-3 shrink-0">
          {collapsed ? "▸" : "▾"}
        </span>
        <span className="truncate">{group.schemaName}</span>
        <span className="ml-auto text-gray-400 font-normal shrink-0">
          {group.fields.length} field
        </span>
      </button>

      {!collapsed && (
        <div className="p-3 space-y-2">
          {group.fields.map((field) => {
            const key = `${group.schemaName}::${field.path}`;
            const value = editedValues[key] ?? field.description;
            return (
              <div
                key={field.path}
                className="space-y-1"
                style={{ paddingLeft: field.depth * 16 }}
              >
                <code className="block text-xs text-gray-500 font-mono wrap-break-word">
                  {field.label}
                  {field.readOnly && (
                    <span className="ml-1 text-gray-400">(chỉ đọc)</span>
                  )}
                </code>
                <textarea
                  value={value}
                  onChange={(e) =>
                    onChange(group.schemaName, field.path, e.target.value)
                  }
                  placeholder="Mô tả field..."
                  rows={2}
                  className={`w-full px-3 py-1.5 border rounded-lg text-sm resize-y focus:outline-none focus:ring-2 focus:ring-indigo-300 ${
                    !value ? "border-red-300 bg-red-50" : "border-gray-200"
                  }`}
                />
              </div>
            );
          })}

          {group.nested.map((nested) =>
            nested.shared ? (
              <div
                key={nested.schemaName}
                className="text-xs text-gray-400 italic px-2 py-1.5 bg-gray-50 rounded-lg"
              >
                {nested.schemaName} — dùng chung nhiều API, sửa ở tab YAML thô
                nếu cần.
              </div>
            ) : (
              <SchemaFieldsEditor
                key={nested.schemaName}
                group={nested}
                editedValues={editedValues}
                onChange={onChange}
              />
            ),
          )}
        </div>
      )}
    </div>
  );
}
