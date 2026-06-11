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
};

export type RedoclyIssue = {
  severity: string;
  message: string;
  ruleId: string;
};

export type DocsBuildResult = {
  bundle_ready: boolean;
  html_ready: boolean;
  spectral: SpectralIssue[];
  redocly: RedoclyIssue[];
};
