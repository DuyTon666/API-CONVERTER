import type { Operation } from "./page";
import { methodTone } from "./theme";

export default function EndpointCard({
  op,
  active = false,
  onClick,
}: {
  op: Operation;
  active?: boolean;
  onClick?: () => void;
}) {
  const tone = methodTone(op.method);
  return (
    <div
      onClick={onClick}
      className={`relative bg-white border rounded-xl pl-5 pr-6 py-5 cursor-pointer transition-colors overflow-hidden ${
        active
          ? "border-[#1F6C9F]/30 ring-1 ring-[#1F6C9F]/15"
          : "border-[#EAEAEA] hover:border-[#D8D8D6]"
      }`}
    >
      <span className={`absolute left-0 top-0 bottom-0 w-[3px] ${tone.solid} ${active ? "opacity-100" : "opacity-40"}`} />
      <div className="flex items-center gap-2.5 overflow-hidden">
        <span className={`text-xs font-semibold tracking-wide px-2.5 py-1 rounded-full ${tone.bg} ${tone.text}`}>
          {op.method}
        </span>
        <code className="flex-1 min-w-0 truncate text-base text-[#2F3437] font-mono">{op.path}</code>
        {op.tags.length > 0 && (
          <div className="flex items-center gap-1.5 shrink-0">
            {op.tags.map((tag) => (
              <span key={tag} className="text-xs uppercase tracking-wide bg-[#F7F6F3] text-gray-500 px-2.5 py-1 rounded-full">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
      {op.operationId && (
        <p className="text-sm text-gray-400 mt-2 font-mono">{op.operationId}</p>
      )}
    </div>
  );
}
