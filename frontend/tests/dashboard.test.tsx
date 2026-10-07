import React from 'react';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { QueryClientProvider } from '@tanstack/react-query';

vi.mock('../src/features/auth/session', () => ({
  authenticatedFetch: (path: string, init?: RequestInit) => fetch('http://localhost/api/v1' + path, init),
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: async () => false,
}));
vi.mock('../src/features/identity-access/SupportBanner', () => ({ SupportBanner: () => null }));
vi.mock('../src/pwa/PwaStatus', () => ({ PwaStatus: () => null }));

import { AuthProvider, type AuthUser } from '../src/lib/auth-context';
import { AcademicYearProvider, useAcademicYear } from '../src/lib/academic-year';
import { AppShell, quickActions } from '../src/app/layout';
import { DashboardPage, TILES, localDate, monthSeries, pickTiles, weekOf, weekSeries, yearSeries } from '../src/app/pages/DashboardPage';
import { visibleNav } from '../src/app/navigation';
import { Sparkline } from '../src/components/Sparkline';
import { Icon } from '../src/app/icons';
import { roleLabel } from '../src/lib/role';
import { getQueryClient } from '../src/lib/query';

const base = 'http://localhost/api/v1';
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  window.matchMedia = ((q: string) => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false })) as never;
  getQueryClient().clear();
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
});

const admin: AuthUser = { user_id: 1, username: 'admin', permissions: [], is_superuser: true, groups: [] };
const student: AuthUser = { user_id: 3, username: 'stu', permissions: [], is_superuser: false, groups: ['Student'], access_modules: ['ATTENDANCE', 'REGISTRATION', 'COMMUNICATION', 'DOCUMENT'] };
const teacher: AuthUser = { user_id: 4, username: 'tea', permissions: ['people_master.view_student', 'communication.view_announcement'], is_superuser: false, groups: ['Teacher'], access_modules: ['ATTENDANCE', 'TIMETABLE'] };

const mount = (user: AuthUser, ui: React.ReactElement, path = '/dashboard') => {
  server.use(http.get(`${base}/auth/me/`, () => HttpResponse.json(user)));
  return render(
    <QueryClientProvider client={getQueryClient()}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
};

describe('series helpers', () => {
  const now = new Date(2026, 9, 7);
  it('builds cumulative yearly, monthly and weekly series from local calendar days', () => {
    expect(yearSeries(['2024-08-01', '2026-01-01', 'bad'], 4, now)).toEqual([0, 1, 1, 2]);
    expect(monthSeries(['2026-10-02', '2026-09-30', '2026-09-01', '2020-01-01', 'bad'], 3, now)).toEqual([0, 2, 1]);
    expect(weekSeries(['2026-10-07', '2026-10-15', '2026-10-16', '2027-01-01', '2026-01-01'], 3, now)).toEqual([1, 2, 0]);
    expect(localDate('2026-10-07').getDate()).toBe(7);
    expect(localDate('2026-10-07T10:00:00Z').getTime()).toBe(new Date('2026-10-07T10:00:00Z').getTime());
  });
  it('lays out weeks Monday to Saturday', () => {
    const { monday, days } = weekOf(0, new Date(2026, 9, 7));
    expect(monday.getDay()).toBe(1);
    expect(days).toHaveLength(6);
    expect(weekOf(1, new Date(2026, 9, 7)).monday.getDate()).toBe(monday.getDate() + 7);
    expect(weekOf(0, new Date(2026, 9, 11)).monday.getDate()).toBe(5);
  });
});

describe('small pieces', () => {
  it('names roles for display', () => {
    expect(roleLabel(null)).toBe('');
    expect(roleLabel(admin)).toBe('Administrator');
    expect(roleLabel(student)).toBe('Student');
    expect(roleLabel({ ...teacher, groups: ['Admissions registrar'] })).toBe('Registrar');
    expect(roleLabel({ ...teacher, groups: ['M9 Coordinator'] })).toBe('Department head');
    expect(roleLabel(teacher)).toBe('Faculty');
    expect(roleLabel({ ...teacher, groups: ['M10 Result cell'] })).toBe('Staff');
    expect(roleLabel({ ...teacher, groups: ['Other'] })).toBe('Staff');
    expect(roleLabel({ ...teacher, groups: [] })).toBe('Member');
    expect(roleLabel({ ...teacher, groups: undefined })).toBe('Member');
  });
  it('renders icons and sparklines, including degenerate series', () => {
    const { container } = render(
      <>
        <Icon name="bell" />
        <Icon name="search" size={10} />
        <Sparkline values={[1, 3, 2]} />
        <Sparkline values={[]} />
        <Sparkline values={[5]} />
        <Sparkline values={[2, 2, 2]} color="#000" height={20} />
      </>,
    );
    expect(container.querySelectorAll('svg').length).toBe(6);
    expect(container.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  });
  it('remembers the academic year and survives unavailable storage', () => {
    function Probe() {
      const { year, choose } = useAcademicYear();
      return (
        <>
          <span data-testid="y">{year?.code ?? 'none'}</span>
          <button onClick={() => choose({ id: 1, code: '2025-26', start: 'a', end: 'b', status: 'ACTIVE' })}>pick</button>
          <button onClick={() => choose(null)}>clear</button>
        </>
      );
    }
    window.localStorage.setItem('sims.academic-year', JSON.stringify({ id: 9, code: 'stored', start: '', end: '', status: '' }));
    const { unmount } = render(<AcademicYearProvider><Probe /></AcademicYearProvider>);
    expect(screen.getByTestId('y')).toHaveTextContent('stored');
    fireEvent.click(screen.getByText('pick'));
    expect(JSON.parse(window.localStorage.getItem('sims.academic-year')!).code).toBe('2025-26');
    fireEvent.click(screen.getByText('clear'));
    expect(window.localStorage.getItem('sims.academic-year')).toBeNull();
    unmount();
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    render(<AcademicYearProvider><Probe /></AcademicYearProvider>);
    expect(screen.getByTestId('y')).toHaveTextContent('none');
    fireEvent.click(screen.getByText('pick'));
    expect(screen.getByTestId('y')).toHaveTextContent('2025-26');
    get.mockRestore();
    set.mockRestore();
  });
  it('picks role-appropriate tiles and quick actions', () => {
    expect(pickTiles(admin, visibleNav(admin)).map((t) => t.id)).toEqual(['students', 'staff', 'pending', 'exams']);
    expect(pickTiles(student, visibleNav(student)).map((t) => t.id)).toEqual(['attendance', 'courses', 'announcements', 'requests']);
    expect(pickTiles(student, visibleNav(student), 2)).toHaveLength(2);
    expect(quickActions(admin, visibleNav(admin)).map((a) => a.label)).toEqual(['Register a student', 'Review applications', 'Take attendance', 'Post an announcement']);
    expect(quickActions(student, visibleNav(student)).map((a) => a.label)).toEqual(['Request a certificate', 'View my registration']);
    expect(quickActions({ ...student, groups: [], access_modules: [] }, [])).toEqual([]);
    const withComms = { ...teacher, permissions: ['communication.add_announcement'] };
    expect(quickActions(withComms, visibleNav(withComms)).some((a) => a.label === 'Post an announcement')).toBe(true);
  });
});

describe('metric tiles', () => {
  const page = (results: unknown[], count = results.length) => HttpResponse.json({ count, results });
  it('computes each tile from its API', async () => {
    const today = new Date().toISOString().slice(0, 10);
    const future = new Date(Date.now() + 5 * 86_400_000).toISOString().slice(0, 10);
    server.use(
      http.get(`${base}/people/students/`, () => page([{ admission_date: '2025-08-01' }, { admission_date: '2024-01-01' }], 2)),
      http.get(`${base}/people/employees/`, () => page([{ employment_status: 'ACTIVE', joining_date: '2020-01-01' }, { employment_status: 'RESIGNED', joining_date: '2019-01-01' }])),
      http.get(`${base}/admissions/applications/`, () => page([{ application_status: 'SUBMITTED', application_date: today }, { application_status: 'ADMITTED' }])),
      http.get(`${base}/assessments/events/`, () => page([{ assessment_date: future, status: 'PLANNED' }, { assessment_date: today, status: 'CANCELLED' }, { assessment_date: '2020-01-01', status: 'PLANNED' }])),
      http.get(`${base}/attendance/mine/`, () => page([{ date: '2026-01-02', status: 'ABSENT' }, { date: '2026-01-01', status: 'PRESENT' }, { date: '2026-01-03', status: 'PRESENT' }])),
      http.get(`${base}/registration/mine/`, () => page([{ roll_number: '07', courses: [{ course: 'A' }, { course: 'B' }] }])),
      http.get(`${base}/communication/feed/`, () => page([{ title: 'Latest', publish_from: today }])),
      http.get(`${base}/documents/certificates/`, () => page([{ status: 'SUBMITTED', requested_at: today }, { status: 'ISSUED', requested_at: today }])),
    );
    const ctx = { yearCode: '2025-26', yearStart: '2025-06-01', yearEnd: '2026-05-31' };
    const by = Object.fromEntries(TILES.map((t) => [t.id, t]));
    expect(await by.students.load(ctx)).toMatchObject({ value: '2', sub: '1 admitted in 2025-26' });
    expect((await by.students.load({})).sub).toBeUndefined();
    expect(await by.staff.load(ctx)).toMatchObject({ value: '2', sub: '1 active' });
    expect(await by.pending.load(ctx)).toMatchObject({ value: '1', sub: 'of 2 applications' });
    expect(await by.exams.load(ctx)).toMatchObject({ value: '1' });
    expect((await by.attendance.load(ctx)).value).toBe('67%');
    expect(await by.courses.load(ctx)).toMatchObject({ value: '2', sub: 'Roll no. 07' });
    expect(await by.announcements.load(ctx)).toMatchObject({ value: '1', sub: 'Latest' });
    expect(await by.requests.load(ctx)).toMatchObject({ value: '2', sub: '1 awaiting action' });
    server.use(
      http.get(`${base}/assessments/events/`, () => page([])),
      http.get(`${base}/attendance/mine/`, () => page([])),
      http.get(`${base}/registration/mine/`, () => page([])),
      http.get(`${base}/communication/feed/`, () => page([])),
    );
    expect((await by.exams.load(ctx)).sub).toBe('Nothing scheduled');
    expect((await by.attendance.load(ctx)).value).toBe('—');
    expect((await by.courses.load(ctx)).sub).toBe('No active registration');
    expect((await by.announcements.load(ctx)).sub).toBe('Nothing new');
    expect(by.exams.show(student, visibleNav(student))).toBe(false);
    expect(by.attendance.show(teacher, visibleNav(teacher))).toBe(false);
  });
});

describe('dashboard widgets', () => {
  const day = (offset: number) => {
    const d = new Date();
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7) + offset);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };
  it('shows the weekly schedule, week navigation and request badges', async () => {
    const seen: string[] = [];
    server.use(
      http.get(`${base}/people/students/`, () => HttpResponse.json({ count: 0, results: [] })),
      http.get(`${base}/timetable/occurrences/`, ({ request }) => {
        seen.push(new URL(request.url).searchParams.get('date_from')!);
        return HttpResponse.json({
          results: [
            { id: '1', course_offering_section_id: '4', date: day(0), start_time: '09:00:00', end_time: '10:00:00', course_label: 'Algorithms', room_label: 'M101', employee_label: 'Dr. A' },
            { id: '2', course_offering_section_id: '5', date: day(0), start_time: '08:00:00', end_time: '09:00:00' },
          ],
        });
      }),
      http.get(`${base}/documents/types/`, () => HttpResponse.json({ count: 1, results: [{ id: '2', certificate_name: 'Bonafide' }] })),
      http.get(`${base}/documents/certificates/`, () =>
        HttpResponse.json({
          count: 4,
          results: [
            { id: '1', request_number: 'R1', certificate_type_id: '2', requested_at: '2026-01-02T00:00:00Z', status: 'SUBMITTED' },
            { id: '2', request_number: 'R2', certificate_type_id: '2', status: 'ISSUED' },
            { id: '3', request_number: 'R3', certificate_type_id: '9', status: 'UNDER_REVIEW' },
            { id: '4', request_number: 'R4', certificate_type_id: '2', status: 'MYSTERY' },
          ],
        }),
      ),
    );
    mount(admin, <DashboardPage />);
    expect(await screen.findByText('Algorithms')).toBeInTheDocument();
    expect(screen.getByText('Class')).toBeInTheDocument();
    expect(await screen.findByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('Under review')).toBeInTheDocument();
    expect(screen.getByText('MYSTERY')).toBeInTheDocument();
    expect(screen.getByText('Certificate')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Review' }).length).toBe(2);
    fireEvent.click(screen.getByRole('button', { name: 'Next week' }));
    await waitFor(() => expect(seen.length).toBeGreaterThan(1));
    fireEvent.click(screen.getByRole('button', { name: 'Previous week' }));
    fireEvent.click(screen.getByRole('button', { name: 'Previous week' }));
    fireEvent.click(screen.getByRole('button', { name: 'This week' }));
  });
  it('hides widgets the user cannot load and labels student requests', async () => {
    server.use(
      http.get(`${base}/timetable/occurrences/`, () => HttpResponse.json({ error: { message: 'no' } }, { status: 403 })),
      http.get(`${base}/documents/types/`, () => HttpResponse.json({ error: { message: 'x' } }, { status: 500 })),
      http.get(`${base}/documents/certificates/`, () => HttpResponse.json({ count: 0, results: [] })),
    );
    mount({ ...student, access_modules: [...(student.access_modules ?? []), 'TIMETABLE'] }, <DashboardPage />);
    expect(await screen.findByText('My requests')).toBeInTheDocument();
    expect(await screen.findByText('No requests yet.')).toBeInTheDocument();
    expect(screen.queryByText('Weekly schedule')).not.toBeInTheDocument();
    cleanup();
    server.use(http.get(`${base}/documents/certificates/`, () => HttpResponse.json({}, { status: 500 })));
    getQueryClient().clear();
    mount(student, <DashboardPage />);
    await waitFor(() => expect(screen.queryByText('My requests')).not.toBeInTheDocument());
  });
});

describe('top bar', () => {
  function Where() {
    return <span data-testid="where">{useLocation().pathname}</span>;
  }
  it('searches modules, switches year, lists announcements and offers quick actions', async () => {
    server.use(
      http.get(`${base}/calendar/academic-years/`, () =>
        HttpResponse.json({
          results: [
            { academic_year_id: 1, year_code: '2025-26', start_date: '2025-06-01', end_date: '2026-05-31', status: 'ACTIVE' },
            { academic_year_id: 2, year_code: '2026-27', start_date: '2026-06-01', end_date: '2027-05-31', status: 'PLANNED' },
          ],
        }),
      ),
      http.get(`${base}/communication/feed/`, () =>
        HttpResponse.json({
          count: 2,
          results: [
            { id: '1', title: 'Exam notice', type: 'Exams', publish_from: '2026-10-01T00:00:00Z' },
            { id: '2', title: 'Holiday' },
          ],
        }),
      ),
    );
    mount(admin, <AppShell><Where /></AppShell>, '/dashboard');
    const search = await screen.findByRole('combobox', { name: 'Search modules' });
    fireEvent.change(search, { target: { value: 'Curric' } });
    fireEvent.click(await screen.findByRole('option', { name: 'Curriculum catalog' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/curriculum'));
    fireEvent.focus(search);
    fireEvent.change(search, { target: { value: 'zzzzzz' } });
    expect(await screen.findByText('No matching module')).toBeInTheDocument();
    fireEvent.change(search, { target: { value: '' } });

    const year = await screen.findByRole('combobox', { name: 'Academic year' });
    await waitFor(() => expect(year).toHaveTextContent('2025-26'));
    fireEvent.mouseDown(year);
    fireEvent.click(await screen.findByRole('option', { name: /2026-27/ }));
    await waitFor(() => expect(year).toHaveTextContent('2026-27'));
    expect(JSON.parse(window.localStorage.getItem('sims.academic-year')!).code).toBe('2026-27');

    fireEvent.click(await screen.findByRole('button', { name: /Notifications, 2 announcements/ }));
    expect(await screen.findByText('Exam notice')).toBeInTheDocument();
    expect(screen.getByText('Holiday')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'Open communication' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/communication'));

    fireEvent.click(screen.getByRole('button', { name: /Quick actions/ }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Review applications' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/admissions/applications'));
  });
  it('shows an empty notification state and the role in the account menu', async () => {
    server.use(http.get(`${base}/communication/feed/`, () => HttpResponse.json({ count: 0, results: [] })));
    mount(teacher, <AppShell><p>x</p></AppShell>, '/dashboard');
    fireEvent.click(await screen.findByRole('button', { name: 'Notifications' }));
    expect(await screen.findByText(/all caught up/)).toBeInTheDocument();
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' });
    fireEvent.click(await screen.findByRole('button', { name: 'Account menu' }));
    const menu = await screen.findByRole('menu');
    expect(within(menu).getByText('Faculty')).toBeInTheDocument();
  });
});
