"use client";

import { useState, useMemo } from "react";
import Fuse from "fuse.js";
import EndpointCard from "./EndpointCard";
import EndpointDetailDrawer from "./EndpointDetailDrawer";
import type { Operation } from "./page";

const METHOD_STYLE: Record<string, { active: string; inactive: string }> = {
  GET:    { active: "bg-blue-600 text-white",   inactive: "bg-blue-50 text-blue-600 hover:bg-blue-100" },
  POST:   { active: "bg-green-600 text-white",  inactive: "bg-green-50 text-green-600 hover:bg-green-100" },
  PUT:    { active: "bg-yellow-500 text-white", inactive: "bg-yellow-50 text-yellow-600 hover:bg-yellow-100" },
  PATCH:  { active: "bg-orange-500 text-white", inactive: "bg-orange-50 text-orange-600 hover:bg-orange-100" },
  DELETE: { active: "bg-red-600 text-white",    inactive: "bg-red-50 text-red-600 hover:bg-red-100" },
};

export default function PortalSearch({ operations }: { operations: Operation[] }) {
  const [query, setQuery] = useState("");
  const [selectedMethods, setSelectedMethods] = useState<Set<string>>(new Set());
  const [selectedTag, setSelectedTag] = useState("");
  const [selected, setSelected] = useState<Operation | null>(null);

  const allTags = useMemo(() => {
    const set = new Set<string>();
    operations.forEach((op) => op.tags.forEach((t) => set.add(t)));
    return Array.from(set).sort();
  }, [operations]);

  const methodCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    operations.forEach((op) => {
      counts[op.method] = (counts[op.method] ?? 0) + 1;
    });
    return counts;
  }, [operations]);

  const fuse = useMemo(
    () =>
      new Fuse(operations, {
        keys: [
          { name: "operationId", weight: 0.3 },
          { name: "summary",     weight: 0.3 },
          { name: "path",        weight: 0.2 },
          { name: "tags",        weight: 0.1 },
          { name: "description", weight: 0.1 },
        ],
        threshold: 0.4,
      }),
    [operations]
  );

  const results = useMemo(() => {
    let list = query.trim() ? fuse.search(query).map((r) => r.item) : operations;
    if (selectedMethods.size > 0)
      list = list.filter((op) => selectedMethods.has(op.method));
    if (selectedTag)
      list = list.filter((op) => op.tags.includes(selectedTag));
    return list;
  }, [query, fuse, operations, selectedMethods, selectedTag]);

  const toggleMethod = (m: string) =>
    setSelectedMethods((prev) => {
      const next = new Set(prev);
      next.has(m) ? next.delete(m) : next.add(m);
      return next;
    });

  const hasFilter = query.trim() || selectedMethods.size > 0 || selectedTag;

  const clearFilters = () => {
    setQuery("");
    setSelectedMethods(new Set());
    setSelectedTag("");
  };

  return (
    <>
      {/* Sidebar */}
      <aside className="w-70 shrink-0 h-full flex flex-col bg-white border-r border-gray-200">
        {/* Header */}
        <div className="px-4 pt-5 pb-3 border-b border-gray-100">
          <div className="flex items-center gap-2 mb-0.5">
            <div className="w-2 h-2 rounded-full bg-blue-500" />
            <span className="text-sm font-bold text-gray-800">Developer Portal</span>
          </div>
          <p className="text-xs text-gray-400 pl-4">{operations.length} endpoints</p>
        </div>

        {/* Search + filters */}
        <div className="px-3 pt-3 pb-2 border-b border-gray-100">
          <input
            type="text"
            placeholder="Tìm endpoint, operationId..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full text-gray-700 border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-400 mb-2"
          />

          <div className="flex flex-wrap gap-1 mb-2">
            {Object.keys(METHOD_STYLE).map((m) => {
              const active = selectedMethods.has(m);
              return (
                <button
                  key={m}
                  onClick={() => toggleMethod(m)}
                  className={`px-2 py-0.5 text-xs font-bold rounded-full transition ${
                    active ? METHOD_STYLE[m].active : METHOD_STYLE[m].inactive
                  }`}
                >
                  {m} {methodCounts[m] ? <span className="opacity-70">({methodCounts[m]})</span> : null}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-2">
            {allTags.length > 0 && (
              <select
                value={selectedTag}
                onChange={(e) => setSelectedTag(e.target.value)}
                className="flex-1 px-2 py-1 text-xs text-gray-600 border border-gray-200 rounded bg-white focus:outline-none"
              >
                <option value="">Tất cả tag</option>
                {allTags.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            )}
            {hasFilter && (
              <button onClick={clearFilters} className="text-xs text-gray-400 hover:text-gray-600 whitespace-nowrap">
                Xoá
              </button>
            )}
          </div>
        </div>

        {/* Endpoint list */}
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
          {results.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-6">Không tìm thấy.</p>
          ) : (
            results.map((op) => (
              <EndpointCard
                key={op.operationId || `${op.method}-${op.path}`}
                op={op}
                active={selected?.operationId === op.operationId && selected?.path === op.path}
                onClick={() => setSelected(op)}
              />
            ))
          )}
        </div>

        {hasFilter && (
          <div className="px-3 py-2 border-t border-gray-100">
            <p className="text-xs text-gray-400">{results.length} / {operations.length} kết quả</p>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 h-full overflow-y-auto">
        {selected ? (
          <div className="max-w-3xl mx-auto py-8 px-6">
            <EndpointDetailDrawer op={selected} onClose={() => setSelected(null)} />
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center px-8">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <p className="text-gray-700 font-medium mb-1">Chọn một endpoint để xem chi tiết</p>
            <p className="text-sm text-gray-400">
              {operations.length} endpoints · {allTags.length} tags
            </p>
          </div>
        )}
      </main>
    </>
  );
}
