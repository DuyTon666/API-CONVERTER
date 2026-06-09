import SchemaViewer from "./SchemaViewer";
import type { Operation } from "./page";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

type Parameter = {
  name: string;
  in: string;
  required?: boolean;
  description?: string;
  schema?: { type?: string; format?: string; default?: unknown };
};

type ResponseObject = {
  description?: string;
  content?: Record<string, { schema?: Record<string, unknown> }>;
};

const METHOD_COLOR: Record<string, string> = {
  GET: "bg-blue-100 text-blue-700",
  POST: "bg-green-100 text-green-700",
  PUT: "bg-yellow-100 text-yellow-700",
  PATCH: "bg-orange-100 text-orange-700",
  DELETE: "bg-red-100 text-red-700",
};

const STATUS_COLOR = (status: string) => {
  if (status.startsWith("2")) return "bg-green-100 text-green-700";
  if (status.startsWith("4")) return "bg-yellow-100 text-yellow-700";
  if (status.startsWith("5")) return "bg-red-100 text-red-700";
  return "bg-gray-100 text-gray-600";
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">{title}</h3>
      {children}
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
  const responses = (op.raw.responses ?? {}) as Record<string, ResponseObject>;
  const requestBody = op.raw.requestBody as
    | { required?: boolean; content?: Record<string, { schema?: Record<string, unknown> }> }
    | undefined;

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-6">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 flex-wrap">
          <span className={`text-xs font-bold px-2 py-0.5 rounded ${METHOD_COLOR[op.method] ?? "bg-gray-100 text-gray-600"}`}>
            {op.method}
          </span>
          <code className="text-sm font-mono text-gray-800 break-all">{op.path}</code>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none ml-2 shrink-0">
          ✕
        </button>
      </div>

      <Tabs defaultValue="api">
        <TabsList>
          <TabsTrigger value="api">Endpoint</TabsTrigger>
          <TabsTrigger value="guide">Hướng dẫn sử dụng</TabsTrigger>
        </TabsList>

        <TabsContent value="api">
          <div className="mt-4">
            {op.tags.length > 0 && (
              <div className="flex gap-2 flex-wrap mb-3">
                {op.tags.map((tag) => (
                  <span key={tag} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{tag}</span>
                ))}
              </div>
            )}

            {op.operationId && (
              <p className="text-xs font-mono text-gray-400 mb-3">{op.operationId}</p>
            )}

            {op.summary && <p className="text-sm font-semibold text-gray-800 mb-1">{op.summary}</p>}
            {op.description && <p className="text-sm text-gray-500 mb-5 whitespace-pre-wrap">{op.description}</p>}

            {parameters.length > 0 && (
              <Section title="Parameters">
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  {parameters.map((p, i) => (
                    <div
                      key={`${p.in}-${p.name}`}
                      className={`px-4 py-3 text-sm ${i < parameters.length - 1 ? "border-b border-gray-100" : ""}`}
                    >
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <code className="font-mono text-gray-800 text-xs">{p.name}</code>
                        <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{p.in}</span>
                        {p.schema?.type && (
                          <span className="text-xs font-semibold text-blue-600">{p.schema.type}</span>
                        )}
                        {p.schema?.format && (
                          <span className="text-xs text-gray-400">&lt;{p.schema.format}&gt;</span>
                        )}
                        {p.required && <span className="text-xs text-red-400">required</span>}
                        {p.schema?.default !== undefined && (
                          <span className="text-xs text-gray-400 font-mono">default: {JSON.stringify(p.schema.default)}</span>
                        )}
                      </div>
                      {p.description && (
                        <p className="text-xs text-gray-400 whitespace-pre-wrap leading-relaxed">{p.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {requestBody && (
              <Section title="Request Body">
                {requestBody.required && (
                  <span className="text-xs text-red-400 mb-2 block">required</span>
                )}
                {Object.entries(requestBody.content ?? {}).map(([mediaType, mediaObj]) => (
                  <div key={mediaType}>
                    <p className="text-xs text-gray-400 font-mono mb-2">{mediaType}</p>
                    {mediaObj.schema && (
                      <SchemaViewer schema={mediaObj.schema as Parameters<typeof SchemaViewer>[0]["schema"]} />
                    )}
                  </div>
                ))}
              </Section>
            )}

            {Object.keys(responses).length > 0 && (
              <Section title="Responses">
                <div className="space-y-4">
                  {Object.entries(responses).map(([status, res]) => {
                    const schema = res.content?.["application/json"]?.schema;
                    return (
                      <div key={status}>
                        <div className="flex items-center gap-3 mb-2">
                          <span className={`text-xs font-bold px-2 py-0.5 rounded ${STATUS_COLOR(status)}`}>
                            {status}
                          </span>
                          <span className="text-sm text-gray-600">{res.description}</span>
                        </div>
                        {schema && (
                          <SchemaViewer schema={schema as Parameters<typeof SchemaViewer>[0]["schema"]} />
                        )}
                      </div>
                    );
                  })}
                </div>
              </Section>
            )}
          </div>
        </TabsContent>

        <TabsContent value="guide">
          <div className="mt-4 text-sm text-gray-500">
            Chưa có hướng dẫn cho endpoint này.
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
