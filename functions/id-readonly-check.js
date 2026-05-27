/**
 * Spectral v6+ custom ruleset
 *
 * Rule: Phân biệt server ID vs client ID để enforce readOnly: true
 *
 *  - Schema trong `responses`   → server-generated ID → BẮT BUỘC readOnly: true
 *  - Schema trong `requestBody` → client-provided ID  → KHÔNG ĐƯỢC có readOnly: true
 */
import { createRulesetFunction } from "@stoplight/spectral-core";

// ─── Helper ───────────────────────────────────────────────────────────────────

/**
 * Nhận dạng ID field theo tên:
 *   "id", "user_id", "ticket_id", "supporterId", ...
 */
function isIdField(name) {
  return name === "id" || name.endsWith("_id") || name.endsWith("Id");
}

/**
 * Duyệt đệ quy properties của một schema (bao gồm nested object + array items).
 * Gọi callback(propSchema, propName, currentPath) cho từng field.
 */
function walkProperties(schema, basePath, callback) {
  if (!schema?.properties) return;

  for (const [propName, propSchema] of Object.entries(schema.properties)) {
    if (!propSchema || typeof propSchema !== "object") continue;

    const currentPath = [...basePath, "properties", propName];
    callback(propSchema, propName, currentPath);

    // Đệ quy vào nested object
    if (propSchema.type === "object") {
      walkProperties(propSchema, currentPath, callback);
    }

    // Đệ quy vào array → items
    if (propSchema.type === "array" && propSchema.items?.type === "object") {
      walkProperties(propSchema.items, [...currentPath, "items"], callback);
    }
  }
}

// ─── Rule 1: Response → server ID phải có readOnly: true ─────────────────────

const serverIdMustBeReadonly = createRulesetFunction(
  { input: null, options: null },
  function (responseContent, _opts, context) {
    const errors = [];
    if (!responseContent || typeof responseContent !== "object") return;

    for (const [mediaType, mediaObj] of Object.entries(responseContent)) {
      if (!mediaObj?.schema) continue;

      // Xử lý allOf (pattern: allOf: [StandardSuccess, { properties: { data: ... } }])
      const schemasToCheck = mediaObj.schema.allOf
        ? mediaObj.schema.allOf
        : [mediaObj.schema];

      for (const schema of schemasToCheck) {
        walkProperties(
          schema,
          [mediaType, "schema"],
          (propSchema, propName, path) => {
            if (!isIdField(propName)) return;
            if (propSchema.readOnly === true) return; // OK

            errors.push({
              message:
                `"${propName}" là server-generated ID trong response` +
                ` → phải thêm readOnly: true`,
              path,
            });
          },
        );
      }
    }

    return errors;
  },
);

// ─── Rule 2: RequestBody → client ID không được có readOnly: true ─────────────

const clientIdMustNotBeReadonly = createRulesetFunction(
  { input: null, options: null },
  function (requestContent, _opts, context) {
    const errors = [];
    if (!requestContent || typeof requestContent !== "object") return;

    for (const [mediaType, mediaObj] of Object.entries(requestContent)) {
      if (!mediaObj?.schema) continue;

      walkProperties(
        mediaObj.schema,
        [mediaType, "schema"],
        (propSchema, propName, path) => {
          if (!isIdField(propName)) return;
          if (propSchema.readOnly !== true) return; // OK

          errors.push({
            message:
              `"${propName}" là client-provided ID trong requestBody` +
              ` → không được có readOnly: true`,
            path,
          });
        },
      );
    }

    return errors;
  },
);

export { serverIdMustBeReadonly, clientIdMustNotBeReadonly };
