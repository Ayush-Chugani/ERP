import { useMemo, useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack } from '@mui/material';
import Grid from '@mui/material/Grid';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, errorMessage, fieldErrors } from '../api/client';
import type { ResourceMeta, Row } from '../api/types';
import { AnnouncementDraft } from '../ai/AiPanels';
import { FieldInput } from './FieldInput';

/** Create / edit dialog generated from the resource metadata served by the API. */
export function ResourceForm({ meta, row, onClose, onSaved }: {
  meta: ResourceMeta; row?: Row; onClose: () => void; onSaved: (saved: Row) => void;
}) {
  const qc = useQueryClient();
  const editing = !!row;
  const fields = useMemo(() => meta.columns.filter((c) => !c.readonly && !c.primary), [meta]);
  const [values, setValues] = useState<Record<string, unknown>>(() => {
    const v: Record<string, unknown> = {};
    for (const c of fields) v[c.name] = row ? row[c.name] ?? null : c.kind === 'bool' ? false : null;
    return v;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');

  const save = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = {};
      for (const c of fields) {
        const v = values[c.name];
        if (editing) {
          if (v !== (row![c.name] ?? null)) body[c.name] = v;
        } else if (v !== null && v !== '') body[c.name] = v;
      }
      if (editing) {
        if (Object.keys(body).length === 0) return row!;
        if ('version' in row!) body.version = row!.version;
        return api<Row>(`/${meta.path}/${row![meta.primary_key]}`, { method: 'PATCH', body });
      }
      return api<Row>(`/${meta.path}`, { method: 'POST', body, headers: { 'Idempotency-Key': crypto.randomUUID() } });
    },
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['list', meta.path] });
      qc.invalidateQueries({ queryKey: ['detail', meta.path] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      onSaved(saved);
    },
    onError: (e) => {
      setErrors(fieldErrors(e));
      setFormError(errorMessage(e));
    },
  });

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>{editing ? `Edit ${meta.title.toLowerCase()}` : `New ${meta.title.toLowerCase()}`}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          {formError && <Alert severity="error">{formError}</Alert>}
          {meta.table === 'announcement' && !editing && (
            <AnnouncementDraft onDraft={(title, description) => setValues((s) => ({ ...s, title, description }))} />
          )}
          <Grid container spacing={2}>
            {fields.map((c) => (
              <Grid key={c.name} size={{ xs: 12, sm: c.kind === 'text' || c.kind === 'json' ? 12 : 6 }}>
                <FieldInput col={c} value={values[c.name]} label={row?.labels?.[c.name]} error={errors[c.name]}
                  onChange={(v) => setValues((s) => ({ ...s, [c.name]: v }))} />
              </Grid>
            ))}
          </Grid>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={save.isPending} onClick={() => { setErrors({}); setFormError(''); save.mutate(); }}>
          {save.isPending ? 'Saving…' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
