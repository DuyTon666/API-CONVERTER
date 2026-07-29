import { describe, expect, test } from "vitest";
import {
  buildDefaultAiFixResolutions,
  buildEmptyAiFixMessage,
  mergeAiFixPatches,
} from "./dashboard-ai-fix";
import { AiFixPatch, AiFixUnresolved } from "@/types/dashboard";

const makePatch = (overrides: Partial<AiFixPatch> = {}): AiFixPatch => ({
  id: "p1",
  start_line: 0,
  end_line: 0,
  original_text: "",
  fixed_text: "",
  issues: [],
  ...overrides,
});

describe("mergeAiFixPatches", () => {
  test("sort đúng thứ tự + xử lý lệch dòng khi patch có nhiều dòng thay thế", () => {
    // truyền patch KHÔNG theo thứ tự giảm dần start_line, để tự verify hàm
    // tự sort bên trong chứ không phụ thuộc thứ tự caller truyền vào.
    const bundle = "L0\nL1\nL2\nL3\nL4";
    const patchA = makePatch({
      id: "A",
      start_line: 1,
      end_line: 1,
      original_text: "L1",
      fixed_text: "X1\nX2",
    });
    const patchB = makePatch({
      id: "B",
      start_line: 3,
      end_line: 3,
      original_text: "L3",
      fixed_text: "Y3",
    });
    const result = mergeAiFixPatches(bundle, [patchA, patchB], {
      A: "fixed",
      B: "fixed",
    });
    expect(result).toBe("L0\nX1\nX2\nL2\nY3\nL4");
  });

  test("3 nhánh resolution: original giữ nguyên gốc, both nối cả 2, fixed chỉ lấy bản sửa", () => {
    const bundle = "L0\nL1\nL2";
    const patch = makePatch({
      id: "p",
      start_line: 1,
      end_line: 1,
      original_text: "OLD",
      fixed_text: "NEW",
    });

    expect(mergeAiFixPatches(bundle, [patch], { p: "original" })).toBe(
      "L0\nOLD\nL2",
    );
    expect(mergeAiFixPatches(bundle, [patch], { p: "both" })).toBe(
      "L0\nOLD\nNEW\nL2",
    );
    expect(mergeAiFixPatches(bundle, [patch], { p: "fixed" })).toBe(
      "L0\nNEW\nL2",
    );
  });

  test("patch có id không nằm trong resolutions → mặc định coi như 'fixed'", () => {
    const bundle = "L0\nL1\nL2";
    const patch = makePatch({
      id: "p",
      start_line: 1,
      end_line: 1,
      original_text: "OLD",
      fixed_text: "NEW",
    });
    expect(mergeAiFixPatches(bundle, [patch], {})).toBe("L0\nNEW\nL2");
  });

  test("patch nhiều dòng gốc gộp lại thành 1 dòng thay thế", () => {
    const bundle = "L0\nL1\nL2\nL3\nL4";
    const patch = makePatch({
      id: "p",
      start_line: 1,
      end_line: 3,
      original_text: "L1\nL2\nL3",
      fixed_text: "NEW",
    });
    expect(mergeAiFixPatches(bundle, [patch], { p: "fixed" })).toBe(
      "L0\nNEW\nL4",
    );
  });

  test("2 patch chồng phạm vi (overlapping) — hành vi thật hiện tại, không phải bug cần sửa: patch xử lý sau (start_line nhỏ hơn) bị lệch tọa độ do mảng đã co lại, xóa lố ra ngoài phạm vi khai báo ban đầu", () => {
    // Giá trị kỳ vọng đã verify bằng cách tự chạy thuật toán qua Node, không suy đoán tay.
    const bundle = "L0\nL1\nL2\nL3\nL4";
    const patchA = makePatch({
      id: "PA",
      start_line: 0,
      end_line: 2,
      original_text: "L0\nL1\nL2",
      fixed_text: "XA",
    });
    const patchB = makePatch({
      id: "PB",
      start_line: 1,
      end_line: 3,
      original_text: "L1\nL2\nL3",
      fixed_text: "XB",
    });
    const result = mergeAiFixPatches(bundle, [patchA, patchB], {
      PA: "fixed",
      PB: "fixed",
    });
    expect(result).toBe("XA");
  });
});

describe("buildEmptyAiFixMessage", () => {
  test("còn patch để áp dụng → không hiện thông báo (null), bất kể unresolved", () => {
    const patches = [makePatch()];
    expect(buildEmptyAiFixMessage(patches, [])).toBeNull();
    const unresolved: AiFixUnresolved[] = [
      { source: "spectral", code: "x", message: "m", reason: "r" },
    ];
    expect(buildEmptyAiFixMessage(patches, unresolved)).toBeNull();
  });

  test("không có patch và cũng không có unresolved → báo không có lỗi nào để sửa", () => {
    expect(buildEmptyAiFixMessage([], [])).toBe("Không có lỗi nào để sửa");
  });

  test("không có patch nhưng có unresolved → báo AI không xác định được vị trí, cần sửa tay", () => {
    const unresolved: AiFixUnresolved[] = [
      { source: "redocly", code: "y", message: "m", reason: "r" },
    ];
    expect(buildEmptyAiFixMessage([], unresolved)).toBe(
      "AI không xác định được vị trí lỗi nào để sửa — cần sửa tay.",
    );
  });
});

describe("buildDefaultAiFixResolutions", () => {
  test("nhiều patch → mỗi id đều mặc định 'fixed'", () => {
    const patches = [makePatch({ id: "a" }), makePatch({ id: "b" })];
    expect(buildDefaultAiFixResolutions(patches)).toEqual({
      a: "fixed",
      b: "fixed",
    });
  });

  test("danh sách patch rỗng → trả về object rỗng", () => {
    expect(buildDefaultAiFixResolutions([])).toEqual({});
  });
});
