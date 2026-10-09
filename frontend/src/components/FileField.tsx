import { useState } from 'react';
import { Alert, Button, Stack, Typography } from '@mui/material';
import UploadIcon from '@mui/icons-material/UploadFile';
import { errorMessage, uploadFile } from '../api/client';

/** Uploads a PDF/PNG/JPEG to the private store and reports the resulting file id to the parent form. */
export function FileField({ label, value, required, onChange }: {
  label: string; value: unknown; required?: boolean; onChange: (id: number | null) => void;
}) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pick = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      const up = await uploadFile(file);
      setName(up.name);
      onChange(up.file_object_id);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Stack spacing={1}>
      <Button component="label" variant="outlined" startIcon={<UploadIcon />} disabled={busy}>
        {busy ? 'Uploading…' : `${label}${required ? ' *' : ''}`}
        <input hidden type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={(e) => pick(e.target.files?.[0])} />
      </Button>
      {value ? <Typography variant="body2" color="text.secondary">Attached: {name || `file #${String(value)}`}</Typography> : null}
      {error && <Alert severity="error">{error}</Alert>}
    </Stack>
  );
}
