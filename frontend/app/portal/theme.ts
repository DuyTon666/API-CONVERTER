// Pastel token palette shared by the portal viewer (EndpointCard, PortalSearch,
// EndpointDetailDrawer). Values match the minimalist-ui pastel spec: washed-out,
// desaturated accents used only for method/status badges — never large surfaces.

export type PastelTone = { bg: string; text: string; solid: string; solidText: string };

export const METHOD_PASTEL: Record<string, PastelTone> = {
  GET: { bg: "bg-[#E1F3FE]", text: "text-[#1F6C9F]", solid: "bg-[#1F6C9F]", solidText: "text-white" },
  POST: { bg: "bg-[#EDF3EC]", text: "text-[#346538]", solid: "bg-[#346538]", solidText: "text-white" },
  PUT: { bg: "bg-[#FBF3DB]", text: "text-[#956400]", solid: "bg-[#956400]", solidText: "text-white" },
  PATCH: { bg: "bg-[#FBF3DB]", text: "text-[#956400]", solid: "bg-[#956400]", solidText: "text-white" },
  DELETE: { bg: "bg-[#FDEBEC]", text: "text-[#9F2F2D]", solid: "bg-[#9F2F2D]", solidText: "text-white" },
};

export const METHOD_FALLBACK: PastelTone = {
  bg: "bg-gray-100",
  text: "text-gray-600",
  solid: "bg-gray-600",
  solidText: "text-white",
};

export function methodTone(method: string): PastelTone {
  return METHOD_PASTEL[method] ?? METHOD_FALLBACK;
}

export function statusTone(status: string): PastelTone {
  if (status.startsWith("2")) return METHOD_PASTEL.POST;
  if (status.startsWith("4")) return METHOD_PASTEL.PUT;
  if (status.startsWith("5")) return METHOD_PASTEL.DELETE;
  return METHOD_FALLBACK;
}

// Verbs that mutate state — try-it-out asks for one extra confirmation before
// firing these, since the portal calls the real production gateway directly.
export const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
