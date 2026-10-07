/**
 * Canonical helpers built on the single session store.
 * Transport (login/logout/authenticatedFetch) lives in features/auth/session
 * and the JSON envelope (request/ApiError/message) in
 * features/common-reference/api — both preserved byte-for-byte for the
 * CJS contract tests. This module adds shared helpers (idempotency, paging)
 * without creating a second token store.
 */
export {
  authenticatedFetch,
  login,
  logout,
  refreshSession,
} from '../features/auth/session';
export { ApiError, message, request } from '../features/common-reference/api';
import { request } from '../features/common-reference/api';

export function idempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
}

export type Page<T> = { count: number; next: string | null; results: T[] };

/** Fetch all pages (bounded) for small lookup collections. */
export async function allPages<T>(path: string, maxPages = 50): Promise<T[]> {
  const out: T[] = [];
  for (let page = 1; page <= maxPages; page += 1) {
    const sep = path.includes('?') ? '&' : '?';
    const data = await request<Page<T>>(`${path}${sep}page=${page}&page_size=100`);
    out.push(...data.results);
    if (!data.next) return out;
  }
  throw new Error('Too many records for this workspace. Narrow the selected scope.');
}
