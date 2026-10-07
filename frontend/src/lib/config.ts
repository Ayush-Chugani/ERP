/**
 * Central frontend configuration.
 * Single source of truth for API base, pagination and app metadata.
 * Backend contract: relative `/api/v1` in production (same-origin, no CORS).
 * Vite proxies `/api` -> Django in dev. Optional VITE_API_BASE_URL override for tests.
 */
export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const APP_NAME = 'SIMS';
export const APP_SUBTITLE = 'Student Information Management System';

export const PAGINATION = {
  defaultPageSize: 25,
  maxPageSize: 100,
  pageSizeOptions: [10, 25, 50, 100],
} as const;

export const SEARCH_DEBOUNCE_MS = 250;
export const OFFLINE_COPY_TTL_MS = 5 * 60 * 1000;

export type ApiEnvelopeError = {
  error: { code: string; message: string; details: unknown };
};

export function isEnvelope(data: unknown): data is ApiEnvelopeError {
  if (typeof data !== 'object' || data === null) return false;
  const err = (data as Record<string, unknown>).error;
  if (typeof err !== 'object' || err === null) return false;
  return typeof (err as Record<string, unknown>).message === 'string';
}
