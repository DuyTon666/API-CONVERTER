import { afterEach, describe, expect, test } from "vitest";
import { ERROR_MESSAGES, resolveErrorMessage } from "./errorMessages";

// ERROR_MESSAGES đang là object rỗng trong code thật — test tự thêm override tạm
// rồi dọn lại ngay sau mỗi test để không ảnh hưởng các test khác.
afterEach(() => {
  for (const key of Object.keys(ERROR_MESSAGES)) {
    delete ERROR_MESSAGES[key];
  }
});

describe("resolveErrorMessage", () => {
  test("code undefined → dùng fallback", () => {
    expect(resolveErrorMessage(undefined, "Lỗi gốc")).toBe("Lỗi gốc");
  });

  test("code rỗng (falsy) → dùng fallback", () => {
    expect(resolveErrorMessage("", "Lỗi gốc")).toBe("Lỗi gốc");
  });

  test("code không có trong map → dùng fallback", () => {
    expect(resolveErrorMessage("KHONG_TON_TAI", "Lỗi gốc")).toBe("Lỗi gốc");
  });

  test("code có override trong map → dùng override, không dùng fallback", () => {
    ERROR_MESSAGES.SOME_CODE = "Thông báo tùy biến";
    expect(resolveErrorMessage("SOME_CODE", "Lỗi gốc")).toBe(
      "Thông báo tùy biến",
    );
  });

  test("override là chuỗi rỗng (falsy) → vẫn rơi về fallback, không trả chuỗi rỗng", () => {
    ERROR_MESSAGES.EMPTY_CODE = "";
    expect(resolveErrorMessage("EMPTY_CODE", "Lỗi gốc")).toBe("Lỗi gốc");
  });
});
