import type { Operation } from "./page";

const METHOD_COLOR: Record<string, string> = {
  GET: "bg-blue-100 text-blue-700",
  POST: "bg-green-100 text-green-700",
  PUT: "bg-yellow-100 text-yellow-700",
  PATCH: "bg-orange-100 text-orange-700",
  DELETE: "bg-red-100 text-red-700",
};

export default function EndpointCard({
  op,
  active = false,
  onClick,
}: {
  op: Operation;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white border rounded-lg px-5 py-4 cursor-pointer transition-shadow ${
        active
          ? "border-blue-400 shadow-md ring-1 ring-blue-200"
          : "border-gray-200 hover:shadow-sm"
      }`}
    >
      <div className="flex items-center gap-2 overflow-hidden">
        <span className={`text-xs font-bold px-2 py-0.5 rounded ${METHOD_COLOR[op.method] ?? "bg-gray-100 text-gray-600"}`}>
          {op.method}
        </span>
        <code className="truncate text-sm text-gray-700 font-mono">{op.path}</code>
        {op.tags.map((tag) => (
          <span key={tag} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">
            {tag}
          </span>
        ))}
      </div>
      {/* <p className="text-sm font-medium text-gray-800">{op.summary}</p> */}
      {op.operationId && (
        <p className="text-xs text-gray-400 mt-1 font-mono">{op.operationId}</p>
      )}
    </div>
  );
}
