import { useState } from 'react';
import { Alert, Button, Card, CardContent, LinearProgress, MenuItem, Rating, Stack, TextField, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, errorMessage } from '../api/client';
import { formatDateTime } from '../components/format';
import { PageHeader } from '../components/PageHeader';
import FeedbackIcon from '@mui/icons-material/RateReviewOutlined';

type Pending = { cycle_id: number; cycle_name: string; closes_at: string; course_offering_id: number; course: string; offering_code: string };
type Item = { questionnaire_item_id: number; is_required: boolean; question_text: string; response_type: string; rating_min: string | null; rating_max: string | null; choices: { id: number; text: string }[] };
type Form = { cycle_id: number; cycle_name: string; allow_text: boolean; items: Item[] };
type Answer = { numeric_score?: number; text_response?: string; choice_ids?: number[] };

function FeedbackForm({ target, onDone }: { target: Pending; onDone: () => void }) {
  const form = useQuery({ queryKey: ['feedback-form', target.cycle_id], queryFn: () => api<Form>(`/feedback/cycles/${target.cycle_id}/form`) });
  const [answers, setAnswers] = useState<Record<number, Answer>>({});
  const submit = useMutation({
    mutationFn: () => api<{ receipt: string }>(`/feedback/cycles/${target.cycle_id}/respond`, {
      method: 'POST',
      body: { course_offering_id: target.course_offering_id, answers: Object.entries(answers).map(([id, a]) => ({ questionnaire_item_id: Number(id), ...a })) },
    }),
  });
  if (form.isLoading) return <LinearProgress />;
  if (!form.data) return <Alert severity="error">{errorMessage(form.error)}</Alert>;
  if (submit.isSuccess) return (
    <Alert severity="success" action={<Button onClick={onDone}>Done</Button>}>
      Thank you. Your response is anonymous. Receipt: <b>{submit.data.receipt}</b>
    </Alert>
  );
  const missing = form.data.items.some((i) => i.is_required && !answers[i.questionnaire_item_id]);
  return (
    <Stack spacing={2}>
      <Typography variant="h6">{target.course}</Typography>
      <Alert severity="info">Your answers are stored without your name and cannot be traced back to you.</Alert>
      {!!submit.error && <Alert severity="error">{errorMessage(submit.error)}</Alert>}
      {form.data.items.map((it) => {
        const set = (a: Answer) => setAnswers((s) => ({ ...s, [it.questionnaire_item_id]: a }));
        return (
          <Stack key={it.questionnaire_item_id} spacing={1}>
            <Typography>{it.question_text}{it.is_required && ' *'}</Typography>
            {it.rating_min !== null && it.rating_max !== null ? (
              <Rating max={Number(it.rating_max)} value={answers[it.questionnaire_item_id]?.numeric_score ?? null} onChange={(_, v) => v && set({ numeric_score: v })} />
            ) : it.choices.length > 0 ? (
              <TextField select value={answers[it.questionnaire_item_id]?.choice_ids?.[0] ?? ''} onChange={(e) => set({ choice_ids: [Number(e.target.value)] })}>
                {it.choices.map((c) => <MenuItem key={c.id} value={c.id}>{c.text}</MenuItem>)}
              </TextField>
            ) : (
              <TextField multiline minRows={2} disabled={!form.data!.allow_text} value={answers[it.questionnaire_item_id]?.text_response ?? ''}
                onChange={(e) => set({ text_response: e.target.value })} helperText={form.data!.allow_text ? '' : 'Comments are switched off for this cycle'} />
            )}
          </Stack>
        );
      })}
      <Button variant="contained" disabled={missing || submit.isPending} onClick={() => submit.mutate()}>{submit.isPending ? 'Submitting…' : 'Submit feedback'}</Button>
    </Stack>
  );
}

export function FeedbackPage() {
  const qc = useQueryClient();
  const pending = useQuery({ queryKey: ['feedback-pending'], queryFn: () => api<{ results: Pending[] }>('/feedback/pending') });
  const [target, setTarget] = useState<Pending | null>(null);
  return (
    <Stack spacing={2} sx={{ maxWidth: 760 }}>
      <PageHeader title="Course feedback" subtitle="Anonymous feedback on your courses" icon={FeedbackIcon} crumbs={[{ label: 'Home', to: '/' }, { label: 'Feedback' }]} />
      {pending.isLoading && <LinearProgress />}
      {target ? (
        <FeedbackForm target={target} onDone={() => { setTarget(null); qc.invalidateQueries({ queryKey: ['feedback-pending'] }); }} />
      ) : (
        <>
          {pending.data?.results.length === 0 && <Alert severity="success">You have no feedback to give right now.</Alert>}
          {pending.data?.results.map((p) => (
            <Card key={`${p.cycle_id}-${p.course_offering_id}`}>
              <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
                <div><Typography variant="subtitle1">{p.course}</Typography><Typography variant="body2" color="text.secondary">{p.cycle_name} · closes {formatDateTime(p.closes_at)}</Typography></div>
                <Button variant="contained" onClick={() => setTarget(p)}>Give feedback</Button>
              </CardContent>
            </Card>
          ))}
        </>
      )}
    </Stack>
  );
}
