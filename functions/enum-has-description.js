/**
 * Kiểm tra schema có enum phải có description.
 * Guard null-safe để tránh crash khi Spectral traverse node null (OpenAPI 3.1).
 */
const enumHasDescription = (targetVal) => {
  if (targetVal === null || typeof targetVal !== 'object') return;
  if (!Array.isArray(targetVal.enum)) return;
  if (!targetVal.description) {
    return [{ message: 'Schema có enum phải có description giải thích ý nghĩa.' }];
  }
};

export default enumHasDescription;