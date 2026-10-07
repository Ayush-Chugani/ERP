import { request, ApiError, authenticatedFetch } from '../../lib/api-client';

export type Row = Record<string, unknown>;
export type Field = {
  name: string;
  label: string;
  required: boolean;
  default?: unknown;
  max: number | null;
  choices: [string, string][];
  kind: 'parent' | 'number' | 'text';
  parent: string | null;
  reference: boolean;
};
export type Resource = {
  path: string;
  title: string;
  id: string;
  parent: string | null;
  fields: Field[];
  can_create: boolean;
  can_manage: boolean;
  count: number;
};

export class OrganizationError extends Error {
  constructor(message: string, public details: Record<string, unknown> = {}) {
    super(message);
  }
}

function toOrgError(e: unknown): never {
  if (e instanceof ApiError) throw new OrganizationError(e.message, e.details);
  throw new OrganizationError(e instanceof Error ? e.message : 'Request failed.');
}

/** Fetch-based client (replaces axios divergence; same exports for tests). */
export const client = {
  async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    try {
      return await request<T>(path, { signal });
    } catch (e) {
      return toOrgError(e);
    }
  },
  async post<T>(path: string, body?: unknown): Promise<T> {
    try {
      return await request<T>(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      return toOrgError(e);
    }
  },
  /** Axios-style compatibility for OrganizationForm: client.request({url, method, data}). */
  async request<T>(config: { url: string; method?: string; data?: unknown; signal?: AbortSignal }): Promise<{ data: T }> {
    try {
      const data = await request<T>(config.url, {
        method: (config.method || 'GET').toUpperCase(),
        headers: config.data === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: config.data === undefined ? undefined : JSON.stringify(config.data),
        signal: config.signal,
      });
      return { data };
    } catch (e) {
      return toOrgError(e);
    }
  },
};

export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  // Preserve low-level behaviour tests rely on: direct authenticatedFetch,
  // envelope error mapping, session-expired dispatch.
  let response: Response;
  try {
    response = await authenticatedFetch(path, { signal });
  } catch {
    throw new OrganizationError(
      'Connection failed. Reload before retrying a write; its outcome may be uncertain.',
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('sims-session-expired'));
    throw new OrganizationError(data?.error?.message || 'Request failed.', data?.error?.details || {});
  }
  return data as T;
}

export function title(row: Row): string {
  const name = Object.keys(row).find((k) => k.endsWith('_name'));
  return String((name && row[name]) || (row as Record<string, unknown>).room_code || 'Record');
}
