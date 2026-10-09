import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router';
import { Box, Button, Chip, Divider, LinearProgress, Paper, Stack, Typography } from '@mui/material';
import Grid from '@mui/material/Grid';
import DeleteIcon from '@mui/icons-material/DeleteOutlined';
import EditIcon from '@mui/icons-material/EditOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useResourceMeta } from '../api/hooks';
import type { ActionInfo, Row } from '../api/types';
import { ActionDialog } from '../components/ActionDialog';
import { formatDateTime, humanize, renderValue, StatusChip } from '../components/format';
import { PageHeader } from '../components/PageHeader';
import { ResourceForm } from '../components/ResourceForm';
import { WORKSPACES, iconForResource, workspaceOf } from '../layout/navConfig';
import { Extras } from './Extras';

type HistoryRow = { from_status: string | null; to_status: string; action: string | null; changed_at: string; changed_by: string | null; remarks: string | null };

export function ResourceDetailPage() {
  const { module = '', slug = '', id = '' } = useParams();
  const path = `${module}/${slug}`;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const meta = useResourceMeta(path);
  const [editing, setEditing] = useState(false);
  const [pending, setPending] = useState<ActionInfo | 'delete' | null>(null);

  const row = useQuery({ queryKey: ['detail', path, id], queryFn: () => api<Row>(`/${path}/${id}`) });
  const history = useQuery({
    queryKey: ['history', path, id],
    queryFn: () => api<{ results: HistoryRow[] }>(`/${path}/${id}/history`),
    enabled: !!meta.data?.actions.length,
  });

  const run = useMutation({
    mutationFn: (vars: { action: ActionInfo | 'delete'; remarks: string }) =>
      vars.action === 'delete'
        ? api(`/${path}/${id}`, { method: 'DELETE' })
        : api<Row>(`/${path}/${id}/actions/${vars.action.name}`, { method: 'POST', body: { remarks: vars.remarks || null }, headers: { 'Idempotency-Key': crypto.randomUUID() } }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['list', path] });
      qc.invalidateQueries({ queryKey: ['detail', path, id] });
      qc.invalidateQueries({ queryKey: ['history', path, id] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      setPending(null);
      if (vars.action === 'delete') navigate(`/r/${path}`, { replace: true });
    },
  });

  if (meta.isLoading || row.isLoading) return <LinearProgress />;
  if (meta.error || row.error || !meta.data || !row.data) return <Navigate to="/" replace />;
  const m = meta.data;
  const r = row.data;
  const ws = WORKSPACES.find((w) => w.key === workspaceOf(m));
  const title = String(m.label_columns.map((c) => r[c]).find(Boolean) ?? `#${id}`);
  const status = (r.workflow_status as string | null | undefined) ?? (m.status_column && !m.status_column.endsWith('_id') ? (r[m.status_column] as string) : null);
  const fields = m.columns.filter((c) => !c.primary);
  const trail = history.data?.results ?? [];

  return (
    <Box>
      <PageHeader
        title={title} icon={iconForResource(m)} chip={status ? <StatusChip value={status} /> : undefined}
        subtitle={m.title}
        crumbs={[{ label: 'Home', to: '/' }, ...(ws ? [{ label: ws.title, to: `/w/${ws.key}` }] : []), { label: m.title, to: `/r/${path}` }, { label: title }]}
        actions={<>
          {(r.actions ?? []).map((a) => (
            <Button key={a.name} variant={a.danger ? 'outlined' : 'contained'} color={a.danger ? 'error' : 'primary'} onClick={() => setPending(a)}>{a.label}</Button>
          ))}
          {m.can.update && !m.read_only && <Button variant="outlined" startIcon={<EditIcon />} onClick={() => setEditing(true)}>Edit</Button>}
          {m.can.delete && !m.read_only && <Button color="error" startIcon={<DeleteIcon />} onClick={() => setPending('delete')}>Delete</Button>}
        </>}
      />

      <Stack spacing={2}>
        <Extras meta={m} row={r} id={id} />
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, lg: trail.length ? 8 : 12 }}>
            <Paper sx={{ p: { xs: 2, md: 3 } }}>
              <Typography variant="h6" sx={{ mb: 2 }}>Details</Typography>
              <Grid container spacing={2.5}>
                {fields.map((c) => (
                  <Grid key={c.name} size={{ xs: 12, sm: 6, xl: 4 }}>
                    <Typography variant="overline" color="text.secondary" component="div">{c.label}</Typography>
                    <Box sx={{ wordBreak: 'break-word', minHeight: 24 }}>{renderValue(c, r, c.name)}</Box>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          </Grid>
          {trail.length > 0 && (
            <Grid size={{ xs: 12, lg: 4 }}>
              <Paper sx={{ p: 2.5 }}>
                <Typography variant="h6" sx={{ mb: 1.5 }}>Workflow history</Typography>
                <Stack divider={<Divider />} spacing={1.5}>
                  {[...trail].reverse().map((h, i) => (
                    <Box key={i}>
                      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                        <Chip size="small" color="primary" variant="outlined" label={humanize(h.action)} />
                        <Typography variant="body2">{humanize(h.from_status || 'new')} → <b>{humanize(h.to_status)}</b></Typography>
                      </Stack>
                      <Typography variant="caption" color="text.secondary">{h.changed_by ?? 'system'} · {formatDateTime(h.changed_at)}</Typography>
                      {h.remarks && <Typography variant="body2" sx={{ mt: 0.5 }}>{h.remarks}</Typography>}
                    </Box>
                  ))}
                </Stack>
              </Paper>
            </Grid>
          )}
        </Grid>
      </Stack>

      {editing && <ResourceForm meta={m} row={r} onClose={() => setEditing(false)} onSaved={() => setEditing(false)} />}
      {pending && (
        <ActionDialog
          action={pending === 'delete' ? { label: 'Delete', remarks: 'none', danger: true } : pending}
          title={pending === 'delete' ? `Delete this ${m.title.toLowerCase()}?` : undefined}
          busy={run.isPending} error={run.error}
          onCancel={() => { run.reset(); setPending(null); }}
          onConfirm={(remarks) => run.mutate({ action: pending, remarks })} />
      )}
    </Box>
  );
}
