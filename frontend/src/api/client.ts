/**
 * The only way the UI talks to the backend: JSON over the versioned REST API.
 *
 * - The short-lived access token lives in memory only (never localStorage), so XSS cannot exfiltrate a long-lived secret.
 * - The refresh token is an HttpOnly cookie managed by the server; we only ever see the rotated access token.
 * - State-changing auth calls carry a CSRF token (double-submit cookie).
 */
export const API_BASE: string = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code = 'error',
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

let access: string | null = null;
let generation = 0;
let refreshFlight: Promise<boolean> | null = null;

function cookie(name: string): string {
  const hit = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`));
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : '';
}

async function csrfToken(): Promise<string> {
  const existing = cookie('sims_csrf');
  if (existing) return existing;
  const r = await fetch(`${API_BASE}/auth/csrf`, { credentials: 'include', cache: 'no-store' });
  if (!r.ok) throw new ApiError(r.status, 'Unable to initialise a secure session.');
  return (await r.json()).csrfToken as string;
}

async function parse(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function toError(status: number, data: unknown): ApiError {
  const env = (data as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null)?.error;
  return new ApiError(status, env?.message || `Request failed (${status}).`, env?.code, env?.details);
}

async function authPost(path: string, body?: unknown): Promise<Response> {
  const token = await csrfToken();
  return fetch(`${API_BASE}/auth/${path}`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

const locked = <T>(run: () => Promise<T>): Promise<T> =>
  typeof navigator !== 'undefined' && navigator.locks ? navigator.locks.request('sims-auth', run) : run();

export async function login(username: string, password: string, mfa?: string, portal?: string): Promise<{ must_change_password: boolean }> {
  generation++;
  access = null;
  const r = await locked(() => authPost('login', { username, password, ...(mfa ? { mfa } : {}), ...(portal ? { portal } : {}) }));
  const data = (await parse(r)) as { access?: string; must_change_password?: boolean } | null;
  if (!r.ok || !data?.access) throw toError(r.status, data);
  access = data.access;
  return { must_change_password: !!data.must_change_password };
}

export function refreshSession(): Promise<boolean> {
  if (!refreshFlight) {
    const mine = generation;
    refreshFlight = locked(async () => {
      const r = await authPost('refresh');
      const data = (await parse(r)) as { access?: string } | null;
      if (mine !== generation) return false;
      access = r.ok && data?.access ? data.access : null;
      return access !== null;
    })
      .catch(() => false)
      .finally(() => {
        refreshFlight = null;
      });
  }
  return refreshFlight;
}

export async function logout(): Promise<void> {
  generation++;
  access = null;
  await refreshFlight;
  await locked(() => authPost('logout'));
}

export function setAccessToken(token: string | null): void {
  access = token;
}

export type Query = Record<string, string | number | boolean | null | undefined>;

export function qs(query?: Query): string {
  if (!query) return '';
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== '') p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : '';
}

export type RequestOptions = { method?: string; body?: unknown; query?: Query; headers?: Record<string, string>; raw?: boolean };

export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  if (!path.startsWith('/')) throw new Error('API paths must start with /');
  const send = async () => {
    const headers = new Headers(opts.headers);
    if (opts.body !== undefined) headers.set('Content-Type', 'application/json');
    if (access) headers.set('Authorization', `Bearer ${access}`);
    return fetch(`${API_BASE}${path}${qs(opts.query)}`, {
      method: opts.method || 'GET',
      headers,
      credentials: 'include',
      cache: 'no-store',
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
  };
  let response: Response;
  try {
    response = await send();
    if (response.status === 401 && !path.startsWith('/auth/') && (await refreshSession())) response = await send();
  } catch {
    throw new ApiError(0, 'Unable to reach the server. Check your connection and try again.', 'network');
  }
  if (opts.raw) {
    if (!response.ok) throw toError(response.status, await parse(response));
    return (await response.text()) as T;
  }
  const data = await parse(response);
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('sims:session-expired'));
    throw toError(response.status, data);
  }
  return data as T;
}

export type UploadedFile = { file_object_id: number; name: string; size: number; mime_type: string; sha256: string };

/** Multipart upload to the private file store; returns the file id to attach to a record. */
export async function uploadFile(file: File, confidentiality = 'CONFIDENTIAL'): Promise<UploadedFile> {
  const send = () => {
    const form = new FormData();
    form.append('file', file);
    form.append('confidentiality', confidentiality);
    const headers = new Headers();
    if (access) headers.set('Authorization', `Bearer ${access}`);
    return fetch(`${API_BASE}/files`, { method: 'POST', body: form, headers, credentials: 'include' });
  };
  let r = await send();
  if (r.status === 401 && (await refreshSession())) r = await send();
  const data = await parse(r);
  if (!r.ok) throw toError(r.status, data);
  return data as UploadedFile;
}

export async function downloadFile(id: number, fallbackName = 'file'): Promise<void> {
  const headers = new Headers();
  if (access) headers.set('Authorization', `Bearer ${access}`);
  const r = await fetch(`${API_BASE}/files/${id}`, { headers, credentials: 'include', cache: 'no-store' });
  if (!r.ok) throw toError(r.status, await parse(r));
  const name = /filename="([^"]+)"/.exec(r.headers.get('Content-Disposition') || '')?.[1] || fallbackName;
  const url = URL.createObjectURL(await r.blob());
  Object.assign(document.createElement('a'), { href: url, download: name }).click();
  URL.revokeObjectURL(url);
}

export const errorMessage = (e: unknown): string => (e instanceof Error ? e.message : 'Something went wrong.');

export function fieldErrors(e: unknown): Record<string, string> {
  if (!(e instanceof ApiError)) return {};
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(e.details || {})) out[k] = Array.isArray(v) ? v.join(' ') : String(v);
  return out;
}
