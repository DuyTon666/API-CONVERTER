/**
 * Rule: Nếu operation có requestBody thì phải có response 400.
 * Nếu không có requestBody thì bỏ qua.
 */
export default function hasRequestBodyMustHave400(operation) {
  if (!operation.requestBody) return;

  if (!operation.responses?.['400']) {
    return [
      {
        message: 'Operation có requestBody phải có response 400 (Bad Request).',
      },
    ];
  }
}