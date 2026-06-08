"use client";

import { ScanResult } from "./types";
import { formatExtensions } from "./format";

type Props = {
  scan: ScanResult | null;
  loading: boolean;
  error: string;
};

export default function ScanCard({ scan, loading, error }: Props) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-700 mb-3">Scan nguồn dữ liệu</h2>

      {loading && <p className="text-sm text-gray-400">Đang quét...</p>}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{error}</div>
      )}

      {scan && (
        <div className="space-y-4">
          <p className="text-sm text-gray-400">
            Nguồn: <span className="font-mono text-gray-600">{scan.source_root}</span>
          </p>

          <div>
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Module folders ({scan.modules.length})</h3>
            {scan.modules.length === 0 ? (
              <p className="text-sm text-gray-400">Chưa có module folder nào.</p>
            ) : (
              <ul className="space-y-2">
                {scan.modules.map((m) => (
                  <li key={m.name} className="flex justify-between items-center bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm">
                    <span className="text-gray-700 font-medium">{m.name}</span>
                    <span className="text-gray-400">
                      {m.total} file{m.total !== 1 ? "s" : ""} ({formatExtensions(m.by_extension)})
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-600 mb-2">File chưa gán module ({scan.unassigned.length})</h3>
            {scan.unassigned.length === 0 ? (
              <p className="text-sm text-gray-400">Không có file nào chưa gán module.</p>
            ) : (
              <ul className="space-y-1 max-h-64 overflow-auto">
                {scan.unassigned.map((f) => (
                  <li key={f.name} className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-700 truncate">
                    {f.name}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
