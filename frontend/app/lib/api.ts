// Shared API base-URL helper.
// TODO(m10): pages currently normalize NEXT_PUBLIC_API_BASE_URL three different
// ways inline (trailing-slash drift). Migrate those call sites to API_BASE /
// apiUrl() here so there is a single source of truth. Migration is deferred
// because it needs a frontend build to verify.
export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim().replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

export function apiUrl(path: string): string {
  return API_BASE + (path.startsWith("/") ? path : "/" + path);
}
