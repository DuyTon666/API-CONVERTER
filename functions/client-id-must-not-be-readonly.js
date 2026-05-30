// functions/client-id-must-not-be-readonly.js

function isIdField(name) {
  return name === "id" || name.endsWith("_id") || name.endsWith("Id");
}

function walkProperties(schema, basePath, callback) {
  if (!schema?.properties) return;

  for (const [propName, propSchema] of Object.entries(schema.properties)) {
    if (!propSchema || typeof propSchema !== "object") continue;

    const currentPath = [...basePath, "properties", propName];
    callback(propSchema, propName, currentPath);

    // ✅ Đệ quy khi có properties, không cần type: object
    if (propSchema.properties) {
      walkProperties(propSchema, currentPath, callback);
    }

    // Đệ quy vào array → items
    if (propSchema.type === "array" && propSchema.items?.properties) {
      walkProperties(propSchema.items, [...currentPath, "items"], callback);
    }
  }
}

export default function (targetVal, opts, context) {
  const errors = [];

  for (const [mediaType, mediaObj] of Object.entries(targetVal)) {
    if (!mediaObj?.schema) continue;

    walkProperties(
      mediaObj.schema,
      [mediaType, "schema"],
      (propSchema, propName, path) => {
        if (!isIdField(propName)) return;
        if (propSchema.readOnly !== true) return;

        errors.push({
          message: `"${propName}" là client-provided ID trong requestBody → không được có readOnly: true`,
          path: [...context.path, ...path],
        });
      }
    );
  }

  return errors;
}