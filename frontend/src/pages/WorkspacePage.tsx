import { useMemo, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { Alert, Box, Card, CardActionArea, Chip, InputAdornment, LinearProgress, Stack, TextField, Typography } from '@mui/material';
import Grid from '@mui/material/Grid';
import SearchIcon from '@mui/icons-material/Search';
import { useMeta } from '../api/hooks';
import { PageHeader } from '../components/PageHeader';
import { WORKSPACES, iconForResource, isSetup, workspaceOf } from '../layout/navConfig';
import type { ResourceSummary } from '../api/types';

function Section({ title, items, muted }: { title: string; items: ResourceSummary[]; muted?: boolean }) {
  if (items.length === 0) return null;
  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="overline" color="text.secondary" component="h2" sx={{ display: 'block', mb: 1.5 }}>{title}</Typography>
      <Grid container spacing={2}>
        {items.map((r) => {
          const IconCmp = iconForResource(r);
          return (
            <Grid key={r.path} size={{ xs: 12, sm: 6, lg: 4, xl: 3 }}>
              <Card sx={{ height: '100%', opacity: muted ? 0.92 : 1, transition: 'box-shadow .15s, border-color .15s', '&:hover': { borderColor: 'primary.main', boxShadow: 3 } }}>
                <CardActionArea component={RouterLink} to={`/r/${r.path}`} sx={{ p: 2, height: '100%' }}>
                  <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
                    <Box sx={{ width: 44, height: 44, borderRadius: 2.5, display: 'grid', placeItems: 'center', bgcolor: 'action.selected', color: 'primary.main', flexShrink: 0 }}><IconCmp /></Box>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="subtitle1" noWrap>{r.title}</Typography>
                      <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }}>
                        {r.can.create && <Chip size="small" label="Can add" color="primary" variant="outlined" />}
                        {r.read_only && <Chip size="small" label="View only" variant="outlined" />}
                      </Stack>
                    </Box>
                  </Stack>
                </CardActionArea>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}

/** Landing page of an area: a card for every page the user is allowed to open in it. */
export function WorkspacePage() {
  const { key = '' } = useParams();
  const meta = useMeta();
  const [q, setQ] = useState('');
  const ws = WORKSPACES.find((w) => w.key === key);
  const items = useMemo(() => {
    const all = (meta.data?.groups ?? []).flatMap((g) => g.resources).filter((r) => workspaceOf(r) === key);
    const t = q.trim().toLowerCase();
    return all.filter((r) => !t || r.title.toLowerCase().includes(t)).sort((a, b) => a.title.localeCompare(b.title));
  }, [meta.data, key, q]);
  if (meta.isLoading) return <LinearProgress />;
  if (!ws) return <Alert severity="warning">That area does not exist.</Alert>;
  return (
    <Box>
      <PageHeader title={ws.title} subtitle={ws.blurb} icon={ws.icon} crumbs={[{ label: 'Home', to: '/' }, { label: ws.title }]} />
      {items.length === 0 && !q && <Alert severity="info">You do not have access to anything in this area yet. Ask an administrator to assign you a role.</Alert>}
      <TextField placeholder={`Search in ${ws.title}…`} value={q} onChange={(e) => setQ(e.target.value)} sx={{ maxWidth: 420, mb: 3 }}
        slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> } }} />
      <Section title="Pages" items={items.filter((r) => !isSetup(r))} />
      <Section title="Setup and reference data" items={items.filter(isSetup)} muted />
      {items.length === 0 && q && <Typography color="text.secondary">Nothing matches “{q}”.</Typography>}
    </Box>
  );
}
