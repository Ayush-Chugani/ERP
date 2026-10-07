import React from 'react';
import axe from 'axe-core';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

vi.mock('../src/features/auth/session', () => ({
  authenticatedFetch: (path: string, init?: RequestInit) => fetch('http://localhost/api/v1' + path, init),
  login: vi.fn(), logout: vi.fn(), refreshSession: async () => false,
}));
vi.mock('../src/features/identity-access/SupportBanner', () => ({ SupportBanner: () => null }));
vi.mock('../src/pwa/PwaStatus', () => ({ PwaStatus: () => null }));

import { AuthProvider } from '../src/lib/auth-context';
import { AppRouter } from '../src/app/router';
import { LoginPage } from '../src/app/pages/LoginPage';
import { getQueryClient } from '../src/lib/query';
import { QueryClientProvider } from '@tanstack/react-query';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterAll(() => server.close());
afterEach(() => { cleanup(); server.resetHandlers(); getQueryClient().clear(); });

const me = (user: object | null) =>
  server.use(
    http.get('http://localhost/api/v1/auth/me/', () => (user ? HttpResponse.json(user) : HttpResponse.json({}, { status: 401 }))),
    http.get('http://localhost/api/v1/people/students/', () => HttpResponse.json({ count: 3, results: [] })),
    http.get('http://localhost/api/v1/people/employees/', () => HttpResponse.json({ count: 2, results: [] })),
    http.get('http://localhost/api/v1/organization/departments/', () => HttpResponse.json({ count: 4, results: [] })),
    http.get('http://localhost/api/v1/organization/programmes/', () => HttpResponse.json({ count: 5, results: [] })),
  );

// jsdom has no layout engine, so colour-contrast is checked by design tokens elsewhere.
async function violations(container: HTMLElement) {
  const result = await axe.run(container, { rules: { 'color-contrast': { enabled: false }, region: { enabled: false } } });
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.html.slice(0, 80)).join(' | ')}`);
}

const wrap = (path: string, ui: React.ReactElement) => (
  <QueryClientProvider client={getQueryClient()}><AuthProvider><MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter></AuthProvider></QueryClientProvider>
);
const admin = { user_id: 1, username: 'admin', permissions: [], is_superuser: true, groups: [] };

describe('accessibility (axe)', () => {
  it('login page has no violations', async () => {
    me(null);
    const { container } = render(wrap('/login', <LoginPage />));
    await screen.findByRole('heading', { name: 'Sign in' });
    expect(await violations(container)).toEqual([]);
  });
  it('dashboard inside the shell has no violations', async () => {
    window.matchMedia = ((q: string) => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false })) as never;
    me(admin);
    const { container } = render(wrap('/dashboard', <AppRouter />));
    await screen.findByText(/Good (morning|afternoon|evening), admin/);
    expect(await violations(container)).toEqual([]);
  });
  it('access-restricted page has no violations', async () => {
    me({ user_id: 3, username: 'student', permissions: [], is_superuser: false, groups: ['Student'] });
    const { container } = render(wrap('/awards', <AppRouter />));
    await screen.findByText('Access restricted');
    expect(await violations(container)).toEqual([]);
  });
});
