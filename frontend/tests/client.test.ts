import { api, ApiError, login, logout, qs, refreshSession, setAccessToken } from '../src/api/client';
import { mockApi } from './helpers';

beforeEach(() => {
  setAccessToken(null);
  document.cookie = 'sims_csrf=; Max-Age=0';
});

describe('api client', () => {
  it('builds query strings without empty values', () => {
    expect(qs({ a: 1, b: '', c: null, d: undefined, e: 'x y' })).toBe('?a=1&e=x+y');
    expect(qs({})).toBe('');
  });

  it('sends the bearer token and never stores it in web storage', async () => {
    const { calls } = mockApi({ 'POST /auth/login': { body: { access: 'secret-token' } }, 'GET /auth/csrf': { body: { csrfToken: 'c.s' } }, 'GET /ping': { body: { ok: true } } });
    await login('u', 'p');
    await api('/ping');
    const headers = new Headers(calls.find((c) => c.path === '/ping')!.init.headers);
    expect(headers.get('Authorization')).toBe('Bearer secret-token');
    expect(JSON.stringify({ ...localStorage })).not.toContain('secret-token');
    expect(JSON.stringify({ ...sessionStorage })).not.toContain('secret-token');
  });

  it('attaches the CSRF token to credential endpoints', async () => {
    const { calls } = mockApi({ 'GET /auth/csrf': { body: { csrfToken: 'c.s' } }, 'POST /auth/login': { body: { access: 'a' } } });
    await login('u', 'p');
    const post = calls.find((c) => c.path === '/auth/login')!;
    expect(new Headers(post.init.headers).get('X-CSRF-Token')).toBe('c.s');
    expect(post.init.credentials).toBe('include');
  });

  it('refreshes once on 401 and retries the request', async () => {
    let first = true;
    mockApi({
      'GET /auth/csrf': { body: { csrfToken: 'c.s' } },
      'POST /auth/refresh': { body: { access: 'new-token' } },
      'GET /data': (_u, init) => {
        const bearer = new Headers(init.headers).get('Authorization');
        if (first || bearer !== 'Bearer new-token') { first = false; return { status: 401, body: { error: { code: 'not_authenticated', message: 'expired', details: {} } } }; }
        return { body: { value: 7 } };
      },
    });
    expect(await api<{ value: number }>('/data')).toEqual({ value: 7 });
  });

  it('raises a session-expired event when refresh fails', async () => {
    mockApi({
      'GET /auth/csrf': { body: { csrfToken: 'c.s' } },
      'POST /auth/refresh': { status: 401, body: { error: { code: 'not_authenticated', message: 'Session expired.', details: {} } } },
      'GET /data': { status: 401, body: { error: { code: 'not_authenticated', message: 'expired', details: {} } } },
    });
    const expired = vi.fn();
    window.addEventListener('sims:session-expired', expired);
    await expect(api('/data')).rejects.toMatchObject({ status: 401 });
    expect(expired).toHaveBeenCalled();
    window.removeEventListener('sims:session-expired', expired);
  });

  it('maps the error envelope to ApiError with field details', async () => {
    mockApi({ 'POST /things': { status: 422, body: { error: { code: 'validation_error', message: 'Some values are invalid.', details: { name: ['Required.'] } } } } });
    const err = await api('/things', { method: 'POST', body: {} }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 422, code: 'validation_error', details: { name: ['Required.'] } });
  });

  it('reports network failures in plain language', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(api('/x')).rejects.toMatchObject({ status: 0, code: 'network' });
  });

  it('refuses absolute URLs so tokens cannot be sent to another origin', async () => {
    await expect(api('https://evil.example/steal')).rejects.toThrow();
  });

  it('logout clears the token', async () => {
    const { calls } = mockApi({ 'GET /auth/csrf': { body: { csrfToken: 'c.s' } }, 'POST /auth/logout': { status: 204 }, 'POST /auth/refresh': { status: 401, body: {} } });
    setAccessToken('t');
    await logout();
    expect(calls.some((c) => c.path === '/auth/logout')).toBe(true);
    expect(await refreshSession()).toBe(false);
  });
});
