import React from 'react';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import {
  clearOfflineCopy,
  currentOfflineCopy,
  saveOfflineCopy,
  subscribeOffline,
  type OfflineCopy,
} from '../src/pwa/offline';
import { PwaStatus } from '../src/pwa/PwaStatus';

const copy = (over: Partial<OfflineCopy> = {}): OfflineCopy => ({
  user_id: 7,
  resource: 'students',
  fetched_at: '',
  expires_at: '',
  truncated: false,
  records: [{ display_name: 'Asha', student_number: 'S1' }],
  ...over,
});

describe('offline copy store', () => {
  beforeEach(() => clearOfflineCopy());
  it('stamps, scopes by user, and notifies subscribers', () => {
    const seen = vi.fn();
    const off = subscribeOffline(seen);
    saveOfflineCopy(copy());
    expect(seen).toHaveBeenCalled();
    const stored = currentOfflineCopy(7)!;
    expect(stored.fetched_at).not.toBe('');
    expect(Date.parse(stored.expires_at)).toBeGreaterThan(Date.now());
    expect(currentOfflineCopy(8)).toBeNull();
    expect(currentOfflineCopy(undefined)).toBeNull();
    off();
    seen.mockClear();
    clearOfflineCopy();
    expect(seen).not.toHaveBeenCalled();
    expect(currentOfflineCopy(7)).toBeNull();
  });
  it('drops expired copies and reads from storage after memory is lost', () => {
    saveOfflineCopy(copy({ expires_at: new Date(Date.now() - 1000).toISOString(), fetched_at: new Date().toISOString() }));
    expect(currentOfflineCopy(7)).toBeNull();
    saveOfflineCopy(copy());
    window.dispatchEvent(new Event('online'));
    expect(currentOfflineCopy(7)).toBeNull();
    window.localStorage.setItem('sims.offline-copy.v1', JSON.stringify({ ...copy(), expires_at: new Date(Date.now() + 60000).toISOString(), fetched_at: new Date().toISOString() }));
    expect(currentOfflineCopy(7)?.resource).toBe('students');
  });
  it('tolerates unreadable or unavailable storage', () => {
    clearOfflineCopy();
    window.localStorage.setItem('sims.offline-copy.v1', '{not json');
    expect(currentOfflineCopy(7)).toBeNull();
    const get = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota');
    });
    const rm = vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(() => saveOfflineCopy(copy())).not.toThrow();
    expect(() => clearOfflineCopy()).not.toThrow();
    window.dispatchEvent(new Event('sims-session-expired'));
    get.mockRestore();
    rm.mockRestore();
  });
});

describe('PwaStatus', () => {
  afterEach(() => {
    cleanup();
    clearOfflineCopy();
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
  });

  it('shows the offline gate with a saved read-only copy and clears it', async () => {
    saveOfflineCopy(copy({ truncated: true }));
    render(<PwaStatus userId={7} />);
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    expect(await screen.findByText('You are offline')).toBeInTheDocument();
    expect(screen.getByText(/display name: Asha/)).toBeInTheDocument();
    expect(screen.getByText('First 100 records only.')).toBeInTheDocument();
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false });
    fireEvent.click(screen.getByRole('button', { name: 'Check connection' }));
    expect(screen.getByText('You are offline')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Clear offline copy' }));
    await waitFor(() => expect(screen.queryByText(/Saved students/)).not.toBeInTheDocument());
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
    fireEvent.click(screen.getByRole('button', { name: 'Check connection' }));
    await waitFor(() => expect(screen.queryByText('You are offline')).not.toBeInTheDocument());
  });

  it('starts offline when the browser is offline and returns online on event', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false });
    render(<PwaStatus />);
    expect(await screen.findByText('You are offline')).toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new Event('online'));
    });
    await waitFor(() => expect(screen.queryByText('You are offline')).not.toBeInTheDocument());
  });

  it('offers installation and reports failures', async () => {
    render(<PwaStatus userId={1} />);
    const prompt = vi.fn().mockResolvedValue(undefined);
    const offer = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), { prompt, userChoice: Promise.resolve({ outcome: 'accepted' }) });
    act(() => {
      window.dispatchEvent(offer);
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Install' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Install' })).not.toBeInTheDocument());
    const failing = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), { prompt: vi.fn().mockRejectedValue(new Error('no')), userChoice: Promise.resolve({ outcome: 'dismissed' }) });
    act(() => {
      window.dispatchEvent(failing);
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Install' }));
    expect(await screen.findByText(/Installation could not be started/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    act(() => {
      window.dispatchEvent(new Event('beforeinstallprompt', { cancelable: true }));
      window.dispatchEvent(new Event('appinstalled'));
    });
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Install' })).not.toBeInTheDocument());
  });

  it('clears an expiring offline copy via its own timer', async () => {
    vi.useFakeTimers();
    saveOfflineCopy(copy({ fetched_at: new Date().toISOString(), expires_at: new Date(Date.now() + 1000).toISOString() }));
    render(<PwaStatus userId={7} />);
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(currentOfflineCopy(7)).toBeNull();
    vi.useRealTimers();
  });
});

describe('PwaStatus service worker updates', () => {
  it('registers in production and applies a waiting update', async () => {
    vi.stubEnv('PROD', true);
    vi.resetModules();
    const listeners: Record<string, () => void> = {};
    const waiting = { postMessage: vi.fn() };
    const reg = {
      waiting,
      installing: { addEventListener: vi.fn((_: string, fn: () => void) => fn()) },
      addEventListener: vi.fn((name: string, fn: () => void) => {
        listeners[name] = fn;
      }),
    };
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: { register: vi.fn().mockResolvedValue(reg), controller: {}, addEventListener: vi.fn((_: string, fn: () => void) => fn()) },
    });
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValue(true);
    const { PwaStatus: Prod } = await import('../src/pwa/PwaStatus');
    render(<Prod userId={1} />);
    const update = await screen.findByRole('button', { name: 'Update' });
    fireEvent.click(update);
    expect(waiting.postMessage).not.toHaveBeenCalled();
    fireEvent.click(update);
    expect(waiting.postMessage).toHaveBeenCalledWith({ type: 'SKIP_WAITING' });
    listeners.updatefound?.();
    confirm.mockRestore();
    cleanup();
    vi.unstubAllEnvs();
  });

  it('explains a failed registration', async () => {
    vi.stubEnv('PROD', true);
    vi.resetModules();
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { register: vi.fn().mockRejectedValue(new Error('x')) } });
    const { PwaStatus: Prod } = await import('../src/pwa/PwaStatus');
    render(<Prod />);
    expect(await screen.findByText(/Offline installation is unavailable/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    cleanup();
    vi.unstubAllEnvs();
  });
});

describe('auth transport (real session module)', () => {
  const server = setupServer();
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  afterEach(() => server.resetHandlers());
  let session: typeof import('../src/features/auth/session');
  let calls: string[];
  beforeEach(async () => {
    vi.resetModules();
    vi.stubEnv('VITE_API_BASE_URL', 'http://api.test/api/v1');
    session = await import('../src/features/auth/session');
    calls = [];
  });
  afterEach(() => vi.unstubAllEnvs());

  const csrf = () => http.get('http://api.test/api/v1/auth/csrf/', () => { calls.push('csrf'); return HttpResponse.json({ csrfToken: 'tok' }); });

  it('logs in, attaches the bearer token and retries once after a 401 refresh', async () => {
    let first = true;
    server.use(
      csrf(),
      http.post('http://api.test/api/v1/auth/login/', async ({ request }) => {
        expect(request.headers.get('x-csrftoken')).toBe('tok');
        expect(await request.json()).toEqual({ username: 'u', password: 'p', mfa: '1' });
        return HttpResponse.json({ access: 'A1', csrfToken: 'tok2' });
      }),
      http.post('http://api.test/api/v1/auth/refresh/', () => HttpResponse.json({ access: 'A2' })),
      http.get('http://api.test/api/v1/things/', ({ request }) => {
        const auth = request.headers.get('authorization');
        if (first) { first = false; return new HttpResponse(null, { status: 401 }); }
        return HttpResponse.json({ auth });
      }),
      http.post('http://api.test/api/v1/things/', async ({ request }) => HttpResponse.json({ type: request.headers.get('content-type') })),
    );
    await session.login('u', 'p', '1');
    const response = await session.authenticatedFetch('/things/');
    expect(await response.json()).toEqual({ auth: 'Bearer A2' });
    const json = await session.authenticatedFetch('/things/', { method: 'POST', body: JSON.stringify({ a: 1 }) });
    expect((await json.json()).type).toBe('application/json');
    const plain = await session.authenticatedFetch('/things/', { method: 'POST', body: 'not json', headers: { 'Content-Type': 'text/plain' } });
    expect((await plain.json()).type).toBe('text/plain');
    const odd = await session.authenticatedFetch('/things/', { method: 'POST', body: 'not json' });
    expect((await odd.json()).type).toContain('text/plain');
  });

  it('rejects absolute paths and failed bootstraps and logins', async () => {
    await expect(session.authenticatedFetch('https://evil.test/x')).rejects.toThrow(/relative API/);
    await expect(session.authenticatedFetch('//evil.test/x')).rejects.toThrow(/relative API/);
    server.use(http.get('http://api.test/api/v1/auth/csrf/', () => new HttpResponse(null, { status: 500 })));
    await expect(session.login('u', 'p')).rejects.toThrow(/initialize authentication/);
    server.use(csrf(), http.post('http://api.test/api/v1/auth/login/', () => new HttpResponse(null, { status: 400 })));
    await expect(session.login('u', 'p')).rejects.toThrow(/Unable to sign in/);
  });

  it('shares one refresh flight, reports a failed refresh, and logs out', async () => {
    let refreshes = 0;
    server.use(
      csrf(),
      http.post('http://api.test/api/v1/auth/refresh/', async () => { refreshes += 1; await new Promise((r) => setTimeout(r, 20)); return HttpResponse.json({ access: 'R' }); }),
    );
    const [a, b] = await Promise.all([session.refreshSession(), session.refreshSession()]);
    expect(a && b).toBe(true);
    expect(refreshes).toBe(1);
    server.use(http.post('http://api.test/api/v1/auth/refresh/', () => new HttpResponse(null, { status: 401 })));
    expect(await session.refreshSession()).toBe(false);
    server.use(http.post('http://api.test/api/v1/auth/refresh/', () => HttpResponse.error()));
    expect(await session.refreshSession()).toBe(false);
    server.use(http.post('http://api.test/api/v1/auth/logout/', () => new HttpResponse(null, { status: 204 })));
    await expect(session.logout()).resolves.toBeUndefined();
    server.use(http.post('http://api.test/api/v1/auth/logout/', () => new HttpResponse(null, { status: 500 })));
    await expect(session.logout()).rejects.toThrow(/sign-out failed/);
  });

  it('works without the Web Locks API', async () => {
    const locks = (navigator as unknown as { locks?: unknown }).locks;
    Object.defineProperty(navigator, 'locks', { configurable: true, value: undefined });
    server.use(csrf(), http.post('http://api.test/api/v1/auth/refresh/', () => HttpResponse.json({ access: 'Z' })));
    expect(await session.refreshSession()).toBe(true);
    Object.defineProperty(navigator, 'locks', { configurable: true, value: locks });
  });

  it('drops an in-flight refresh result after a newer login or logout', async () => {
    server.use(
      csrf(),
      http.post('http://api.test/api/v1/auth/refresh/', async () => { await new Promise((r) => setTimeout(r, 30)); return HttpResponse.json({ access: 'late' }); }),
      http.post('http://api.test/api/v1/auth/logout/', () => new HttpResponse(null, { status: 204 })),
    );
    const pending = session.refreshSession();
    await new Promise((r) => setTimeout(r, 5));
    const done = session.logout();
    expect(await pending).toBe(false);
    await done;
  });
});
