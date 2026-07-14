type SchemaObject = {
  type?: string | string[];
  format?: string;
  properties?: Record<string, SchemaObject>;
  items?: SchemaObject;
  allOf?: SchemaObject[];
  anyOf?: SchemaObject[];
  oneOf?: SchemaObject[];
  required?: string[];
  description?: string;
  example?: unknown;
  enum?: unknown[];
};

const TYPE_COLOR: Record<string, string> = {
  string: "text-green-600",
  integer: "text-blue-600",
  number: "text-blue-600",
  boolean: "text-purple-600",
  object: "text-orange-500",
  array: "text-pink-600",
  null: "text-gray-400",
};

function mergeComposed(schemas: SchemaObject[]): SchemaObject {
  const result: SchemaObject = { properties: {}, required: [] };
  for (const s of schemas) {
    if (s.properties) Object.assign(result.properties!, s.properties);
    if (s.required) result.required!.push(...s.required);
    if (s.type && !result.type) result.type = s.type;
    if (s.description && !result.description) result.description = s.description;
  }
  if (Object.keys(result.properties!).length === 0) delete result.properties;
  return result;
}

function getType(schema: SchemaObject): string {
  const composed = schema.allOf ?? schema.anyOf ?? schema.oneOf;
  if (composed) return getType(mergeComposed(composed));
  if (!schema.type) {
    if (schema.properties) return "object";
    if (schema.items) return "array";
    return "any";
  }
  if (Array.isArray(schema.type))
    return schema.type.filter((t) => t !== "null").join(" | ") || "null";
  return schema.type;
}

function SchemaRow({
  name,
  schema,
  required,
  depth,
}: {
  name: string;
  schema: SchemaObject;
  required: boolean;
  depth: number;
}) {
  const composed = schema.allOf ?? schema.anyOf ?? schema.oneOf;
  const resolved = composed ? mergeComposed(composed) : schema;
  const type = getType(resolved);
  const childProps = resolved.properties;
  const arrayChildProps = type === "array" && resolved.items
    ? (resolved.items.allOf ? mergeComposed(resolved.items.allOf) : resolved.items).properties
    : undefined;

  return (
    <div>
      <div
        className="flex items-start gap-3 py-3 border-b border-gray-100 last:border-0"
        style={{ paddingLeft: `${depth * 20 + 16}px`, paddingRight: "16px" }}
      >
        <span className="font-mono text-gray-800 text-sm min-w-[140px] shrink-0 pt-0.5">{name}</span>
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-sm font-semibold ${TYPE_COLOR[type] ?? "text-gray-500"}`}>
              {type}
              {resolved.format ? `<${resolved.format}>` : ""}
              {type === "array" && resolved.items ? `[${getType(resolved.items)}]` : ""}
            </span>
            {required && (
              <span className="text-sm text-red-400">required</span>
            )}
            {resolved.enum && (
              <span className="text-sm text-gray-400">
                enum: {resolved.enum.map((v) => JSON.stringify(v)).join(", ")}
              </span>
            )}
            {resolved.example !== undefined && (
              <span className="text-sm text-gray-400 font-mono">
                example: {JSON.stringify(resolved.example)}
              </span>
            )}
          </div>
          {resolved.description && (
            <span className="text-sm text-gray-400 whitespace-pre-wrap leading-relaxed">
              {resolved.description}
            </span>
          )}
        </div>
      </div>

      {childProps && (
        <SchemaProperties properties={childProps} required={resolved.required ?? []} depth={depth + 1} />
      )}
      {arrayChildProps && (
        <SchemaProperties
          properties={arrayChildProps}
          required={
            resolved.items
              ? (resolved.items.allOf ? mergeComposed(resolved.items.allOf) : resolved.items).required ?? []
              : []
          }
          depth={depth + 1}
        />
      )}
    </div>
  );
}

function SchemaProperties({
  properties,
  required,
  depth,
}: {
  properties: Record<string, SchemaObject>;
  required: string[];
  depth: number;
}) {
  return (
    <>
      {Object.entries(properties).map(([name, schema]) => (
        <SchemaRow
          key={name}
          name={name}
          schema={schema}
          required={required.includes(name)}
          depth={depth}
        />
      ))}
    </>
  );
}

export default function SchemaViewer({ schema }: { schema: SchemaObject }) {
  const composed = schema.allOf ?? schema.anyOf ?? schema.oneOf;
  const resolved = composed ? mergeComposed(composed) : schema;

  if (!resolved.properties) {
    const type = getType(resolved);
    return (
      <span className={`text-sm font-semibold ${TYPE_COLOR[type] ?? "text-gray-500"}`}>
        {type}
      </span>
    );
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      <SchemaProperties
        properties={resolved.properties}
        required={resolved.required ?? []}
        depth={0}
      />
    </div>
  );
}
