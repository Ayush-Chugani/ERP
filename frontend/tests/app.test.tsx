import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppRoutes } from '../src/App';
import { setAccessToken } from '../src/api/client';
import { authRoutes, ME, mockApi, renderApp } from './helpers';

const meta = {
  groups: [{ title: 'People', resources: [{ path: 'people/student', table: 'student', title: 'Student', module: 'people', label_columns: ['display_name'], list_columns: ['display_name', 'student_status'], status_column: 'student_status', read_only: false, searchable: true, can: { read: true, create: true, update: true, delete: false, export: true }, actions: [] }] }],
};
const studentMeta = {
  ...meta.groups[0].resources[0], primary_key: 'student_id',
  columns: [
    { name: 'student_id', label: 'Student', kind: 'int', required: false, nullable: false, readonly: true, max_length: null, choices: null, primary: true, references: null },
    { name: 'display_name', label: 'Display name', kind: 'string', required: true, nullable: false, readonly: false, max_length: 250, choices: null, primary: false, references: null },
    { name: 'student_status', label: 'Student status', kind: 'enum', required: false, nullable: false, readonly: true, max_length: null, choices: ['ACTIVE', 'APPLICANT'], primary: false, references: null },
  ],
};

beforeEach(() => setAccessToken(null));

describe('application shell', () => {
  it('sends anonymous visitors to the sign-in page', async () => {
    mockApi({ ...authRoutes, 'POST /auth/refresh': { status: 401, body: {} } });
    renderApp(<AppRoutes />, '/r/people/student');
    expect(await screen.findByRole('list', { name: /sign-in portals/i })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /sign in$/i })).toHaveLength(8);
  });

  it('offers a separate entrance per audience and sends the chosen portal with the login', async () => {
    const { calls } = mockApi({
      ...authRoutes, 'POST /auth/refresh': { status: 401, body: {} },
      'POST /auth/login': { status: 403, body: { error: { code: 'wrong_portal', message: 'This account cannot sign in through the Administrator portal. Please use the Student portal.', details: {} } } },
    });
    renderApp(<AppRoutes />, '/login?portal=admin');
    expect(await screen.findByRole('heading', { name: /administrator sign in/i })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/username/i), 'student');
    await userEvent.type(screen.getByLabelText(/^password/i), 'pw');
    await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }));
    expect(await screen.findByText(/please use the student portal/i)).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.path === '/auth/login')?.init.body))).toMatchObject({ portal: 'admin' });
    await userEvent.click(screen.getByRole('button', { name: /all portals/i }));
    expect(await screen.findByRole('list', { name: /sign-in portals/i })).toBeInTheDocument();
  });

  it('signs in and shows the dashboard for the user', async () => {
    mockApi({
      ...authRoutes, 'POST /auth/refresh': { status: 401, body: {} },
      'POST /auth/login': { body: { access: 'tok', csrfToken: 't.sig', must_change_password: false } },
      'GET /meta': { body: meta },
      'GET /dashboard': { body: { tiles: [{ label: 'Active students', value: 47, link: 'people/student' }], unread_notifications: 0 } },
    });
    renderApp(<AppRoutes />, '/login?portal=office');
    await userEvent.type(await screen.findByLabelText(/username/i), 'registrar');
    await userEvent.type(screen.getByLabelText(/^password/i), 'Whatever#12345');
    await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }));
    expect(await screen.findByText(/rekha registrar/i, { selector: 'h1' })).toBeInTheDocument();
    expect(await screen.findByText('47')).toBeInTheDocument();
  });

  it('shows a clear message when credentials are rejected', async () => {
    mockApi({
      ...authRoutes, 'POST /auth/refresh': { status: 401, body: {} },
      'POST /auth/login': { status: 401, body: { error: { code: 'not_authenticated', message: 'Unable to sign in. Check your credentials and try again.', details: {} } } },
    });
    renderApp(<AppRoutes />, '/login?portal=office');
    await userEvent.type(await screen.findByLabelText(/username/i), 'x');
    await userEvent.type(screen.getByLabelText(/^password/i), 'y');
    await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }));
    expect(await screen.findByText(/unable to sign in/i)).toBeInTheDocument();
  });

  it('forces a password change before anything else', async () => {
    mockApi({ ...authRoutes, 'GET /auth/me': { body: { ...ME, must_change_password: true } }, 'GET /meta': { body: meta }, 'GET /dashboard': { body: { tiles: [], unread_notifications: 0 } }, 'GET /auth/sessions': { body: { results: [] } } });
    renderApp(<AppRoutes />, '/');
    expect(await screen.findByText(/you must choose a new password/i)).toBeInTheDocument();
  });

  it('renders a metadata-driven list with search and rows', async () => {
    mockApi({
      ...authRoutes, 'GET /meta': { body: meta }, 'GET /dashboard': { body: { tiles: [], unread_notifications: 0 } },
      'GET /meta/people/student': { body: studentMeta },
      'GET /people/student': { body: { count: 1, page: 1, page_size: 25, next: null, previous: null, results: [{ student_id: 5, display_name: 'Asha Verma', student_status: 'ACTIVE', labels: {} }] } },
    });
    renderApp(<AppRoutes />, '/r/people/student');
    expect(await screen.findByText('Asha Verma')).toBeInTheDocument();
    expect(screen.getByText('1 records')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /new/i })).toBeInTheDocument();
  });

  it('hides create/export when the user lacks those permissions', async () => {
    const readOnly = { ...studentMeta, can: { read: true, create: false, update: false, delete: false, export: false } };
    mockApi({
      ...authRoutes, 'GET /meta': { body: meta }, 'GET /dashboard': { body: { tiles: [], unread_notifications: 0 } },
      'GET /meta/people/student': { body: readOnly },
      'GET /people/student': { body: { count: 0, page: 1, page_size: 25, next: null, previous: null, results: [] } },
    });
    renderApp(<AppRoutes />, '/r/people/student');
    await waitFor(() => expect(screen.getByText(/nothing here yet/i)).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /new/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /export/i })).not.toBeInTheDocument();
  });

  it('shows an error state instead of crashing when the API fails', async () => {
    mockApi({
      ...authRoutes, 'GET /meta': { body: meta }, 'GET /dashboard': { body: { tiles: [], unread_notifications: 0 } },
      'GET /meta/people/student': { body: studentMeta },
      'GET /people/student': { status: 403, body: { error: { code: 'permission_denied', message: 'You do not have permission to perform this action.', details: {} } } },
    });
    renderApp(<AppRoutes />, '/r/people/student');
    expect(await screen.findByText(/do not have permission/i)).toBeInTheDocument();
  });
});


describe('navigation and access', () => {
  const commonRoutes = {
    ...authRoutes, 'GET /meta': { body: meta }, 'GET /dashboard': { body: { tiles: [], unread_notifications: 0 } },
  };

  it('builds the menu only from areas the API says the user can use', async () => {
    mockApi(commonRoutes);
    renderApp(<AppRoutes />, '/');
    expect(await screen.findByRole('button', { name: /students/i })).toBeInTheDocument();       // people/student -> Students area
    expect(screen.queryByRole('button', { name: /^staff$/i })).not.toBeInTheDocument();           // nothing readable in Staff
    expect(screen.queryByText(/background jobs/i)).not.toBeInTheDocument();                       // no IAM.OPERATIONS permission
  });

  it('shows administration links only with the matching permissions', async () => {
    mockApi(commonRoutes);
    renderApp(<AppRoutes />, '/');
    expect(await screen.findByText('Users')).toBeInTheDocument();                                  // IAM.ALL.READ grants IAM.USERS.READ
    expect(screen.queryByText(/audit trail/i)).not.toBeInTheDocument();
  });

  it('opens the command palette with Ctrl+K and jumps to a page', async () => {
    mockApi({ ...commonRoutes, 'GET /meta/people/student': { body: studentMeta }, 'GET /people/student': { body: { count: 0, page: 1, page_size: 25, next: null, previous: null, results: [] } } });
    renderApp(<AppRoutes />, '/');
    await screen.findByRole('button', { name: /students/i });
    await userEvent.keyboard('{Control>}k{/Control}');
    const box = await screen.findByLabelText(/search pages/i, { selector: 'input' });
    await userEvent.type(box, 'student');
    await userEvent.keyboard('{Enter}');
    expect(await screen.findByRole('heading', { name: 'Student' })).toBeInTheDocument();
  });

  it('lists an area as cards with only permitted pages', async () => {
    mockApi(commonRoutes);
    renderApp(<AppRoutes />, '/w/students');
    expect(await screen.findByRole('heading', { name: 'Students' })).toBeInTheDocument();
    expect(await screen.findByText('Student', { selector: 'h6, .MuiTypography-subtitle1' })).toBeInTheDocument();
  });

  it('lets the user switch between light and dark themes', async () => {
    mockApi(commonRoutes);
    renderApp(<AppRoutes />, '/');
    const toggle = await screen.findByRole('button', { name: /change theme/i });
    const before = toggle.getAttribute('aria-label');
    await userEvent.click(toggle);
    await waitFor(() => expect(screen.getByRole('button', { name: /change theme/i }).getAttribute('aria-label')).not.toBe(before));
  });
});

describe('owner dashboard', () => {
  it('shows the installation overview to a super administrator', async () => {
    setAccessToken('tok');
    mockApi({
      ...authRoutes, 'GET /auth/me': { body: { ...ME, is_superuser: true, roles: [], permissions: [] } }, 'GET /meta': { body: { groups: [] } },
      'GET /ops/overview': { body: {
        generated_at: '2026-10-08T10:00:00Z', people: { students: 51, staff: 16 }, users: { total: 9, active: 9, locked: 0, with_mfa: 1 },
        users_by_role: [{ role: 'STUDENT', name: 'Student', users: 2 }], sessions: { active: 3 }, logins_24h: { successful: 5, failed: 1 },
        recent_logins: [], recent_audit: [], jobs: { summary: { done: 4 }, last_completed_at: null }, workflow: { grievances_open: 1 },
        system: { environment: 'development', schema: '0003', storage: 'local', ai_enabled: true, ai_model: 'Qwen', database: 'connected' } } },
    });
    renderApp(<AppRoutes />, '/owner');
    expect(await screen.findByRole('heading', { name: /owner dashboard/i })).toBeInTheDocument();
    expect(await screen.findByText('51')).toBeInTheDocument();
    expect(screen.getByText('Qwen')).toBeInTheDocument();
  });
});

describe('route guards and self-service labels', () => {
  const base = { ...authRoutes, 'GET /meta': { body: { groups: [] } }, 'GET /dashboard': { body: { tiles: [], unread_notifications: 0 } } };
  const student = { ...ME, username: 'student', full_name: 'Sam Student', roles: ['STUDENT'], permissions: ['STUDENT.OWN.READ'], student_ids: [7] };

  it('quietly sends a student who opens /admin/users back Home (no error screen)', async () => {
    mockApi({ ...base, 'GET /auth/me': { body: student } });
    renderApp(<AppRoutes />, '/admin/users');
    expect(await screen.findByText(/sam student/i, { selector: 'h1' })).toBeInTheDocument();
    expect(screen.queryByText(/not found|no access|not have access|permission/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /new user/i })).not.toBeInTheDocument();
  });

  it('sends non-owners away from /owner and unknown addresses without a message', async () => {
    mockApi(base);
    renderApp(<AppRoutes />, '/owner');
    expect(await screen.findByText(/at a glance|good (morning|afternoon|evening)/i)).toBeInTheDocument();
    expect(screen.queryByText(/not found|no access/i)).not.toBeInTheDocument();
  });

  it('lets a user with the permission open /admin/users', async () => {
    mockApi({ ...base, 'GET /admin/users': { body: { count: 0, page: 1, page_size: 25, next: null, previous: null, results: [] } } });
    renderApp(<AppRoutes />, '/admin/users');
    await waitFor(() => expect(screen.getByRole('heading', { name: /users/i })).toBeInTheDocument());
  });

  it('words dashboard tiles in the first person for self-service students', async () => {
    mockApi({
      ...base, 'GET /auth/me': { body: student },
      'GET /dashboard': { body: { tiles: [
        { label: 'Certificate requests to review', value: 1, link: 'a/b' }, { label: 'Open grievances', value: 2, link: 'a/c' }, { label: 'Active mentor assignments', value: 3, link: 'a/d' },
      ], unread_notifications: 0 } },
    });
    renderApp(<AppRoutes />, '/');
    expect(await screen.findByText('My certificate requests')).toBeInTheDocument();
    expect(screen.getByText('My open grievances')).toBeInTheDocument();
    expect(screen.getByText('My mentors')).toBeInTheDocument();
    expect(screen.queryByText('Certificate requests to review')).not.toBeInTheDocument();
  });

  it('keeps staff tile labels unchanged', async () => {
    mockApi({ ...base, 'GET /dashboard': { body: { tiles: [{ label: 'Open grievances', value: 2, link: 'a/c' }], unread_notifications: 0 } } });
    renderApp(<AppRoutes />, '/');
    expect(await screen.findByText('Open grievances')).toBeInTheDocument();
  });
});
