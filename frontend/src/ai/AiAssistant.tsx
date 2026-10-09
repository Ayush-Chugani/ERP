import { useRef, useState, type FormEvent } from 'react';
import { Alert, Box, Divider, Drawer, IconButton, LinearProgress, Stack, TextField, Tooltip, Typography } from '@mui/material';
import AutoAwesome from '@mui/icons-material/AutoAwesomeOutlined';
import Close from '@mui/icons-material/Close';
import Send from '@mui/icons-material/SendOutlined';
import { useMutation } from '@tanstack/react-query';
import { api, errorMessage } from '../api/client';
import { useAiStatus } from './useAi';

type Turn = { q: string; a: string };

/** "Ask SIMS": how-to help. It has no access to records; answers are shown as plain text only. */
export function AiAssistant() {
  const ai = useAiStatus();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const end = useRef<HTMLDivElement>(null);
  const ask = useMutation({
    mutationFn: (question: string) => api<{ answer: string }>('/ai/assistant', { method: 'POST', body: { question } }),
    onSuccess: (r, question) => {
      setTurns((t) => [...t, { q: question, a: r.answer }]);
      setTimeout(() => end.current?.scrollIntoView?.({ behavior: 'smooth' }), 50);
    },
  });
  if (!ai.enabled) return null;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (q.trim().length < 2) return;
    ask.mutate(q.trim());
    setQ('');
  };
  return (
    <>
      <Tooltip title="Ask SIMS (AI help)">
        <IconButton color="inherit" aria-label="Ask SIMS" onClick={() => setOpen(true)}><AutoAwesome sx={{ color: 'primary.main' }} /></IconButton>
      </Tooltip>
      <Drawer anchor="right" open={open} onClose={() => setOpen(false)} slotProps={{ paper: { sx: { width: { xs: '100%', sm: 420 } } } }}>
        <Stack sx={{ height: '100%' }}>
          <Stack direction="row" sx={{ p: 2, alignItems: 'center', justifyContent: 'space-between' }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}><AutoAwesome color="primary" /><Typography variant="h6">Ask SIMS</Typography></Stack>
            <IconButton aria-label="Close assistant" onClick={() => setOpen(false)}><Close /></IconButton>
          </Stack>
          <Divider />
          <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
            {turns.length === 0 && (
              <Typography color="text.secondary">Ask how to do something, for example how to record fee clearance or where to mark attendance. The assistant cannot see any records.</Typography>
            )}
            <Stack spacing={2}>
              {turns.map((t, i) => (
                <Box key={i}>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>{t.q}</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', bgcolor: 'action.hover', p: 1.5, borderRadius: 2 }}>{t.a}</Typography>
                </Box>
              ))}
              {ask.isPending && <LinearProgress />}
              {!!ask.error && <Alert severity="error">{errorMessage(ask.error)}</Alert>}
              <div ref={end} />
            </Stack>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ px: 2 }}>AI-generated. Check important details before acting.</Typography>
          <Box component="form" onSubmit={submit} sx={{ p: 2, display: 'flex', gap: 1 }}>
            <TextField placeholder="Ask a question…" value={q} onChange={(e) => setQ(e.target.value)} slotProps={{ htmlInput: { maxLength: 500, 'aria-label': 'Your question' } }} />
            <IconButton type="submit" color="primary" aria-label="Send question" disabled={ask.isPending || q.trim().length < 2}><Send /></IconButton>
          </Box>
        </Stack>
      </Drawer>
    </>
  );
}
