 export default function(targetVal, opts, context) {
  const operation = targetVal;

  const isPublic =
    Array.isArray(operation.security) &&
    operation.security.length === 0;

  if (isPublic) return;

  const errors = [];

  if (!operation.responses?.['401']) {
    errors.push({
      message: 'Endpoint private phải có response 401 (Unauthorized)',
      path: [...context.path, 'responses']
    });
  } 

  if (!operation.responses?.['403']) {
    errors.push({
      message: 'Endpoint private phải có response 403 (Forbidden)',
      path: [...context.path, 'responses']
    });
  } 

  return errors.length > 0 ? errors : undefined;
};
