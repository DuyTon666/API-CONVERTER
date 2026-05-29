export default function (targetVal, opts, context) {
  if (!targetVal.requestBody)
    return;

  if (!targetVal.responses?.['400']) {
    return [
      {
        message: 'Operation có requestBody phải có response 400',
        path: [...context.path, 'responses'],
      }
    ];
  }
}