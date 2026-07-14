"use client";

import { useState } from "react";
import type { Operation } from "./page";
import { methodTone, statusTone, MUTATING_METHODS } from "./theme";
import { generateExample } from "./openapi-utils";

type Parameter = {
  name: string;
  in: string;
  required?: boolean;
  description?: string;
  schema?: { type?: string; format?: string; default?: unknown; enum?: unknown[] };
};

type RequestBody = {
  required?: boolean;
  content?: Record<string, { schema?: Record<string, unknown> }>;
};

type SentResult = {
  status: number;
  statusText: string;
  timeMs: number;
  body: string;
};

function buildUrl(baseUrl: string, path: string, params: Parameter[], values: Record<string, string>) {
  let resolvedPath = path;
  const query = new URLSearchParams();
  for (const p of params) {
    const value = values[p.name];
    if (p.in === "path") {
      resolvedPath = resolvedPath.replace(`{${p.name}}`, value ? encodeURIComponent(value) : `{${p.name}}`);
    } else if (p.in === "query" && value) {
      query.append(p.name, value);
    }
  }
  const qs = query.toString();
  return `${baseUrl}${resolvedPath}${qs ? `?${qs}` : ""}`;
}

function buildCurl(method: string, url: string, headers: Record<string, string>, body: string | null) {
  const parts = [`curl -X ${method} '${url}'`];
  for (const [k, v] of Object.entries(headers)) parts.push(`-H '${k}: ${v}'`);
  if (body) parts.push(`--data '${body.replace(/'/g, "'\\''")}'`);
  return parts.join(" \\\n  ");
}

export default function TryItOut({ op, baseUrl }: { op: Operation; baseUrl: string }) {
  const parameters = (op.raw.parameters ?? []) as Parameter[];
  const requestBody = op.raw.requestBody as RequestBody | undefined;
  const bodySchema = requestBody?.content?.["application/json"]?.schema;
  const isMutating = MUTATING_METHODS.has(op.method);

  const [values, setValues] = useState<Record<string, string>>({});
  const [bodyText, setBodyText] = useState(() =>
    bodySchema ? JSON.stringify(generateExample(bodySchema), null, 2) : ""
  );
  const [armed, setArmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const headerParams = parameters.filter((p) => p.in === "header");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  for (const p of headerParams) if (values[p.name]) headers[p.name] = values[p.name];

  const url = buildUrl(baseUrl, op.path, parameters, values);
  const body = isMutating && bodyText.trim() ? bodyText : null;
  const curl = buildCurl(op.method, url, headers, body);

  async function send() {
    if (isMutating && !armed) {
      setArmed(true);
      return;
    }
    setArmed(false);
    setLoading(true);
    setError(null);
    setResult(null);
    const started = performance.now();
    try {
      const res = await fetch(url, {
        method: op.method,
        headers,
        body: body ?? undefined,
      });
      const text = await res.text();
      setResult({
        status: res.status,
        statusText: res.statusText,
        timeMs: Math.round(performance.now() - started),
        body: text,
      });
    } catch {
      setError(
        "Không gọi được request — có thể do CORS chặn từ production gateway, hoặc mạng lỗi."
      );
    } finally {
      setLoading(false);
    }
  }

  function copyCurl() {
    navigator.clipboard.writeText(curl);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const tone = methodTone(op.method);

  return (
    <div className="px-8 py-7 border-b border-[#F0F0EE]">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Try it out</h3>
        <span className="text-sm text-gray-400">
          gọi thẳng tới <code className="font-mono">{baseUrl || "(chưa có server url)"}</code>
        </span>
      </div>

      {(parameters.filter((p) => p.in !== "header").length > 0) && (
        <div className="space-y-3 mb-4">
          {parameters
            .filter((p) => p.in !== "header")
            .map((p) => (
              <label key={`${p.in}-${p.name}`} className="flex items-center gap-3 text-sm">
                <span className="w-44 shrink-0 truncate font-mono text-gray-600" title={`${p.name} (${p.in})`}>
                  {p.name}
                  {p.required && <span className="text-[#9F2F2D] ml-0.5">*</span>}
                  <span className="text-gray-300 ml-1">({p.in})</span>
                </span>
                <input
                  type="text"
                  value={values[p.name] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.value }))}
                  placeholder={p.schema?.type ?? "string"}
                  className="flex-1 border border-[#EAEAEA] rounded-lg px-3 py-2 font-mono focus:outline-none focus:ring-2 focus:ring-[#1F6C9F]/20"
                />
              </label>
            ))}
        </div>
      )}

      {headerParams.length > 0 && (
        <div className="space-y-3 mb-4">
          {headerParams.map((p) => (
            <label key={`header-${p.name}`} className="flex items-center gap-3 text-sm">
              <span className="w-44 shrink-0 truncate font-mono text-gray-600" title={`${p.name} (header)`}>
                {p.name}
                {p.required && <span className="text-[#9F2F2D] ml-0.5">*</span>}
                <span className="text-gray-300 ml-1">(header)</span>
              </span>
              <input
                type="text"
                value={values[p.name] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.value }))}
                className="flex-1 border border-[#EAEAEA] rounded-lg px-3 py-2 font-mono focus:outline-none focus:ring-2 focus:ring-[#1F6C9F]/20"
              />
            </label>
          ))}
        </div>
      )}

      {isMutating && bodySchema && (
        <div className="mb-4">
          <p className="text-sm text-gray-400 mb-2">Request body (JSON)</p>
          <textarea
            value={bodyText}
            onChange={(e) => setBodyText(e.target.value)}
            rows={6}
            className="w-full border border-[#EAEAEA] rounded-lg px-4 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#1F6C9F]/20"
          />
        </div>
      )}

      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={send}
          disabled={loading}
          className={`px-5 py-2 text-sm font-semibold rounded-full transition-colors disabled:opacity-50 ${
            armed ? `${tone.solid} ${tone.solidText}` : `${tone.bg} ${tone.text} hover:brightness-95`
          }`}
        >
          {loading ? "Đang gửi…" : armed ? "Xác nhận gửi (production)" : "Gửi request"}
        </button>
        {armed && (
          <button onClick={() => setArmed(false)} className="text-sm text-gray-400 hover:text-gray-600">
            Huỷ
          </button>
        )}
        <button onClick={copyCurl} className="text-sm text-gray-400 hover:text-gray-600 ml-auto">
          {copied ? "Đã copy!" : "Copy as curl"}
        </button>
      </div>

      {error && <p className="text-sm text-[#9F2F2D] mb-3">{error}</p>}

      {result && (
        <div className="border border-[#EAEAEA] rounded-lg overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 bg-[#F7F6F3] border-b border-[#EAEAEA]">
            <span className={`text-sm font-bold px-2.5 py-1 rounded-full ${statusTone(String(result.status)).bg} ${statusTone(String(result.status)).text}`}>
              {result.status} {result.statusText}
            </span>
            <span className="text-sm text-gray-400">{result.timeMs} ms</span>
          </div>
          <pre className="px-4 py-3 text-sm font-mono overflow-x-auto whitespace-pre-wrap break-all">{result.body}</pre>
        </div>
      )}
    </div>
  );
}
