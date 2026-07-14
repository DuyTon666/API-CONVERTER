type SchemaObject = Record<string, unknown>;

export function generateExample(schema: SchemaObject, depth = 0): unknown {
  if (depth > 5) return null;
  if (schema.example !== undefined) return schema.example;
  const composed = (schema.allOf ?? schema.anyOf ?? schema.oneOf) as SchemaObject[] | undefined;
  if (composed?.length) {
    const merged: SchemaObject = {};
    for (const s of composed) Object.assign(merged, s);
    return generateExample(merged, depth);
  }
  const type = schema.type as string | undefined;
  if (type === "object" || schema.properties) {
    const props = schema.properties as Record<string, SchemaObject> | undefined;
    if (!props) return {};
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(props)) result[k] = generateExample(v, depth + 1);
    return result;
  }
  if (type === "array") {
    const items = schema.items as SchemaObject | undefined;
    return items ? [generateExample(items, depth + 1)] : [];
  }
  if (type === "string")  return (schema.format as string) === "date-time" ? "2024-01-01T00:00:00Z" : (schema.enum as unknown[])?.[0] ?? "string";
  if (type === "integer" || type === "number") return 0;
  if (type === "boolean") return false;
  return null;
}
