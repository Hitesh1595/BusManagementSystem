/** Drop null/undefined/empty values so ky doesn't serialize them as "undefined". */
export function cleanParams(
  params: Record<string, string | number | boolean | null | undefined>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      out[key] = String(value);
    }
  }
  return out;
}

export interface PageParams {
  limit?: number;
  offset?: number;
}
