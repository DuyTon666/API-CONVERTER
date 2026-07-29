import { afterEach, describe, expect, test, vi } from "vitest";
import { apiFetch, formatFetchError, readErrorDetail } from "./client";

describe("formatFetchError", () => {
  test("TypeError bất kỳ → thông báo cố định về mất kết nối", () => {
    expect(formatFetchError(new TypeError("failed to fetch"))).toBe(
      "Không thể kết nối tới backend, kiểm tra server có đang chạy không",
    );
  });

  test("Error/RangeError thường → dùng .message", () => {
    expect(formatFetchError(new Error("lỗi cụ thể"))).toBe("lỗi cụ thể");
    expect(formatFetchError(new RangeError("vượt giới hạn"))).toBe(
      "vượt giới hạn",
    );
  });

  test("giá trị không phải Error → dùng fallback mặc định", () => {
    expect(formatFetchError("boom")).toBe("Lỗi kết nối backend");
    expect(formatFetchError(undefined)).toBe("Lỗi kết nối backend");
  });

  test("giá trị không phải Error → dùng fallback tùy biến nếu truyền vào", () => {
    expect(formatFetchError("boom", "Lỗi tùy biến")).toBe("Lỗi tùy biến");
  });
});

describe("readErrorDetail", () => {
  test("detail là object có message → lấy đúng message đó", async () => {
    const res = new Response(
      JSON.stringify({ detail: { message: "Không tìm thấy" } }),
      { status: 404, statusText: "Not Found" },
    );
    expect(await readErrorDetail(res)).toBe("Không tìm thấy");
  });

  test("detail là string → dùng thẳng string đó", async () => {
    const res = new Response(JSON.stringify({ detail: "Sai định dạng" }), {
      status: 400,
      statusText: "Bad Request",
    });
    expect(await readErrorDetail(res)).toBe("Sai định dạng");
  });

  test("detail là mảng (lỗi 422 validation) → rơi về fallback = statusText", async () => {
    const res = new Response(
      JSON.stringify({ detail: [{ msg: "field required" }] }),
      { status: 422, statusText: "Unprocessable Entity" },
    );
    expect(await readErrorDetail(res)).toBe("Unprocessable Entity");
  });

  test("detail là object nhưng thiếu message → fallback = statusText", async () => {
    const res = new Response(JSON.stringify({ detail: { code: "X" } }), {
      status: 500,
      statusText: "Internal Server Error",
    });
    expect(await readErrorDetail(res)).toBe("Internal Server Error");
  });

  test("body không phải JSON hợp lệ → fallback = statusText, không throw", async () => {
    const res = new Response("<html>not json</html>", {
      status: 502,
      statusText: "Bad Gateway",
    });
    expect(await readErrorDetail(res)).toBe("Bad Gateway");
  });
});

describe("apiFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("response ok → resolve về JSON đã parse", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ hello: "world" }), { status: 200 }),
        ),
    );
    await expect(apiFetch("/fake")).resolves.toEqual({ hello: "world" });
  });

  test("response not-ok → reject với đúng message từ readErrorDetail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Không có quyền" }), {
          status: 403,
          statusText: "Forbidden",
        }),
      ),
    );
    await expect(apiFetch("/fake")).rejects.toThrow("Không có quyền");
  });

  test("fetch reject thẳng bằng TypeError → không bị nuốt/bọc lại", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("network down")),
    );
    await expect(apiFetch("/fake")).rejects.toThrow(TypeError);
  });
});
