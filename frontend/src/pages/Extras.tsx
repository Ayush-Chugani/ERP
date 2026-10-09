import { useState } from 'react';
import { Link as RouterLink } from 'react-router';
import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Paper, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, errorMessage, fieldErrors } from '../api/client';
import type { ResourceMeta, Row } from '../api/types';
import { FeedbackSummaryPanel, RecordSummary, StudentInsights } from '../ai/AiPanels';

type Props = { meta: ResourceMeta; row: Row; id: string };

function Link({ to, children }: { to: string; children: string }) {
  return <Button component={RouterLink} to={to} variant="contained">{children}</Button>;
}

function Calculate({ label, url, id }: { label: string; url: string; id: string }) {
  const qc = useQueryClient();
  const run = useMutation({ mutationFn: () => api<Record<string, unknown>>(url, { method: 'POST' }), onSuccess: () => qc.invalidateQueries() });
  return (
    <Stack spacing={1} sx={{ alignItems: 'flex-start' }}>
      <Button variant="contained" disabled={run.isPending} onClick={() => run.mutate()} data-testid={`calc-${id}`}>{run.isPending ? 'Calculating…' : label}</Button>
      {!!run.error && <Alert severity="error">{errorMessage(run.error)}</Alert>}
      {run.data && <Alert severity="success">{Object.entries(run.data).map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v ?? '—'}`).join(' · ')}</Alert>}
    </Stack>
  );
}

type Summary = { fee_cleared: boolean; next_step: string | null; student_id: number | null; enrolment_id: number | null; applicant: { name: string; email: string | null } };

function Admission({ row, id }: { row: Row; id: string }) {
  const qc = useQueryClient();
  const summary = useQuery({ queryKey: ['admission-summary', id, row.version], queryFn: () => api<Summary>(`/admissions/admission-application/${id}/summary`) });
  const [mode, setMode] = useState<'clear' | 'admit' | null>(null);
  const [reference, setReference] = useState('');
  const [scheme, setScheme] = useState('');
  const [semester, setSemester] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const schemes = useQuery({ queryKey: ['lookup', 'curriculum/curriculum-scheme', 'admit'], enabled: mode === 'admit', queryFn: () => api<{ results: { id: number; label: string }[] }>('/lookups/curriculum/curriculum-scheme', { query: { limit: 100 } }) });
  const semesters = useQuery({ queryKey: ['lookup', 'calendar/semester'], enabled: mode === 'admit', queryFn: () => api<{ results: { id: number; label: string }[] }>('/lookups/calendar/semester', { query: { limit: 100 } }) });
  const done = () => { setMode(null); qc.invalidateQueries(); };
  const clear = useMutation({ mutationFn: () => api(`/admissions/admission-application/${id}/clearance`, { method: 'POST', body: { reference } }), onSuccess: done });
  const admit = useMutation({
    mutationFn: () => api(`/admissions/admission-application/${id}/admit`, { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() },
      body: { curriculum_scheme_id: Number(scheme), admission_semester_id: Number(semester), admission_date: date } }),
    onSuccess: done,
  });
  const s = summary.data;
  if (!s || row.application_status !== 'SELECTED') {
    return s?.student_id ? (
      <Paper sx={{ p: 2 }}><Typography>Admitted — <RouterLink to={`/r/people/student/${s.student_id}`}>open student record</RouterLink>{s.enrolment_id ? <> · <RouterLink to={`/r/admissions/student-programme-enrolment/${s.enrolment_id}`}>enrolment</RouterLink></> : null}</Typography></Paper>
    ) : null;
  }
  return (
    <Paper sx={{ p: 2 }}>
      <Stack spacing={1.5}>
        <Typography variant="h6">Admission</Typography>
        <Typography variant="body2" color="text.secondary">{s.applicant.name} is selected. {s.fee_cleared ? 'Fees are cleared — ready to admit.' : 'Record the fee clearance before admitting.'}</Typography>
        <Stack direction="row" spacing={1}>
          {!s.fee_cleared && <Button variant="outlined" onClick={() => setMode('clear')}>Record fee clearance</Button>}
          <Button variant="contained" disabled={!s.fee_cleared} onClick={() => setMode('admit')}>Admit student</Button>
        </Stack>
      </Stack>
      {mode === 'clear' && (
        <Dialog open onClose={() => setMode(null)} fullWidth maxWidth="xs">
          <DialogTitle>Record fee clearance</DialogTitle>
          <DialogContent>
            {!!clear.error && <Alert severity="error" sx={{ mb: 2 }}>{errorMessage(clear.error)}</Alert>}
            <TextField autoFocus label="Receipt / reference" value={reference} onChange={(e) => setReference(e.target.value)} sx={{ mt: 1 }} />
          </DialogContent>
          <DialogActions><Button onClick={() => setMode(null)}>Cancel</Button><Button variant="contained" disabled={!reference.trim() || clear.isPending} onClick={() => clear.mutate()}>Record</Button></DialogActions>
        </Dialog>
      )}
      {mode === 'admit' && (
        <Dialog open onClose={() => setMode(null)} fullWidth maxWidth="sm">
          <DialogTitle>Admit {s.applicant.name}</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ mt: 1 }}>
              {!!admit.error && <Alert severity="error">{errorMessage(admit.error)} {Object.values(fieldErrors(admit.error)).join(' ')}</Alert>}
              <TextField select label="Curriculum scheme" value={scheme} onChange={(e) => setScheme(e.target.value)}>{schemes.data?.results.map((o) => <MenuItem key={o.id} value={String(o.id)}>{o.label}</MenuItem>)}</TextField>
              <TextField select label="Admission semester" value={semester} onChange={(e) => setSemester(e.target.value)}>{semesters.data?.results.map((o) => <MenuItem key={o.id} value={String(o.id)}>{o.label}</MenuItem>)}</TextField>
              <TextField type="date" label="Admission date" value={date} onChange={(e) => setDate(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
            </Stack>
          </DialogContent>
          <DialogActions><Button onClick={() => setMode(null)}>Cancel</Button><Button variant="contained" disabled={!scheme || !semester || admit.isPending} onClick={() => admit.mutate()}>Admit</Button></DialogActions>
        </Dialog>
      )}
    </Paper>
  );
}

/** Module-specific tools shown on a record's page, next to the generic workflow actions. */
function Tools({ meta, row, id }: Props) {
  switch (meta.table) {
    case 'class_session':
      return <Paper sx={{ p: 2 }}><Link to={`/attendance/sessions/${id}`}>Mark attendance</Link></Paper>;
    case 'assessment_event':
      return <Paper sx={{ p: 2 }}><Link to={`/assessments/events/${id}/marks`}>Enter marks</Link></Paper>;
    case 'course_offering':
      return meta.can.update ? <Paper sx={{ p: 2 }}><Calculate label="Calculate results" url={`/assessments/offerings/${id}/calculate-results`} id={id} /></Paper> : null;
    case 'student_term_registration':
      return meta.can.update ? <Paper sx={{ p: 2 }}><Calculate label="Calculate term result" url={`/assessments/term-registrations/${id}/calculate-term-result`} id={id} /></Paper> : null;
    case 'admission_application':
      return <Admission row={row} id={id} />;
    case 'student':
      return <StudentInsights studentId={id} />;
    case 'feedback_cycle':
      return <FeedbackSummaryPanel cycleId={id} />;
    default:
      return null;
  }
}

const NO_SUMMARY = new Set(['student', 'feedback_cycle']);

export function Extras(props: Props) {
  return (
    <>
      <Tools {...props} />
      {!NO_SUMMARY.has(props.meta.table) && <RecordSummary path={props.meta.path} id={props.id} />}
    </>
  );
}
