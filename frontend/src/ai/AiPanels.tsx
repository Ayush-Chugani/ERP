import { useState } from 'react';
import { Alert, Button, Chip, InputAdornment, LinearProgress, Paper, Stack, TextField, Typography } from '@mui/material';
import AutoAwesome from '@mui/icons-material/AutoAwesomeOutlined';
import { useMutation } from '@tanstack/react-query';
import { api, errorMessage } from '../api/client';
import { useAiStatus } from './useAi';

function Disclaimer() {
  return <Typography variant="caption" color="text.secondary">AI-generated — review before relying on it.</Typography>;
}

/** Summarise the record being viewed (the server applies the same access rules as opening it). */
export function RecordSummary({ path, id }: { path: string; id: string }) {
  const ai = useAiStatus();
  const run = useMutation({ mutationFn: () => api<{ summary: string }>('/ai/summarize-record', { method: 'POST', body: { path, id } }) });
  if (!ai.enabled) return null;
  return (
    <Paper sx={{ p: 2 }}>
      <Stack spacing={1.5}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <AutoAwesome color="primary" fontSize="small" />
          <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>AI summary</Typography>
          <Button size="small" variant="outlined" onClick={() => run.mutate()} disabled={run.isPending}>{run.data ? 'Refresh' : 'Summarise this record'}</Button>
        </Stack>
        {run.isPending && <LinearProgress />}
        {!!run.error && <Alert severity="error">{errorMessage(run.error)}</Alert>}
        {run.data && (
          <>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{run.data.summary}</Typography>
            <Disclaimer />
          </>
        )}
      </Stack>
    </Paper>
  );
}

type Insight = {
  attendance_percentage: number | null;
  risk: 'low' | 'medium' | 'high';
  flags: { type: string; course?: string; percentage?: number; failed_courses?: number }[];
  narrative: string | null;
};

/** Early-warning view for one student: deterministic flags, optionally worded by AI. */
export function StudentInsights({ studentId }: { studentId: string }) {
  const ai = useAiStatus();
  const run = useMutation({
    mutationFn: () => api<Insight>('/ai/student-insights', { method: 'POST', body: { student_id: Number(studentId), narrative: ai.enabled } }),
  });
  const color = { low: 'success', medium: 'warning', high: 'error' } as const;
  return (
    <Paper sx={{ p: 2 }}>
      <Stack spacing={1.5}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <AutoAwesome color="primary" fontSize="small" />
          <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>Student insights</Typography>
          <Button size="small" variant="outlined" onClick={() => run.mutate()} disabled={run.isPending}>{run.data ? 'Refresh' : 'Check progress'}</Button>
        </Stack>
        {run.isPending && <LinearProgress />}
        {!!run.error && <Alert severity="error">{errorMessage(run.error)}</Alert>}
        {run.data && (
          <Stack spacing={1}>
            <Stack direction="row" spacing={1}>
              <Chip color={color[run.data.risk]} label={`${run.data.risk} risk`} />
              <Chip variant="outlined" label={`Attendance ${run.data.attendance_percentage ?? '—'}%`} />
            </Stack>
            {run.data.flags.length === 0 && <Typography variant="body2">No concerns found in attendance or results.</Typography>}
            {run.data.flags.map((f, i) => (
              <Typography key={i} variant="body2">
                {f.type === 'attendance' ? `Attendance ${f.percentage}% in ${f.course ?? 'a course'} (below 75%)` : `${f.failed_courses} failed course(s)`}
              </Typography>
            ))}
            {run.data.narrative && (
              <>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', bgcolor: 'action.hover', p: 1.5, borderRadius: 2 }}>{run.data.narrative}</Typography>
                <Disclaimer />
              </>
            )}
          </Stack>
        )}
      </Stack>
    </Paper>
  );
}

type FeedbackSummary = { summary: string; themes: string[]; sentiment: string; comments_analysed: number };

export function FeedbackSummaryPanel({ cycleId }: { cycleId: string }) {
  const ai = useAiStatus();
  const run = useMutation({ mutationFn: () => api<FeedbackSummary>('/ai/summarize-feedback', { method: 'POST', body: { cycle_id: Number(cycleId) } }) });
  if (!ai.enabled) return null;
  return (
    <Paper sx={{ p: 2 }}>
      <Stack spacing={1.5}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <AutoAwesome color="primary" fontSize="small" />
          <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>Written comments</Typography>
          <Button size="small" variant="outlined" onClick={() => run.mutate()} disabled={run.isPending}>Summarise comments</Button>
        </Stack>
        {run.isPending && <LinearProgress />}
        {!!run.error && <Alert severity="info">{errorMessage(run.error)}</Alert>}
        {run.data && (
          <Stack spacing={1}>
            <Typography variant="body2">{run.data.summary}</Typography>
            <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
              {run.data.themes.map((t) => <Chip key={t} size="small" label={t} />)}
              <Chip size="small" variant="outlined" label={`${run.data.sentiment} · ${run.data.comments_analysed} comments`} />
            </Stack>
            <Disclaimer />
          </Stack>
        )}
      </Stack>
    </Paper>
  );
}

export type SuggestedFilters = { search: string; filters: Record<string, string>; ordering: string };

/** Plain-English filter box above a list; the suggestion is applied through the normal, scope-filtered list API. */
export function AiFilterBox({ path, onApply }: { path: string; onApply: (f: SuggestedFilters) => void }) {
  const ai = useAiStatus();
  const [q, setQ] = useState('');
  const run = useMutation({
    mutationFn: () => api<SuggestedFilters>('/ai/query-to-filters', { method: 'POST', body: { path, question: q } }),
    onSuccess: (f) => onApply(f),
  });
  if (!ai.enabled) return null;
  return (
    <Stack spacing={0.5} sx={{ flexGrow: 1, maxWidth: 520 }}>
      <TextField
        placeholder="Ask in plain English, e.g. active students from CSE" value={q} onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && q.trim().length > 1) run.mutate(); }}
        slotProps={{
          input: {
            startAdornment: <InputAdornment position="start"><AutoAwesome color="primary" fontSize="small" /></InputAdornment>,
            endAdornment: <Button size="small" disabled={run.isPending || q.trim().length < 2} onClick={() => run.mutate()}>Filter</Button>,
          },
          htmlInput: { maxLength: 300, 'aria-label': 'Ask AI to filter' },
        }}
      />
      {!!run.error && <Typography variant="caption" color="error">{errorMessage(run.error)}</Typography>}
    </Stack>
  );
}

/** Drafts an announcement title and body from a topic. */
export function AnnouncementDraft({ onDraft }: { onDraft: (title: string, description: string) => void }) {
  const ai = useAiStatus();
  const [topic, setTopic] = useState('');
  const run = useMutation({
    mutationFn: () => api<{ title: string; description: string }>('/ai/draft-announcement', { method: 'POST', body: { topic } }),
    onSuccess: (d) => onDraft(d.title, d.description),
  });
  if (!ai.enabled) return null;
  return (
    <Stack spacing={1} sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 2, bgcolor: 'action.hover' }}>
      <Stack direction="row" spacing={1}>
        <TextField
          placeholder="Draft with AI: what is the announcement about?" value={topic} onChange={(e) => setTopic(e.target.value)}
          slotProps={{
            input: { startAdornment: <InputAdornment position="start"><AutoAwesome color="primary" fontSize="small" /></InputAdornment> },
            htmlInput: { maxLength: 200, 'aria-label': 'Announcement topic' },
          }}
        />
        <Button variant="outlined" disabled={run.isPending || topic.trim().length < 3} onClick={() => run.mutate()}>{run.isPending ? 'Drafting…' : 'Draft'}</Button>
      </Stack>
      {!!run.error && <Typography variant="caption" color="error">{errorMessage(run.error)}</Typography>}
      {run.isSuccess && <Disclaimer />}
    </Stack>
  );
}
