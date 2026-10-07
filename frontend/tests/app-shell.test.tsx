import React from 'react';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const transport = vi.hoisted(() => ({
  login: vi.fn(async () => undefined),
  logout: vi.fn(async () => undefined),
}));
vi.mock('../src/features/auth/session', () => ({
  authenticatedFetch: (path: string, init?: RequestInit) => fetch('http://localhost/api/v1' + path, init),
  login: transport.login,
  logout: transport.logout,
  refreshSession: async () => false,
}));
vi.mock('../src/features/identity-access/PasswordChange', () => ({
  PasswordChange: ({ onChanged }: { onChanged: () => void }) => <button onClick={onChanged}>change-password-stub</button>,
}));
vi.mock('../src/features/identity-access/SupportBanner', () => ({ SupportBanner: () => null }));
vi.mock('../src/pwa/PwaStatus', () => ({ PwaStatus: () => null }));

import { AuthProvider, hasPermission, useAuth, type AuthUser } from '../src/lib/auth-context';
import { NAV_ITEMS, visibleNav } from '../src/app/navigation';
import { LoginPage } from '../src/app/pages/LoginPage';
import { DashboardPage } from '../src/app/pages/DashboardPage';
import { NotFoundPage } from '../src/app/pages/NotFoundPage';
import { AppShell } from '../src/app/layout';
import { AppRouter } from '../src/app/router';
import { App } from '../src/app/App';
import { ErrorBoundary } from '../src/components/ErrorBoundary';
import { EmptyState, ErrorAlert, Loading, PageHeader } from '../src/components/feedback';
import { getQueryClient } from '../src/lib/query';
import { theme } from '../src/app/theme';
import { isEnvelope } from '../src/lib/config';

const admin: AuthUser = { user_id: 1, username: 'admin', permissions: [], is_superuser: true, groups: [] };
const student: AuthUser = { user_id: 3, username: 'student', permissions: [], is_superuser: false, groups: ['Student'], access_modules: ['ATTENDANCE', 'REGISTRATION'] };
const registrar: AuthUser = { user_id: 4, username: 'registrar', permissions: ['people_master.view_student', 'admission_enrolment.view_x', 'term_registration.view_y'], is_superuser: false, access_modules: ['AWARDS'] };
const nobody: AuthUser = { user_id: 9, username: 'nobody', permissions: [], is_superuser: false };

let me: AuthUser | null = admin;
let mql = true;
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterAll(() => server.close());
beforeEach(() => {
  me = admin;
  mql = true;
  window.matchMedia = ((query: string) => ({
    matches: mql, media: query, onchange: null, addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
  server.use(
    http.get('http://localhost/api/v1/auth/me/', () => (me ? HttpResponse.json(me) : HttpResponse.json({ error: { message: 'no' } }, { status: 401 }))),
    http.get('http://localhost/api/v1/people/students/', () => HttpResponse.json({ count: 51, results: [] })),
    http.get('http://localhost/api/v1/people/employees/', () => HttpResponse.json({ count: 16, results: [] })),
    http.get('http://localhost/api/v1/organization/departments/', () => HttpResponse.json({ count: 22, results: [] })),
    http.get('http://localhost/api/v1/organization/programmes/', () => HttpResponse.json({}, { status: 500 })),
  );
  getQueryClient().clear();
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.location.hash = '';
});

const qc = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
function Probe() {
  const a = useAuth();
  return (
    <div>
      <span data-testid="state">{a.checking ? 'checking' : a.user ? 'in:' + a.user.username : 'out'}</span>
      <span data-testid="failure">{a.failure}</span>
      <span data-testid="retry">{String(a.retryLogout)}</span>
      <button onClick={() => void a.signIn('u', 'p', '123').catch(() => {})}>in</button>
      <button onClick={() => void a.signOut().catch(() => {})}>out</button>
      <button onClick={() => void a.refreshUser()}>refresh</button>
      <button onClick={a.clearFailure}>clear</button>
    </div>
  );
}
const withAuth = (ui: React.ReactElement, path = '/') => (
  <QueryClientProvider client={qc()}>
    <AuthProvider>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </AuthProvider>
  </QueryClientProvider>
);

describe('navigation rules', () => {
  it('shows everything to a superuser and nothing gated to an unprivileged user', () => {
    expect(visibleNav(null)).toEqual([]);
    expect(visibleNav(admin).length).toBe(NAV_ITEMS.length);
    const titles = visibleNav(nobody).map((n) => n.path);
    expect(titles).toEqual(['/dashboard']);
  });
  it('grants staff by Django permission, IAM module or student group', () => {
    const regPaths = visibleNav(registrar).map((n) => n.path);
    expect(regPaths).toEqual(expect.arrayContaining(['/people', '/admissions', '/registration', '/awards']));
    expect(regPaths).not.toContain('/security');
    const stuPaths = visibleNav(student).map((n) => n.path);
    expect(stuPaths).toEqual(expect.arrayContaining(['/attendance', '/registration']));
    expect(stuPaths).not.toContain('/people');
    expect(stuPaths).not.toContain('/admissions');
  });
  it('treats a throwing predicate as visible', () => {
    const broken = { ...nobody, permissions: null } as unknown as AuthUser;
    expect(() => visibleNav(broken)).not.toThrow();
  });
  it('hasPermission handles anonymous, superuser, exact and prefix matches', () => {
    expect(hasPermission(null, 'x')).toBe(false);
    expect(hasPermission(admin, 'x')).toBe(true);
    expect(hasPermission({ ...nobody, permissions: ['a.b'] }, 'a')).toBe(true);
    expect(hasPermission({ ...nobody, permissions: ['a'] }, 'a')).toBe(true);
    expect(hasPermission({ ...nobody, permissions: ['b.c'] }, 'a')).toBe(false);
  });
});

describe('AuthProvider', () => {
  it('restores a session, signs out, and reports transport failures', async () => {
    render(withAuth(<Probe />));
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('in:admin'));
    fireEvent.click(screen.getByText('refresh'));
    transport.logout.mockRejectedValueOnce(new Error('Server sign-out failed.'));
    fireEvent.click(screen.getByText('out'));
    await waitFor(() => expect(screen.getByTestId('retry')).toHaveTextContent('true'));
    expect(screen.getByTestId('failure')).toHaveTextContent('Server sign-out failed.');
    fireEvent.click(screen.getByText('clear'));
    expect(screen.getByTestId('failure')).toHaveTextContent('');
    fireEvent.click(screen.getByText('out'));
    await waitFor(() => expect(screen.getByTestId('retry')).toHaveTextContent('false'));
  });
  it('is signed out on 401 without a failure, and surfaces other errors', async () => {
    me = null;
    render(withAuth(<Probe />));
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('out'));
    expect(screen.getByTestId('failure')).toHaveTextContent('session expired');
    cleanup();
    server.use(http.get('http://localhost/api/v1/auth/me/', () => HttpResponse.json({ error: { message: 'Boom' } }, { status: 500 })));
    render(withAuth(<Probe />));
    await waitFor(() => expect(screen.getByTestId('failure')).toHaveTextContent('Boom'));
  });
  it('signs in, records failures and reacts to session expiry', async () => {
    me = null;
    render(withAuth(<Probe />));
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('out'));
    transport.login.mockRejectedValueOnce(new Error('Bad credentials'));
    fireEvent.click(screen.getByText('in'));
    await waitFor(() => expect(screen.getByTestId('failure')).toHaveTextContent('Bad credentials'));
    me = student;
    fireEvent.click(screen.getByText('in'));
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('in:student'));
    expect(transport.login).toHaveBeenLastCalledWith('u', 'p', '123');
    act(() => {
      window.dispatchEvent(new Event('sims-session-expired'));
    });
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('out'));
    expect(screen.getByTestId('failure')).toHaveTextContent('session expired');
  });
  it('requires a provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/inside AuthProvider/);
    spy.mockRestore();
  });
});

describe('LoginPage', () => {
  it('signs in and navigates, clearing the password on failure', async () => {
    me = null;
    render(withAuth(<LoginPage />, '/login'));
    await waitFor(() => expect(screen.getByLabelText(/Username/)).toBeEnabled());
    fireEvent.change(screen.getByLabelText(/Username/), { target: { value: ' admin ' } });
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: 'secret' } });
    transport.login.mockRejectedValueOnce(new Error('Unable to sign in.'));
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Unable to sign in.')).toBeInTheDocument();
    expect(screen.getByLabelText(/^Password/)).toHaveValue('');
    me = admin;
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: 'secret' } });
    fireEvent.change(screen.getByLabelText(/Verification code/), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(transport.login).toHaveBeenLastCalledWith('admin', 'secret', '123456'));
  });
  it('offers a retry after a failed server sign-out', async () => {
    function Seed() {
      const a = useAuth();
      return <button onClick={() => void a.signOut().catch(() => {})}>fail-out</button>;
    }
    render(withAuth(<><Seed /><LoginPage /></>, '/login'));
    await waitFor(() => expect(screen.getByText('fail-out')).toBeEnabled());
    transport.logout.mockRejectedValueOnce(new Error('offline'));
    fireEvent.click(screen.getByText('fail-out'));
    const retry = await screen.findByRole('button', { name: 'Retry server sign-out' });
    fireEvent.click(retry);
    await waitFor(() => expect(transport.logout).toHaveBeenCalledTimes(2));
  });
});

describe('DashboardPage', () => {
  it('shows live counts for an admin, tolerating failed tiles', async () => {
    render(withAuth(<DashboardPage />, '/dashboard'));
    expect(await screen.findByText(/Good (morning|afternoon|evening), admin/)).toBeInTheDocument();
    expect(await screen.findByText('51')).toBeInTheDocument();
    expect(await screen.findByText('16')).toBeInTheDocument();
    expect((await screen.findAllByText('—')).length).toBeGreaterThan(0);
  });
  it('hides tiles and groups the user cannot reach, and warns when nothing is visible', async () => {
    me = student;
    const { unmount } = render(withAuth(<DashboardPage />, '/dashboard'));
    expect(await screen.findByText(/Good (morning|afternoon|evening), student/)).toBeInTheDocument();
    expect(screen.queryByText('Enrolled students')).not.toBeInTheDocument();
    expect(await screen.findByText('My attendance')).toBeInTheDocument();
    unmount();
    me = nobody;
    render(withAuth(<DashboardPage />, '/dashboard'));
    expect(await screen.findByText(/No modules are visible/)).toBeInTheDocument();
  });
  it('asks for a password change when required', async () => {
    me = { ...admin, must_change_password: true };
    const reload = vi.fn();
    const original = window.location;
    Object.defineProperty(window, 'location', { configurable: true, value: { ...original, reload } });
    render(withAuth(<DashboardPage />, '/dashboard'));
    fireEvent.click(await screen.findByText('change-password-stub'));
    expect(reload).toHaveBeenCalled();
    Object.defineProperty(window, 'location', { configurable: true, value: original });
  });
});

describe('AppShell navigation', () => {
  it('lists only groups and opens a flyout on hover', async () => {
    me = registrar;
    render(withAuth(<AppShell><p>content</p></AppShell>, '/people'));
    const nav = await screen.findByRole('navigation', { name: 'SIMS navigation' });
    expect(within(nav).getByText('Workspace')).toBeInTheDocument();
    expect(within(nav).queryByText('Platform')).not.toBeInTheDocument();
    const trigger = within(nav).getByRole('button', { name: /Academic core/ });
    const wrapper = trigger.parentElement!;
    fireEvent.mouseEnter(wrapper);
    expect(await screen.findByRole('link', { name: 'People' })).toHaveAttribute('href', '/people');
    fireEvent.mouseLeave(wrapper);
    fireEvent.click(trigger);
    expect(await screen.findByRole('link', { name: 'People' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'People' }));
    await waitFor(() => expect(screen.queryByRole('link', { name: 'People' })).not.toBeInTheDocument());
  });
  it('expands groups in place on small screens and signs out', async () => {
    mql = false;
    me = student;
    render(withAuth(<AppShell><p>content</p></AppShell>, '/attendance'));
    fireEvent.click(await screen.findByLabelText('Open navigation'));
    const group = await screen.findByText('Academic core');
    fireEvent.click(group);
    expect(await screen.findByRole('link', { name: 'Attendance' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'Attendance' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Account menu' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: /Sign out/ }));
    await waitFor(() => expect(transport.logout).toHaveBeenCalled());
  });
  it('reports a failed sign-out with a retry', async () => {
    me = admin;
    render(withAuth(<AppShell><p>content</p></AppShell>, '/dashboard'));
    transport.logout.mockRejectedValueOnce(new Error('Server sign-out failed.'));
    fireEvent.click(await screen.findByRole('button', { name: 'Account menu' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: /Sign out/ }));
    expect(await screen.findByText('Server sign-out failed.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry server sign-out' }));
    await waitFor(() => expect(transport.logout).toHaveBeenCalledTimes(2));
  });
  it('contains render errors in the boundary', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const Bomb = () => {
      throw new Error('kaboom');
    };
    render(<ErrorBoundary><Bomb /></ErrorBoundary>);
    expect(screen.getByText(/Something went wrong/)).toBeInTheDocument();
    spy.mockRestore();
  });
});

describe('AppRouter', () => {
  it('shows the login page when signed out and a 404 page for unknown routes', async () => {
    me = null;
    const { unmount } = render(withAuth(<AppRouter />, '/people'));
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    unmount();
    me = admin;
    render(withAuth(<AppRouter />, '/no-such-page'));
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
  });
  it('blocks typed URLs for modules outside the role', async () => {
    me = student;
    render(withAuth(<AppRouter />, '/awards'));
    expect(await screen.findByText('Access restricted')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to dashboard' })).toHaveAttribute('href', '/dashboard');
  });
  it('redirects the root to the dashboard and forces a password change first', async () => {
    me = admin;
    const { unmount } = render(withAuth(<AppRouter />, '/'));
    expect(await screen.findByText(/Good (morning|afternoon|evening), admin/)).toBeInTheDocument();
    unmount();
    me = { ...admin, must_change_password: true };
    render(withAuth(<AppRouter />, '/people'));
    expect(await screen.findByText('change-password-stub')).toBeInTheDocument();
  });
});

describe('shared pieces', () => {
  it('renders page header, alerts, empty and loading states', () => {
    const retry = vi.fn();
    render(
      <MemoryRouter>
        <PageHeader overline="Over" title="Title" description="Desc" actions={<button>act</button>} />
        <PageHeader overline="Bare" title="Bare title" />
        <ErrorAlert message="bad" onRetry={retry} />
        <ErrorAlert message="plain" />
        <EmptyState title="Nothing" hint="Add one" />
        <EmptyState title="Empty" />
        <Loading label="Working" />
        <NotFoundPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalled();
    expect(screen.getByText('Add one')).toBeInTheDocument();
    expect(screen.getByText('Working')).toBeInTheDocument();
  });
  it('exposes the theme, query client singleton and envelope guard', () => {
    expect(theme.palette.primary.main).toBe('#1f4fa3');
    expect(getQueryClient()).toBe(getQueryClient());
    expect(isEnvelope({ error: { message: 'm' } })).toBe(true);
    expect(isEnvelope(null)).toBe(false);
    expect(isEnvelope({ error: 'x' })).toBe(false);
    expect(isEnvelope({ error: null })).toBe(false);
    expect(isEnvelope({ error: { message: 3 } })).toBe(false);
  });
  it('mounts the full application', async () => {
    me = null;
    window.location.hash = '#/login';
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});
