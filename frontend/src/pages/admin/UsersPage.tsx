import { useState } from 'react';
import {
  Alert, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, LinearProgress, MenuItem, Paper, Stack,
  Table, TableBody, TableCell, TableHead, TablePagination, TableRow, TextField, Tooltip, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import LockResetIcon from '@mui/icons-material/LockReset';
import LogoutIcon from '@mui/icons-material/Logout';
import BlockIcon from '@mui/icons-material/Block';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../api/auth';
import { api, errorMessage, fieldErrors } from '../../api/client';
import type { Page } from '../../api/types';
import { StatusChip } from '../../components/format';
import { PageHeader } from '../../components/PageHeader';
import UsersIcon from '@mui/icons-material/PeopleAltOutlined';

type RoleAssignment = { assignment_id: number; role_code: string; scope_type: string; scope_id: number | null };
type User = {
  user_id: number; username: string; email: string; first_name: string; last_name: string; is_active: boolean;
  is_superuser: boolean; account_status: string; mfa_enabled: boolean; roles: RoleAssignment[];
};
type Role = { role_id: number; role_code: string; role_name: string; role_level: string; is_assignable: boolean };

const SCOPES = ['GLOBAL', 'INSTITUTION', 'CAMPUS', 'DEPARTMENT', 'PROGRAMME', 'SELF'];
const LOOKUP: Record<string, string> = { INSTITUTION: 'organization/institution', CAMPUS: 'organization/campus', DEPARTMENT: 'organization/department', PROGRAMME: 'organization/programme' };

function CreateUser({ onClose, onCreated }: { onClose: () => void; onCreated: (pw: string | null, name: string) => void }) {
  const { user } = useAuth();
  const [v, setV] = useState({ username: '', email: '', first_name: '', last_name: '' });
  const [roleCode, setRoleCode] = useState('');
  const [institution, setInstitution] = useState('');
  const [scopeId, setScopeId] = useState('');
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<{ results: Role[] }>('/security/roles') });
  const orgs = useQuery({ queryKey: ['organisations'], enabled: !!user?.is_superuser, queryFn: () => api<{ results: { institution_id: number; institution_name: string }[] }>('/security/organisations') });
  const role = roles.data?.results.find((r) => r.role_code === roleCode);
  const level = role?.role_level ?? '';
  const lookup = useQuery({ queryKey: ['lookup', LOOKUP[level]], enabled: !!LOOKUP[level] && level !== 'INSTITUTION', queryFn: () => api<{ results: { id: number; label: string }[] }>(`/lookups/${LOOKUP[level]}`, { query: { limit: 100 } }) });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const create = useMutation({
    mutationFn: () => api<{ temporary_password?: string; username: string }>('/security/users', { method: 'POST', body: { ...v, ...(institution ? { institution_id: Number(institution) } : {}), ...(roleCode ? { role_code: roleCode, scope_type: level === 'GLOBAL' ? 'GLOBAL' : level, ...(LOOKUP[level] && level !== 'INSTITUTION' ? { scope_id: Number(scopeId) } : {}) } : {}) } }),
    onSuccess: (r) => onCreated(r.temporary_password ?? null, r.username),
    onError: (e) => setErrors({ ...fieldErrors(e), _: errorMessage(e) }),
  });
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>New user</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {errors._ && <Alert severity="error">{errors._}</Alert>}
          {(['username', 'email', 'first_name', 'last_name'] as const).map((k) => (
            <TextField key={k} label={k.replace('_', ' ')} value={v[k]} error={!!errors[k]} helperText={errors[k]}
              onChange={(e) => setV({ ...v, [k]: e.target.value })} required={k === 'username' || k === 'email'} />
          ))}
          {user?.is_superuser && (
            <TextField select label="Organisation" value={institution} onChange={(e) => setInstitution(e.target.value)} helperText="Leave empty for a platform-level account">
              <MenuItem value="">None (platform)</MenuItem>
              {orgs.data?.results.map((o) => <MenuItem key={o.institution_id} value={String(o.institution_id)}>{o.institution_name}</MenuItem>)}
            </TextField>
          )}
          <TextField select label="Role (optional)" value={roleCode} onChange={(e) => { setRoleCode(e.target.value); setScopeId(''); }}>
            <MenuItem value="">No role yet</MenuItem>
            {roles.data?.results.filter((r) => r.is_assignable).map((r) => <MenuItem key={r.role_code} value={r.role_code}>{r.role_name}</MenuItem>)}
          </TextField>
          {!!LOOKUP[level] && level !== 'INSTITUTION' && (
            <TextField select label={level.charAt(0) + level.slice(1).toLowerCase()} value={scopeId} onChange={(e) => setScopeId(e.target.value)} required>
              {lookup.data?.results.map((o) => <MenuItem key={o.id} value={String(o.id)}>{o.label}</MenuItem>)}
            </TextField>
          )}
          <Typography variant="caption" color="text.secondary">A temporary password is generated and shown once; the user must change it at first sign-in.</Typography>
        </Stack>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Cancel</Button><Button variant="contained" onClick={() => create.mutate()} disabled={!v.username || !v.email || (!!LOOKUP[level] && level !== 'INSTITUTION' && !scopeId) || create.isPending}>Create</Button></DialogActions>
    </Dialog>
  );
}

function Assign({ user, onClose }: { user: User; onClose: () => void }) {
  const qc = useQueryClient();
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<{ results: Role[] }>('/security/roles') });
  const [roleCode, setRoleCode] = useState('');
  const [scope, setScope] = useState('INSTITUTION');
  const [scopeId, setScopeId] = useState('');
  const lookup = useQuery({ queryKey: ['lookup', LOOKUP[scope]], enabled: !!LOOKUP[scope], queryFn: () => api<{ results: { id: number; label: string }[] }>(`/lookups/${LOOKUP[scope]}`, { query: { limit: 100 } }) });
  const assign = useMutation({
    mutationFn: () => api('/security/role-assignments', { method: 'POST', body: { user_id: user.user_id, role_code: roleCode, scope_type: scope, scope_id: LOOKUP[scope] ? Number(scopeId) : undefined } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); onClose(); },
  });
  const revoke = useMutation({ mutationFn: (id: number) => api(`/security/role-assignments/${id}`, { method: 'DELETE' }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); onClose(); } });
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Roles for {user.username}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {!!assign.error && <Alert severity="error">{errorMessage(assign.error)}</Alert>}
          {!!revoke.error && <Alert severity="error">{errorMessage(revoke.error)}</Alert>}
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
            {user.roles.map((r) => <Chip key={r.assignment_id} label={`${r.role_code} · ${r.scope_type}${r.scope_id ? ` #${r.scope_id}` : ''}`} onDelete={() => revoke.mutate(r.assignment_id)} />)}
            {user.roles.length === 0 && <Typography color="text.secondary">No roles assigned.</Typography>}
          </Stack>
          <TextField select label="Role" value={roleCode} onChange={(e) => { setRoleCode(e.target.value); const r = roles.data?.results.find((x) => x.role_code === e.target.value); if (r) setScope(r.role_level === 'SELF' ? 'SELF' : r.role_level); }}>
            {roles.data?.results.filter((r) => r.is_assignable || true).map((r) => <MenuItem key={r.role_code} value={r.role_code}>{r.role_name} ({r.role_level.toLowerCase()})</MenuItem>)}
          </TextField>
          <TextField select label="Scope" value={scope} onChange={(e) => { setScope(e.target.value); setScopeId(''); }}>{SCOPES.map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}</TextField>
          {LOOKUP[scope] && (
            <TextField select label={scope.charAt(0) + scope.slice(1).toLowerCase()} value={scopeId} onChange={(e) => setScopeId(e.target.value)}>
              {lookup.data?.results.map((o) => <MenuItem key={o.id} value={String(o.id)}>{o.label}</MenuItem>)}
            </TextField>
          )}
        </Stack>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Close</Button><Button variant="contained" disabled={!roleCode || (!!LOOKUP[scope] && !scopeId) || assign.isPending} onClick={() => assign.mutate()}>Assign role</Button></DialogActions>
    </Dialog>
  );
}

export function UsersPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [assigning, setAssigning] = useState<User | null>(null);
  const [secret, setSecret] = useState<{ username: string; password: string } | null>(null);
  const users = useQuery({ queryKey: ['users', page, search], queryFn: () => api<Page<User>>('/security/users', { query: { page, search: search || undefined } }), placeholderData: (p) => p });
  const refresh = () => qc.invalidateQueries({ queryKey: ['users'] });
  const reset = useMutation({ mutationFn: (u: User) => api<{ temporary_password: string }>(`/security/users/${u.user_id}/reset-password`, { method: 'POST' }).then((r) => ({ u, r })), onSuccess: ({ u, r }) => setSecret({ username: u.username, password: r.temporary_password }) });
  const sessions = useMutation({ mutationFn: (u: User) => api(`/security/users/${u.user_id}/revoke-sessions`, { method: 'POST' }) });
  const toggle = useMutation({ mutationFn: (u: User) => api(`/security/users/${u.user_id}`, { method: 'PATCH', body: { is_active: !u.is_active } }), onSuccess: refresh });
  const unlock = useMutation({ mutationFn: (u: User) => api(`/security/users/${u.user_id}/unlock`, { method: 'POST' }), onSuccess: refresh });

  return (
    <Stack spacing={2}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <PageHeader title="Users" subtitle="Create accounts, assign roles and manage access" icon={UsersIcon} crumbs={[{ label: 'Home', to: '/' }, { label: 'Administration' }, { label: 'Users' }]} />
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreating(true)}>New user</Button>
      </Stack>
      <TextField placeholder="Search users…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} sx={{ maxWidth: 360 }} />
      {!!users.error && <Alert severity="error">{errorMessage(users.error)}</Alert>}
      {!!(reset.error || toggle.error || sessions.error || unlock.error) && <Alert severity="error">{errorMessage(reset.error ?? toggle.error ?? sessions.error ?? unlock.error)}</Alert>}
      <Paper>
        {users.isFetching && <LinearProgress />}
        <Table size="small">
          <TableHead><TableRow><TableCell>User</TableCell><TableCell>Status</TableCell><TableCell>Roles</TableCell><TableCell align="right">Actions</TableCell></TableRow></TableHead>
          <TableBody>
            {users.data?.results.map((u) => (
              <TableRow key={u.user_id} hover>
                <TableCell><Typography variant="body2" sx={{ fontWeight: 600 }}>{u.username}{u.is_superuser && ' ★'}</Typography><Typography variant="caption" color="text.secondary">{[u.first_name, u.last_name].join(' ').trim() || u.email}</Typography></TableCell>
                <TableCell><StatusChip value={u.account_status} />{u.mfa_enabled && <Chip size="small" sx={{ ml: 0.5 }} label="MFA" />}</TableCell>
                <TableCell sx={{ maxWidth: 320 }}>{u.roles.map((r) => r.role_code).join(', ') || '—'}</TableCell>
                <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                  <Button size="small" onClick={() => setAssigning(u)}>Roles</Button>
                  <Tooltip title="Reset password"><IconButton size="small" aria-label="Reset password" onClick={() => reset.mutate(u)}><LockResetIcon fontSize="small" /></IconButton></Tooltip>
                  <Tooltip title="Sign out everywhere"><IconButton size="small" aria-label="Revoke sessions" onClick={() => sessions.mutate(u)}><LogoutIcon fontSize="small" /></IconButton></Tooltip>
                  <Tooltip title={u.is_active ? 'Deactivate' : 'Activate'}><IconButton size="small" aria-label="Toggle active" onClick={() => toggle.mutate(u)}><BlockIcon fontSize="small" color={u.is_active ? 'inherit' : 'error'} /></IconButton></Tooltip>
                  {u.account_status === 'ACTIVE' && <Button size="small" onClick={() => unlock.mutate(u)}>Unlock</Button>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <TablePagination component="div" count={users.data?.count ?? 0} page={page - 1} rowsPerPage={25} rowsPerPageOptions={[25]} onPageChange={(_, p) => setPage(p + 1)} />
      </Paper>
      {creating && <CreateUser onClose={() => setCreating(false)} onCreated={(pw, name) => { setCreating(false); refresh(); if (pw) setSecret({ username: name, password: pw }); }} />}
      {assigning && <Assign user={users.data?.results.find((u) => u.user_id === assigning.user_id) ?? assigning} onClose={() => setAssigning(null)} />}
      {secret && (
        <Dialog open onClose={() => setSecret(null)}>
          <DialogTitle>Temporary password for {secret.username}</DialogTitle>
          <DialogContent><Alert severity="warning" sx={{ mb: 2 }}>Shown once. Share it securely; the user must change it at first sign-in.</Alert><Typography sx={{ fontFamily: 'monospace', fontSize: 18, userSelect: 'all' }}>{secret.password}</Typography></DialogContent>
          <DialogActions><Button onClick={() => setSecret(null)}>Done</Button></DialogActions>
        </Dialog>
      )}
    </Stack>
  );
}
