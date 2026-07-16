"use client";

import { useState } from "react";
import SchemaViewer from "./SchemaViewer";
import TryItOut from "./TryItOut";
import type { Operation } from "./page";
import { methodTone, statusTone, categoryTone, type PastelTone } from "./theme";
import { generateExample } from "./openapi-utils";

type SchemaObject = Record<string, unknown>;

type Parameter = {
  name: string;
  in: string;
  required?: boolean;
  description?: string;
  schema?: {
    type?: string;
    format?: string;
    default?: unknown;
    enum?: unknown[];
  };
};

type ResponseObject = {
  description?: string;
  content?: Record<string, { schema?: SchemaObject }>;
};

type ErrorEntry = { code: string; category: string; message: string };

function JsonBlock({ value }: { value: unknown }) {
  const json = JSON.stringify(value, null, 2);
  const highlighted = json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(\.\d+)?([eE][+-]?\d+)?)/g,
    (match) => {
      if (/^"/.test(match)) {
        if (/:$/.test(match))
          return `<span class="text-indigo-600 font-medium">${match}</span>`;
        return `<span class="text-emerald-600">${match}</span>`;
      }
      if (/true|false/.test(match))
        return `<span class="text-amber-500">${match}</span>`;
      if (/null/.test(match))
        return `<span class="text-gray-400">${match}</span>`;
      return `<span class="text-blue-500">${match}</span>`;
    },
  );
  return (
    <pre
      className="bg-slate-50 border border-slate-200 rounded-lg px-5 py-4 text-sm overflow-x-auto leading-relaxed"
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  );
}

function SchemaExampleToggle({ schema }: { schema: SchemaObject }) {
  const [view, setView] = useState<"example" | "schema">("example");
  return (
    <div>
      <div className="flex gap-1.5 mb-3">
        {(["example", "schema"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-3.5 py-1.5 text-sm rounded transition ${
              view === v
                ? "bg-indigo-600 text-white"
                : "bg-gray-100 text-gray-500 hover:bg-gray-200"
            }`}
          >
            {v === "example" ? "Example" : "Schema"}
          </button>
        ))}
      </div>
      {view === "example" ? (
        <JsonBlock value={generateExample(schema)} />
      ) : (
        <SchemaViewer
          schema={schema as Parameters<typeof SchemaViewer>[0]["schema"]}
        />
      )}
    </div>
  );
}

function ErrorCodesTable({ entries }: { entries: ErrorEntry[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-gray-400 hover:text-gray-600 transition"
      >
        <svg
          className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        Mã lỗi nghiệp vụ ({entries.length})
      </button>
      {open && (
        <table className="w-full text-sm border border-[#EAEAEA] rounded-lg overflow-hidden">
          <thead className="bg-[#F7F6F3] text-gray-400 uppercase">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium">Mã</th>
              <th className="px-4 py-2.5 text-left font-medium">Nhóm</th>
              <th className="px-4 py-2.5 text-left font-medium">Ý nghĩa</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => {
              const tone = categoryTone(e.category);
              return (
                <tr
                  key={e.code}
                  className={i % 2 === 0 ? "bg-white" : "bg-[#FBFBFA]"}
                >
                  <td className="px-4 py-2.5 font-mono text-[#2F3437] font-medium">
                    {e.code}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${tone.bg} ${tone.text}`}
                    >
                      {e.category}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-gray-500">{e.message}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ResponseCard({
  status,
  res,
  st,
  errors,
}: {
  status: string;
  res: ResponseObject;
  st: PastelTone;
  errors?: ErrorEntry[];
}) {
  const [open, setOpen] = useState(false);
  const schema = res.content?.["application/json"]?.schema;
  const hasErrors = errors && errors.length > 0;

  return (
    <div className="border border-[#EAEAEA] rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`w-full flex items-center gap-3 px-5 py-3 bg-[#F7F6F3] text-left ${open ? "border-b border-[#EAEAEA]" : ""}`}
      >
        <span
          className={`text-sm font-bold px-2.5 py-1 rounded-full ${st.bg} ${st.text}`}
        >
          {status}
        </span>
        <span className="text-base text-gray-600 flex-1">
          {res.description}
        </span>
        {hasErrors && (
          <span className="text-xs font-medium text-gray-400">
            {errors!.length} mã lỗi
          </span>
        )}
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform shrink-0 ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>
      {open && (
        <div className="px-5 py-4 space-y-4">
          {schema && <SchemaExampleToggle schema={schema} />}
          {hasErrors && <ErrorCodesTable entries={errors!} />}
        </div>
      )}
    </div>
  );
}

export default function EndpointDetailDrawer({
  op,
  baseUrl,
  onClose,
}: {
  op: Operation;
  baseUrl: string;
  onClose: () => void;
}) {
  const parameters = (op.raw.parameters ?? []) as Parameter[];
  const responses = (op.raw.responses ?? {}) as Record<string, ResponseObject>;
  const errorResponsesMap = (op.raw["x-error-responses"] ?? {}) as Record<
    string,
    ErrorEntry[]
  >;
  const requestBody = op.raw.requestBody as
    | {
        required?: boolean;
        content?: Record<string, { schema?: SchemaObject }>;
      }
    | undefined;
  const tone = methodTone(op.method);

  return (
    <div className="bg-white border border-[#EAEAEA] rounded-xl overflow-hidden">
      <div className={`h-1 ${tone.solid}`} />

      {/* Header */}
      <div className="px-8 py-7 border-b border-[#F0F0EE]">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3 flex-wrap">
            <span
              className={`text-sm font-semibold tracking-wide px-3 py-1.5 rounded-full ${tone.bg} ${tone.text}`}
            >
              {op.method}
            </span>
            <code className="text-lg font-mono text-[#2F3437] break-all">
              {op.path}
            </code>
          </div>
          <button
            onClick={onClose}
            className="text-gray-300 hover:text-gray-500 text-2xl leading-none ml-4 shrink-0"
          >
            ✕
          </button>
        </div>
        {op.summary && (
          <p className="mt-4 text-xl font-semibold text-[#2F3437]">
            {op.summary}
          </p>
        )}
        {op.description && (
          <p className="mt-2 text-base text-gray-500 whitespace-pre-wrap leading-relaxed">
            {op.description}
          </p>
        )}
        {(op.tags.length > 0 || op.operationId) && (
          <div className="mt-4 flex items-center gap-2 flex-wrap">
            {op.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs uppercase tracking-wide bg-[#F7F6F3] text-gray-500 px-2.5 py-1 rounded-full"
              >
                {tag}
              </span>
            ))}
            {op.operationId && (
              <span className="text-sm font-mono text-gray-400">
                {op.operationId}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Parameters */}
      {parameters.length > 0 && (
        <div className="px-8 py-7 border-b border-[#F0F0EE]">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
            Parameters
          </h3>
          <table className="w-full text-sm border border-[#EAEAEA] rounded-lg overflow-hidden">
            <thead className="bg-[#F7F6F3] text-gray-400 uppercase">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-left font-medium">In</th>
                <th className="px-4 py-3 text-left font-medium">Type</th>
                <th className="px-4 py-3 text-left font-medium">Required</th>
                <th className="px-4 py-3 text-left font-medium">Description</th>
              </tr>
            </thead>
            <tbody>
              {parameters.map((p, i) => (
                <tr
                  key={`${p.in}-${p.name}`}
                  className={i % 2 === 0 ? "bg-white" : "bg-[#FBFBFA]"}
                >
                  <td className="px-4 py-3 font-mono text-[#2F3437] font-medium">
                    {p.name}
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 bg-[#F7F6F3] text-gray-500 rounded">
                      {p.in}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[#1F6C9F] font-medium">
                    {p.schema?.type ?? "—"}
                    {p.schema?.format ? (
                      <span className="text-gray-400 ml-1">
                        ({p.schema.format})
                      </span>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    {p.required ? (
                      <span className="text-[#9F2F2D] font-bold">*</span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {p.description ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Request Body */}
      {requestBody && (
        <div className="px-8 py-7 border-b border-[#F0F0EE]">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
              Request Body
            </h3>
            {requestBody.required && (
              <span className="text-sm text-[#9F2F2D]">required</span>
            )}
          </div>
          {Object.entries(requestBody.content ?? {}).map(
            ([mediaType, mediaObj]) => (
              <div key={mediaType}>
                <p className="text-sm font-mono text-gray-400 mb-3">
                  {mediaType}
                </p>
                {mediaObj.schema && (
                  <SchemaExampleToggle schema={mediaObj.schema} />
                )}
              </div>
            ),
          )}
        </div>
      )}

      {/* Try it out */}
      {baseUrl && <TryItOut op={op} baseUrl={baseUrl} />}

      {/* Responses */}
      {Object.keys(responses).length > 0 && (
        <div className="px-8 py-7">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
            Responses
          </h3>
          <div className="space-y-4">
            {Object.entries(responses).map(([status, res]) => (
              <ResponseCard
                key={status}
                status={status}
                res={res}
                st={statusTone(status)}
                errors={errorResponsesMap[status]}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
