"use client";

import { useEffect, useRef } from "react";
import Fuse from "fuse.js";
import "swagger-ui-dist/swagger-ui.css";

/* eslint-disable @typescript-eslint/no-explicit-any */
// taggedOps là cấu trúc Immutable.js nội bộ của swagger-ui, không có type public
type ImmutableAny = any;

const FUSE_OPTIONS = {
  keys: [
    { name: "operationId", weight: 0.3 },
    { name: "summary", weight: 0.25 },
    { name: "path", weight: 0.2 },
    { name: "method", weight: 0.05 },
    { name: "tag", weight: 0.1 },
    { name: "description", weight: 0.1 },
  ],
  threshold: 0.4,
  ignoreLocation: true,
  useExtendedSearch: true,
};

// Thay thuật toán filter mặc định (so khớp chuỗi theo tag) bằng fuzzy search
// trên từng operation; tag nào không còn operation khớp thì ẩn luôn.
const fuseFilterPlugin = () => ({
  fn: {
    opsFilter: (taggedOps: ImmutableAny, phrase: string) =>
      taggedOps
        .map((tagObj: ImmutableAny, tag: string) => {
          const ops = tagObj.get("operations");
          const entries = ops.toArray().map((op: ImmutableAny) => ({
            tag,
            path: op.get("path") ?? "",
            method: op.get("method") ?? "",
            operationId: op.getIn(["operation", "operationId"]) ?? "",
            summary: op.getIn(["operation", "summary"]) ?? "",
            description: op.getIn(["operation", "description"]) ?? "",
          }));
          const fuse = new Fuse(entries, FUSE_OPTIONS);
          const matched = new Set(fuse.search(phrase).map((r) => r.refIndex));
          return tagObj.set(
            "operations",
            ops.filter((_op: ImmutableAny, i: number) => matched.has(i))
          );
        })
        .filter((tagObj: ImmutableAny) => tagObj.get("operations").size > 0),
  },
});

export default function SwaggerView({ spec }: { spec: Record<string, unknown> }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    let cancelled = false;

    // swagger-ui-dist là bundle UMD đúc sẵn — Turbopack không phải biên dịch
    // cây import của apidom nên né được bug refract (vercel/next.js#86507)
    import("swagger-ui-dist").then(({ SwaggerUIBundle }) => {
      if (cancelled) return;
      SwaggerUIBundle({
        domNode: node,
        spec,
        filter: true,
        plugins: [fuseFilterPlugin],
      });
    });

    return () => {
      // Strict Mode chạy effect 2 lần trong dev — cleanup để không render chồng
      cancelled = true;
      node.innerHTML = "";
    };
  }, [spec]);

  return <div ref={ref} className="h-screen overflow-y-auto bg-white" />;
}
