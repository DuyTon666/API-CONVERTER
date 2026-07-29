import {
  AiFixPatch,
  AiFixResolution,
  AiFixUnresolved,
} from "@/types/dashboard";

// Ghép từng patch vào bundleContent theo lựa chọn của người dùng (giữ bản gốc/
// bản AI sửa/cả hai) — xử lý từ dòng cuối lên đầu để patch chưa xử lý không bị lệch
// số dòng. Lưu ý: không có validate chống patch chồng phạm vi (overlapping) — nếu
// patch chồng nhau, patch xử lý trước (start_line lớn hơn) làm co mảng lại, khiến
// deleteCount của patch xử lý sau (tính trên tọa độ gốc) có thể xóa lố ra ngoài
// phạm vi khai báo ban đầu. Đây là hành vi thật hiện tại, không phải bug cần sửa ở
// đây.
export function mergeAiFixPatches(
  bundleContent: string,
  patches: AiFixPatch[],
  resolutions: Record<string, AiFixResolution>,
): string {
  const lines = bundleContent.split("\n");
  const sorted = [...patches].sort((a, b) => b.start_line - a.start_line);
  for (const patch of sorted) {
    const resolution = resolutions[patch.id] ?? "fixed";
    const replacement =
      resolution === "original"
        ? patch.original_text
        : resolution === "both"
          ? `${patch.original_text}\n${patch.fixed_text}`
          : patch.fixed_text;
    lines.splice(
      patch.start_line,
      patch.end_line - patch.start_line + 1,
      ...replacement.split("\n"),
    );
  }
  return lines.join("\n");
}

// Thông báo hiển thị khi AI-fix không trả về patch nào để áp dụng.
export function buildEmptyAiFixMessage(
  patches: AiFixPatch[],
  unresolved: AiFixUnresolved[],
): string | null {
  if (patches.length > 0) return null;
  return unresolved.length > 0
    ? "AI không xác định được vị trí lỗi nào để sửa — cần sửa tay."
    : "Không có lỗi nào để sửa";
}

// Mặc định mọi patch mới nhận từ AI-fix đều ở trạng thái "fixed" (dùng bản AI sửa).
export function buildDefaultAiFixResolutions(
  patches: AiFixPatch[],
): Record<string, AiFixResolution> {
  return Object.fromEntries(
    patches.map((p) => [p.id, "fixed" as AiFixResolution]),
  );
}
