import { describe, expect, test } from "vitest";
import { mergeImportProgress } from "./dashboard-import-progress";
import { ImportModuleProgress } from "@/types/dashboard";

const makeProgress = (
  name: string,
  overrides: Partial<ImportModuleProgress> = {},
): ImportModuleProgress => ({
  name,
  status: "running",
  total: 10,
  success: 0,
  failed: 0,
  skipped: 0,
  needs_review: 0,
  error: "",
  ...overrides,
});

describe("mergeImportProgress", () => {
  test("module chưa có trong danh sách → thêm vào cuối, giữ nguyên phần tử cũ", () => {
    const prev = [makeProgress("ticket")];
    const incoming = makeProgress("order");
    const result = mergeImportProgress(prev, incoming);
    expect(result).toEqual([makeProgress("ticket"), makeProgress("order")]);
  });

  test("module đã có → thay đúng vị trí, không đổi thứ tự các phần tử khác", () => {
    const prev = [
      makeProgress("ticket", { success: 5 }),
      makeProgress("order"),
      makeProgress("admin"),
    ];
    const incoming = makeProgress("order", { success: 3, status: "done" });
    const result = mergeImportProgress(prev, incoming);
    expect(result).toEqual([
      makeProgress("ticket", { success: 5 }),
      makeProgress("order", { success: 3, status: "done" }),
      makeProgress("admin"),
    ]);
  });

  test("prev rỗng → trả về mảng chỉ có incoming", () => {
    const incoming = makeProgress("ticket");
    expect(mergeImportProgress([], incoming)).toEqual([incoming]);
  });

  test("không mutate mảng prev gốc — quan trọng vì dùng trong setState updater", () => {
    const prev = [makeProgress("ticket")];
    const snapshotBefore = [...prev];
    mergeImportProgress(prev, makeProgress("order"));
    expect(prev).toEqual(snapshotBefore);
  });
});
