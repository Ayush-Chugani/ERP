import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router';
import { Alert, Box, Button, IconButton, InputAdornment, Stack, TextField, Typography } from '@mui/material';
import LockOutlined from '@mui/icons-material/LockOutlined';
import PersonOutline from '@mui/icons-material/PersonOutlined';
import School from '@mui/icons-material/SchoolOutlined';
import Security from '@mui/icons-material/VerifiedUserOutlined';
import Insights from '@mui/icons-material/InsightsOutlined';
import ArrowBack from '@mui/icons-material/ArrowBackOutlined';
import AdminPanel from '@mui/icons-material/AdminPanelSettingsOutlined';
import Apartment from '@mui/icons-material/ApartmentOutlined';
import Badge from '@mui/icons-material/BadgeOutlined';
import FactCheck from '@mui/icons-material/FactCheckOutlined';
import HowToReg from '@mui/icons-material/HowToRegOutlined';
import Support from '@mui/icons-material/SupportAgentOutlined';
import type { SvgIconComponent } from '@mui/icons-material';
import Visibility from '@mui/icons-material/VisibilityOutlined';
import VisibilityOff from '@mui/icons-material/VisibilityOffOutlined';
import { useAuth } from '../api/auth';
import { ApiError, errorMessage } from '../api/client';
import { ColorModeToggle } from '../components/ColorModeToggle';

export const PORTALS: { key: string; title: string; blurb: string; icon: SvgIconComponent }[] = [
  { key: 'student', title: 'Student', blurb: 'Your record, timetable, results and requests', icon: School },
  { key: 'faculty', title: 'Faculty', blurb: 'Attendance, marks, mentoring and research records', icon: Badge },
  { key: 'leadership', title: 'Department & campus heads', blurb: 'Reviews, approvals and oversight', icon: Apartment },
  { key: 'office', title: 'Registrar & admissions', blurb: 'Admissions, enrolment, documents and the calendar', icon: HowToReg },
  { key: 'exam', title: 'Examination cell', blurb: 'Results calculation and publication', icon: FactCheck },
  { key: 'support', title: 'Support & finance', blurb: 'Grievances, fee clearance and audits', icon: Support },
  { key: 'organisation', title: 'Organisation administrator', blurb: 'Create and manage your own institution\'s accounts', icon: Apartment },
  { key: 'admin', title: 'Administrator', blurb: 'Users, roles, audit trail and system jobs', icon: AdminPanel },
];

const POINTS = [
  { icon: School, text: 'Admissions to alumni in one connected workspace' },
  { icon: Security, text: 'Role-based access: you only see what your role allows' },
  { icon: Insights, text: 'Live attendance, results and approvals' },
];

export function LoginPage() {
  const { user, signIn, notice } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mfa, setMfa] = useState('');
  const [needMfa, setNeedMfa] = useState(false);
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [params, setParams] = useSearchParams();
  const portal = PORTALS.find((p) => p.key === params.get('portal'));
  const from = (location.state as { from?: string } | null)?.from || '/';

  if (user) return <Navigate to={from === '/' && user.is_superuser ? '/owner' : from} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await signIn(username.trim(), password, needMfa ? mfa.trim() : undefined, portal?.key);
      navigate(from === '/' && portal?.key === 'admin' ? '/owner' : from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && /verification code/i.test(err.message)) setNeedMfa(true);
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.05fr 1fr' }, bgcolor: 'background.default' }}>
      <Box sx={{ display: { xs: 'none', md: 'flex' }, flexDirection: 'column', justifyContent: 'space-between', p: 6, color: '#fff', position: 'relative', overflow: 'hidden',
        background: 'linear-gradient(150deg,#FB923C 0%,#EA580C 50%,#9A3412 100%)' }}>
        <Box sx={{ position: 'absolute', right: -120, top: -120, width: 420, height: 420, borderRadius: '50%', bgcolor: 'rgba(255,255,255,.10)' }} />
        <Box sx={{ position: 'absolute', left: -80, bottom: -140, width: 360, height: 360, borderRadius: '50%', bgcolor: 'rgba(255,255,255,.08)' }} />
        <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', position: 'relative' }}>
          <Box sx={{ width: 44, height: 44, borderRadius: 3, display: 'grid', placeItems: 'center', bgcolor: 'rgba(255,255,255,.2)', fontWeight: 800, fontSize: 20 }}>S</Box>
          <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: 2 }}>SIMS</Typography>
        </Stack>
        <Box sx={{ position: 'relative' }}>
          <Typography variant="h3" sx={{ fontWeight: 800, mb: 2, lineHeight: 1.15 }}>Run your campus from one place.</Typography>
          <Stack spacing={2}>
            {POINTS.map((p) => (
              <Stack key={p.text} direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                <Box sx={{ width: 36, height: 36, borderRadius: 2, display: 'grid', placeItems: 'center', bgcolor: 'rgba(255,255,255,.18)' }}><p.icon fontSize="small" /></Box>
                <Typography>{p.text}</Typography>
              </Stack>
            ))}
          </Stack>
        </Box>
        <Typography variant="caption" sx={{ opacity: 0.85, position: 'relative' }}>Student Information Management System</Typography>
      </Box>

      <Box sx={{ display: 'grid', placeItems: 'center', p: 3, position: 'relative' }}>
        <Box sx={{ position: 'absolute', top: 12, right: 12 }}><ColorModeToggle /></Box>
        {!portal ? (
          <Stack spacing={2.5} sx={{ width: '100%', maxWidth: 460 }}>
            <Box>
              <Typography variant="h4" component="h1">Welcome to SIMS</Typography>
              <Typography color="text.secondary">Choose how you sign in</Typography>
            </Box>
            {notice && <Alert severity="info">{notice}</Alert>}
            <Stack spacing={1.25} role="list" aria-label="Sign-in portals">
              {PORTALS.map((p) => (
                <Box key={p.key} role="listitem">
                  <Button fullWidth variant="outlined" color="inherit" onClick={() => setParams({ portal: p.key })} aria-label={`${p.title} sign in`}
                    sx={{ justifyContent: 'flex-start', textAlign: 'left', p: 1.5, gap: 1.5, borderColor: 'divider', '&:hover': { borderColor: 'primary.main', bgcolor: 'action.hover' } }}>
                    <Box sx={{ width: 40, height: 40, borderRadius: 2, display: 'grid', placeItems: 'center', bgcolor: 'primary.light', color: 'primary.main', flexShrink: 0 }}><p.icon /></Box>
                    <Box>
                      <Typography sx={{ fontWeight: 700 }}>{p.title}</Typography>
                      <Typography variant="body2" color="text.secondary">{p.blurb}</Typography>
                    </Box>
                  </Button>
                </Box>
              ))}
            </Stack>
          </Stack>
        ) : (
        <Box component="form" onSubmit={submit} sx={{ width: '100%', maxWidth: 400 }}>
          <Stack spacing={2.5}>
            <Box>
              <Button size="small" color="inherit" startIcon={<ArrowBack fontSize="small" />} onClick={() => setParams({})} sx={{ mb: 1, ml: -1 }}>All portals</Button>
              <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                <Box sx={{ width: 44, height: 44, borderRadius: 2, display: 'grid', placeItems: 'center', bgcolor: 'primary.light', color: 'primary.main' }}><portal.icon /></Box>
                <Box sx={{ minWidth: 0 }}><Typography variant="h4" component="h1" sx={{ fontSize: { xs: '1.5rem', sm: '1.75rem' }, lineHeight: 1.2 }}>{portal.title} sign in</Typography><Typography color="text.secondary">{portal.blurb}</Typography></Box>
              </Stack>
            </Box>
            {notice && <Alert severity="info">{notice}</Alert>}
            {error && <Alert severity="error">{error}</Alert>}
            <TextField label="Username" autoComplete="username" autoFocus required value={username} onChange={(e) => setUsername(e.target.value)}
              slotProps={{ input: { startAdornment: <InputAdornment position="start"><PersonOutline fontSize="small" /></InputAdornment> } }} />
            <TextField label="Password" type={show ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)}
              slotProps={{ input: {
                startAdornment: <InputAdornment position="start"><LockOutlined fontSize="small" /></InputAdornment>,
                endAdornment: <InputAdornment position="end"><IconButton size="small" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}</IconButton></InputAdornment>,
              } }} />
            {needMfa && <TextField label="Verification code" autoComplete="one-time-code" required value={mfa} onChange={(e) => setMfa(e.target.value)} slotProps={{ htmlInput: { inputMode: 'numeric', maxLength: 8 } }} />}
            <Button type="submit" variant="contained" size="large" disabled={busy || !username || !password}>{busy ? 'Signing in…' : 'Sign in'}</Button>
          </Stack>
        </Box>
        )}
      </Box>
    </Box>
  );
}
