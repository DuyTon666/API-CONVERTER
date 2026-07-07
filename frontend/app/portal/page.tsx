export const dynamic = "force-dynamic";

import path from "path";
import fs from "fs";
import yaml from "js-yaml";
import PortalSearch from "./PortalSearch";

export type Operation = {
  method: string;
  path: string;
  operationId: string;
  summary: string;
  description: string;
  tags: string[];
  raw: Record<string, unknown>;
};

function resolveRefs(obj: unknown, spec: Record<string, unknown>, depth = 0): unknown {
  if (depth > 10) return obj;
  if (Array.isArray(obj)) return obj.map((item) => resolveRefs(item, spec, depth + 1));
  if (obj !== null && typeof obj === "object") {
    const record = obj as Record<string, unknown>;
    if (typeof record["$ref"] === "string" && record["$ref"].startsWith("#/")) {
      const parts = record["$ref"].slice(2).split("/");
      let resolved: unknown = spec;
      for (const part of parts) {
        if (resolved !== null && typeof resolved === "object") {
          resolved = (resolved as Record<string, unknown>)[part];
        } else return obj;
      }
      return resolveRefs(resolved, spec, depth + 1);
    }
    return Object.fromEntries(
      Object.entries(record).map(([k, v]) => [k, resolveRefs(v, spec, depth + 1)])
    );
  }
  return obj;
}

function extractOperations(spec: Record<string, unknown>): Operation[] {
  const operations: Operation[] = [];
  const methods = ["get", "post", "put", "patch", "delete"];
  const paths = (spec.paths ?? {}) as Record<string, Record<string, unknown>>;

  for (const [apiPath, pathItem] of Object.entries(paths)) {
    for (const method of methods) {
      const op = pathItem[method] as Record<string, unknown> | undefined;
      if (!op) continue;
      const resolved = resolveRefs(op, spec) as Record<string, unknown>;
      operations.push({
        method: method.toUpperCase(),
        path: apiPath,
        operationId: (resolved.operationId as string) ?? "",
        summary: (resolved.summary as string) ?? "",
        description: (resolved.description as string) ?? "",
        tags: (resolved.tags as string[]) ?? [],
        raw: resolved,
      });
    }
  }
  return operations;
}

export default function PortalPage() {
  const yamlPath = path.join(process.cwd(), "..", "dist", "openapi-bundled.yaml");
  let operations: Operation[] = [];
  let baseUrl = "";

  try {
    const raw = fs.readFileSync(yamlPath, "utf-8");
    const spec = yaml.load(raw) as Record<string, unknown>;
    operations = extractOperations(spec);
    const servers = spec.servers as { url?: string }[] | undefined;
    baseUrl = servers?.[0]?.url ?? "";
  } catch {
    // file chưa tồn tại hoặc lỗi parse
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#FBFBFA]">
      <PortalSearch operations={operations} baseUrl={baseUrl} />
    </div>
  );
}
