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
    <section className="bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
      <h2 className="font-semibold text-gray-900 mb-4">Scan nguồn dữ liệu</h2>

      {loading && <p className="text-sm text-gray-400">Đang quét...</p>}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {error}
        </div>
      )}

      {scan && (
        <>
          <ul className="space-y-1 text-sm">
            {scan.modules.length === 0 && (
              <li className="px-3 py-2 text-gray-400">
                Chưa có module folder nào.
              </li>
            )}
            {scan.modules.map((m) => (
              <li
                key={m.name}
                className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50"
                title={formatExtensions(m.by_extension)}
              >
                <span className="font-medium text-gray-800">📁 {m.name}</span>
                <span className="text-gray-400">
                  {m.total} file{m.total !== 1 ? "s" : ""}
                </span>
              </li>
            ))}
          </ul>

          {scan.unassigned.length > 0 && (
            <details className="mt-1 group" open>
              <summary className="list-none flex items-center justify-between px-3 py-2 rounded-lg hover:bg-amber-50 cursor-pointer text-sm text-amber-600 font-medium">
                <span>⚠️ File chưa gán ({scan.unassigned.length})</span>
                <span className="text-gray-400 group-open:rotate-180 transition-transform">
                  ⌄
                </span>
              </summary>
              <ul className="mt-1 ml-3 space-y-1 text-sm text-gray-500 max-h-64 overflow-auto">
                {scan.unassigned.map((f) => (
                  <li
                    key={f.name}
                    className="px-3 py-1.5 rounded-lg hover:bg-gray-50 truncate"
                  >
                    {f.name}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </section>
  );
}
