import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { Box, Dialog, InputAdornment, List, ListItemButton, ListItemIcon, ListItemText, TextField, Typography } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useAuth, can } from '../api/auth';
import { useMeta } from '../api/hooks';
import { HomeIcon, WORKSPACES, iconForResource, navResources, workspaceOf, type Icon } from './navConfig';
import AccountIcon from '@mui/icons-material/ManageAccountsOutlined';

type Entry = { label: string; hint: string; to: string; icon: Icon };

/** Ctrl/⌘+K quick jump to any page the signed-in user can open (built only from what the API says they may see). */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const meta = useMeta();
  const [q, setQ] = useState('');
  const [active, setActive] = useState(0);

  const entries = useMemo<Entry[]>(() => {
    const list: Entry[] = [
      { label: 'Dashboard', hint: 'Home', to: '/', icon: HomeIcon },
      { label: 'Account and security', hint: 'Profile, password, devices', to: '/account', icon: AccountIcon },
    ];
    const visible = new Set<string>();
    for (const r of navResources(meta.data?.groups)) {
      const ws = workspaceOf(r);
      visible.add(ws);
      list.push({ label: r.title, hint: WORKSPACES.find((w) => w.key === ws)?.title ?? 'Page', to: `/r/${r.path}`, icon: iconForResource(r) });
    }
    for (const w of WORKSPACES) if (visible.has(w.key)) list.push({ label: w.title, hint: 'Area', to: `/w/${w.key}`, icon: w.icon });
    if (can(user, 'IAM.USERS.READ')) list.push({ label: 'Users', hint: 'Administration', to: '/admin/users', icon: AccountIcon });
    if (can(user, 'IAM.ROLES.READ')) list.push({ label: 'Roles and permissions', hint: 'Administration', to: '/admin/roles', icon: AccountIcon });
    if (can(user, 'AUDIT.AUDIT_LOG.READ')) list.push({ label: 'Audit trail', hint: 'Administration', to: '/admin/audit', icon: AccountIcon });
    return list;
  }, [meta.data, user]);

  const results = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (t ? entries.filter((e) => e.label.toLowerCase().includes(t) || e.hint.toLowerCase().includes(t)) : entries).slice(0, 40);
  }, [entries, q]);

  useEffect(() => setActive(0), [q, open]);
  useEffect(() => { if (!open) setQ(''); }, [open]);

  const go = (e?: Entry) => { if (e) { navigate(e.to); onClose(); } };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" slotProps={{ paper: { sx: { alignSelf: 'flex-start', mt: '12vh' } } }}>
      <Box sx={{ p: 2, pb: 1 }}>
        <TextField autoFocus placeholder="Search pages and records…  (↑ ↓ to move, Enter to open)" value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, results.length - 1)); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
            else if (e.key === 'Enter') go(results[active]);
          }}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon /></InputAdornment> }, htmlInput: { 'aria-label': 'Search pages' } }} />
      </Box>
      <List dense sx={{ maxHeight: 360, overflow: 'auto', pt: 0 }} role="listbox">
        {results.length === 0 && <Typography color="text.secondary" sx={{ p: 3, textAlign: 'center' }}>No matching pages.</Typography>}
        {results.map((e, i) => (
          <ListItemButton key={`${e.to}-${e.label}`} selected={i === active} onMouseEnter={() => setActive(i)} onClick={() => go(e)} role="option" aria-selected={i === active}>
            <ListItemIcon sx={{ minWidth: 36, color: 'primary.main' }}><e.icon fontSize="small" /></ListItemIcon>
            <ListItemText primary={e.label} secondary={e.hint} />
          </ListItemButton>
        ))}
      </List>
    </Dialog>
  );
}
