import { Alert, Button, Chip, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, errorMessage } from '../../api/client';
import { formatDateTime, StatusChip } from '../../components/format';
import { PageHeader } from '../../components/PageHeader';
import JobsIcon from '@mui/icons-material/MemoryOutlined';

type Job = { job_id: number; kind: string; queue: string; status: string; attempts: number; max_attempts: number; run_at: string; finished_at: string | null; last_error: string | null };

export function JobsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['jobs'], queryFn: () => api<{ summary: Record<string, number>; results: Job[] }>('/ops/jobs', { query: { page_size: 50 } }), refetchInterval: 10_000 });
  const retry = useMutation({ mutationFn: (id: number) => api(`/ops/jobs/${id}/retry`, { method: 'POST' }), onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }) });
  return (
    <Stack spacing={2}>
      <PageHeader title="Background jobs" subtitle="Queued, running and failed jobs" icon={JobsIcon} crumbs={[{ label: 'Home', to: '/' }, { label: 'Administration' }, { label: 'Jobs' }]} />
      <Stack direction="row" spacing={1}>{Object.entries(q.data?.summary ?? {}).map(([s, n]) => <Chip key={s} label={`${s}: ${n}`} />)}</Stack>
      {!!q.error && <Alert severity="error">{errorMessage(q.error)}</Alert>}
      <Paper>
        <Table size="small">
          <TableHead><TableRow><TableCell>Job</TableCell><TableCell>Status</TableCell><TableCell>Attempts</TableCell><TableCell>Scheduled</TableCell><TableCell>Error</TableCell><TableCell /></TableRow></TableHead>
          <TableBody>
            {q.data?.results.map((j) => (
              <TableRow key={j.job_id}>
                <TableCell>{j.kind}<Typography variant="caption" color="text.secondary" component="div">#{j.job_id} · {j.queue}</Typography></TableCell>
                <TableCell><StatusChip value={j.status} /></TableCell>
                <TableCell>{j.attempts}/{j.max_attempts}</TableCell>
                <TableCell>{formatDateTime(j.run_at)}</TableCell>
                <TableCell sx={{ maxWidth: 320 }}><Typography variant="caption" noWrap component="div">{j.last_error}</Typography></TableCell>
                <TableCell>{j.status === 'dead' && <Button size="small" onClick={() => retry.mutate(j.job_id)}>Retry</Button>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
