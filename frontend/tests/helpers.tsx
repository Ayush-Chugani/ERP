import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@mui/material/styles';
import { render } from '@testing-library/react';
import { AuthProvider } from '../src/api/auth';
import { theme } from '../src/theme';

export type Handler = (url: URL, init: RequestInit) => { status?: number; body?: unknown };
export type Routes = Record<string, Handler | { status?: number; body?: unknown }>;

/** Replace fetch with an in-memory API. Keys are "METHOD /path" (without /api/v1). */
export function mockApi(routes: Routes) {
  const calls: { method: string; path: string; init: RequestInit }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), 'http://localhost');
    const path = url.pathname.replace(/^\/api\/v1/, '');
    const method = (init.method || 'GET').toUpperCase();
    calls.push({ method, path, init });
    const hit = routes[`${method} ${path}`];
    if (!hit) return new Response(JSON.stringify({ error: { code: 'not_found', message: 'Not found.', details: {} } }), { status: 404 });
    const out = typeof hit === 'function' ? hit(url, init) : hit;
    const status = out.status ?? 200;
    return new Response(status === 204 ? null : JSON.stringify(out.body ?? {}), { status, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fn);
  return { fn, calls };
}

export const ME = {
  user_id: 1, username: 'registrar', email: 'r@example.org', full_name: 'Rekha Registrar', is_superuser: false,
  must_change_password: false, mfa_enabled: false, roles: ['REGISTRAR'], permissions: ['STUDENT.ALL.READ', 'IAM.ALL.READ'],
  access_modules: ['STUDENT'], student_ids: [], employee_ids: [],
};

export const authRoutes: Routes = {
  'GET /auth/csrf': { body: { csrfToken: 't.sig' } },
  'POST /auth/refresh': { body: { access: 'tok-1', csrfToken: 't.sig' } },
  'GET /auth/me': { body: ME },
};

export function renderApp(ui: ReactNode, route = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ThemeProvider theme={theme}>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider>{ui}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}
