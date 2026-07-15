// Pastel token palette shared by the portal viewer (EndpointCard, PortalSearch,
// EndpointDetailDrawer). Values match the minimalist-ui pastel spec: washed-out,
// desaturated accents used only for method/status badges — never large surfaces.

export type PastelTone = {
  bg: string;
  text: string;
  solid: string;
  solidText: string;
};

export const METHOD_PASTEL: Record<string, PastelTone> = {
  GET: {
    bg: "bg-[#E1F3FE]",
    text: "text-[#1F6C9F]",
    solid: "bg-[#1F6C9F]",
    solidText: "text-white",
  },
  POST: {
    bg: "bg-[#EDF3EC]",
    text: "text-[#346538]",
    solid: "bg-[#346538]",
    solidText: "text-white",
  },
  PUT: {
    bg: "bg-[#FBF3DB]",
    text: "text-[#956400]",
    solid: "bg-[#956400]",
    solidText: "text-white",
  },
  PATCH: {
    bg: "bg-[#FBF3DB]",
    text: "text-[#956400]",
    solid: "bg-[#956400]",
    solidText: "text-white",
  },
  DELETE: {
    bg: "bg-[#FDEBEC]",
    text: "text-[#9F2F2D]",
    solid: "bg-[#9F2F2D]",
    solidText: "text-white",
  },
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

// Màu chip cho category của x-error-responses — cùng convention pastel với
// METHOD_PASTEL ở trên, nhưng chỉ cần bg/text (không cần solid vì chip nhỏ,
// không dùng làm nền lớn).
export type CategoryTone = { bg: string; text: string };

const CATEGORY_PASTEL: Record<string, CategoryTone> = {
  Auth: { bg: "bg-[#E1F3FE]", text: "text-[#1F6C9F]" },
  Input: { bg: "bg-[#F1EAFB]", text: "text-[#5B3FA0]" },
  Business: { bg: "bg-[#EDF3EC]", text: "text-[#346538]" },
  State: { bg: "bg-[#FBF3DB]", text: "text-[#956400]" },
  Validation: { bg: "bg-[#FCEAF1]", text: "text-[#9D174D]" },
  "Not Found": { bg: "bg-[#E7F6F8]", text: "text-[#0E7490]" },
};

// Category hiếm gặp (Compat, Concurrency, Rate Limit...) dùng chung 1 màu
// xám trung tính — cùng lý do đã áp dụng bên SwaggerView.tsx: tránh bịa 24
// màu riêng biệt gây loãng, chỉ tô màu cho nhóm hay gặp để mắt quét nhanh.
const CATEGORY_FALLBACK: CategoryTone = {
  bg: "bg-gray-100",
  text: "text-gray-600",
};

export function categoryTone(category: string): CategoryTone {
  return CATEGORY_PASTEL[category] ?? CATEGORY_FALLBACK;
}
