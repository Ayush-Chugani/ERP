import { useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { Alert, Breadcrumbs, Button, Chip, LinearProgress, Link, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, errorMessage } from '../api/client';
import { formatDate, StatusChip } from '../components/format';

type Student = { student_id: number; name: string; student_number: string; status: string | null; remarks: string | null };
type Roster = { class_session_id: number; register_status: string; session_date: string; students: Student[] };
const STATUSES = ['PRESENT', 'ABSENT', 'LATE', 'EXCUSED', 'ON_DUTY'];

/** Mark a class register: every roster student gets a status; saved in one request and validated by the server. */
export function AttendancePage() {
  const { id = '' } = useParams();
  const qc = useQueryClient();
  const roster = useQuery({ queryKey: ['roster', id], queryFn: () => api<Roster>(`/attendance/sessions/${id}/roster`) });
  const [marks, setMarks] = useState<Record<number, { status: string; remarks: string }>>({});
  useEffect(() => {
    if (roster.data) setMarks(Object.fromEntries(roster.data.students.map((s) => [s.student_id, { status: s.status ?? 'PRESENT', remarks: s.remarks ?? '' }])));
  }, [roster.data]);
  const save = useMutation({
    mutationFn: () => api(`/attendance/sessions/${id}/marks`, { method: 'PUT', body: { marks: Object.entries(marks).map(([sid, m]) => ({ student_id: Number(sid), status: m.status, remarks: m.remarks })) } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roster', id] }),
  });
  const bulk = (status: string) => setMarks((m) => Object.fromEntries(Object.entries(m).map(([k, v]) => [k, { ...v, status }])));
  if (roster.isLoading) return <LinearProgress />;
  if (roster.error || !roster.data) return <Alert severity="error">{errorMessage(roster.error)}</Alert>;
  const r = roster.data;
  const closed = !['OPEN', 'REOPENED'].includes(r.register_status);
  const absent = Object.values(marks).filter((m) => m.status === 'ABSENT').length;
  return (
    <Stack spacing={2}>
      <Breadcrumbs>
        <Link component={RouterLink} to="/r/attendance/class-session" underline="hover" color="inherit">Class sessions</Link>
        <Link component={RouterLink} to={`/r/attendance/class-session/${id}`} underline="hover" color="inherit">Session #{id}</Link>
        <Typography color="text.primary">Mark attendance</Typography>
      </Breadcrumbs>
      <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
        <Typography variant="h4">Attendance · {formatDate(r.session_date)}</Typography>
        <StatusChip value={r.register_status} />
      </Stack>
      {closed && <Alert severity="info">The register is {r.register_status.toLowerCase()}. Open or reopen it from the session page to change marks.</Alert>}
      {save.isSuccess && <Alert severity="success">Attendance saved.</Alert>}
      {!!save.error && <Alert severity="error">{errorMessage(save.error)}</Alert>}
      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
        <Button size="small" disabled={closed} onClick={() => bulk('PRESENT')}>Mark all present</Button>
        <Button size="small" disabled={closed} onClick={() => bulk('ABSENT')}>Mark all absent</Button>
        <Chip label={`${r.students.length - absent} / ${r.students.length} present`} />
        <span style={{ flexGrow: 1 }} />
        <Button variant="contained" disabled={closed || save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save attendance'}</Button>
      </Stack>
      <Paper>
        <Table size="small">
          <TableHead><TableRow><TableCell>Student</TableCell><TableCell>Number</TableCell><TableCell sx={{ width: 180 }}>Status</TableCell><TableCell>Remarks</TableCell></TableRow></TableHead>
          <TableBody>
            {r.students.map((s) => (
              <TableRow key={s.student_id} hover>
                <TableCell>{s.name}</TableCell>
                <TableCell>{s.student_number}</TableCell>
                <TableCell>
                  <TextField select value={marks[s.student_id]?.status ?? 'PRESENT'} disabled={closed} aria-label={`Status for ${s.name}`}
                    onChange={(e) => setMarks((m) => ({ ...m, [s.student_id]: { ...m[s.student_id], status: e.target.value } }))}>
                    {STATUSES.map((v) => <MenuItem key={v} value={v}>{v.replace('_', ' ').toLowerCase()}</MenuItem>)}
                  </TextField>
                </TableCell>
                <TableCell><TextField value={marks[s.student_id]?.remarks ?? ''} disabled={closed} slotProps={{ htmlInput: { maxLength: 500 } }}
                  onChange={(e) => setMarks((m) => ({ ...m, [s.student_id]: { ...m[s.student_id], remarks: e.target.value } }))} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
