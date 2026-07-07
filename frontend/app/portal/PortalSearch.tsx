"use client";

import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import Fuse from "fuse.js";
import EndpointCard from "./EndpointCard";
import EndpointDetailDrawer from "./EndpointDetailDrawer";
import type { Operation } from "./page";
import { methodTone, METHOD_PASTEL } from "./theme";

const MIN_SIDEBAR_WIDTH = 260;
const MAX_SIDEBAR_WIDTH = 720;
const DEFAULT_SIDEBAR_WIDTH = 416;
const STORAGE_KEY = "portal-sidebar-width";
const COLLAPSED_KEY = "portal-sidebar-collapsed";

export default function PortalSearch({
  operations,
  baseUrl,
}: {
  operations: Operation[];
  baseUrl: string;
}) {
  const [query, setQuery] = useState("");
  const [selectedMethods, setSelectedMethods] = useState<Set<string>>(new Set());
  const [selectedTag, setSelectedTag] = useState("");
  const [selected, setSelected] = useState<Operation | null>(null);

  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
  const [collapsed, setCollapsed] = useState(false);
  const [dragging, setDragging] = useState(false);
  const draggingRef = useRef(false);

  useEffect(() => {
    const savedWidth = Number(localStorage.getItem(STORAGE_KEY));
    if (savedWidth >= MIN_SIDEBAR_WIDTH && savedWidth <= MAX_SIDEBAR_WIDTH) {
      setSidebarWidth(savedWidth);
    }
    setCollapsed(localStorage.getItem(COLLAPSED_KEY) === "1");
  }, []);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    draggingRef.current = true;
    setDragging(true);
  }, []);

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!draggingRef.current) return;
      const next = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, e.clientX));
      setSidebarWidth(next);
    }
    function onUp() {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      setDragging(false);
      setSidebarWidth((w) => {
        localStorage.setItem(STORAGE_KEY, String(w));
        return w;
      });
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
      return next;
    });
  };

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
      <aside
        style={{ width: collapsed ? 0 : sidebarWidth }}
        className={`shrink-0 h-full flex flex-col bg-white border-r border-[#EAEAEA] overflow-hidden ${
          dragging ? "" : "transition-[width] duration-150"
        }`}
      >
        {/* Header */}
        <div className="px-5 pt-6 pb-4 border-b border-[#F0F0EE]">
          <div className="flex items-center justify-between mb-0.5">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-[#1F6C9F]" />
              <span className="text-base font-bold text-[#2F3437] whitespace-nowrap">Developer Portal</span>
            </div>
            <button
              onClick={toggleCollapsed}
              title="Thu gọn sidebar"
              className="shrink-0 w-6 h-6 flex items-center justify-center rounded-md text-gray-400 hover:text-gray-600 hover:bg-[#F7F6F3] transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7M19 19l-7-7 7-7" />
              </svg>
            </button>
          </div>
          <p className="text-sm text-gray-400 pl-4.5 whitespace-nowrap">{operations.length} endpoints</p>
        </div>

        {/* Search + filters */}
        <div className="px-4 pt-4 pb-3 border-b border-[#F0F0EE]">
          <input
            type="text"
            placeholder="Tìm endpoint, operationId..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full text-[#2F3437] border border-[#EAEAEA] rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1F6C9F]/20 mb-3"
          />

          <div className="flex flex-wrap gap-1.5 mb-3">
            {Object.keys(METHOD_PASTEL).map((m) => {
              const active = selectedMethods.has(m);
              const tone = methodTone(m);
              return (
                <button
                  key={m}
                  onClick={() => toggleMethod(m)}
                  className={`px-2.5 py-1 text-xs font-semibold tracking-wide rounded-full transition-colors ${
                    active ? `${tone.solid} ${tone.solidText}` : `${tone.bg} ${tone.text} hover:brightness-95`
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
                className="flex-1 px-2.5 py-1.5 text-sm text-gray-600 border border-[#EAEAEA] rounded-lg bg-white focus:outline-none"
              >
                <option value="">Tất cả tag</option>
                {allTags.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            )}
            {hasFilter && (
              <button onClick={clearFilters} className="text-sm text-gray-400 hover:text-gray-600 whitespace-nowrap">
                Xoá
              </button>
            )}
          </div>
        </div>

        {/* Endpoint list */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1.5">
          {results.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">Không tìm thấy.</p>
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
          <div className="px-4 py-2.5 border-t border-[#F0F0EE]">
            <p className="text-sm text-gray-400">{results.length} / {operations.length} kết quả</p>
          </div>
        )}
      </aside>

      {/* Resize handle */}
      {!collapsed && (
        <div
          onMouseDown={startResize}
          className="w-1 shrink-0 h-full cursor-col-resize hover:bg-[#1F6C9F]/30 active:bg-[#1F6C9F]/40 transition-colors"
        />
      )}

      {/* Main content */}
      <main className="flex-1 h-full overflow-y-auto bg-[#FBFBFA] relative">
        {collapsed && (
          <button
            onClick={toggleCollapsed}
            title="Mở sidebar"
            className="fixed left-3 top-3 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-white border border-[#EAEAEA] text-gray-400 hover:text-gray-600 hover:border-[#D8D8D6] transition-colors shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </button>
        )}
        {selected ? (
          <div className="max-w-[1400px] mx-auto py-10 px-10">
            <EndpointDetailDrawer op={selected} baseUrl={baseUrl} onClose={() => setSelected(null)} />
          </div>
        ) : (
          <div className="relative h-full overflow-y-auto">
            {/* Ambient background — soft pastel light spots, purely decorative */}
            <div
              className="fixed inset-0 pointer-events-none"
              style={{
                background:
                  "radial-gradient(600px circle at 15% 10%, rgba(31,108,159,0.05), transparent 60%), radial-gradient(500px circle at 85% 30%, rgba(52,101,56,0.05), transparent 60%), radial-gradient(700px circle at 50% 90%, rgba(149,100,0,0.04), transparent 60%)",
              }}
            />

            <div className="relative max-w-[1400px] mx-auto px-12 py-16">
              <div className="w-16 h-16 rounded-2xl bg-[#E1F3FE] flex items-center justify-center mb-6">
                <svg className="w-8 h-8 text-[#1F6C9F]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <p className="text-2xl text-[#2F3437] font-semibold mb-2">Chọn một endpoint để xem chi tiết</p>
              <p className="text-base text-gray-400 mb-10">
                {operations.length} endpoints trên {allTags.length} module — gõ để tìm hoặc lọc theo method/tag bên trái.
              </p>

              {/* Method breakdown */}
              <div className="grid grid-cols-5 gap-4 mb-12">
                {Object.keys(METHOD_PASTEL).map((m) => {
                  const tone = methodTone(m);
                  return (
                    <button
                      key={m}
                      onClick={() => setSelectedMethods(new Set([m]))}
                      className={`rounded-xl border border-[#EAEAEA] bg-white px-4 py-5 text-left hover:border-[#D8D8D6] transition-colors`}
                    >
                      <span className={`inline-block text-xs font-semibold tracking-wide px-2 py-1 rounded-full ${tone.bg} ${tone.text} mb-3`}>
                        {m}
                      </span>
                      <p className="text-3xl font-semibold text-[#2F3437]">{methodCounts[m] ?? 0}</p>
                    </button>
                  );
                })}
              </div>

              {/* Tag directory */}
              {allTags.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
                    Duyệt theo module
                  </h3>
                  <div className="flex flex-wrap gap-2.5">
                    {allTags.map((tag) => (
                      <button
                        key={tag}
                        onClick={() => setSelectedTag(tag)}
                        className="text-sm px-4 py-2 rounded-full bg-white border border-[#EAEAEA] text-gray-600 hover:border-[#D8D8D6] hover:bg-[#F7F6F3] transition-colors"
                      >
                        {tag}
                        <span className="text-gray-300 ml-1.5">
                          {operations.filter((o) => o.tags.includes(tag)).length}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </>
  );
}
