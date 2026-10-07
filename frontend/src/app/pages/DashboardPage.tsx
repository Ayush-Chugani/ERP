import { useState } from 'react';
import { Alert, Box, Button, Chip, IconButton, Paper, Skeleton, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth, type AuthUser } from '../../lib/auth-context';
import { request } from '../../lib/api-client';
import { useAcademicYear } from '../../lib/academic-year';
import { visibleNav, type NavItem } from '../navigation';
import { PasswordChange } from '../../features/identity-access/PasswordChange';
import { PageHeader } from '../../components/feedback';
import { Sparkline } from '../../components/Sparkline';
import { Icon } from '../icons';

type Page<T> = { count: number; results: T[] };
type Row = Record<string, unknown>;
type Metric = { value: string; sub?: string; series: number[] };

// ---- series helpers -------------------------------------------------------------------------
/** Date-only strings ("2026-10-07") are calendar dates, so read them as local days, not UTC midnight. */
export function localDate(value: unknown): Date {
  const s = String(value);
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? new Date(Number(s.slice(0, 4)), Number(s.slice(5, 7)) - 1, Number(s.slice(8, 10))) : new Date(s);
}

/** Cumulative count per calendar year for the last `years` years (including this one). */
export function yearSeries(dates: unknown[], years = 7, now = new Date()): number[] {
  const end = now.getFullYear();
  const ys = dates.map((d) => localDate(d).getFullYear()).filter((y) => Number.isFinite(y));
  const out: number[] = [];
  for (let y = end - years + 1; y <= end; y += 1) out.push(ys.filter((v) => v <= y).length);
  return out;
}

/** Items per calendar month for the last `months` months (including this one). */
export function monthSeries(dates: unknown[], months = 7, now = new Date()): number[] {
  const keys = dates.map((d) => {
    const t = localDate(d);
    return Number.isFinite(t.getTime()) ? t.getFullYear() * 12 + t.getMonth() : NaN;
  });
  const cur = now.getFullYear() * 12 + now.getMonth();
  return Array.from({ length: months }, (_, i) => keys.filter((k) => k === cur - (months - 1 - i)).length);
}

/** Items per week for the next `weeks` weeks starting today. */
export function weekSeries(dates: unknown[], weeks = 6, now = new Date()): number[] {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 86_400_000;
  const idx = dates.map((d) => Math.floor((localDate(d).getTime() - start) / (7 * day)));
  return Array.from({ length: weeks }, (_, i) => idx.filter((k) => k === i).length);
}

// ---- metric definitions ---------------------------------------------------------------------
type Tile = {
  id: string;
  label: string;
  hint: string;
  color: string;
  to: string;
  show: (user: AuthUser, nav: NavItem[]) => boolean;
  load: (ctx: { yearCode?: string; yearStart?: string; yearEnd?: string }) => Promise<Metric>;
};

const hasNav = (nav: NavItem[], path: string) => nav.some((n) => n.path === path);
const isStudent = (u: AuthUser) => (u.groups ?? []).includes('Student');

export const TILES: Tile[] = [
  {
    id: 'students',
    label: 'Enrolled students',
    hint: 'Active student records in your scope',
    color: '#3b5bdb',
    to: '/people/students',
    show: (_u, nav) => hasNav(nav, '/people'),
    load: async ({ yearStart, yearEnd, yearCode }) => {
      const d = await request<Page<Row>>('/people/students/?page_size=100');
      const inYear = yearStart && yearEnd ? d.results.filter((r) => String(r.admission_date ?? '') >= yearStart && String(r.admission_date ?? '') <= yearEnd).length : 0;
      return { value: String(d.count), sub: yearCode ? `${inYear} admitted in ${yearCode}` : undefined, series: yearSeries(d.results.map((r) => r.admission_date)) };
    },
  },
  {
    id: 'staff',
    label: 'Faculty & staff',
    hint: 'Employees in your scope',
    color: '#0ca678',
    to: '/people/employees',
    show: (_u, nav) => hasNav(nav, '/people'),
    load: async () => {
      const d = await request<Page<Row>>('/people/employees/?page_size=100');
      const active = d.results.filter((r) => r.employment_status === 'ACTIVE').length;
      return { value: String(d.count), sub: `${active} active`, series: yearSeries(d.results.map((r) => r.joining_date), 10) };
    },
  },
  {
    id: 'pending',
    label: 'Applications to review',
    hint: 'Submitted or under review',
    color: '#f08c00',
    to: '/admissions/applications',
    show: (_u, nav) => hasNav(nav, '/admissions'),
    load: async () => {
      const d = await request<Page<Row>>('/admissions/applications/?page_size=100');
      const open = d.results.filter((r) => ['SUBMITTED', 'UNDER_REVIEW'].includes(String(r.application_status)));
      return { value: String(open.length), sub: `of ${d.count} applications`, series: monthSeries(d.results.map((r) => r.application_date)) };
    },
  },
  {
    id: 'exams',
    label: 'Upcoming assessments',
    hint: 'Planned tests from today',
    color: '#7048e8',
    to: '/assessments',
    show: (u, nav) => hasNav(nav, '/assessments') && !isStudent(u),
    load: async () => {
      const d = await request<Page<Row>>('/assessments/events/?page_size=100');
      const today = new Date().toISOString().slice(0, 10);
      const up = d.results.filter((r) => String(r.assessment_date ?? '') >= today && r.status !== 'CANCELLED');
      const next = up.map((r) => String(r.assessment_date)).sort()[0];
      return { value: String(up.length), sub: next ? `Next: ${new Date(next).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}` : 'Nothing scheduled', series: weekSeries(up.map((r) => r.assessment_date)) };
    },
  },
  {
    id: 'attendance',
    label: 'My attendance',
    hint: 'Share of sessions marked present',
    color: '#0ca678',
    to: '/attendance',
    show: (u, nav) => isStudent(u) && hasNav(nav, '/attendance'),
    load: async () => {
      const d = await request<Page<Row>>('/attendance/mine/?page_size=100');
      const rows = [...d.results].sort((a, b) => String(a.date).localeCompare(String(b.date)));
      const present = rows.filter((r) => r.status === 'PRESENT').length;
      let seen = 0;
      let ok = 0;
      const series = rows.slice(-12).map((r) => {
        seen += 1;
        ok += r.status === 'PRESENT' ? 1 : 0;
        return Math.round((ok / seen) * 100);
      });
      return { value: rows.length ? `${Math.round((present / rows.length) * 100)}%` : '—', sub: `${present} of ${rows.length} sessions`, series };
    },
  },
  {
    id: 'courses',
    label: 'Registered courses',
    hint: 'Courses this term',
    color: '#3b5bdb',
    to: '/registration',
    show: (u, nav) => isStudent(u) && hasNav(nav, '/registration'),
    load: async () => {
      const d = await request<Page<Row>>('/registration/mine/');
      const courses = d.results.flatMap((r) => (Array.isArray(r.courses) ? (r.courses as unknown[]) : []));
      return { value: String(courses.length), sub: d.results[0] ? `Roll no. ${String(d.results[0].roll_number ?? '—')}` : 'No active registration', series: courses.map((_, i) => i + 1) };
    },
  },
  {
    id: 'announcements',
    label: 'Announcements',
    hint: 'Published for you',
    color: '#d6336c',
    to: '/communication',
    show: (_u, nav) => hasNav(nav, '/communication'),
    load: async () => {
      const d = await request<Page<Row>>('/communication/feed/?page_size=50');
      return { value: String(d.count), sub: d.results[0] ? String(d.results[0].title) : 'Nothing new', series: monthSeries(d.results.map((r) => r.publish_from)) };
    },
  },
  {
    id: 'requests',
    label: 'Certificate requests',
    hint: 'Requests you can see',
    color: '#1098ad',
    to: '/documents',
    show: (_u, nav) => hasNav(nav, '/documents'),
    load: async () => {
      const d = await request<Page<Row>>('/documents/certificates/?page_size=100');
      const open = d.results.filter((r) => ['SUBMITTED', 'UNDER_REVIEW'].includes(String(r.status))).length;
      return { value: String(d.count), sub: `${open} awaiting action`, series: monthSeries(d.results.map((r) => r.requested_at)) };
    },
  },
];

export function pickTiles(user: AuthUser, nav: NavItem[], max = 4): Tile[] {
  return TILES.filter((t) => t.show(user, nav)).slice(0, max);
}

function MetricCard({ tile }: { tile: Tile }) {
  const { year } = useAcademicYear();
  const q = useQuery({
    queryKey: ['dash-metric', tile.id, year?.id ?? null],
    queryFn: () => tile.load({ yearCode: year?.code, yearStart: year?.start, yearEnd: year?.end }),
    staleTime: 60_000,
    retry: false,
  });
  return (
    <Paper
      component={Link}
      to={tile.to}
      aria-label={`${tile.label}: ${q.isLoading ? 'loading' : (q.data?.value ?? 'unavailable')}`}
      sx={{ p: 2.25, textDecoration: 'none', color: 'inherit', display: 'block', transition: 'box-shadow .15s, border-color .15s', '&:hover': { borderColor: tile.color, boxShadow: '0 6px 18px rgba(20,33,61,.08)' } }}
    >
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 1 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>{tile.label}</Typography>
          <Typography sx={{ fontSize: 30, fontWeight: 700, lineHeight: 1.25, mt: 0.25 }}>
            {q.isLoading ? <Skeleton width={64} /> : (q.data?.value ?? '—')}
          </Typography>
        </Box>
        <Box sx={{ width: 4, height: 34, borderRadius: 2, bgcolor: tile.color, opacity: 0.85 }} />
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', minHeight: 20 }} noWrap>
        {q.isLoading ? ' ' : (q.data?.sub ?? tile.hint)}
      </Typography>
      <Box sx={{ mt: 0.5 }}>{q.data && <Sparkline values={q.data.series} color={tile.color} />}</Box>
    </Paper>
  );
}

// ---- weekly schedule ------------------------------------------------------------------------
type Occurrence = { id: string; course_section_id?: string; course_offering_section_id: string; date: string; start_time: string; end_time: string; course_label?: string; employee_label?: string; room_label?: string };

const PALETTE = [
  { bg: '#edf2ff', bar: '#3b5bdb' },
  { bg: '#e6fcf5', bar: '#0ca678' },
  { bg: '#fff4e6', bar: '#f08c00' },
  { bg: '#f3f0ff', bar: '#7048e8' },
  { bg: '#e3fafc', bar: '#1098ad' },
  { bg: '#fff0f6', bar: '#d6336c' },
];
const hash = (s: string) => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const hm = (t: string) => t.slice(0, 5);

export function weekOf(offset: number, now = new Date()): { monday: Date; days: Date[] } {
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7) + offset * 7);
  return { monday, days: Array.from({ length: 6 }, (_, i) => new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)) };
}

function ScheduleWidget() {
  const [offset, setOffset] = useState(0);
  const { monday, days } = weekOf(offset);
  const to = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6);
  const q = useQuery({
    queryKey: ['dash-schedule', iso(monday)],
    queryFn: () => request<{ results: Occurrence[] }>(`/timetable/occurrences/?date_from=${iso(monday)}&date_to=${iso(to)}`),
    staleTime: 60_000,
    retry: false,
  });
  if (q.isError) return null;
  const today = iso(new Date());
  const rows = q.data?.results ?? [];
  const label = `${days[0].toLocaleDateString(undefined, { day: 'numeric', month: 'short' })} – ${days[5].toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}`;
  return (
    <Paper sx={{ p: { xs: 2, sm: 2.5 } }}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
        <Box>
          <Typography variant="h6" component="h2">Weekly schedule</Typography>
          <Typography variant="body2" color="text.secondary">{label}</Typography>
        </Box>
        <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
          <IconButton size="small" aria-label="Previous week" onClick={() => setOffset((o) => o - 1)}><Icon name="chevronLeft" size={18} /></IconButton>
          <Button size="small" onClick={() => setOffset(0)} disabled={offset === 0}>This week</Button>
          <IconButton size="small" aria-label="Next week" onClick={() => setOffset((o) => o + 1)}><Icon name="chevronRight" size={18} /></IconButton>
          <Button component={Link} to="/timetable" size="small">Full timetable</Button>
        </Stack>
      </Stack>
      {q.isLoading ? (
        <Skeleton variant="rounded" height={160} />
      ) : (
        <Box sx={{ display: 'grid', gap: 1.25, gridTemplateColumns: { xs: 'repeat(2, minmax(0,1fr))', md: 'repeat(6, minmax(0,1fr))' } }}>
          {days.map((day) => {
            const key = iso(day);
            const items = rows.filter((r) => r.date === key).sort((a, b) => a.start_time.localeCompare(b.start_time));
            const isToday = key === today;
            return (
              <Box key={key} sx={{ minWidth: 0 }}>
                <Box sx={{ px: 1, py: 0.75, mb: 1, borderRadius: 1.5, bgcolor: isToday ? 'primary.main' : 'action.hover', color: isToday ? '#fff' : 'text.primary', textAlign: 'center' }}>
                  <Typography sx={{ fontSize: 12.5, fontWeight: 700 }}>{day.toLocaleDateString(undefined, { weekday: 'short' })}</Typography>
                  <Typography sx={{ fontSize: 12, opacity: 0.85 }}>{day.getDate()}</Typography>
                </Box>
                <Stack spacing={1}>
                  {items.length === 0 && <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center', py: 1 }}>No classes</Typography>}
                  {items.map((o) => {
                    const c = PALETTE[hash(String(o.course_offering_section_id)) % PALETTE.length];
                    return (
                      <Box key={o.id} sx={{ p: 1, borderRadius: 1.5, bgcolor: c.bg, borderLeft: `3px solid ${c.bar}` }}>
                        <Typography sx={{ fontSize: 11.5, fontWeight: 700, color: c.bar, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <Icon name="clock" size={12} /> {hm(o.start_time)}–{hm(o.end_time)}
                        </Typography>
                        <Typography sx={{ fontSize: 13, fontWeight: 600, lineHeight: 1.25, mt: 0.25 }}>{o.course_label ?? 'Class'}</Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }} noWrap>
                          {[o.room_label, o.employee_label].filter(Boolean).join(' · ')}
                        </Typography>
                      </Box>
                    );
                  })}
                </Stack>
              </Box>
            );
          })}
        </Box>
      )}
    </Paper>
  );
}

// ---- recent requests ------------------------------------------------------------------------
const STATUS: Record<string, { label: string; color: 'success' | 'warning' | 'info' | 'default' | 'error' }> = {
  ISSUED: { label: 'Approved', color: 'success' },
  APPROVED: { label: 'Approved', color: 'success' },
  SUBMITTED: { label: 'Pending', color: 'warning' },
  UNDER_REVIEW: { label: 'Under review', color: 'info' },
  REJECTED: { label: 'Rejected', color: 'error' },
  CANCELLED: { label: 'Cancelled', color: 'default' },
};

function RequestsWidget({ mine }: { mine: boolean }) {
  const q = useQuery({
    queryKey: ['dash-requests'],
    queryFn: async () => {
      const [list, types] = await Promise.all([
        request<Page<Row>>('/documents/certificates/?page_size=6'),
        request<Page<Row>>('/documents/types/?page_size=100').catch(() => ({ count: 0, results: [] as Row[] })),
      ]);
      const names = new Map(types.results.map((t) => [String(t.id), String(t.certificate_name ?? t.label)]));
      return list.results.map((r): Row => ({ ...r, type_name: names.get(String(r.certificate_type_id)) ?? 'Certificate' }));
    },
    staleTime: 60_000,
    retry: false,
  });
  if (q.isError) return null;
  const rows = q.data ?? [];
  return (
    <Paper sx={{ p: { xs: 2, sm: 2.5 }, overflow: 'hidden' }}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="h6" component="h2">{mine ? 'My requests' : 'Recent student requests'}</Typography>
        <Button component={Link} to="/documents" size="small">View all</Button>
      </Stack>
      {q.isLoading ? (
        <Skeleton variant="rounded" height={140} />
      ) : rows.length === 0 ? (
        <Typography color="text.secondary" sx={{ py: 2 }}>No requests yet.</Typography>
      ) : (
        <Box sx={{ overflowX: 'auto' }}>
          <Table aria-label="Recent requests">
            <TableHead>
              <TableRow>
                <TableCell>Request</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Requested</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r) => {
                const s = STATUS[String(r.status)] ?? { label: String(r.status), color: 'default' as const };
                const open = ['SUBMITTED', 'UNDER_REVIEW'].includes(String(r.status));
                return (
                  <TableRow key={String(r.id)}>
                    <TableCell sx={{ fontWeight: 600 }}>{String(r.request_number)}</TableCell>
                    <TableCell>{String(r.type_name)}</TableCell>
                    <TableCell>{r.requested_at ? new Date(String(r.requested_at)).toLocaleDateString() : '—'}</TableCell>
                    <TableCell><Chip size="small" color={s.color} variant={s.color === 'default' ? 'outlined' : 'filled'} label={s.label} /></TableCell>
                    <TableCell align="right">
                      <Button component={Link} to="/documents" size="small" variant={open && !mine ? 'contained' : 'text'}>{open && !mine ? 'Review' : 'View'}</Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Box>
      )}
    </Paper>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  if ((user as { must_change_password?: boolean } | null)?.must_change_password) {
    return <PasswordChange onChanged={() => window.location.reload()} />;
  }
  const nav = visibleNav(user);
  const items = nav.filter((n) => n.path !== '/dashboard');
  const tiles = user ? pickTiles(user, nav) : [];
  const student = !!user && isStudent(user);
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  return (
    <Stack spacing={3}>
      <PageHeader
        overline="Dashboard"
        title={`${greeting}, ${user?.username || 'colleague'}`}
        description="Here is what's happening across your campus today."
      />

      {tiles.length > 0 && (
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', lg: `repeat(${Math.min(tiles.length, 4)}, minmax(0, 1fr))` } }}>
          {tiles.map((t) => (
            <MetricCard key={t.id} tile={t} />
          ))}
        </Box>
      )}

      {nav.some((n) => n.path === '/timetable') && <ScheduleWidget />}
      {nav.some((n) => n.path === '/documents') && <RequestsWidget mine={student} />}

      {items.length === 0 && (
        <Alert severity="warning">No modules are visible for this account. Ask an administrator to grant access.</Alert>
      )}
    </Stack>
  );
}
