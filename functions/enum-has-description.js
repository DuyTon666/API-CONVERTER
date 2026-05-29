export default function(targetVal, opts, context) {
  if (!targetVal || !targetVal.enum) {
    return [];
  }

  if (!targetVal.description) {
    return [
      {
        message: 'Enum phải có description.',
        path: [...context.path, 'description'],
      },
    ];
  }

  return [];
}
