import { useState } from 'react';
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../lib/auth-context';
import { clearOfflineCopy } from '../../pwa/offline';
import { Icon, type IconName } from '../icons';

const HIGHLIGHTS: { icon: IconName; title: string; text: string }[] = [
  { icon: 'academic', title: 'Academics in one place', text: 'Curriculum, timetable, attendance and results.' },
  { icon: 'people', title: 'Student lifecycle', text: 'From admission to registration and records.' },
  { icon: 'shield', title: 'Secure by role', text: 'Everyone sees only what their role allows.' },
];

function Brand({ light = false }: { light?: boolean }) {
  return (
    <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', color: light ? '#fff' : 'text.primary' }}>
      <Box
        aria-hidden
        sx={{ width: 40, height: 40, borderRadius: '11px', background: 'linear-gradient(135deg,#5b7cfa,#3b5bdb)', color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 18, boxShadow: '0 6px 14px rgba(59,91,219,.35)' }}
      >
        S
      </Box>
      <Box>
        <Typography sx={{ fontWeight: 700, fontSize: 20, lineHeight: 1.1 }}>SIMS</Typography>
        <Typography variant="body2" sx={{ opacity: light ? 0.75 : 1, color: light ? 'inherit' : 'text.secondary' }}>
          Student Information Management System
        </Typography>
      </Box>
    </Stack>
  );
}

export function LoginPage() {
  const { signIn, busy, failure, retryLogout, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: string } };
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mfa, setMfa] = useState('');

  async function onSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    clearOfflineCopy();
    try {
      await signIn(username.trim(), password, mfa || undefined);
      setMfa('');
      setPassword('');
      navigate(location.state?.from || '/dashboard', { replace: true });
    } catch {
      setPassword('');
    }
  }

  return (
    <Box sx={{ minHeight: '100dvh', display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'minmax(360px, 5fr) minmax(420px, 6fr)' }, bgcolor: 'background.default' }}>
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'space-between',
          p: { md: 5, lg: 7 },
          color: '#fff',
          position: 'relative',
          overflow: 'hidden',
          backgroundImage: 'linear-gradient(160deg, #1b2b52 0%, #14213d 55%, #0e182d 100%)',
        }}
      >
        <Box aria-hidden sx={{ position: 'absolute', width: 420, height: 420, borderRadius: '50%', right: -140, top: -120, background: 'radial-gradient(circle, rgba(91,124,250,.35), transparent 68%)' }} />
        <Box aria-hidden sx={{ position: 'absolute', width: 360, height: 360, borderRadius: '50%', left: -120, bottom: -140, background: 'radial-gradient(circle, rgba(12,166,120,.22), transparent 68%)' }} />
        <Box sx={{ position: 'relative' }}>
          <Brand light />
        </Box>
        <Box sx={{ position: 'relative', maxWidth: 460 }}>
          <Typography component="p" sx={{ fontSize: { md: 30, lg: 36 }, fontWeight: 700, lineHeight: 1.2, letterSpacing: '-0.02em' }}>
            Everything your campus needs, in one place.
          </Typography>
          <Stack spacing={2.5} sx={{ mt: 4 }}>
            {HIGHLIGHTS.map((h) => (
              <Stack key={h.title} direction="row" spacing={2} sx={{ alignItems: 'flex-start' }}>
                <Box sx={{ width: 38, height: 38, borderRadius: '10px', bgcolor: 'rgba(255,255,255,.1)', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                  <Icon name={h.icon} size={19} />
                </Box>
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>{h.title}</Typography>
                  <Typography variant="body2" sx={{ opacity: 0.72 }}>{h.text}</Typography>
                </Box>
              </Stack>
            ))}
          </Stack>
        </Box>
        <Typography variant="caption" sx={{ position: 'relative', opacity: 0.55 }}>
          © {new Date().getFullYear()} SIMS · University ERP
        </Typography>
      </Box>

      <Box sx={{ display: 'grid', placeItems: 'center', p: { xs: 2.5, sm: 4 } }}>
        <Box sx={{ width: '100%', maxWidth: 400 }}>
          <Box sx={{ display: { xs: 'block', md: 'none' }, mb: 4 }}>
            <Brand />
          </Box>
          <Stack component="form" spacing={2.5} onSubmit={onSubmit}>
            <Box>
              <Typography variant="h5" component="h1" sx={{ fontSize: '1.65rem', letterSpacing: '-0.01em' }}>
                Sign in
              </Typography>
              <Typography color="text.secondary" sx={{ mt: 0.5 }}>
                Use your campus username and password.
              </Typography>
            </Box>
            {failure && <Alert severity="error">{failure}</Alert>}
            {retryLogout && (
              <Button disabled={busy} onClick={() => void signOut()}>
                Retry server sign-out
              </Button>
            )}
            <TextField
              label="Username"
              autoComplete="username"
              required
              fullWidth
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={busy}
            />
            <TextField
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              fullWidth
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
            />
            <TextField
              label="Verification code (only if enabled)"
              type="password"
              autoComplete="one-time-code"
              fullWidth
              value={mfa}
              onChange={(e) => setMfa(e.target.value)}
              disabled={busy}
            />
            <Button type="submit" variant="contained" size="large" disabled={busy} fullWidth sx={{ py: 1.25, fontSize: 15.5 }}>
              {busy ? 'Please wait…' : 'Sign in'}
            </Button>
            <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>
              Trouble signing in? Contact your campus administrator.
            </Typography>
          </Stack>
        </Box>
      </Box>
    </Box>
  );
}
