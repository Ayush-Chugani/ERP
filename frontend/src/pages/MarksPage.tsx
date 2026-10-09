import { useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { Alert, Breadcrumbs, Button, LinearProgress, Link, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, errorMessage } from '../api/client';
import { StatusChip } from '../components/format';

type Row = { course_registration_id: number; student_id: number; display_name: string; student_number: string; attendance_status: string | null; marks_obtained: string | null; remarks: string | null };
type Roster = { assessment_event_id: number; title: string; maximum_marks: string; status: string; students: Row[] };

/** Enter marks for an assessment event; absent / exempted / malpractice entries carry no marks. */
export function MarksPage() {
  const { id = '' } = useParams();
  const qc = useQueryClient();
  const roster = useQuery({ queryKey: ['marks-roster', id], queryFn: () => api<Roster>(`/assessments/events/${id}/roster`) });
  const [rows, setRows] = useState<Record<number, { status: string; marks: string; remarks: string }>>({});
  useEffect(() => {
    if (roster.data) setRows(Object.fromEntries(roster.data.students.map((s) => [s.course_registration_id, { status: s.attendance_status ?? 'PRESENT', marks: s.marks_obtained ?? '', remarks: s.remarks ?? '' }])));
  }, [roster.data]);
  const save = useMutation({
    mutationFn: () => api(`/assessments/events/${id}/marks`, {
      method: 'PUT',
      body: { marks: Object.entries(rows).filter(([, r]) => r.status !== 'PRESENT' || r.marks !== '').map(([rid, r]) => ({
        course_registration_id: Number(rid), attendance_status: r.status, marks_obtained: r.status === 'PRESENT' ? r.marks : null, remarks: r.remarks })) },
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['marks-roster', id] }); qc.invalidateQueries({ queryKey: ['detail'] }); },
  });
  if (roster.isLoading) return <LinearProgress />;
  if (roster.error || !roster.data) return <Alert severity="error">{errorMessage(roster.error)}</Alert>;
  const r = roster.data;
  const closed = !['PLANNED', 'CONDUCTED'].includes(r.status);
  const max = Number(r.maximum_marks);
  const invalid = Object.values(rows).some((x) => x.status === 'PRESENT' && x.marks !== '' && (Number(x.marks) < 0 || Number(x.marks) > max || Number.isNaN(Number(x.marks))));
  return (
    <Stack spacing={2}>
      <Breadcrumbs>
        <Link component={RouterLink} to="/r/assessments/assessment-event" underline="hover" color="inherit">Assessments</Link>
        <Link component={RouterLink} to={`/r/assessments/assessment-event/${id}`} underline="hover" color="inherit">{r.title}</Link>
        <Typography color="text.primary">Enter marks</Typography>
      </Breadcrumbs>
      <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}><Typography variant="h4">{r.title} · out of {max}</Typography><StatusChip value={r.status} /></Stack>
      {closed && <Alert severity="info">This assessment is {r.status.toLowerCase()}; marks can no longer be changed.</Alert>}
      {save.isSuccess && <Alert severity="success">Marks saved.</Alert>}
      {!!save.error && <Alert severity="error">{errorMessage(save.error)}</Alert>}
      <Stack direction="row" sx={{ justifyContent: 'flex-end' }}>
        <Button variant="contained" disabled={closed || invalid || save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save marks'}</Button>
      </Stack>
      <Paper>
        <Table size="small">
          <TableHead><TableRow><TableCell>Student</TableCell><TableCell>Number</TableCell><TableCell sx={{ width: 170 }}>Attendance</TableCell><TableCell sx={{ width: 130 }}>Marks</TableCell><TableCell>Remarks</TableCell></TableRow></TableHead>
          <TableBody>
            {r.students.map((s) => {
              const v = rows[s.course_registration_id] ?? { status: 'PRESENT', marks: '', remarks: '' };
              const bad = v.status === 'PRESENT' && v.marks !== '' && (Number(v.marks) < 0 || Number(v.marks) > max);
              const set = (patch: Partial<typeof v>) => setRows((m) => ({ ...m, [s.course_registration_id]: { ...v, ...patch } }));
              return (
                <TableRow key={s.course_registration_id} hover>
                  <TableCell>{s.display_name}</TableCell>
                  <TableCell>{s.student_number}</TableCell>
                  <TableCell><TextField select disabled={closed} value={v.status} aria-label={`Attendance for ${s.display_name}`} onChange={(e) => set({ status: e.target.value, marks: e.target.value === 'PRESENT' ? v.marks : '' })}>
                    {['PRESENT', 'ABSENT', 'EXEMPTED', 'MALPRACTICE'].map((x) => <MenuItem key={x} value={x}>{x.toLowerCase()}</MenuItem>)}</TextField></TableCell>
                  <TableCell><TextField type="number" disabled={closed || v.status !== 'PRESENT'} value={v.marks} error={bad} aria-label={`Marks for ${s.display_name}`}
                    onChange={(e) => set({ marks: e.target.value })} slotProps={{ htmlInput: { min: 0, max, step: 0.5 } }} /></TableCell>
                  <TableCell><TextField disabled={closed} value={v.remarks} onChange={(e) => set({ remarks: e.target.value })} slotProps={{ htmlInput: { maxLength: 500 } }} /></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
