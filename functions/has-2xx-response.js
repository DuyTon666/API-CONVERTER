// functions/has-2xx-response.js

export default function (targetVal, opts, context) {
  const responses = targetVal?.responses;

  if (!responses || typeof responses !== "object") {
    return [
      {
        message: "POST phải có ít nhất một response 2xx",
        path: [...context.path, "responses"],
      },
    ];
  }

  const has2xx = Object.keys(responses).some((status) => /^2\d\d$/.test(String(status)));

  if (!has2xx) {
    return [
      {
        message: "POST phải có ít nhất một response 2xx",
        path: [...context.path, "responses"],
      },
    ];
  }
}