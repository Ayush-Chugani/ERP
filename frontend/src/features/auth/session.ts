import { API_BASE } from '../../lib/api';
let access: string | null = null;
let csrf = '';
let refreshFlight: Promise<boolean> | null = null;
let generation = 0;
async function bootstrap() {
  const response = await fetch(`${API_BASE}/auth/csrf/`, { credentials: 'include', cache: 'no-store' });
  if (!response.ok) throw new Error('Unable to initialize authentication');
  csrf = (await response.json()).csrfToken;
}
async function post(path: string, body?: unknown) {
  if (!csrf) await bootstrap();
  return fetch(`${API_BASE}/auth/${path}/`, {method:'POST', credentials:'include', cache:'no-store',
    headers:{'Content-Type':'application/json','X-CSRFToken':csrf}, body:body === undefined ? undefined : JSON.stringify(body)});
}
async function coordinated<T>(run: () => Promise<T>): Promise<T> {
  return navigator.locks ? navigator.locks.request('sims-auth-refresh', run) : run();
}
export async function login(username: string, password: string, mfa?: string) {
  generation++; access = null;
  await refreshFlight;
  const current = generation;
  await coordinated(async () => {
  await bootstrap();
  const response = await post('login',{username,password,...(mfa?{mfa}:{})});
  if (!response.ok) throw new Error('Unable to sign in. Check your credentials and try again.');
  const data = await response.json();
  if (current === generation) { access=data.access; csrf=data.csrfToken; }
  });
}
export function refreshSession(): Promise<boolean> {
  if (!refreshFlight) {
    const current = generation;
    const run = async () => {
      // Cookies/CSRF may have rotated in another tab. Bootstrap under the browser lock.
      await bootstrap();
      const response = await post('refresh');
      if (current !== generation) return false;
      access = response.ok ? (await response.json()).access : null;
      return !!access;
    };
    refreshFlight = coordinated(run)
      .catch(() => { access=null; return false; }).finally(() => { refreshFlight=null; });
  }
  return refreshFlight;
}
export async function logout() {
  generation++; access=null;
  // Complete any refresh before logout so it cannot replace the revoked cookie afterward.
  await refreshFlight;
  await coordinated(async () => {
  await bootstrap();
  const response=await post('logout');
  if (!response.ok) throw new Error('Server sign-out failed. Retry while online.');
  });
}
export async function authenticatedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!path.startsWith('/') || path.startsWith('//')) throw new Error('Use a relative API resource path');
  const send = () => {
    const headers = new Headers(init.headers);
    // JSON callers share this transport. Preserve explicit media types and
    // let the browser supply multipart boundaries for FormData uploads.
    if (!headers.has('Content-Type') && typeof init.body === 'string') {
      try {
        JSON.parse(init.body);
        headers.set('Content-Type', 'application/json');
      } catch { /* Non-JSON string bodies retain the browser's media type. */ }
    }
    if (access) headers.set('Authorization', `Bearer ${access}`);
    return fetch(`${API_BASE}${path}`, {...init, headers, credentials:'include',cache:'no-store'});
  };
  const response=await send();
  if (response.status===401 && await refreshSession()) return send();
  return response;
}
