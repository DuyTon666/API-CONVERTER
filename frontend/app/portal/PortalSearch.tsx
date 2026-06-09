"use client";

import { useState, useMemo } from "react";
import Fuse from "fuse.js";
import EndpointCard from "./EndpointCard";
import EndpointDetailDrawer from "./EndpointDetailDrawer";
import type { Operation } from "./page";

export default function PortalSearch({ operations }: { operations: Operation[] }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Operation | null>(null);

  const fuse = useMemo(
    () =>
      new Fuse(operations, {
        keys: [
          { name: "operationId", weight: 0.3 },
          { name: "summary", weight: 0.3 },
          { name: "path", weight: 0.2 },
          { name: "tags", weight: 0.1 },
          { name: "description", weight: 0.1 },
        ],
        threshold: 0.4,
      }),
    [operations]
  );

  const results = query.trim() ? fuse.search(query).map((r) => r.item) : operations;

  return (
    <div className="flex gap-6 items-start">
      <div className={selected ? "w-1/2" : "w-full"}>
        <input
          type="text"
          placeholder="Tìm endpoint, operationId, tag..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full text-gray-700 border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
        />
        <p className="text-xs text-gray-400 mb-4">{results.length} kết quả</p>
        <div className="space-y-3">
          {results.map((op) => (
            <EndpointCard
              key={op.operationId || `${op.method}-${op.path}`}
              op={op}
              active={selected?.operationId === op.operationId && selected?.path === op.path}
              onClick={() => setSelected(op)}
            />
          ))}
        </div>
      </div>

      {selected && (
        <div className="w-1/2 sticky top-6 max-h-[calc(100vh-3rem)] overflow-y-auto">
          <EndpointDetailDrawer op={selected} onClose={() => setSelected(null)} />
        </div>
      )}
    </div>
  );
}
