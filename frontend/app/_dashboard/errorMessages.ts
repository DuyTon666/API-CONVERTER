export const ERROR_MESSAGES: Record<string, string> = {
  // Điền mã lỗi muốn ghi đè chữ hiển thị ở đây, ví dụ:
  // BUNDLE_NOT_FOUND: "Chưa có tài liệu — bấm \"Build tài liệu\" ở card bên dưới trước nhé",
};

export function resolveErrorMessage(code: string | undefined, fallback: string): string {
  if (code && ERROR_MESSAGES[code]) return ERROR_MESSAGES[code];
  return fallback; // không override → dùng message gốc từ backend
}
