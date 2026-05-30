export default function (schema, _opts, context) {
  const errors = [];

  if (!schema.properties) return errors;

  for (const [propName, propSchema] of Object.entries(schema.properties)) {
    if (!propSchema.description || propSchema.description.trim() === "") {
      errors.push({
        message: `Property "${propName}" thiếu description.`,
        path: [...context.path, "properties", propName],
      });
    }
  }

  return errors;
}