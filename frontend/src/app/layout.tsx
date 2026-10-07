import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  AppBar,
  Autocomplete,
  Avatar,
  Badge,
  Box,
  Button,
  Collapse,
  CssBaseline,
  Divider,
  Drawer,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
  Popover,
  Popper,
  Select,
  Stack,
  TextField,
  ThemeProvider,
  Toolbar,
  Typography,
  useMediaQuery,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth, type AuthUser } from '../lib/auth-context';
import { request } from '../lib/api-client';
import { AcademicYearProvider, useAcademicYear, type AcademicYear } from '../lib/academic-year';
import { roleLabel } from '../lib/role';
import { NAV_GROUPS, visibleNav, type NavItem } from './navigation';
import { theme } from './theme';
import { GROUP_ICONS, Icon } from './icons';
import { PwaStatus } from '../pwa/PwaStatus';
import { SupportBanner } from '../features/identity-access/SupportBanner';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { clearOfflineCopy } from '../pwa/offline';

const DRAWER_WIDTH = 252;
const TOPBAR = 64;
const NAVY = '#14213d';
const NAVY_LINE = 'rgba(255,255,255,.09)';
const SIDEBAR_TEXT = '#c4cee3';

function BrandMark() {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
      <Box
        aria-hidden
        sx={{
          width: 34,
          height: 34,
          borderRadius: '10px',
          flexShrink: 0,
          background: 'linear-gradient(135deg, #5b7cfa 0%, #3b5bdb 100%)',
          display: 'grid',
          placeItems: 'center',
          color: '#fff',
          fontWeight: 700,
          fontSize: 16,
          boxShadow: '0 4px 10px rgba(59,91,219,.35)',
        }}
      >
        S
      </Box>
      <Box sx={{ lineHeight: 1.15, minWidth: 0 }}>
        <Typography sx={{ fontWeight: 700, fontSize: 16, color: 'inherit' }}>SIMS</Typography>
        <Typography variant="caption" sx={{ color: 'inherit', opacity: 0.7, display: 'block', whiteSpace: 'nowrap' }}>
          University ERP
        </Typography>
      </Box>
    </Box>
  );
}

function NavGroup({
  group,
  items,
  pathname,
  flyout,
  onNavigate,
}: {
  group: string;
  items: NavItem[];
  pathname: string;
  flyout: boolean;
  onNavigate: () => void;
}) {
  const [open, setOpen] = useState(false);
  const anchor = useRef<HTMLDivElement | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const active = items.some((i) => pathname === i.path || pathname.startsWith(`${i.path}/`));
  const show = () => {
    window.clearTimeout(timer.current);
    setOpen(true);
  };
  const hide = () => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setOpen(false), 160);
  };
  // The flyout is a white card; the in-place (mobile) list sits on the navy drawer.
  const linkColor = flyout ? 'text.primary' : SIDEBAR_TEXT;
  const links = items.map((item) => {
    const here = pathname === item.path || pathname.startsWith(`${item.path}/`);
    return (
      <ListItem key={item.path} disablePadding>
        <ListItemButton
          component={Link}
          to={item.path}
          selected={here}
          onClick={() => {
            setOpen(false);
            onNavigate();
          }}
          sx={{
            px: 1.5,
            py: 0.9,
            color: linkColor,
            '&.Mui-selected': flyout ? {} : { backgroundColor: 'rgba(255,255,255,.1)', color: '#fff', '&:hover': { backgroundColor: 'rgba(255,255,255,.14)' } },
            '&:hover': flyout ? {} : { backgroundColor: 'rgba(255,255,255,.06)' },
          }}
        >
          <ListItemText
            primary={item.short}
            sx={{ '& .MuiListItemText-primary': { fontSize: 14.5, fontWeight: here ? 600 : 400, whiteSpace: 'nowrap' } }}
          />
        </ListItemButton>
      </ListItem>
    );
  });
  const trigger = (
    <ListItemButton
      selected={active && !open}
      onClick={() => (flyout ? show() : setOpen((v) => !v))}
      aria-haspopup="true"
      aria-expanded={open}
      sx={{
        px: 1.5,
        py: 1.1,
        gap: 1.5,
        color: active || open ? '#fff' : SIDEBAR_TEXT,
        backgroundColor: open ? 'rgba(255,255,255,.08)' : undefined,
        '&.Mui-selected': { backgroundColor: 'rgba(91,124,250,.22)', color: '#fff', '&:hover': { backgroundColor: 'rgba(91,124,250,.3)' } },
        '&:hover': { backgroundColor: 'rgba(255,255,255,.07)' },
      }}
    >
      <Icon name={GROUP_ICONS[group] ?? 'dashboard'} size={19} />
      <ListItemText primary={group} sx={{ '& .MuiListItemText-primary': { fontSize: 15, fontWeight: active ? 600 : 500 } }} />
      <Box component="span" aria-hidden sx={{ opacity: 0.7, display: 'grid', transform: flyout ? 'none' : open ? 'rotate(90deg)' : 'none', transition: 'transform .15s' }}>
        <Icon name="chevronRight" size={16} />
      </Box>
    </ListItemButton>
  );
  if (!flyout) {
    return (
      <Box component="li" sx={{ listStyle: 'none' }}>
        {trigger}
        <Collapse in={open} unmountOnExit>
          <List dense disablePadding sx={{ pl: 4.5, pb: 0.5 }}>{links}</List>
        </Collapse>
      </Box>
    );
  }
  return (
    <Box component="li" sx={{ listStyle: 'none' }} ref={anchor} onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide}>
      {trigger}
      <Popper open={open} anchorEl={anchor.current} placement="right-start" sx={{ zIndex: (t) => t.zIndex.drawer + 2 }} modifiers={[{ name: 'offset', options: { offset: [0, -4] } }]}>
        <Paper elevation={0} onMouseEnter={show} onMouseLeave={hide} sx={{ minWidth: 220, p: 0.75, ml: 0.5, boxShadow: '0 12px 32px rgba(20,33,61,.18)' }}>
          <List dense disablePadding aria-label={group}>{links}</List>
        </Paper>
      </Popper>
    </Box>
  );
}

function GlobalSearch({ items, onGo }: { items: NavItem[]; onGo: (path: string) => void }) {
  return (
    <Autocomplete
      size="small"
      options={items}
      value={null}
      blurOnSelect
      clearOnBlur
      getOptionLabel={(o) => o.title}
      groupBy={(o) => o.group}
      onChange={(_, option) => option && onGo(option.path)}
      noOptionsText="No matching module"
      sx={{ width: { md: 280, lg: 360 } }}
      renderInput={(params) => (
        <TextField
          {...params}
          placeholder="Search modules…"
          slotProps={{
            inputLabel: params.slotProps.inputLabel,
            htmlInput: { ...params.slotProps.htmlInput, 'aria-label': 'Search modules' },
            input: {
              ...params.slotProps.input,
              startAdornment: (
                <>
                  <InputAdornment position="start" sx={{ color: 'text.secondary' }}>
                    <Icon name="search" size={18} />
                  </InputAdornment>
                  {params.slotProps.input.startAdornment}
                </>
              ),
            },
          }}
          sx={{ '& .MuiOutlinedInput-root': { backgroundColor: 'rgba(241,244,250,.9)', borderRadius: 2.5, '& fieldset': { borderColor: 'transparent' } } }}
        />
      )}
    />
  );
}

type YearRow = { academic_year_id: number; year_code: string; start_date: string; end_date: string; status: string };

function YearSwitch() {
  const { year, choose } = useAcademicYear();
  const q = useQuery({
    queryKey: ['academic-years'],
    queryFn: () => request<{ results: YearRow[] }>('/calendar/academic-years/?page_size=50'),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const years: AcademicYear[] = (q.data?.results ?? []).map((r) => ({ id: r.academic_year_id, code: r.year_code, start: r.start_date, end: r.end_date, status: r.status }));
  useEffect(() => {
    if (!year && years.length) choose(years.find((y) => y.status === 'ACTIVE') ?? years[0]);
  }, [year, years.length]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!years.length) return null;
  return (
    <Select
      size="small"
      value={year ? String(year.id) : ''}
      onChange={(e) => choose(years.find((y) => String(y.id) === e.target.value) ?? null)}
      inputProps={{ 'aria-label': 'Academic year' }}
      startAdornment={<Box sx={{ mr: 1, display: 'grid', color: 'text.secondary' }}><Icon name="calendar" size={16} /></Box>}
      sx={{ display: { xs: 'none', lg: 'inline-flex' }, minWidth: 150, backgroundColor: 'rgba(241,244,250,.9)', borderRadius: 2.5, '& fieldset': { borderColor: 'transparent' } }}
    >
      {years.map((y) => (
        <MenuItem key={y.id} value={String(y.id)}>
          {y.code} · {y.status.toLowerCase()}
        </MenuItem>
      ))}
    </Select>
  );
}

type Announcement = { id: string; title: string; description?: string; type?: string; publish_from?: string };

function Notifications({ enabled }: { enabled: boolean }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const q = useQuery({
    queryKey: ['notifications'],
    queryFn: () => request<{ count: number; results: Announcement[] }>('/communication/feed/?page_size=5'),
    enabled,
    refetchInterval: 60_000,
    retry: false,
  });
  if (!enabled) return null;
  const count = q.data?.count ?? 0;
  return (
    <>
      <IconButton aria-label={`Notifications${count ? `, ${count} announcements` : ''}`} onClick={(e) => setAnchor(e.currentTarget)} sx={{ color: 'text.secondary' }}>
        <Badge badgeContent={count} color="error" max={99}>
          <Icon name="bell" size={21} />
        </Badge>
      </IconButton>
      <Popover open={!!anchor} anchorEl={anchor} onClose={() => setAnchor(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }} slotProps={{ paper: { sx: { width: 340, mt: 1 } } }}>
        <Box sx={{ p: 2, pb: 1 }}>
          <Typography variant="subtitle1">Announcements</Typography>
        </Box>
        <Divider />
        {count === 0 ? (
          <Typography color="text.secondary" sx={{ p: 2 }}>You're all caught up.</Typography>
        ) : (
          <List disablePadding>
            {q.data!.results.map((a) => (
              <ListItem key={a.id} divider sx={{ display: 'block', py: 1.25 }}>
                <Typography sx={{ fontWeight: 600, fontSize: 14 }}>{a.title}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {[a.type, a.publish_from ? new Date(a.publish_from).toLocaleDateString() : ''].filter(Boolean).join(' · ')}
                </Typography>
              </ListItem>
            ))}
          </List>
        )}
        <Box sx={{ p: 1 }}>
          <Button component={Link} to="/communication" size="small" fullWidth onClick={() => setAnchor(null)}>
            Open communication
          </Button>
        </Box>
      </Popover>
    </>
  );
}

export function quickActions(user: AuthUser, nav: NavItem[]): { label: string; to: string }[] {
  const has = (path: string) => nav.some((n) => n.path === path);
  const perm = (p: string) => user.is_superuser || user.permissions.includes(p);
  const student = (user.groups ?? []).includes('Student');
  const out: { label: string; to: string }[] = [];
  if (has('/people') && perm('people_master.add_student')) out.push({ label: 'Register a student', to: '/people/students' });
  if (has('/admissions')) out.push({ label: 'Review applications', to: '/admissions/applications' });
  if (has('/attendance') && !student) out.push({ label: 'Take attendance', to: '/attendance' });
  if (has('/communication') && !student && (user.is_superuser || user.permissions.some((p) => p.startsWith('communication.')))) out.push({ label: 'Post an announcement', to: '/communication' });
  if (has('/documents') && student) out.push({ label: 'Request a certificate', to: '/documents' });
  if (has('/registration') && student) out.push({ label: 'View my registration', to: '/registration' });
  return out;
}

function QuickActions({ actions }: { actions: { label: string; to: string }[] }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  if (!actions.length) return null;
  return (
    <>
      <Button variant="contained" size="small" startIcon={<Icon name="plus" size={16} />} onClick={(e) => setAnchor(e.currentTarget)} sx={{ display: { xs: 'none', sm: 'inline-flex' }, borderRadius: 2.5, px: 1.75 }}>
        Quick actions
      </Button>
      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)} slotProps={{ paper: { sx: { mt: 1, minWidth: 210 } } }}>
        {actions.map((a) => (
          <MenuItem key={a.to + a.label} component={Link} to={a.to} onClick={() => setAnchor(null)}>
            {a.label}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}

function AccountMenu({ user, busy, onSignOut }: { user: AuthUser; busy: boolean; onSignOut: () => void }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const role = roleLabel(user);
  return (
    <>
      <Button
        onClick={(e) => setAnchor(e.currentTarget)}
        aria-label="Account menu"
        aria-haspopup="menu"
        color="inherit"
        sx={{ textTransform: 'none', gap: 1.25, px: 1, borderRadius: 2.5, color: 'text.primary', border: 'none', backgroundColor: 'transparent', '&:hover': { backgroundColor: 'rgba(20,33,61,.05)', border: 'none' } }}
      >
        <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.light', color: 'primary.dark', fontSize: 14, fontWeight: 700 }}>{user.username.slice(0, 1).toUpperCase()}</Avatar>
        <Box sx={{ textAlign: 'left', lineHeight: 1.15, display: { xs: 'none', sm: 'block' } }}>
          <Typography sx={{ fontSize: 13.5, fontWeight: 600, maxWidth: 140 }} noWrap>{user.username}</Typography>
          <Typography variant="caption" color="text.secondary">{role}</Typography>
        </Box>
        <Box component="span" sx={{ display: { xs: 'none', sm: 'grid' }, color: 'text.secondary' }}><Icon name="chevronDown" size={16} /></Box>
      </Button>
      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)} slotProps={{ paper: { sx: { mt: 1, minWidth: 220 } } }}>
        <Box sx={{ px: 2, py: 1 }}>
          <Typography sx={{ fontWeight: 600 }}>{user.username}</Typography>
          <Typography variant="caption" color="text.secondary">{role}</Typography>
        </Box>
        <Divider />
        <MenuItem
          disabled={busy}
          onClick={() => {
            setAnchor(null);
            onSignOut();
          }}
          sx={{ gap: 1.25, mt: 0.5 }}
        >
          <Icon name="logout" size={18} /> Sign out
        </MenuItem>
      </Menu>
    </>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, signOut, busy } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const desktop = useMediaQuery(theme.breakpoints.up('md'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [signOutError, setSignOutError] = useState('');

  const nav = visibleNav(user);
  const grouped = NAV_GROUPS.map((group) => ({
    group,
    items: nav.filter((n) => n.group === group),
  })).filter((g) => g.items.length > 0);

  async function handleSignOut(): Promise<void> {
    clearOfflineCopy();
    setSignOutError('');
    try {
      await signOut();
      navigate('/login', { replace: true });
    } catch (e) {
      setSignOutError(e instanceof Error ? e.message : 'Sign-out failed.');
    }
  }

  const drawer = (
    <List sx={{ px: 1.5, py: 1.5 }} disablePadding>
      {grouped.map(({ group, items }) => (
        <NavGroup key={group} group={group} items={items} pathname={location.pathname} flyout={desktop} onNavigate={() => setMobileOpen(false)} />
      ))}
    </List>
  );

  const sidebarSx = { bgcolor: NAVY, color: '#fff', backgroundImage: `linear-gradient(180deg, ${NAVY} 0%, #0f182d 100%)` };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AcademicYearProvider>
        <PwaStatus userId={user?.user_id} />
        <Box sx={{ display: 'flex', minHeight: '100dvh', alignItems: 'stretch' }}>
          {desktop ? (
            <Box
              component="nav"
              aria-label="SIMS navigation"
              sx={{ ...sidebarSx, width: DRAWER_WIDTH, flexShrink: 0, position: 'sticky', top: 0, height: '100dvh', overflowY: 'auto', borderRight: `1px solid ${NAVY_LINE}` }}
            >
              <Box sx={{ height: TOPBAR, px: 2.5, display: 'flex', alignItems: 'center', borderBottom: `1px solid ${NAVY_LINE}` }}>
                <BrandMark />
              </Box>
              {drawer}
            </Box>
          ) : (
            <Drawer anchor="left" open={mobileOpen} onClose={() => setMobileOpen(false)} ModalProps={{ keepMounted: true }} slotProps={{ paper: { sx: { ...sidebarSx, width: DRAWER_WIDTH } } }}>
              <Box role="presentation">
                <Box sx={{ height: TOPBAR, px: 2.5, display: 'flex', alignItems: 'center', borderBottom: `1px solid ${NAVY_LINE}` }}>
                  <BrandMark />
                </Box>
                {drawer}
              </Box>
            </Drawer>
          )}

          <Box sx={{ flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
            <SupportBanner />
            <AppBar
              position="sticky"
              sx={{ backgroundColor: 'rgba(255,255,255,.78)', backdropFilter: 'blur(14px) saturate(1.4)', WebkitBackdropFilter: 'blur(14px) saturate(1.4)', borderBottom: '1px solid rgba(20,33,61,.08)' }}
            >
              <Toolbar sx={{ gap: { xs: 0.5, sm: 1.5 }, minHeight: `${TOPBAR}px !important`, px: { xs: 1.5, sm: 3 } }}>
                {!desktop && (
                  <IconButton edge="start" onClick={() => setMobileOpen((v) => !v)} aria-label="Open navigation">
                    <Icon name="menu" size={22} />
                  </IconButton>
                )}
                {!desktop && (
                  <Box sx={{ color: 'text.primary' }}>
                    <BrandMark />
                  </Box>
                )}
                {desktop && <GlobalSearch items={nav} onGo={(path) => navigate(path)} />}
                <Box sx={{ flexGrow: 1 }} />
                {user && (
                  <Stack direction="row" spacing={{ xs: 0.25, sm: 1.25 }} sx={{ alignItems: 'center' }}>
                    {nav.some((n) => n.path === '/calendar') && <YearSwitch />}
                    <QuickActions actions={quickActions(user, nav)} />
                    <Notifications enabled={nav.some((n) => n.path === '/communication')} />
                    <AccountMenu user={user} busy={busy} onSignOut={handleSignOut} />
                  </Stack>
                )}
              </Toolbar>
            </AppBar>
            {signOutError && (
              <Alert severity="error" action={<Button onClick={handleSignOut}>Retry server sign-out</Button>}>
                {signOutError}
              </Alert>
            )}
            <Box
              component="main"
              sx={{ flexGrow: 1, minWidth: 0, px: { xs: 2, sm: 3, lg: 4 }, py: { xs: 2.5, md: 3 }, pb: { xs: 6, md: 8 } }}
            >
              <Box sx={{ maxWidth: 1280, mx: 'auto', width: '100%' }}>
                <ErrorBoundary>{children}</ErrorBoundary>
              </Box>
            </Box>
          </Box>
        </Box>
      </AcademicYearProvider>
    </ThemeProvider>
  );
}

// Re-export to keep old import surface working if referenced.
export { theme };
