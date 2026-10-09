import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { Alert, Box, Card, CardContent, Chip, LinearProgress, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import Grid from '@mui/material/Grid';
import AdminPanel from '@mui/icons-material/AdminPanelSettingsOutlined';
import { useQuery } from '@tanstack/react-query';
import { api, errorMessage } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';

type Overview = {
  generated_at: string;
  people: Record<string, number>;
  users: Record<string, number>;
  users_by_role: { role: string; name: string; users: number }[];
  sessions: { active: number };
  logins_24h: { successful: number; failed: number };
  recent_logins: { username: string; ok: boolean; at: string; ip: string | null; reason: string | null }[];
  recent_audit: { at: string; actor: string | null; action: string; module: string; resource: string; record_id: string | null }[];
  jobs: { summary: Record<string, number>; last_completed_at: string | null };
  workflow: Record<string, number>;
  system: { environment: string; schema: string | null; storage: string; ai_enabled: boolean; ai_model: string; database: string };
};

const label = (k: string) => k.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase());
const when = (v: string | null) => (v ? new Date(v).toLocaleString() : '—');

function Stat({ title, value, tone }: { title: string; value: number | string; tone?: 'warn' | 'bad' }) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="h4" sx={{ fontWeight: 800, color: tone === 'bad' ? 'error.main' : tone === 'warn' ? 'warning.main' : 'primary.main' }}>{value}</Typography>
        <Typography variant="body2" color="text.secondary">{title}</Typography>
      </CardContent>
    </Card>
  );
}

function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
          <Typography variant="h6">{title}</Typography>{action}
        </Stack>
        {children}
      </CardContent>
    </Card>
  );
}

function Row({ name, children }: { name: string; children: ReactNode }) {
  return <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}><Typography>{name}</Typography><Box>{children}</Box></Stack>;
}

/** Application-owner dashboard: people, access, activity, background work and system health on one page. */
export function OwnerDashboardPage() {
  const q = useQuery({ queryKey: ['owner-overview'], queryFn: () => api<Overview>('/ops/overview'), refetchInterval: 60_000 });
  const d = q.data;
  const dead = d?.jobs.summary.dead ?? 0;
  return (
    <Box>
      <PageHeader title="Owner dashboard" subtitle="Everything about your SIMS installation at a glance" icon={AdminPanel}
        crumbs={[{ label: 'Home', to: '/' }, { label: 'Owner dashboard' }]}
        chip={d && <Chip size="small" color="success" label={`${d.system.environment} · schema ${d.system.schema ?? '?'}`} />} />
      {q.isLoading && <LinearProgress />}
      {q.error && <Alert severity="error">{errorMessage(q.error)}</Alert>}
      {d && (
        <Stack spacing={3}>
          <Grid container spacing={2}>
            {Object.entries(d.people).map(([k, v]) => <Grid key={k} size={{ xs: 6, sm: 4, md: 2 }}><Stat title={label(k)} value={v} /></Grid>)}
          </Grid>
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}><Stat title="Signed-in sessions" value={d.sessions.active} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}><Stat title="Sign-ins (24 h)" value={d.logins_24h.successful} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}><Stat title="Failed sign-ins (24 h)" value={d.logins_24h.failed} tone={d.logins_24h.failed > 10 ? 'bad' : d.logins_24h.failed ? 'warn' : undefined} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}><Stat title="Locked accounts" value={d.users.locked} tone={d.users.locked ? 'warn' : undefined} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}><Stat title="Accounts with 2-step" value={`${d.users.with_mfa}/${d.users.active}`} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}><Stat title="Dead jobs" value={dead} tone={dead ? 'bad' : undefined} /></Grid>
          </Grid>

          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Section title="Accounts by role" action={<Chip component={RouterLink} to="/admin/users" clickable size="small" label="Manage users" />}>
                <Table size="small">
                  <TableHead><TableRow><TableCell>Role</TableCell><TableCell align="right">People</TableCell></TableRow></TableHead>
                  <TableBody>{d.users_by_role.map((r) => <TableRow key={r.role}><TableCell>{r.name}</TableCell><TableCell align="right">{r.users}</TableCell></TableRow>)}</TableBody>
                </Table>
              </Section>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Stack spacing={2}>
                <Section title="Work in progress">
                  <Stack spacing={1}>{Object.entries(d.workflow).map(([k, v]) => <Row key={k} name={label(k)}><b>{v}</b></Row>)}</Stack>
                </Section>
                <Section title="System" action={<Chip component={RouterLink} to="/admin/jobs" clickable size="small" label="Background jobs" />}>
                  <Stack spacing={1}>
                    <Row name="Database"><Chip size="small" color="success" label={d.system.database} /></Row>
                    <Row name="File storage"><b>{d.system.storage}</b></Row>
                    <Row name="AI assistant"><Chip size="small" color={d.system.ai_enabled ? 'success' : 'default'} label={d.system.ai_enabled ? d.system.ai_model : 'off'} /></Row>
                    <Row name="Job queue"><span>{Object.entries(d.jobs.summary).map(([k, v]) => `${k} ${v}`).join(' · ') || 'empty'}</span></Row>
                    <Row name="Last job finished"><span>{when(d.jobs.last_completed_at)}</span></Row>
                  </Stack>
                </Section>
              </Stack>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Section title="Recent sign-ins">
                <Table size="small">
                  <TableBody>
                    {d.recent_logins.map((l, i) => (
                      <TableRow key={i}>
                        <TableCell>{l.username}</TableCell>
                        <TableCell><Chip size="small" color={l.ok ? 'success' : 'error'} label={l.ok ? 'ok' : l.reason || 'failed'} /></TableCell>
                        <TableCell>{when(l.at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Section>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Section title="Latest changes" action={<Chip component={RouterLink} to="/admin/audit" clickable size="small" label="Audit trail" />}>
                <Table size="small">
                  <TableBody>
                    {d.recent_audit.map((a, i) => (
                      <TableRow key={i}>
                        <TableCell>{a.actor ?? 'system'}</TableCell>
                        <TableCell>{a.action} {a.resource.replaceAll('_', ' ')}</TableCell>
                        <TableCell>{when(a.at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Section>
            </Grid>
          </Grid>
          <Typography variant="caption" color="text.secondary">Updated {when(d.generated_at)} · refreshes every minute</Typography>
        </Stack>
      )}
    </Box>
  );
}
