export default (input) => {
  const operation = input;

  const isPublic =
    Array.isArray(operation.security) &&
    operation.security.length === 0;

  if (isPublic) return;

  const errors = [];

  if (!operation.responses?.['401']) {
    errors.push({
      message: 'Endpoint private phải có response 401 (Unauthorized)',
    });
  } else if (!operation.responses['401'].description) {
    errors.push({
      message: 'Response 401 phải có description',
    });
  }

  if (!operation.responses?.['403']) {
    errors.push({
      message: 'Endpoint private phải có response 403 (Forbidden)',
    });
  } else if (!operation.responses['403'].description) {
    errors.push({
      message: 'Response 403 phải có description',
    });
  }

  return errors.length > 0 ? errors : undefined;
};
