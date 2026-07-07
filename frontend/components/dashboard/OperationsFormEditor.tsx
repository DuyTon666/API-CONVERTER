"use client";

import { useEffect, useState } from "react";
import { formatFetchError } from "@/lib/api/client";
import {
  aiSuggestOperation,
  fetchOperations,
  updateOperations,
} from "@/lib/api/dashboard/operations";
import {
  fetchSchemaFields,
  updateSchemaFields,
} from "@/lib/api/dashboard/schemaFields";
import { relintDocs } from "@/lib/api/dashboard/docs";
import SchemaFieldsEditor from "./SchemaFieldsEditor";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Operation,
  OperationParameter as Parameter,
  OperationResponseDescription as ResponseDescription,
  OperationDataSchemas,
  SchemaGroup,
  SchemaFieldUpdate,
} from "@/types/dashboard";

type EditState = {
  summary: string;
  description: string;
  parameters: Parameter[];
  responses: ResponseDescription[];
  // key ghép "${schemaName}::${path}" -> mô tả đã sửa cho field trong schema.
  schemaFields: Record<string, string>;
};

const METHOD_COLOR: Record<string, string> = {
  GET: "bg-blue-100 text-blue-700",
  POST: "bg-green-100 text-green-700",
  PUT: "bg-amber-100 text-amber-700",
  PATCH: "bg-orange-100 text-orange-700",
  DELETE: "bg-red-100 text-red-700",
};

// Làm phẳng 1 SchemaGroup (kể cả nested không shared) thành list field kèm
// schemaName riêng — mirror của schema_fields.flatten_schema_group() bên
// backend, dùng cho tính % hoàn chỉnh / kiểm tra dirty ở frontend.
function flattenSchemaGroup(
  group: SchemaGroup | null,
): (SchemaGroup["fields"][number] & { schemaName: string })[] {
  if (!group) return [];
  const flat = group.fields.map((f) => ({
    ...f,
    schemaName: group.schemaName,
  }));
  for (const nested of group.nested) {
    if (!nested.shared) flat.push(...flattenSchemaGroup(nested));
  }
  return flat;
}

// Áp edit (schemaFields record) lên 1 SchemaGroup, trả về group mới với
// description đã ghi đè theo edit đang chờ lưu — dùng cho payload AI-suggest
// (gửi state hiện tại, kể cả chưa lưu) và commit lại dataSchemas sau khi lưu.
function applyEditsToGroup(
  group: SchemaGroup | null,
  schemaFieldEdits: Record<string, string>,
): SchemaGroup | null {
  if (!group) return null;
  return {
    ...group,
    fields: group.fields.map((f) => ({
      ...f,
      description:
        schemaFieldEdits[`${group.schemaName}::${f.path}`] ?? f.description,
    })),
    nested: group.nested.map((n) => applyEditsToGroup(n, schemaFieldEdits)!),
  };
}

export default function OperationsFormEditor() {
  const backend = process.env.NEXT_PUBLIC_API_URL;

  const [operations, setOperations] = useState<Operation[]>([]);
  const [dataSchemas, setDataSchemas] = useState<OperationDataSchemas[]>([]);
  const [edits, setEdits] = useState<Record<string, EditState>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [relinting, setRelinting] = useState(false);
  const [savedCount, setSavedCount] = useState<number | null>(null);
  const [relintSummary, setRelintSummary] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState("all");

  const [aiSuggesting, setAiSuggesting] = useState<Record<string, boolean>>({});
  const [expandedOps, setExpandedOps] = useState<Record<string, boolean>>({});

  const toggleExpanded = (opId: string) => {
    setExpandedOps((prev) => ({ ...prev, [opId]: !prev[opId] }));
  };

  useEffect(() => {
    Promise.all([fetchOperations(backend!), fetchSchemaFields(backend!)])
      .then(([ops, schemas]) => {
        setOperations(ops);
        setDataSchemas(schemas);
        setError("");
      })
      .catch((e: unknown) => setError(formatFetchError(e, "Lỗi kết nối")))
      .finally(() => setLoading(false));
  }, [backend]);

  const dataSchemasByOpId = Object.fromEntries(
    dataSchemas.map((d) => [d.operationId, d]),
  );

  const getValue = (op: Operation, field: "summary" | "description") =>
    edits[op.operationId]?.[field] ?? op[field];

  const getCompleteness = (op: Operation) => {
    const params = edits[op.operationId]?.parameters ?? op.parameters;
    const responses = edits[op.operationId]?.responses ?? op.responses;
    const schemas = dataSchemasByOpId[op.operationId];
    const schemaFields = [
      ...flattenSchemaGroup(schemas?.request ?? null),
      ...flattenSchemaGroup(schemas?.response ?? null),
    ];
    const total = 2 + params.length + responses.length + schemaFields.length;
    let filled = 0;
    if (getValue(op, "summary")) filled++;
    if (getValue(op, "description")) filled++;
    filled += params.filter((p) => p.description).length;
    filled += responses.filter((r) => r.description).length;
    filled += schemaFields.filter((f) => {
      const key = `${f.schemaName}::${f.path}`;
      return edits[op.operationId]?.schemaFields?.[key] ?? f.description;
    }).length;
    return Math.round((filled / total) * 100);
  };

  // Base EditState của 1 operation: field nào đã có trong "prev" (state đang sửa
  // dở) thì giữ, chưa có thì lấy từ operation gốc — dùng chung cho mọi handler
  // thay đổi field, tránh lặp lại khối fallback này ở từng handler riêng.
  const baseEditState = (
    prev: Record<string, EditState>,
    opId: string,
  ): EditState => {
    const op = operations.find((o) => o.operationId === opId);
    return {
      summary: prev[opId]?.summary ?? op?.summary ?? "",
      description: prev[opId]?.description ?? op?.description ?? "",
      parameters: prev[opId]?.parameters ?? op?.parameters ?? [],
      responses: prev[opId]?.responses ?? op?.responses ?? [],
      schemaFields: prev[opId]?.schemaFields ?? {},
    };
  };

  const handleChange = (
    opId: string,
    field: "summary" | "description",
    value: string,
  ) => {
    setSavedCount(null);
    setRelintSummary(null);
    setEdits((prev) => ({
      ...prev,
      [opId]: { ...baseEditState(prev, opId), [field]: value },
    }));
  };

  const handleParamChange = (
    opId: string,
    paramName: string,
    value: string,
  ) => {
    setSavedCount(null);
    setRelintSummary(null);
    setEdits((prev) => {
      const base = baseEditState(prev, opId);
      return {
        ...prev,
        [opId]: {
          ...base,
          parameters: base.parameters.map((p) =>
            p.name === paramName ? { ...p, description: value } : p,
          ),
        },
      };
    });
  };

  const handleResponseChange = (opId: string, code: string, value: string) => {
    setSavedCount(null);
    setRelintSummary(null);
    setEdits((prev) => {
      const base = baseEditState(prev, opId);
      return {
        ...prev,
        [opId]: {
          ...base,
          responses: base.responses.map((r) =>
            r.code === code ? { ...r, description: value } : r,
          ),
        },
      };
    });
  };

  const handleSchemaFieldChange = (
    opId: string,
    schemaName: string,
    path: string,
    value: string,
  ) => {
    setSavedCount(null);
    setRelintSummary(null);
    setEdits((prev) => {
      const base = baseEditState(prev, opId);
      return {
        ...prev,
        [opId]: {
          ...base,
          schemaFields: {
            ...base.schemaFields,
            [`${schemaName}::${path}`]: value,
          },
        },
      };
    });
  };

  const handleAiSuggest = async (opId: string) => {
    setAiSuggesting((prev) => ({ ...prev, [opId]: true }));
    try {
      const op = operations.find((o) => o.operationId === opId);
      if (!op) return;
      const current = edits[opId];
      const schemas = dataSchemasByOpId[opId];
      const payload = {
        operationId: op.operationId,
        method: op.method,
        path: op.path,
        summary: current?.summary ?? op.summary,
        description: current?.description ?? op.description,
        parameters: current?.parameters ?? op.parameters,
        responses: current?.responses ?? op.responses,
        dataSchemas: {
          request: applyEditsToGroup(
            schemas?.request ?? null,
            current?.schemaFields ?? {},
          ),
          response: applyEditsToGroup(
            schemas?.response ?? null,
            current?.schemaFields ?? {},
          ),
        },
      };

      let suggestion;
      try {
        suggestion = await aiSuggestOperation(backend!, payload);
      } catch (e: unknown) {
        setError("Lỗi gợi ý AI: " + formatFetchError(e));
        return;
      }

      setSavedCount(null);
      setRelintSummary(null);

      const baseParams = current?.parameters ?? op.parameters;
      const baseResponses = current?.responses ?? op.responses;

      const mergedParams = baseParams.map((p) => {
        const found = suggestion.parameters?.find(
          (sp: Parameter) => sp.name === p.name,
        );
        return found ? { ...p, description: found.description } : p;
      });
      const mergedResponses = baseResponses.map((r) => {
        const found = suggestion.responses?.find(
          (sr: ResponseDescription) => sr.code === r.code,
        );
        return found ? { ...r, description: found.description } : r;
      });

      const suggestedSchemaFields = [
        ...(suggestion.dataSchemas?.request ?? []),
        ...(suggestion.dataSchemas?.response ?? []),
      ];
      const mergedSchemaFields = { ...(current?.schemaFields ?? {}) };
      for (const f of suggestedSchemaFields) {
        mergedSchemaFields[`${f.schemaName}::${f.path}`] = f.description;
      }

      setEdits((prev) => ({
        ...prev,
        [opId]: {
          summary: suggestion.summary ?? current?.summary ?? op.summary,
          description:
            suggestion.description ?? current?.description ?? op.description,
          parameters: mergedParams,
          responses: mergedResponses,
          schemaFields: mergedSchemaFields,
        },
      }));
    } finally {
      setAiSuggesting((prev) => ({ ...prev, [opId]: false }));
    }
  };

  const isDirty = (op: Operation) => {
    const e = edits[op.operationId];
    if (!e) return false;
    if (e.summary !== op.summary || e.description !== op.description)
      return true;
    if (
      e.parameters.some(
        (p, i) => p.description !== op.parameters[i].description,
      )
    )
      return true;
    if (
      e.responses.some((r, i) => r.description !== op.responses[i].description)
    )
      return true;

    const schemas = dataSchemasByOpId[op.operationId];
    const schemaFields = [
      ...flattenSchemaGroup(schemas?.request ?? null),
      ...flattenSchemaGroup(schemas?.response ?? null),
    ];
    if (
      schemaFields.some((f) => {
        const key = `${f.schemaName}::${f.path}`;
        return key in e.schemaFields && e.schemaFields[key] !== f.description;
      })
    )
      return true;

    return false;
  };

  const dirtyOps = operations.filter(isDirty);

  const doSave = async (): Promise<boolean> => {
    if (dirtyOps.length === 0) return true;
    setSaving(true);
    try {
      const payload = dirtyOps.map((op) => ({
        operationId: op.operationId,
        summary: edits[op.operationId]!.summary,
        description: edits[op.operationId]!.description,
        parameters: edits[op.operationId]!.parameters,
        responses: edits[op.operationId]!.responses,
      }));

      const schemaPayload: SchemaFieldUpdate[] = [];
      for (const op of dirtyOps) {
        const e = edits[op.operationId]!;
        const schemas = dataSchemasByOpId[op.operationId];
        const schemaFields = [
          ...flattenSchemaGroup(schemas?.request ?? null),
          ...flattenSchemaGroup(schemas?.response ?? null),
        ];
        for (const f of schemaFields) {
          const key = `${f.schemaName}::${f.path}`;
          if (key in e.schemaFields && e.schemaFields[key] !== f.description) {
            schemaPayload.push({
              schemaName: f.schemaName,
              path: f.path,
              description: e.schemaFields[key],
            });
          }
        }
      }

      let data;
      try {
        data = await updateOperations(backend!, payload);
        if (schemaPayload.length > 0) {
          await updateSchemaFields(backend!, schemaPayload);
        }
      } catch (e: unknown) {
        setError("Lỗi lưu: " + formatFetchError(e));
        return false;
      }

      // Commit edits into operations list, clear dirty state
      setOperations((prev) =>
        prev.map((op) => {
          const e = edits[op.operationId];
          return e
            ? {
                ...op,
                summary: e.summary,
                description: e.description,
                parameters: e.parameters,
                responses: e.responses,
              }
            : op;
        }),
      );
      // Commit schema field edits vào dataSchemas — nếu không, sau khi clear
      // edits thì % hoàn chỉnh/dirty sẽ tính lại dựa trên mô tả CŨ (trước lưu).
      if (schemaPayload.length > 0) {
        setDataSchemas((prev) =>
          prev.map((d) => {
            const e = edits[d.operationId];
            if (!e) return d;
            return {
              ...d,
              request: applyEditsToGroup(d.request, e.schemaFields),
              response: applyEditsToGroup(d.response, e.schemaFields),
            };
          }),
        );
      }
      setEdits({});
      setSavedCount(data.updated);
      return true;
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAndRelint = async () => {
    const ok = await doSave();
    if (!ok) return;
    setRelinting(true);
    try {
      const data = await relintDocs(backend!);
      const total = (data.spectral?.length ?? 0) + (data.redocly?.length ?? 0);
      setRelintSummary(total === 0 ? "Không có lỗi" : `${total} vấn đề`);
    } finally {
      setRelinting(false);
    }
  };

  // Tags
  const allTags = [
    ...new Set(
      operations.flatMap((op) =>
        op.tags.length ? op.tags : ["(Chưa có tag)"],
      ),
    ),
  ];

  // Filter
  const q = search.toLowerCase();
  const filtered = operations.filter((op) => {
    const matchSearch =
      !q ||
      op.path.toLowerCase().includes(q) ||
      getValue(op, "summary").toLowerCase().includes(q);
    const matchTag =
      tagFilter === "all" ||
      (tagFilter === "(Chưa có tag)"
        ? op.tags.length === 0
        : op.tags.includes(tagFilter));
    return matchSearch && matchTag;
  });

  const visibleTags = tagFilter === "all" ? allTags : [tagFilter];
  const grouped = Object.fromEntries(
    visibleTags.map((tag) => [
      tag,
      filtered.filter((op) =>
        tag === "(Chưa có tag)" ? op.tags.length === 0 : op.tags.includes(tag),
      ),
    ]),
  );

  if (loading) {
    return (
      <div className="p-6 text-sm text-gray-400">
        Đang tải danh sách operations...
      </div>
    );
  }
  if (error) {
    return <div className="p-6 text-sm text-red-600">{error}</div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search + filter */}
      <div className="px-4 py-3 border-b flex gap-2 shrink-0">
        <input
          type="text"
          placeholder="Tìm theo path hoặc tên..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
        />
        <Select value={tagFilter} onValueChange={setTagFilter}>
          <SelectTrigger className="min-w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tất cả ({operations.length})</SelectItem>
            {allTags.map((tag) => (
              <SelectItem key={tag} value={tag}>
                {tag} (
                {
                  operations.filter((o) =>
                    tag === "(Chưa có tag)"
                      ? o.tags.length === 0
                      : o.tags.includes(tag),
                  ).length
                }
                )
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Operations list */}
      <div className="flex-1 overflow-auto p-4 space-y-6">
        {visibleTags.map((tag) => {
          const ops = grouped[tag];
          if (!ops?.length) return null;
          return (
            <div key={tag}>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                🏷 {tag} · {ops.length} endpoint
              </p>
              <div className="space-y-3">
                {ops.map((op) => {
                  const dirty = isDirty(op);
                  const schemas = dataSchemasByOpId[op.operationId];
                  const pct = getCompleteness(op);
                  const expanded = !!expandedOps[op.operationId];
                  return (
                    <div
                      key={op.operationId}
                      className={`border rounded-xl transition-colors ${
                        dirty
                          ? "border-amber-300 bg-amber-50/40"
                          : "border-gray-200 bg-white"
                      }`}
                    >
                      {/* Header — bấm để thu gọn/mở rộng, giống Swagger UI */}
                      <div
                        onClick={() => toggleExpanded(op.operationId)}
                        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
                      >
                        <div className="flex items-center gap-2 min-w-0 flex-1 overflow-hidden">
                          <span className="text-gray-400 text-xs w-3 shrink-0">
                            {expanded ? "▾" : "▸"}
                          </span>
                          <span
                            className={`text-xs font-bold px-2 py-0.5 rounded shrink-0 ${
                              METHOD_COLOR[op.method] ??
                              "bg-gray-100 text-gray-600"
                            }`}
                          >
                            {op.method}
                          </span>
                          <code className="text-xs text-gray-500 font-mono shrink-0">
                            {op.path}
                          </code>
                          {!expanded && getValue(op, "summary") && (
                            <span className="text-xs text-gray-400 truncate min-w-0">
                              — {getValue(op, "summary")}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {dirty && (
                            <span
                              className="w-2 h-2 rounded-full bg-amber-500 shrink-0"
                              title="Có thay đổi chưa lưu"
                            />
                          )}
                          <span
                            className={`inline-flex items-center justify-center min-w-19 text-xs font-medium px-2 py-0.5 rounded-full ${
                              pct === 100
                                ? "bg-emerald-100 text-emerald-700"
                                : pct >= 50
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-rose-100 text-rose-700"
                            }`}
                          >
                            {pct}% hoàn chỉnh
                          </span>

                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAiSuggest(op.operationId);
                            }}
                            disabled={
                              !!aiSuggesting[op.operationId] || pct === 100
                            }
                            className="inline-flex items-center justify-center min-w-27 text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 hover:bg-indigo-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
                          >
                            {aiSuggesting[op.operationId]
                              ? "Đang gợi ý..."
                              : "✨ Gợi ý AI"}
                          </button>
                        </div>
                      </div>

                      {expanded && (
                        <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3">
                          {/* Summary */}
                          <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1">
                              Tên gọi <span className="text-red-400">*</span>
                            </label>
                            <input
                              type="text"
                              value={getValue(op, "summary")}
                              onChange={(e) =>
                                handleChange(
                                  op.operationId,
                                  "summary",
                                  e.target.value,
                                )
                              }
                              placeholder="Nhập tên gọi ngắn gọn..."
                              className={`w-full px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 ${
                                !getValue(op, "summary")
                                  ? "border-red-300 bg-red-50"
                                  : "border-gray-200"
                              }`}
                            />
                          </div>

                          {/* Description */}
                          <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1">
                              Mô tả chi tiết
                            </label>
                            <textarea
                              value={getValue(op, "description")}
                              onChange={(e) =>
                                handleChange(
                                  op.operationId,
                                  "description",
                                  e.target.value,
                                )
                              }
                              placeholder="Mô tả chi tiết API này làm gì..."
                              rows={2}
                              className="w-full px-3 py-1.5 border border-gray-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300"
                            />
                          </div>

                          {/* Parameters */}
                          {op.parameters.length > 0 && (
                            <div>
                              <label className="block text-xs font-medium text-gray-500 mb-1">
                                Tham số
                              </label>
                              <div className="space-y-2">
                                {(
                                  edits[op.operationId]?.parameters ??
                                  op.parameters
                                ).map((p) => (
                                  <div
                                    key={p.name}
                                    className="flex items-center gap-2"
                                  >
                                    <code className="text-xs text-gray-500 font-mono w-28 shrink-0 truncate">
                                      {p.name}
                                    </code>
                                    <input
                                      type="text"
                                      value={p.description}
                                      onChange={(e) =>
                                        handleParamChange(
                                          op.operationId,
                                          p.name,
                                          e.target.value,
                                        )
                                      }
                                      placeholder="Mô tả tham số..."
                                      className="flex-1 px-3 py-1 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                                    />
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Responses */}
                          {op.responses.length > 0 && (
                            <div>
                              <label className="block text-xs font-medium text-gray-500 mb-1">
                                Phản hồi
                              </label>
                              <div className="space-y-2">
                                {(
                                  edits[op.operationId]?.responses ??
                                  op.responses
                                ).map((p) => (
                                  <div
                                    key={p.code}
                                    className="flex items-center gap-2"
                                  >
                                    <code className="text-xs text-gray-500 font-mono w-28 shrink-0 truncate">
                                      {p.code}
                                    </code>
                                    <input
                                      type="text"
                                      value={p.description}
                                      onChange={(e) =>
                                        handleResponseChange(
                                          op.operationId,
                                          p.code,
                                          e.target.value,
                                        )
                                      }
                                      placeholder="Mô tả phản hồi..."
                                      className="flex-1 px-3 py-1 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                                    />
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Trường dữ liệu (schema) */}
                          {(schemas?.request || schemas?.response) && (
                            <div>
                              <label className="block text-xs font-medium text-gray-500 mb-1">
                                Trường dữ liệu
                              </label>
                              <div className="space-y-2">
                                {schemas?.request && (
                                  <div>
                                    <p className="text-xs text-gray-400 mb-1">
                                      Dữ liệu gửi lên
                                    </p>
                                    <SchemaFieldsEditor
                                      group={schemas.request}
                                      editedValues={
                                        edits[op.operationId]?.schemaFields ??
                                        {}
                                      }
                                      onChange={(schemaName, path, value) =>
                                        handleSchemaFieldChange(
                                          op.operationId,
                                          schemaName,
                                          path,
                                          value,
                                        )
                                      }
                                    />
                                  </div>
                                )}
                                {schemas?.response && (
                                  <div>
                                    <p className="text-xs text-gray-400 mb-1">
                                      Dữ liệu trả về
                                    </p>
                                    <SchemaFieldsEditor
                                      group={schemas.response}
                                      editedValues={
                                        edits[op.operationId]?.schemaFields ??
                                        {}
                                      }
                                      onChange={(schemaName, path, value) =>
                                        handleSchemaFieldChange(
                                          op.operationId,
                                          schemaName,
                                          path,
                                          value,
                                        )
                                      }
                                    />
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-12">
            Không tìm thấy endpoint nào.
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="border-t px-4 py-3 flex items-center gap-3 shrink-0">
        <div className="flex-1 flex items-center gap-3 text-xs">
          {dirtyOps.length > 0 && (
            <span className="text-amber-600 font-medium">
              {dirtyOps.length} thay đổi chưa lưu
            </span>
          )}
          {savedCount !== null && dirtyOps.length === 0 && (
            <span className="text-emerald-600">
              ✓ Đã lưu {savedCount} thay đổi
            </span>
          )}
          {relintSummary && (
            <span
              className={
                relintSummary === "Không có lỗi"
                  ? "text-emerald-600"
                  : "text-amber-600"
              }
            >
              · Kiểm tra: {relintSummary}
            </span>
          )}
        </div>
        <button
          onClick={doSave}
          disabled={saving || relinting || dirtyOps.length === 0}
          className="px-4 py-1.5 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 text-sm disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        <button
          onClick={handleSaveAndRelint}
          disabled={saving || relinting || dirtyOps.length === 0}
          className="px-4 py-1.5 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 text-sm disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {relinting ? "Đang kiểm tra..." : "Lưu & Kiểm tra lại"}
        </button>
      </div>
    </div>
  );
}
