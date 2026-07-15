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
            ops.filter((_op: ImmutableAny, i: number) => matched.has(i)),
          );
        })
        .filter((tagObj: ImmutableAny) => tagObj.get("operations").size > 0),
  },
});

// Escape để chèn message/category vào HTML an toàn — dữ liệu do người phụ
// trách 2.pipeline nhập tay qua docx, không phải input người dùng cuối,
// nhưng vẫn escape cho chắc, tránh vỡ layout nếu lỡ có ký tự `<`/`&`.
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Category phổ biến có màu chip riêng để mắt quét nhanh nhóm hay gặp;
// category còn lại (Compat, Concurrency, Rate Limit...) dùng chung 1 màu
// xám trung tính — không bịa 24 màu riêng biệt gây loãng.
const CATEGORY_CHIP_CLASS: Record<string, string> = {
  Auth: "auth",
  Input: "input",
  Business: "business",
  State: "state",
  Validation: "validation",
  "Not Found": "notfound",
};

function categoryChipClass(category: string): string {
  return CATEGORY_CHIP_CLASS[category] ?? "default";
}

// Style dùng chung cho bảng mã lỗi — chèn 1 lần duy nhất vào document.head
// lúc plugin khởi tạo lần đầu (không phải mỗi dòng status), tránh lặp thẻ <style>.
const ERROR_CODES_STYLE_ID = "error-codes-plugin-style";
const ERROR_CODES_CSS = `
.errcodes-details-cell { padding: 0 20px 12px !important; border-bottom: none !important; }
.errcodes-details { margin-top: 10px; }
.errcodes-details summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #3b4151;
  list-style: none;
}
.errcodes-details summary::-webkit-details-marker { display: none; }
.errcodes-details summary::before {
  content: "▸";
  display: inline-block;
  width: 12px;
  transition: transform 0.15s ease;
}
.errcodes-details[open] summary::before { transform: rotate(90deg); }
.errcodes-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 6px;
  font-size: 12.5px;
}
.errcodes-table th,
.errcodes-table td {
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid #e8e8e8;
}
.errcodes-table th { color: #6b7280; font-weight: 600; }
.errcodes-chip {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 600;
  white-space: nowrap;
}
.errcodes-chip.auth { background: #dbeafe; color: #1e40af; }
.errcodes-chip.input { background: #ede9fe; color: #5b21b6; }
.errcodes-chip.business { background: #dcfce7; color: #166534; }
.errcodes-chip.state { background: #ffedd5; color: #9a3412; }
.errcodes-chip.validation { background: #fce7f3; color: #9d174d; }
.errcodes-chip.notfound { background: #e0f2fe; color: #075985; }
.errcodes-chip.default { background: #f3f4f6; color: #4b5563; }
`;

function ensureErrorCodesStyleInjected() {
  if (document.getElementById(ERROR_CODES_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = ERROR_CODES_STYLE_ID;
  style.textContent = ERROR_CODES_CSS;
  document.head.appendChild(style);
}

type ErrorEntry = { code: string; category: string; message: string };

function buildErrorTableHtml(entries: ErrorEntry[], defaultOpen: boolean) {
  const rows = entries
    .map(
      (e) => `
        <tr>
          <td>${escapeHtml(e.code)}</td>
          <td><span class="errcodes-chip ${categoryChipClass(e.category)}">${escapeHtml(e.category)}</span></td>
          <td>${escapeHtml(e.message)}</td>
        </tr>`,
    )
    .join("");
  return `
    <details class="errcodes-details"${defaultOpen ? " open" : ""}>
      <summary>${entries.length} mã lỗi</summary>
      <table class="errcodes-table">
        <thead><tr><th>Mã</th><th>Nhóm</th><th>Ý nghĩa</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </details>`;
}

// Chèn bảng x-error-responses vào từng dòng status trong bảng Responses có
// sẵn của Swagger UI. Bọc component "response" (số ít — 1 dòng status/lần)
// thay vì "responses" (số nhiều — cả bảng), vì cần biết đúng status code
// (props.code) đang render để tra đúng mảng mã lỗi tương ứng.
//
// Không dùng JSX ở đây: swagger-ui-dist là bundle UMD mang theo React
// riêng của nó, tách biệt với React của Next — JSX viết trong file này bị
// biên dịch bằng React của Next, tạo ra element có $$typeof khác "họ", khi
// đưa cho swagger-ui-dist render sẽ vỡ (React error #31, đã gặp lúc spike).
// Giải pháp: dùng system.React.createElement — đúng bản React nội bộ của
// swagger-ui — và build phần markup thêm bằng dangerouslySetInnerHTML.
const errorCodesPlugin = () => ({
  wrapComponents: {
    response:
      (Original: ImmutableAny, system: ImmutableAny) =>
      (props: ImmutableAny) => {
        ensureErrorCodesStyleInjected();

        const operation = system.specSelectors
          .specJson()
          .getIn(["paths", props.path, props.method]);
        const errorMapForOperation = operation?.getIn(["x-error-responses"]);
        const entriesForThisStatus = errorMapForOperation
          ?.get(String(props.code))
          ?.toJS?.() as ErrorEntry[] | undefined;

        // Không có mã lỗi cho status này -> giữ nguyên dòng gốc, không render thêm gì.
        if (!entriesForThisStatus || entriesForThisStatus.length === 0) {
          return system.React.createElement(Original, props);
        }

        // Operation chỉ có đúng 1 status kèm lỗi -> mở sẵn luôn cho đỡ phải bấm.
        const defaultOpen = errorMapForOperation.keySeq().size === 1;

        return system.React.createElement(
          system.React.Fragment,
          null,
          system.React.createElement(Original, props),
          // Original render ra 1 <tr> (1 dòng của bảng Responses) — nếu chèn
          // <div> làm sibling thì HTML không hợp lệ (div không được phép là
          // con trực tiếp của <table>), trình duyệt sẽ tự kéo nó ra khỏi
          // bảng và vỡ layout. Phải chèn thêm 1 <tr><td colSpan> khác, giữ
          // đúng cấu trúc bảng — colSpan={100} là mẹo "chiếm hết cột" mà
          // không cần biết chính xác bảng có bao nhiêu cột.
          system.React.createElement(
            "tr",
            null,
            system.React.createElement("td", {
              colSpan: 100,
              className: "errcodes-details-cell",
              dangerouslySetInnerHTML: {
                __html: buildErrorTableHtml(entriesForThisStatus, defaultOpen),
              },
            }),
          ),
        );
      },
  },
});

export default function SwaggerView({
  spec,
}: {
  spec: Record<string, unknown>;
}) {
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
        plugins: [fuseFilterPlugin, errorCodesPlugin],
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
