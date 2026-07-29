import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import {
  getDeployBlockedReason,
  countLintIssues,
  isSupportedFile,
  formatExtensions,
  formatBytes,
  formatDate,
  formatRelativeTime,
  partitionFiles,
} from "./dashboard-format";
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
    expect(reason).toBe(
      "Bundle đang có 1 lỗi lint — sửa hết lỗi trước khi deploy",
    );
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

describe("isSupportedFile", () => {
  test("nhận .pdf và .docx", () => {
    expect(isSupportedFile("contract.pdf")).toBe(true);
    expect(isSupportedFile("contract.docx")).toBe(true);
  });

  test("không phân biệt hoa/thường", () => {
    expect(isSupportedFile("contract.PDF")).toBe(true);
    expect(isSupportedFile("contract.DOCX")).toBe(true);
  });

  test("từ chối định dạng không hỗ trợ", () => {
    expect(isSupportedFile("contract.zip")).toBe(false);
  });

  test("không bị lừa khi .pdf nằm giữa tên nhưng đuôi thật là .txt", () => {
    expect(isSupportedFile("notes.pdf.txt")).toBe(false);
  });

  test("chấp nhận tên file chỉ có phần mở rộng", () => {
    expect(isSupportedFile(".docx")).toBe(true);
  });
});

describe("formatExtensions", () => {
  test("format nhiều phần mở rộng cách nhau bởi dấu phẩy", () => {
    expect(formatExtensions({ ".pdf": 3, ".docx": 2 })).toBe(
      ".pdf: 3, .docx: 2",
    );
  });

  test("object rỗng trả về chuỗi rỗng", () => {
    expect(formatExtensions({})).toBe("");
  });
});

describe("formatBytes", () => {
  test("0 byte", () => {
    expect(formatBytes(0)).toBe("0 B");
  });

  test("dưới 1024 byte giữ nguyên đơn vị B", () => {
    expect(formatBytes(1023)).toBe("1023 B");
  });

  test("đúng 1024 byte lên KB", () => {
    expect(formatBytes(1024)).toBe("1 KB");
  });

  test("làm tròn KB", () => {
    expect(formatBytes(1536)).toBe("2 KB");
  });

  test("gần 1 MB nhưng chưa đủ vẫn hiển thị KB, không tự cuộn lên MB", () => {
    // hành vi thật của code hiện tại — không phải bug, chỉ lock lại bằng test
    expect(formatBytes(1048575)).toBe("1024 KB");
  });

  test("đúng 1 MB", () => {
    expect(formatBytes(1048576)).toBe("1.0 MB");
  });

  test("2.5 MB", () => {
    expect(formatBytes(2621440)).toBe("2.5 MB");
  });
});

describe("formatDate", () => {
  test("null trả về dấu gạch ngang", () => {
    expect(formatDate(null)).toBe("-");
  });

  test("ngày hợp lệ format theo vi-VN", () => {
    const value = "2026-07-20T10:30:00Z";
    const expected = new Date(value).toLocaleString("vi-VN");
    expect(formatDate(value)).toBe(expected);
  });

  test("chuỗi không phải ngày hợp lệ không throw — trả về 'Invalid Date' chứ không rơi vào nhánh catch", () => {
    expect(formatDate("not-a-date")).toBe(
      new Date("not-a-date").toLocaleString("vi-VN"),
    );
  });
});

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-20T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("null trả về em dash", () => {
    expect(formatRelativeTime(null)).toBe("—");
  });

  test("vừa xong (30 giây trước)", () => {
    const value = new Date(Date.now() - 30 * 1000).toISOString();
    expect(formatRelativeTime(value)).toBe("vừa xong");
  });

  test("59 phút trước", () => {
    const value = new Date(Date.now() - 59 * 60 * 1000).toISOString();
    expect(formatRelativeTime(value)).toBe("59 phút trước");
  });

  test("đúng 1 phút trước (biên dưới)", () => {
    const value = new Date(Date.now() - 60 * 1000).toISOString();
    expect(formatRelativeTime(value)).toBe("1 phút trước");
  });

  test("đúng 60 phút = 1 giờ trước (biên chuyển)", () => {
    const value = new Date(Date.now() - 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(value)).toBe("1 giờ trước");
  });

  test("23 giờ trước", () => {
    const value = new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(value)).toBe("23 giờ trước");
  });

  test("đúng 24 giờ = 1 ngày trước (biên chuyển)", () => {
    const value = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(value)).toBe("1 ngày trước");
  });

  test("29 ngày trước", () => {
    const value = new Date(
      Date.now() - 29 * 24 * 60 * 60 * 1000,
    ).toISOString();
    expect(formatRelativeTime(value)).toBe("29 ngày trước");
  });

  test("đúng 30 ngày thì chuyển sang hiển thị theo ngày cụ thể (toLocaleDateString)", () => {
    const value = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
    const expected = value.toLocaleDateString("vi-VN");
    expect(formatRelativeTime(value.toISOString())).toBe(expected);
  });

  test("chuỗi không phải ngày hợp lệ trả về chính giá trị gốc — khác formatDate", () => {
    expect(formatRelativeTime("not-a-date")).toBe("not-a-date");
  });

  test("đối chiếu formatDate và formatRelativeTime với cùng input không hợp lệ — 2 hàm xử lý khác nhau", () => {
    expect(formatRelativeTime("not-a-date")).toBe("not-a-date");
    expect(formatDate("not-a-date")).not.toBe("not-a-date");
  });
});

describe("partitionFiles", () => {
  test("toàn bộ file hợp lệ → rejectedMessage null", () => {
    const files = [{ name: "a.pdf" }, { name: "b.docx" }];
    const result = partitionFiles(files);
    expect(result.supported).toEqual(files);
    expect(result.rejected).toEqual([]);
    expect(result.rejectedMessage).toBeNull();
  });

  test("toàn bộ file không hợp lệ → rejectedMessage đúng nội dung template gốc", () => {
    const files = [{ name: "a.zip" }, { name: "b.exe" }];
    const result = partitionFiles(files);
    expect(result.supported).toEqual([]);
    expect(result.rejected).toEqual(files);
    expect(result.rejectedMessage).toBe(
      `Bỏ qua 2 file sai định dạng (chỉ nhân .pdf/.docx):
      a.zip, b.exe`,
    );
  });

  test("hỗn hợp file hợp lệ/không hợp lệ → giữ đúng thứ tự tương đối trong từng nhóm", () => {
    const files = [
      { name: "a.pdf" },
      { name: "x.zip" },
      { name: "b.docx" },
      { name: "y.exe" },
    ];
    const result = partitionFiles(files);
    expect(result.supported).toEqual([{ name: "a.pdf" }, { name: "b.docx" }]);
    expect(result.rejected).toEqual([{ name: "x.zip" }, { name: "y.exe" }]);
  });

  test("danh sách rỗng → cả 2 nhóm rỗng, rejectedMessage null", () => {
    const result = partitionFiles([]);
    expect(result.supported).toEqual([]);
    expect(result.rejected).toEqual([]);
    expect(result.rejectedMessage).toBeNull();
  });
});
