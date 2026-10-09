import { useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, TextField } from '@mui/material';
import { errorMessage } from '../api/client';
import type { ActionInfo } from '../api/types';

/** Confirmation (and remarks entry) for a workflow action or destructive operation. */
export function ActionDialog({ action, title, busy, error, onCancel, onConfirm }: {
  action: Pick<ActionInfo, 'label' | 'remarks' | 'danger'>;
  title?: string; busy?: boolean; error?: unknown; onCancel: () => void; onConfirm: (remarks: string) => void;
}) {
  const [remarks, setRemarks] = useState('');
  const needs = action.remarks !== 'none';
  const missing = action.remarks === 'required' && !remarks.trim();
  return (
    <Dialog open onClose={onCancel} fullWidth maxWidth="sm">
      <DialogTitle>{title ?? action.label}</DialogTitle>
      <DialogContent>
        {!needs && <DialogContentText>Are you sure you want to “{action.label}”?</DialogContentText>}
        {!!error && <Alert severity="error" sx={{ mb: 2 }}>{errorMessage(error)}</Alert>}
        {needs && (
          <TextField autoFocus multiline minRows={2} label={action.remarks === 'required' ? 'Remarks (required)' : 'Remarks (optional)'}
            value={remarks} onChange={(e) => setRemarks(e.target.value)} slotProps={{ htmlInput: { maxLength: 1000 } }} sx={{ mt: 1 }} />
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="contained" color={action.danger ? 'error' : 'primary'} disabled={busy || missing} onClick={() => onConfirm(remarks.trim())}>
          {busy ? 'Working…' : action.label}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
