export type ScanModule = {
  name: string;
  total: number;
  by_extension: Record<string, number>;
};

export type ScanResult = {
  source_root: string;
  modules: ScanModule[];
  unassigned: { name: string }[];
};

export type ModuleInfo = {
  name: string;
  status: string;
  file_count: number;
  endpoint_count: number;
  last_import_at: string | null;
  last_import_status: string | null;
  created_at: string | null;
};

export type ModuleListResult = {
  modules: ModuleInfo[];
  summary: { total: number; by_status: Record<string, number> };
};

export type SuggestionItem = {
  file: string;
  method?: string;
  endpoint?: string;
  service_in_doc?: string;
  suggested_module?: string;
  final_module?: string;
  confidence_score?: number;
  confidence_label?: string;
  approval_status: string;
  approved_module?: string | null;
  conflict?: boolean;
};

export type SuggestionsResult = {
  exists: boolean;
  source_root?: string;
  total?: number;
  items: SuggestionItem[];
  summary: Record<string, number>;
  // File backend xác định là bị bỏ qua khi duyệt (vd: lỗi parse, thiếu module) — xem
  // _skip_reason trong backend/routers/modules.py.
  skipped?: SkippedApproval[];
};

export type SkippedApproval = {
  file: string;
  reason: string;
};

export type AppliedItem = { file: string; module: string; action: string };
export type SkippedItem = { file: string; skip_reason: string };
export type ApplyResult = {
  applied: AppliedItem[];
  skipped: SkippedItem[];
};

export type ImportModuleProgress = {
  name: string;
  status: "pending" | "running" | "done" | "error";
  total: number;
  success: number;
  failed: number;
  skipped: number;
  needs_review: number;
  error: string;
};

export type SpectralIssue = {
  severity: number;
  message: string;
  code: string;
  path: string[];
  range?: {
    start: { line: number; character: number };
    end: { line: number; character: number };
  };
};

export type RedoclyIssue = {
  severity: string;
  message: string;
  ruleId: string;
  location?: Array<{
    pointer?: string;
  }>;
  // Gắn thêm ở backend (_enrich_redocly_with_line_col) từ kết quả lint --format
  // checkstyle — không nằm trong location[], nằm trực tiếp trên issue.
  line?: number;
  column?: number;
};

export type DocsBuildResult = {
  bundle_ready: boolean;
  html_ready: boolean;
  spectral: SpectralIssue[];
  redocly: RedoclyIssue[];
};

export type DocsStatus = {
  bundle_ready: boolean;
  html_ready: boolean;
};

export type AiFixIssueRef = {
  source: "spectral" | "redocly";
  code: string;
  message: string;
};

// 1 vị trí lỗi đã được AI đề xuất sửa — đoạn gốc + đoạn đã sửa, để hiển thị
// diff kiểu conflict (chưa áp dụng, chờ người dùng chọn 1 trong 3 lựa chọn).
export type AiFixPatch = {
  id: string;
  start_line: number;
  end_line: number;
  original_text: string;
  fixed_text: string;
  issues: AiFixIssueRef[];
};

// Lỗi không xác định được vị trí để sửa, hoặc AI sửa nhưng không hợp lệ — cần sửa tay.
export type AiFixUnresolved = AiFixIssueRef & {
  reason: string;
};

export type AiFixResult = {
  patches: AiFixPatch[];
  unresolved: AiFixUnresolved[];
  failed: AiFixUnresolved[];
};

export type AiFixResolution = "original" | "fixed" | "both";

// 1 field bị phát hiện xung đột giữa giá trị sửa tay (Form Editor) và giá trị
// pipeline vừa sinh lại khi import — xem backend/routers/modules.py
// (_resolve_manual_edits_after_import) và 3.build/reports/manual_edit_conflicts.json.
export type ManualEditConflict = {
  kind: "operation" | "schema";
  entityId: string;
  module: string;
  field: string;
  old_value: string;
  new_value: string;
  detected_at: string;
};

// Form Editor (OperationsFormEditor) — /docs/operations chỉ trả summary/description
// ở cấp operation, cộng parameters[].description/responses[].description.
export type OperationParameter = {
  name: string;
  in: string;
  description: string;
};

export type OperationResponseDescription = {
  code: string;
  description: string;
};

export type Operation = {
  operationId: string;
  method: string;
  path: string;
  tags: string[];
  summary: string;
  description: string;
  parameters: OperationParameter[];
  responses: OperationResponseDescription[];
};

export type OperationUpdatePayload = {
  operationId: string;
  summary: string;
  description: string;
  parameters: OperationParameter[];
  responses: OperationResponseDescription[];
};

export type OperationAiSuggestPayload = {
  operationId: string;
  method: string;
  path: string;
  summary: string;
  description: string;
  parameters: OperationParameter[];
  responses: OperationResponseDescription[];
  dataSchemas?: { request: SchemaGroup | null; response: SchemaGroup | null };
};

export type OperationAiSuggestResult = {
  summary?: string;
  description?: string;
  parameters?: OperationParameter[];
  responses?: OperationResponseDescription[];
  dataSchemas?: {
    request?: SchemaFieldUpdate[];
    response?: SchemaFieldUpdate[];
  };
};

// Sửa mô tả field trong schema (components/schemas) — mở rộng của Form Editor,
// nhúng vào từng operation card thay vì tab riêng (xem SchemaFieldsEditor.tsx).
export type SchemaFieldEntry = {
  path: string;
  label: string;
  depth: number;
  type: string;
  description: string;
  readOnly: boolean;
};

export type SchemaGroup = {
  schemaName: string;
  shared: boolean;
  fields: SchemaFieldEntry[];
  nested: SchemaGroup[];
};

export type OperationDataSchemas = {
  operationId: string;
  request: SchemaGroup | null;
  response: SchemaGroup | null;
};

export type SchemaFieldUpdate = {
  schemaName: string;
  path: string;
  description: string;
};

// 1 entry mã lỗi trong report review — xem 3.build/reports/errors/<module>/error_codes_review.json
// (backend/services/error_codes.py đọc thẳng file này, không đổi shape).
export type ErrorReviewEntry = {
  code: string;
  status: "new" | "duplicate_ok" | "conflict" | "needs_review" | string;
  matched_namespace: string | null;
  source_file: string;
  incoming: { http_status: string; category: string; message: string };
  existing_in_map?: { http_status: string; message: string } | null;
  resolution: {
    decision: string;
    approved_by: string;
    approved_at: string;
    new_code?: string;
  } | null;
};

export type ErrorReviewSummary = {
  total: number;
  new: number;
  duplicate_ok: number;
  conflict: number;
  needs_review: number;
  intra_batch_conflict: number;
  missing_http_status: number;
};

export type ErrorReviewReport = {
  summary: ErrorReviewSummary;
  entries: ErrorReviewEntry[];
};

// Kết quả POST /errors/{module}/apply — backend regex-parse từ stdout của
// apply_decisions() (2.pipeline), xem comment trong error_codes.py.
export type ErrorApplyResult = {
  applied: number;
  skipped: number;
  rejected: number;
  raw_output: string;
};
