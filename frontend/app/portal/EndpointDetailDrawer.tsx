"use client";

import { useState } from "react";
import SchemaViewer from "./SchemaViewer";
import type { Operation } from "./page";

type SchemaObject = Record<string, unknown>;

type Parameter = {
  name: string;
  in: string;
  required?: boolean;
  description?: string;
  schema?: { type?: string; format?: string; default?: unknown; enum?: unknown[] };
};

type ResponseObject = {
  description?: string;
  content?: Record<string, { schema?: SchemaObject }>;
};

const METHOD_COLOR: Record<string, string> = {
  GET:    "bg-blue-100 text-blue-700 border border-blue-200",
  POST:   "bg-green-100 text-green-700 border border-green-200",
  PUT:    "bg-yellow-100 text-yellow-700 border border-yellow-200",
  PATCH:  "bg-orange-100 text-orange-700 border border-orange-200",
  DELETE: "bg-red-100 text-red-700 border border-red-200",
};

const STATUS_COLOR = (s: string) => {
  if (s.startsWith("2")) return "bg-green-100 text-green-700 border border-green-200";
  if (s.startsWith("4")) return "bg-yellow-100 text-yellow-700 border border-yellow-200";
  if (s.startsWith("5")) return "bg-red-100 text-red-700 border border-red-200";
  return "bg-gray-100 text-gray-500 border border-gray-200";
};

function generateExample(schema: SchemaObject, depth = 0): unknown {
  if (depth > 5) return null;
  if (schema.example !== undefined) return schema.example;
  const composed = (schema.allOf ?? schema.anyOf ?? schema.oneOf) as SchemaObject[] | undefined;
  if (composed?.length) {
    const merged: SchemaObject = {};
    for (const s of composed) Object.assign(merged, s);
    return generateExample(merged, depth);
  }
  const type = schema.type as string | undefined;
  if (type === "object" || schema.properties) {
    const props = schema.properties as Record<string, SchemaObject> | undefined;
    if (!props) return {};
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(props)) result[k] = generateExample(v, depth + 1);
    return result;
  }
  if (type === "array") {
    const items = schema.items as SchemaObject | undefined;
    return items ? [generateExample(items, depth + 1)] : [];
  }
  if (type === "string")  return (schema.format as string) === "date-time" ? "2024-01-01T00:00:00Z" : (schema.enum as unknown[])?.[0] ?? "string";
  if (type === "integer" || type === "number") return 0;
  if (type === "boolean") return false;
  return null;
}

function JsonBlock({ value }: { value: unknown }) {
  const json = JSON.stringify(value, null, 2);
  const highlighted = json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(\.\d+)?([eE][+-]?\d+)?)/g,
    (match) => {
      if (/^"/.test(match)) {
        if (/:$/.test(match)) return `<span class="text-indigo-600 font-medium">${match}</span>`;
        return `<span class="text-emerald-600">${match}</span>`;
      }
      if (/true|false/.test(match)) return `<span class="text-amber-500">${match}</span>`;
      if (/null/.test(match))       return `<span class="text-gray-400">${match}</span>`;
      return `<span class="text-blue-500">${match}</span>`;
    }
  );
  return (
    <pre
      className="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 text-xs overflow-x-auto leading-relaxed"
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  );
}

function SchemaExampleToggle({ schema }: { schema: SchemaObject }) {
  const [view, setView] = useState<"example" | "schema">("example");
  return (
    <div>
      <div className="flex gap-1 mb-2">
        {(["example", "schema"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-3 py-1 text-xs rounded transition ${
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
        <SchemaViewer schema={schema as Parameters<typeof SchemaViewer>[0]["schema"]} />
      )}
    </div>
  );
}

export default function EndpointDetailDrawer({
  op,
  onClose,
}: {
  op: Operation;
  onClose: () => void;
}) {
  const parameters = (op.raw.parameters ?? []) as Parameter[];
  const responses  = (op.raw.responses ?? {}) as Record<string, ResponseObject>;
  const requestBody = op.raw.requestBody as
    | { required?: boolean; content?: Record<string, { schema?: SchemaObject }> }
    | undefined;

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">

      {/* Header */}
      <div className="px-6 py-5 border-b border-gray-100">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`text-xs font-bold px-2.5 py-1 rounded ${METHOD_COLOR[op.method] ?? "bg-gray-100 text-gray-600"}`}>
              {op.method}
            </span>
            <code className="text-sm font-mono text-gray-800 break-all">{op.path}</code>
          </div>
          <button onClick={onClose} className="text-gray-300 hover:text-gray-500 text-xl leading-none ml-4 shrink-0">✕</button>
        </div>
        {op.summary && <p className="mt-3 text-base font-semibold text-gray-800">{op.summary}</p>}
        {op.description && <p className="mt-1 text-sm text-gray-500 whitespace-pre-wrap">{op.description}</p>}
        {(op.tags.length > 0 || op.operationId) && (
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            {op.tags.map((tag) => (
              <span key={tag} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{tag}</span>
            ))}
            {op.operationId && (
              <span className="text-xs font-mono text-gray-400">{op.operationId}</span>
            )}
          </div>
        )}
      </div>

      {/* Parameters */}
      {parameters.length > 0 && (
        <div className="px-6 py-5 border-b border-gray-100">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">Parameters</h3>
          <table className="w-full text-xs border border-gray-200 rounded-lg overflow-hidden">
            <thead className="bg-gray-50 text-gray-400 uppercase">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Name</th>
                <th className="px-3 py-2 text-left font-medium">In</th>
                <th className="px-3 py-2 text-left font-medium">Type</th>
                <th className="px-3 py-2 text-left font-medium">Required</th>
                <th className="px-3 py-2 text-left font-medium">Description</th>
              </tr>
            </thead>
            <tbody>
              {parameters.map((p, i) => (
                <tr key={`${p.in}-${p.name}`} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                  <td className="px-3 py-2 font-mono text-gray-800 font-medium">{p.name}</td>
                  <td className="px-3 py-2">
                    <span className="px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">{p.in}</span>
                  </td>
                  <td className="px-3 py-2 text-blue-600 font-medium">
                    {p.schema?.type ?? "—"}
                    {p.schema?.format ? <span className="text-gray-400 ml-1">({p.schema.format})</span> : null}
                  </td>
                  <td className="px-3 py-2">
                    {p.required
                      ? <span className="text-red-500 font-bold">*</span>
                      : <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-3 py-2 text-gray-500">{p.description ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Request Body */}
      {requestBody && (
        <div className="px-6 py-5 border-b border-gray-100">
          <div className="flex items-center gap-2 mb-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">Request Body</h3>
            {requestBody.required && <span className="text-xs text-red-400">required</span>}
          </div>
          {Object.entries(requestBody.content ?? {}).map(([mediaType, mediaObj]) => (
            <div key={mediaType}>
              <p className="text-xs font-mono text-gray-400 mb-2">{mediaType}</p>
              {mediaObj.schema && <SchemaExampleToggle schema={mediaObj.schema} />}
            </div>
          ))}
        </div>
      )}

      {/* Responses */}
      {Object.keys(responses).length > 0 && (
        <div className="px-6 py-5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">Responses</h3>
          <div className="space-y-3">
            {Object.entries(responses).map(([status, res]) => {
              const schema = res.content?.["application/json"]?.schema;
              return (
                <div key={status} className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="flex items-center gap-3 px-4 py-2.5 bg-gray-50 border-b border-gray-200">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${STATUS_COLOR(status)}`}>
                      {status}
                    </span>
                    <span className="text-sm text-gray-600">{res.description}</span>
                  </div>
                  {schema && (
                    <div className="px-4 py-3">
                      <SchemaExampleToggle schema={schema} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}