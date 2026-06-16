export const dynamic = "force-dynamic";

import path from "path";
import fs from "fs";
import yaml from "js-yaml";
import SwaggerView from "./SwaggerView";

export default function SwaggerPage() {
  const yamlPath = path.join(process.cwd(), "..", "dist", "openapi-bundled.yaml");
  let spec: Record<string, unknown> | null = null;

  try {
    const raw = fs.readFileSync(yamlPath, "utf-8");
    spec = yaml.load(raw) as Record<string, unknown>;
  } catch {
    // file chưa tồn tại hoặc lỗi parse
  }

  if (!spec) {
    return (
      <div className="h-screen flex flex-col items-center justify-center text-center px-8 bg-gray-50">
        <p className="text-gray-700 font-medium mb-1">Chưa có bundle OpenAPI</p>
        <p className="text-sm text-gray-400">
          Chạy build tài liệu từ Dashboard để tạo dist/openapi-bundled.yaml trước.
        </p>
      </div>
    );
  }

  return <SwaggerView spec={spec} />;
}