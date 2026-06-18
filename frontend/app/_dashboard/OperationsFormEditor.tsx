"use client";

import { useEffect, useState } from "react";

type Operation = {
  operationId: string;
  method: string;
  path: string;
  tags: string[];
  summary: string;
  description: string;
};

type EditState = { summary: string; description: string };

const METHOD_COLOR: Record<string, string> = {
  GET: "bg-blue-100 text-blue-700",
  POST: "bg-green-100 text-green-700",
  PUT: "bg-amber-100 text-amber-700",
  PATCH: "bg-orange-100 text-orange-700",
  DELETE: "bg-red-100 text-red-700",
};

export default function OperationsFormEditor() {
  const backend = process.env.NEXT_PUBLIC_API_URL;

  const [operations, setOperations] = useState<Operation[]>([]);
  const [edits, setEdits] = useState<Record<string, EditState>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [relinting, setRelinting] = useState(false);
  const [savedCount, setSavedCount] = useState<number | null>(null);
  const [relintSummary, setRelintSummary] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState("all");

  useEffect(() => {
    fetch(`${backend}/docs/operations`)
      .then((r) => {
        if (!r.ok) throw new Error("Không thể tải danh sách operations");
        return r.json();
      })
      .then((data: Operation[]) => {
        setOperations(data);
        setError("");
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Lỗi kết nối"))
      .finally(() => setLoading(false));
  }, [backend]);

  const getValue = (op: Operation, field: keyof EditState) =>
    edits[op.operationId]?.[field] ?? op[field];

  const handleChange = (opId: string, field: keyof EditState, value: string) => {
    setSavedCount(null);
    setRelintSummary(null);
    setEdits((prev) => ({
      ...prev,
      [opId]: {
        summary: prev[opId]?.summary ?? operations.find((o) => o.operationId === opId)?.summary ?? "",
        description: prev[opId]?.description ?? operations.find((o) => o.operationId === opId)?.description ?? "",
        [field]: value,
      },
    }));
  };

  const isDirty = (op: Operation) => {
    const e = edits[op.operationId];
    return !!e && (e.summary !== op.summary || e.description !== op.description);
  };

  const dirtyOps = operations.filter(isDirty);

  const doSave = async (): Promise<boolean> => {
    if (dirtyOps.length === 0) return true;
    setSaving(true);
    try {
      const payload = dirtyOps.map((op) => ({
        operationId: op.operationId,
        summary: edits[op.operationId]!.summary,
        description: edits[op.operationId]!.description,
      }));
      const res = await fetch(`${backend}/docs/operations`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: res.statusText }));
        setError("Lỗi lưu: " + data.detail);
        return false;
      }
      const data = await res.json();
      // Commit edits into operations list, clear dirty state
      setOperations((prev) =>
        prev.map((op) => {
          const e = edits[op.operationId];
          return e ? { ...op, summary: e.summary, description: e.description } : op;
        }),
      );
      setEdits({});
      setSavedCount(data.updated);
      return true;
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAndRelint = async () => {
    const ok = await doSave();
    if (!ok) return;
    setRelinting(true);
    try {
      const res = await fetch(`${backend}/docs/relint`, { method: "POST" });
      const data = await res.json();
      const total = (data.spectral?.length ?? 0) + (data.redocly?.length ?? 0);
      setRelintSummary(total === 0 ? "Không có lỗi" : `${total} vấn đề`);
    } finally {
      setRelinting(false);
    }
  };

  // Tags
  const allTags = [
    ...new Set(operations.flatMap((op) => (op.tags.length ? op.tags : ["(Chưa có tag)"]))),
  ];

  // Filter
  const q = search.toLowerCase();
  const filtered = operations.filter((op) => {
    const matchSearch =
      !q ||
      op.path.toLowerCase().includes(q) ||
      getValue(op, "summary").toLowerCase().includes(q);
    const matchTag =
      tagFilter === "all" ||
      (tagFilter === "(Chưa có tag)" ? op.tags.length === 0 : op.tags.includes(tagFilter));
    return matchSearch && matchTag;
  });

  const visibleTags = tagFilter === "all" ? allTags : [tagFilter];
  const grouped = Object.fromEntries(
    visibleTags.map((tag) => [
      tag,
      filtered.filter((op) =>
        tag === "(Chưa có tag)" ? op.tags.length === 0 : op.tags.includes(tag),
      ),
    ]),
  );

  if (loading) {
    return <div className="p-6 text-sm text-gray-400">Đang tải danh sách operations...</div>;
  }
  if (error) {
    return <div className="p-6 text-sm text-red-600">{error}</div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search + filter */}
      <div className="px-4 py-3 border-b flex gap-2 shrink-0">
        <input
          type="text"
          placeholder="Tìm theo path hoặc tên..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
        />
        <select
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
          className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none"
        >
          <option value="all">Tất cả ({operations.length})</option>
          {allTags.map((tag) => (
            <option key={tag} value={tag}>
              {tag} ({operations.filter((o) => (tag === "(Chưa có tag)" ? o.tags.length === 0 : o.tags.includes(tag))).length})
            </option>
          ))}
        </select>
      </div>

      {/* Operations list */}
      <div className="flex-1 overflow-auto p-4 space-y-6">
        {visibleTags.map((tag) => {
          const ops = grouped[tag];
          if (!ops?.length) return null;
          return (
            <div key={tag}>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                🏷 {tag} · {ops.length} endpoint
              </p>
              <div className="space-y-3">
                {ops.map((op) => {
                  const dirty = isDirty(op);
                  return (
                    <div
                      key={op.operationId}
                      className={`border rounded-xl p-4 space-y-3 transition-colors ${
                        dirty
                          ? "border-amber-300 bg-amber-50/40"
                          : "border-gray-200 bg-white"
                      }`}
                    >
                      {/* Method + Path */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`text-xs font-bold px-2 py-0.5 rounded ${
                            METHOD_COLOR[op.method] ?? "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {op.method}
                        </span>
                        <code className="text-xs text-gray-500 font-mono">{op.path}</code>
                        {dirty && (
                          <span className="ml-auto text-xs text-amber-600 font-medium">
                            ● chưa lưu
                          </span>
                        )}
                      </div>

                      {/* Summary */}
                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          Tên gọi <span className="text-red-400">*</span>
                        </label>
                        <input
                          type="text"
                          value={getValue(op, "summary")}
                          onChange={(e) =>
                            handleChange(op.operationId, "summary", e.target.value)
                          }
                          placeholder="Nhập tên gọi ngắn gọn..."
                          className={`w-full px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 ${
                            !getValue(op, "summary")
                              ? "border-red-300 bg-red-50"
                              : "border-gray-200"
                          }`}
                        />
                      </div>

                      {/* Description */}
                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          Mô tả chi tiết
                        </label>
                        <textarea
                          value={getValue(op, "description")}
                          onChange={(e) =>
                            handleChange(op.operationId, "description", e.target.value)
                          }
                          placeholder="Mô tả chi tiết API này làm gì..."
                          rows={2}
                          className="w-full px-3 py-1.5 border border-gray-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-12">
            Không tìm thấy endpoint nào.
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="border-t px-4 py-3 flex items-center gap-3 shrink-0">
        <div className="flex-1 flex items-center gap-3 text-xs">
          {dirtyOps.length > 0 && (
            <span className="text-amber-600 font-medium">
              {dirtyOps.length} thay đổi chưa lưu
            </span>
          )}
          {savedCount !== null && dirtyOps.length === 0 && (
            <span className="text-emerald-600">✓ Đã lưu {savedCount} thay đổi</span>
          )}
          {relintSummary && (
            <span
              className={
                relintSummary === "Không có lỗi" ? "text-emerald-600" : "text-amber-600"
              }
            >
              · Kiểm tra: {relintSummary}
            </span>
          )}
        </div>
        <button
          onClick={doSave}
          disabled={saving || relinting || dirtyOps.length === 0}
          className="px-4 py-1.5 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 text-sm disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        <button
          onClick={handleSaveAndRelint}
          disabled={saving || relinting || dirtyOps.length === 0}
          className="px-4 py-1.5 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 text-sm disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {relinting ? "Đang kiểm tra..." : "Lưu & Kiểm tra lại"}
        </button>
      </div>
    </div>
  );
}