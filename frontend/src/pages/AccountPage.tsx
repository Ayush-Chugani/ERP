import { useState, type FormEvent } from 'react';
import {
  Alert, Button, Chip, Divider, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../api/auth';
import { api, errorMessage, fieldErrors, setAccessToken } from '../api/client';
import { formatDateTime } from '../components/format';
import { PageHeader } from '../components/PageHeader';
import AccountIcon from '@mui/icons-material/ManageAccountsOutlined';

type Sess = { session_id: string; created_at: string; last_used_at: string; ip_address: string | null; user_agent: string | null; current: boolean };

function csrf(): Record<string, string> {
  const hit = document.cookie.split('; ').find((c) => c.startsWith('sims_csrf='));
  return hit ? { 'X-CSRF-Token': decodeURIComponent(hit.slice(10)) } : {};
}

export function AccountPage() {
  const { user, reload } = useAuth();
  const qc = useQueryClient();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);

  const sessions = useQuery({ queryKey: ['sessions'], queryFn: () => api<{ results: Sess[] }>('/auth/sessions') });
  const change = useMutation({
    mutationFn: () => api<{ access: string }>('/auth/change-password', { method: 'POST', body: { current_password: current, new_password: next } }),
    onSuccess: async (r) => {
      setAccessToken(r.access);
      setCurrent(''); setNext(''); setConfirm('');
      setMsg({ type: 'success', text: 'Password changed. Other devices have been signed out.' });
      await reload();
      qc.invalidateQueries({ queryKey: ['sessions'] });
    },
    onError: (e) => setMsg({ type: 'error', text: Object.values(fieldErrors(e)).join(' ') || errorMessage(e) }),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/auth/sessions/${id}`, { method: 'DELETE', headers: csrf() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  });
  const startMfa = useMutation({ mutationFn: () => api<{ secret: string; otpauth_uri: string }>('/auth/mfa/setup', { method: 'POST' }), onSuccess: setSetup });
  const enableMfa = useMutation({
    mutationFn: () => api('/auth/mfa/enable', { method: 'POST', body: { code: mfaCode } }),
    onSuccess: async () => { setSetup(null); setMfaCode(''); setMsg({ type: 'success', text: 'Two-step verification is on.' }); await reload(); },
    onError: (e) => setMsg({ type: 'error', text: errorMessage(e) }),
  });
  const disableMfa = useMutation({
    mutationFn: () => api('/auth/mfa/disable', { method: 'POST', body: { code: mfaCode, password: current } }),
    onSuccess: async () => { setMfaCode(''); setCurrent(''); setMsg({ type: 'success', text: 'Two-step verification is off.' }); await reload(); },
    onError: (e) => setMsg({ type: 'error', text: errorMessage(e) }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setMsg(null);
    if (next !== confirm) return setMsg({ type: 'error', text: 'The new passwords do not match.' });
    change.mutate();
  };

  return (
    <Stack spacing={3} sx={{ maxWidth: 900 }}>
      <PageHeader title="Account and security" subtitle="Profile, password, two-step verification and signed-in devices" icon={AccountIcon} crumbs={[{ label: 'Home', to: '/' }, { label: 'Account' }]} />
      {user?.must_change_password && <Alert severity="warning">You must choose a new password before you can use the system.</Alert>}
      {msg && <Alert severity={msg.type} onClose={() => setMsg(null)}>{msg.text}</Alert>}

      <Paper sx={{ p: 3 }}>
        <Typography variant="h6">Profile</Typography>
        <Typography>{user?.full_name} · {user?.username}</Typography>
        <Typography color="text.secondary">{user?.email}</Typography>
        <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap' }}>{user?.roles.map((r) => <Chip key={r} size="small" label={r} />)}</Stack>
      </Paper>

      <Paper component="form" onSubmit={submit} sx={{ p: 3 }}>
        <Stack spacing={2} sx={{ maxWidth: 420 }}>
          <Typography variant="h6">Change password</Typography>
          <TextField label="Current password" type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          <TextField label="New password" type="password" autoComplete="new-password" required value={next} onChange={(e) => setNext(e.target.value)}
            helperText="At least 12 characters, mixing three of: lowercase, uppercase, digits, symbols." />
          <TextField label="Confirm new password" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          <Button type="submit" variant="contained" disabled={change.isPending}>Update password</Button>
        </Stack>
      </Paper>

      <Paper sx={{ p: 3 }}>
        <Stack spacing={2} sx={{ maxWidth: 520 }}>
          <Typography variant="h6">Two-step verification</Typography>
          {user?.mfa_enabled ? (
            <>
              <Alert severity="success">Enabled. You will be asked for a code from your authenticator app when you sign in.</Alert>
              <TextField label="Authenticator code" value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} />
              <TextField label="Current password" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} />
              <Button color="error" onClick={() => disableMfa.mutate()} disabled={!mfaCode || !current}>Turn off</Button>
            </>
          ) : setup ? (
            <>
              <Typography variant="body2">Add this key to an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password…), then enter the 6-digit code.</Typography>
              <Typography sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{setup.secret}</Typography>
              <TextField label="6-digit code" value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} slotProps={{ htmlInput: { inputMode: 'numeric', maxLength: 6 } }} />
              <Button variant="contained" onClick={() => enableMfa.mutate()} disabled={mfaCode.length !== 6}>Confirm and enable</Button>
            </>
          ) : (
            <Button variant="outlined" onClick={() => startMfa.mutate()}>Set up two-step verification</Button>
          )}
        </Stack>
      </Paper>

      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Signed-in devices</Typography>
        <Divider />
        <Table size="small">
          <TableHead><TableRow><TableCell>Device</TableCell><TableCell>Last active</TableCell><TableCell>Address</TableCell><TableCell /></TableRow></TableHead>
          <TableBody>
            {sessions.data?.results.map((s) => (
              <TableRow key={s.session_id}>
                <TableCell sx={{ maxWidth: 280 }}><Typography variant="body2" noWrap title={s.user_agent ?? ''}>{s.user_agent || 'Unknown'}</Typography></TableCell>
                <TableCell>{formatDateTime(s.last_used_at)}</TableCell>
                <TableCell>{s.ip_address}</TableCell>
                <TableCell align="right">{s.current ? <Chip size="small" color="primary" label="This device" /> : <Button size="small" color="error" onClick={() => revoke.mutate(s.session_id)}>Sign out</Button>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
