import { describe, expect, test } from "vitest";
import { getDeployBlockedReason, countLintIssues } from "./dashboard-format";
import { DocsBuildResult } from "@/types/dashboard";

// Bundle giả không có lỗi lint nào — dùng làm baseline "mọi thứ ổn".
const cleanDocsResult: DocsBuildResult = {
  bundle_ready: true,
  html_ready: true,
  spectral: [],
  redocly: [],
};

describe("getDeployBlockedReason", () => {
  test("chặn khi chưa có bundle", () => {
    const reason = getDeployBlockedReason({
      bundleReady: false,
      docsResult: null,
      busy: false,
    });
    expect(reason).toBe("Chưa có bundle — hãy build tài liệu trước");
  });

  test("chặn khi có bundle nhưng chưa từng lint lần nào", () => {
    const reason = getDeployBlockedReason({
      bundleReady: true,
      docsResult: null,
      busy: false,
    });
    expect(reason).toBe('Hãy "Kiểm tra lỗi" ít nhất 1 lần trước khi deploy');
  });

  test("chặn khi lint còn lỗi severity error", () => {
    const docsResult: DocsBuildResult = {
      ...cleanDocsResult,
      spectral: [{ severity: 0 } as DocsBuildResult["spectral"][number]],
    };
    const reason = getDeployBlockedReason({
      bundleReady: true,
      docsResult,
      busy: false,
    });
    expect(reason).toBe("Bundle đang có 1 lỗi lint — sửa hết lỗi trước khi deploy");
  });

  test("chặn khi đang có thao tác khác chạy", () => {
    const reason = getDeployBlockedReason({
      bundleReady: true,
      docsResult: cleanDocsResult,
      busy: true,
    });
    expect(reason).toBe("Đang có thao tác khác chạy, đợi xong đã");
  });

  test("không chặn khi mọi điều kiện đều ổn", () => {
    const reason = getDeployBlockedReason({
      bundleReady: true,
      docsResult: cleanDocsResult,
      busy: false,
    });
    expect(reason).toBeNull();
  });
});

describe("countLintIssues", () => {
  test("đếm đúng số lỗi error/warn từ cả spectral và redocly", () => {
    const docsResult: DocsBuildResult = {
      ...cleanDocsResult,
      spectral: [
        { severity: 0 },
        { severity: 1 },
      ] as DocsBuildResult["spectral"],
      redocly: [
        { severity: "error" },
        { severity: "warning" },
      ] as DocsBuildResult["redocly"],
    };
    expect(countLintIssues(docsResult)).toEqual({ error: 2, warn: 2 });
  });
});
