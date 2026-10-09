import { Link as RouterLink } from 'react-router';
import { Alert, Box, Card, CardActionArea, Chip, LinearProgress, Stack, Typography } from '@mui/material';
import Grid from '@mui/material/Grid';
import ArrowForward from '@mui/icons-material/ArrowForward';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../api/auth';
import { api, errorMessage } from '../api/client';
import { useMeta } from '../api/hooks';
import type { Dashboard } from '../api/types';
import { WORKSPACES, iconForResource, navResources, workspaceOf } from '../layout/navConfig';

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

/** People who only see their own records get first-person tile labels. */
const SELF_SERVICE_LABELS: Record<string, string> = {
  'Certificate requests to review': 'My certificate requests',
  'Open grievances': 'My open grievances',
  'Active mentor assignments': 'My mentors',
};
export const tileLabel = (label: string, selfService: boolean): string => (selfService ? SELF_SERVICE_LABELS[label] ?? label : label);

export function DashboardPage() {
  const { user } = useAuth();
  const meta = useMeta();
  const q = useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/dashboard') });
  const resources = navResources(meta.data?.groups);
  const byPath = new Map(resources.map((r) => [r.path, r]));
  const areas = WORKSPACES.filter((w) => resources.some((r) => workspaceOf(r) === w.key));
  const selfService = (user?.student_ids.length ?? 0) > 0;
  const role = user?.roles.length ? user.roles.map((r) => r.replaceAll('_', ' ').toLowerCase()).join(' · ') : user?.is_superuser ? 'super administrator' : '';

  return (
    <Stack spacing={4}>
      <Box sx={{ p: { xs: 3, md: 4 }, borderRadius: 4, color: '#fff', position: 'relative', overflow: 'hidden',
        background: 'linear-gradient(135deg,#FB923C 0%,#EA580C 55%,#C2410C 100%)' }}>
        <Box sx={{ position: 'absolute', right: -60, top: -60, width: 240, height: 240, borderRadius: '50%', bgcolor: 'rgba(255,255,255,.12)' }} />
        <Box sx={{ position: 'absolute', right: 80, bottom: -90, width: 200, height: 200, borderRadius: '50%', bgcolor: 'rgba(255,255,255,.08)' }} />
        <Typography variant="overline" sx={{ opacity: 0.9 }}>{new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })}</Typography>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 800 }}>{greeting()}, {user?.full_name}</Typography>
        {role && <Chip label={role} size="small" sx={{ mt: 1, bgcolor: 'rgba(255,255,255,.2)', color: '#fff', textTransform: 'capitalize' }} />}
      </Box>

      {q.isLoading && <LinearProgress />}
      {q.error && <Alert severity="error">{errorMessage(q.error)}</Alert>}

      {q.data && q.data.tiles.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 2 }}>At a glance</Typography>
          <Grid container spacing={2}>
            {q.data.tiles.map((t) => {
              const res = byPath.get(t.link);
              const IconCmp = res ? iconForResource(res) : undefined;
              return (
                <Grid key={t.label} size={{ xs: 12, sm: 6, lg: 3 }}>
                  <Card sx={{ height: '100%', '&:hover': { borderColor: 'primary.main', boxShadow: 3 } }}>
                    <CardActionArea component={RouterLink} to={`/r/${t.link}`} sx={{ p: 2.5, height: '100%' }}>
                      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <Box>
                          <Typography variant="h3" sx={{ fontWeight: 800, color: 'primary.main', lineHeight: 1 }}>{t.value}</Typography>
                          <Typography color="text.secondary" sx={{ mt: 1 }}>{tileLabel(t.label, selfService)}</Typography>
                        </Box>
                        {IconCmp && <Box sx={{ width: 44, height: 44, borderRadius: 2.5, display: 'grid', placeItems: 'center', bgcolor: 'action.selected', color: 'primary.main' }}><IconCmp /></Box>}
                      </Stack>
                    </CardActionArea>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        </Box>
      )}

      {areas.length > 0 ? (
        <Box>
          <Typography variant="h6" sx={{ mb: 2 }}>Your areas</Typography>
          <Grid container spacing={2}>
            {areas.map((w) => (
              <Grid key={w.key} size={{ xs: 12, md: 6, xl: 4 }}>
                <Card sx={{ height: '100%', '&:hover': { borderColor: 'primary.main', boxShadow: 3 } }}>
                  <CardActionArea component={RouterLink} to={`/w/${w.key}`} sx={{ p: 2.5, height: '100%' }}>
                    <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
                      <Box sx={{ width: 52, height: 52, borderRadius: 3, display: 'grid', placeItems: 'center', bgcolor: 'primary.main', color: 'primary.contrastText' }}><w.icon /></Box>
                      <Box sx={{ flexGrow: 1 }}>
                        <Typography variant="subtitle1">{w.title}</Typography>
                        <Typography variant="body2" color="text.secondary">{w.blurb}</Typography>
                      </Box>
                      <ArrowForward color="primary" />
                    </Stack>
                  </CardActionArea>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      ) : (
        !meta.isLoading && <Alert severity="info">No areas are available to your account yet. An administrator can assign you a role.</Alert>
      )}
    </Stack>
  );
}
