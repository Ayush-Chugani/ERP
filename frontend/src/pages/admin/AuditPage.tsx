import { useState } from 'react';
import { Alert, Chip, LinearProgress, Paper, Stack, Table, TableBody, TableCell, TableHead, TablePagination, TableRow, TextField, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { api, errorMessage } from '../../api/client';
import type { Page } from '../../api/types';
import { formatDateTime, humanize } from '../../components/format';
import { PageHeader } from '../../components/PageHeader';
import AuditIcon from '@mui/icons-material/HistoryOutlined';

type Entry = { audit_id: number; occurred_at: string; actor_user_id: number | null; action: string; module: string; resource: string; record_id: string | null; reason: string | null; after: Record<string, unknown> | null; ip_address: string | null };

export function AuditPage() {
  const [resource, setResource] = useState('');
  const [action, setAction] = useState('');
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ['audit', resource, action, page],
    queryFn: () => api<Page<Entry>>('/security/audit', { query: { resource: resource || undefined, action: action || undefined, page, page_size: 50 } }),
    placeholderData: (p) => p,
  });
  return (
    <Stack spacing={2}>
      <PageHeader title="Audit trail" subtitle="Every change, who made it and when" icon={AuditIcon} crumbs={[{ label: 'Home', to: '/' }, { label: 'Administration' }, { label: 'Audit trail' }]} />
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
        <TextField label="Resource (table)" value={resource} onChange={(e) => { setResource(e.target.value); setPage(1); }} sx={{ maxWidth: 260 }} />
        <TextField label="Action" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} sx={{ maxWidth: 200 }} />
      </Stack>
      {!!q.error && <Alert severity="error">{errorMessage(q.error)}</Alert>}
      <Paper>
        {q.isFetching && <LinearProgress />}
        <Table size="small">
          <TableHead><TableRow><TableCell>When</TableCell><TableCell>Who</TableCell><TableCell>Action</TableCell><TableCell>Record</TableCell><TableCell>Details</TableCell></TableRow></TableHead>
          <TableBody>
            {q.data?.results.map((e) => (
              <TableRow key={e.audit_id}>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDateTime(e.occurred_at)}</TableCell>
                <TableCell>{e.actor_user_id ? `#${e.actor_user_id}` : 'system'}</TableCell>
                <TableCell><Chip size="small" label={humanize(e.action)} /></TableCell>
                <TableCell>{e.resource}{e.record_id ? ` · ${e.record_id}` : ''}</TableCell>
                <TableCell sx={{ maxWidth: 360 }}><Typography variant="caption" noWrap component="div">{e.reason || (e.after ? JSON.stringify(e.after) : '')}</Typography></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <TablePagination component="div" count={q.data?.count ?? 0} page={page - 1} rowsPerPage={50} rowsPerPageOptions={[50]} onPageChange={(_, p) => setPage(p + 1)} />
      </Paper>
    </Stack>
  );
}
