import OrgIcon from '@mui/icons-material/ApartmentOutlined';
import { useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import {
  AppBar, Avatar, Badge, Box, Button, Collapse, Divider, Drawer, IconButton, List, ListItemButton, ListItemIcon, ListItemText,
  ListSubheader, Menu, MenuItem, Toolbar, Tooltip, Typography, useMediaQuery,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import AccountIcon from '@mui/icons-material/ManageAccountsOutlined';
import AuditIcon from '@mui/icons-material/HistoryOutlined';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import ChevronRight from '@mui/icons-material/ChevronRight';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import FeedbackIcon from '@mui/icons-material/RateReviewOutlined';
import JobsIcon from '@mui/icons-material/MemoryOutlined';
import Logout from '@mui/icons-material/LogoutOutlined';
import MenuIcon from '@mui/icons-material/Menu';
import NotificationsIcon from '@mui/icons-material/NotificationsNoneOutlined';
import RolesIcon from '@mui/icons-material/VpnKeyOutlined';
import SearchIcon from '@mui/icons-material/Search';
import UsersIcon from '@mui/icons-material/PeopleAltOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { can, useAuth } from '../api/auth';
import { api } from '../api/client';
import { useMeta } from '../api/hooks';
import type { Dashboard, Notice, Page } from '../api/types';
import { AiAssistant } from '../ai/AiAssistant';
import { ColorModeToggle } from '../components/ColorModeToggle';
import { formatDateTime } from '../components/format';
import { CommandPalette } from './CommandPalette';
import { HomeIcon, WORKSPACES, iconForResource, isSetup, navResources, workspaceOf, type Icon } from './navConfig';

const FULL = 272;
const RAIL = 76;

function Brand({ compact }: { compact: boolean }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: compact ? 0 : 2.5, justifyContent: compact ? 'center' : 'flex-start', height: 64 }}>
      <Box sx={{ width: 36, height: 36, borderRadius: 2.5, display: 'grid', placeItems: 'center', color: '#fff', fontWeight: 800,
        background: 'linear-gradient(135deg,#FB923C,#C2410C)', boxShadow: '0 4px 12px rgba(234,88,12,.35)' }}>S</Box>
      {!compact && (
        <Box>
          <Typography sx={{ fontWeight: 800, letterSpacing: 1.5, lineHeight: 1 }}>SIMS</Typography>
          <Typography variant="caption" color="text.secondary">Campus management</Typography>
        </Box>
      )}
    </Box>
  );
}

function NavRow({ to, label, icon: IconCmp, compact, end, nested, onClick }: {
  to: string; label: string; icon?: Icon; compact: boolean; end?: boolean; nested?: boolean; onClick?: () => void;
}) {
  const item = (
    <ListItemButton component={NavLink} to={to} end={end} onClick={onClick}
      sx={{ mx: 1, my: 0.25, borderRadius: 2, minHeight: nested ? 36 : 44, pl: nested ? 6 : compact ? 0 : 2, justifyContent: compact ? 'center' : 'flex-start', position: 'relative',
        '&.active': { bgcolor: 'action.selected', color: 'primary.main', fontWeight: 700,
          '&::before': { content: '""', position: 'absolute', left: -8, top: 8, bottom: 8, width: 4, borderRadius: 4, bgcolor: 'primary.main' } } }}>
      {IconCmp && <ListItemIcon sx={{ minWidth: compact ? 0 : 40, color: 'inherit', justifyContent: 'center' }}><IconCmp fontSize={nested ? 'small' : 'medium'} /></ListItemIcon>}
      {!compact && <ListItemText primary={label} slotProps={{ primary: { variant: 'body2', noWrap: true, sx: { fontWeight: 'inherit' } } }} />}
    </ListItemButton>
  );
  return compact ? <Tooltip title={label} placement="right">{item}</Tooltip> : item;
}

function Bell() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const summary = useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/dashboard'), refetchInterval: 60_000 });
  const items = useQuery({ queryKey: ['notifications'], queryFn: () => api<Page<Notice>>('/notifications', { query: { page_size: 8 } }), enabled: !!anchor });
  const readAll = useMutation({
    mutationFn: () => api('/notifications/read-all', { method: 'POST' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['notifications'] }); qc.invalidateQueries({ queryKey: ['dashboard'] }); },
  });
  return (
    <>
      <Tooltip title="Notifications">
        <IconButton color="inherit" aria-label="Notifications" onClick={(e) => setAnchor(e.currentTarget)}>
          <Badge color="primary" badgeContent={summary.data?.unread_notifications ?? 0}><NotificationsIcon /></Badge>
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)} slotProps={{ paper: { sx: { width: 380, maxWidth: '95vw' } } }}>
        <Box sx={{ px: 2, py: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle2">Notifications</Typography>
          <Button size="small" onClick={() => readAll.mutate()}>Mark all read</Button>
        </Box>
        <Divider />
        {items.data?.results.length === 0 && <MenuItem disabled>You are all caught up.</MenuItem>}
        {items.data?.results.map((n) => (
          <MenuItem key={n.notification_id} sx={{ whiteSpace: 'normal', display: 'block', borderLeft: 3, borderColor: n.read_at ? 'transparent' : 'primary.main' }}
            onClick={() => { api(`/notifications/${n.notification_id}/read`, { method: 'POST' }).then(() => qc.invalidateQueries({ queryKey: ['dashboard'] })); setAnchor(null); if (n.link) navigate(n.link); }}>
            <Typography variant="body2" sx={{ fontWeight: n.read_at ? 400 : 700 }}>{n.title}</Typography>
            {n.body && <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{n.body}</Typography>}
            <Typography variant="caption" color="text.disabled">{formatDateTime(n.created_at)}</Typography>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}

export function Shell() {
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up('md'));
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const meta = useMeta();
  const [drawer, setDrawer] = useState(false);
  const [menu, setMenu] = useState<HTMLElement | null>(null);
  const [palette, setPalette] = useState(false);
  const [collapsed, setCollapsed] = useState(() => { try { return localStorage.getItem('sims.nav') === 'rail'; } catch { return false; } });
  const [openWs, setOpenWs] = useState<string | null>(null);
  const compact = desktop && collapsed;

  useEffect(() => { try { localStorage.setItem('sims.nav', collapsed ? 'rail' : 'full'); } catch { /* storage unavailable */ } }, [collapsed]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette(true); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Only areas and pages the API says this user can read (role-based access decides what exists here).
  const areas = useMemo(() => {
    const byKey = new Map<string, { path: string; title: string; icon: Icon; setup: boolean }[]>();
    for (const r of navResources(meta.data?.groups)) {
      const k = workspaceOf(r);
      if (!byKey.has(k)) byKey.set(k, []);
      byKey.get(k)!.push({ path: r.path, title: r.title, icon: iconForResource(r), setup: isSetup(r) });
    }
    return WORKSPACES.filter((w) => byKey.has(w.key)).map((w) => ({ ...w, items: byKey.get(w.key)!.sort((a, b) => a.title.localeCompare(b.title)) }));
  }, [meta.data]);

  // The area containing the current page is expanded automatically.
  useEffect(() => {
    const m = /^\/(?:r\/([^/]+\/[^/]+)|w\/([^/]+))/.exec(location.pathname);
    if (!m) return;
    const hit = m[2] ? areas.find((a) => a.key === m[2]) : areas.find((a) => a.items.some((i) => i.path === m[1]));
    if (hit) setOpenWs(hit.key);
  }, [location.pathname, areas]);

  const mine = [(user?.student_ids.length ?? 0) > 0 && can(user, 'FEEDBACK.FEEDBACK_RESPONSE.CREATE') && { to: '/feedback', label: 'Course feedback', icon: FeedbackIcon }].filter(Boolean) as { to: string; label: string; icon: Icon }[];
  const admin = [
    user?.is_superuser && { to: '/owner', label: 'Owner dashboard', icon: AuditIcon },
    can(user, 'IAM.USERS.READ') && { to: '/admin/organisations', label: user?.is_superuser ? 'Organisations' : 'My organisation', icon: OrgIcon },
    can(user, 'IAM.USERS.READ') && { to: '/admin/users', label: 'Users', icon: UsersIcon },
    can(user, 'IAM.ROLES.READ') && { to: '/admin/roles', label: 'Roles & permissions', icon: RolesIcon },
    can(user, 'AUDIT.AUDIT_LOG.READ') && { to: '/admin/audit', label: 'Audit trail', icon: AuditIcon },
    can(user, 'IAM.OPERATIONS.CONFIGURE') && { to: '/admin/jobs', label: 'Background jobs', icon: JobsIcon },
  ].filter(Boolean) as { to: string; label: string; icon: Icon }[];

  const close = () => setDrawer(false);
  const nav = (
    <Box role="navigation" aria-label="Main" sx={{ width: compact ? RAIL : FULL, display: 'flex', flexDirection: 'column', height: '100%', transition: 'width .2s' }}>
      <Brand compact={compact} />
      <Box sx={{ flexGrow: 1, overflowY: 'auto', pb: 2 }}>
        <List disablePadding>
          <NavRow to="/" end label="Home" icon={HomeIcon} compact={compact} onClick={close} />
          {areas.map((a) => {
            const isOpen = !compact && openWs === a.key;
            return (
              <Box key={a.key}>
                {compact ? (
                  <NavRow to={`/w/${a.key}`} label={a.title} icon={a.icon} compact onClick={close} />
                ) : (
                  <ListItemButton onClick={() => { setOpenWs(isOpen ? null : a.key); navigate(`/w/${a.key}`); }}
                    sx={{ mx: 1, my: 0.25, borderRadius: 2, minHeight: 44, color: isOpen ? 'primary.main' : 'text.primary' }}>
                    <ListItemIcon sx={{ minWidth: 40, color: 'inherit' }}><a.icon /></ListItemIcon>
                    <ListItemText primary={a.title} slotProps={{ primary: { variant: 'body2', sx: { fontWeight: 600 } } }} />
                    {isOpen ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
                  </ListItemButton>
                )}
                <Collapse in={isOpen} unmountOnExit>
                  <List disablePadding>
                    {a.items.filter((i) => !i.setup).slice(0, 9).map((i) => <NavRow key={i.path} to={`/r/${i.path}`} label={i.title} icon={i.icon} compact={false} nested onClick={close} />)}
                    {a.items.length > a.items.filter((i) => !i.setup).slice(0, 9).length && <NavRow to={`/w/${a.key}`} label={`All ${a.items.length} pages`} compact={false} nested onClick={close} />}
                  </List>
                </Collapse>
              </Box>
            );
          })}
          {mine.length > 0 && (
            <>
              {!compact && <ListSubheader disableSticky sx={{ bgcolor: 'transparent', lineHeight: '36px', mt: 1 }}>My tools</ListSubheader>}
              {mine.map((m) => <NavRow key={m.to} {...m} compact={compact} onClick={close} />)}
            </>
          )}
          {admin.length > 0 && (
            <>
              {compact ? <Divider sx={{ my: 1 }} /> : <ListSubheader disableSticky sx={{ bgcolor: 'transparent', lineHeight: '36px', mt: 1 }}>Administration</ListSubheader>}
              {admin.map((m) => <NavRow key={m.to} {...m} compact={compact} onClick={close} />)}
            </>
          )}
        </List>
      </Box>
      {desktop && (
        <Box sx={{ p: 1, borderTop: 1, borderColor: 'divider', display: 'flex', justifyContent: compact ? 'center' : 'flex-end' }}>
          <Tooltip title={collapsed ? 'Expand menu' : 'Collapse menu'}>
            <IconButton size="small" aria-label={collapsed ? 'Expand menu' : 'Collapse menu'} onClick={() => setCollapsed(!collapsed)}>{collapsed ? <ChevronRight /> : <ChevronLeft />}</IconButton>
          </Tooltip>
        </Box>
      )}
    </Box>
  );

  const width = desktop ? (collapsed ? RAIL : FULL) : 0;
  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar position="fixed" color="inherit" elevation={0}
        sx={{ width: `calc(100% - ${width}px)`, ml: `${width}px`, borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper', color: 'text.primary', transition: 'width .2s, margin .2s' }}>
        <Toolbar sx={{ gap: 1 }}>
          {!desktop && <IconButton edge="start" aria-label="Open navigation" onClick={() => setDrawer(true)}><MenuIcon /></IconButton>}
          <Button onClick={() => setPalette(true)} startIcon={<SearchIcon />} color="inherit" aria-label="Search pages"
            sx={{ flexGrow: { xs: 1, md: 0 }, minWidth: { md: 360 }, justifyContent: 'flex-start', color: 'text.secondary', bgcolor: 'action.hover', border: 1, borderColor: 'divider', px: 2 }}>
            <Box component="span" sx={{ flexGrow: 1, textAlign: 'left' }}>Search…</Box>
            <Box component="kbd" sx={{ display: { xs: 'none', md: 'inline' }, fontSize: 11, border: 1, borderColor: 'divider', borderRadius: 1, px: 0.75 }}>Ctrl K</Box>
          </Button>
          <Box sx={{ flexGrow: 1 }} />
          <AiAssistant />
          <ColorModeToggle />
          <Bell />
          <Tooltip title="Account">
            <IconButton onClick={(e) => setMenu(e.currentTarget)} aria-label="Account menu" sx={{ ml: 0.5 }}>
              <Avatar sx={{ width: 34, height: 34, bgcolor: 'primary.main', color: 'primary.contrastText', fontSize: 14, fontWeight: 700 }}>
                {(user?.full_name || user?.username || '?').slice(0, 1).toUpperCase()}
              </Avatar>
            </IconButton>
          </Tooltip>
          <Menu anchorEl={menu} open={!!menu} onClose={() => setMenu(null)}>
            <Box sx={{ px: 2, py: 1, maxWidth: 280 }}>
              <Typography variant="subtitle2">{user?.full_name}</Typography>
              <Typography variant="caption" color="text.secondary">{user?.roles.join(', ') || (user?.is_superuser ? 'Super administrator' : 'No role assigned')}</Typography>
            </Box>
            <Divider />
            <MenuItem onClick={() => { setMenu(null); navigate('/account'); }}><ListItemIcon><AccountIcon fontSize="small" /></ListItemIcon>Account and security</MenuItem>
            <MenuItem onClick={async () => { setMenu(null); await signOut(); navigate('/login', { replace: true }); }}><ListItemIcon><Logout fontSize="small" /></ListItemIcon>Sign out</MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>
      {desktop ? (
        <Drawer variant="permanent" sx={{ width, flexShrink: 0, '& .MuiDrawer-paper': { width, boxSizing: 'border-box', borderRight: 1, borderColor: 'divider', overflowX: 'hidden', transition: 'width .2s' } }}>{nav}</Drawer>
      ) : (
        <Drawer open={drawer} onClose={close} ModalProps={{ keepMounted: true }}>{nav}</Drawer>
      )}
      <Box component="main" sx={{ flexGrow: 1, minWidth: 0, p: { xs: 2, md: 4 }, maxWidth: 1600 }}>
        <Toolbar />
        <Outlet />
      </Box>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </Box>
  );
}
