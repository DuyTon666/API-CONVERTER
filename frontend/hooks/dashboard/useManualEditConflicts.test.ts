import { describe, expect, test } from "vitest";
import { conflictKey } from "./useManualEditConflicts";
import { ManualEditConflict } from "@/types/dashboard";

// Fixture điền đủ mọi field bắt buộc của ManualEditConflict dù conflictKey chỉ đọc
// kind/entityId/field.
const base: ManualEditConflict = {
  kind: "schema",
  entityId: "User.email",
  module: "ticket",
  field: "description",
  old_value: "cũ",
  new_value: "mới",
  detected_at: "2026-07-20T10:00:00Z",
};

describe("conflictKey", () => {
  test("format đúng: kind:entityId::field", () => {
    expect(conflictKey(base)).toBe("schema:User.email::description");
  });

  test("đổi kind (giữ entityId/field) → key khác", () => {
    const other: ManualEditConflict = { ...base, kind: "operation" };
    expect(conflictKey(other)).not.toBe(conflictKey(base));
  });

  test("đổi entityId → key khác", () => {
    const other: ManualEditConflict = { ...base, entityId: "User.name" };
    expect(conflictKey(other)).not.toBe(conflictKey(base));
  });

  test("đổi field → key khác", () => {
    const other: ManualEditConflict = { ...base, field: "summary" };
    expect(conflictKey(other)).not.toBe(conflictKey(base));
  });
});
