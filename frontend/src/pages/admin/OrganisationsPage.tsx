import { useState } from 'react';
import {
  Alert, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, LinearProgress, Paper, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ApartmentIcon from '@mui/icons-material/ApartmentOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../api/auth';
import { api, errorMessage, fieldErrors } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';

type Org = { institution_id: number; institution_code: string; institution_name: string; is_active: boolean; accounts: number; students: number; staff: number; administrators: string[] };
type Created = { institution: { institution_id: number; code: string; name: string }; administrator: { username: string; email: string; temporary_password?: string } };

const EMPTY = { code: '', name: '', admin_username: '', admin_email: '', admin_first_name: '', admin_last_name: '' };

function CreateOrganisation({ onClose, onCreated }: { onClose: () => void; onCreated: (c: Created) => void }) {
  const [v, setV] = useState(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const create = useMutation({
    mutationFn: () => api<Created>('/security/organisations', { method: 'POST', body: v }),
    onSuccess: onCreated,
    onError: (e) => setErrors({ ...fieldErrors(e), _: errorMessage(e) }),
  });
  const field = (k: keyof typeof EMPTY, label: string, required = false) => (
    <TextField key={k} label={label} value={v[k]} required={required} error={!!errors[k]} helperText={errors[k]} onChange={(e) => setV({ ...v, [k]: e.target.value })} />
  );
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>New organisation</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {errors._ && <Alert severity="error">{errors._}</Alert>}
          <Typography variant="subtitle2">Organisation</Typography>
          {field('code', 'Short code (e.g. ABCU)', true)}
          {field('name', 'Name', true)}
          <Typography variant="subtitle2" sx={{ pt: 1 }}>Its administrator</Typography>
          {field('admin_username', 'Username', true)}
          {field('admin_email', 'Email', true)}
          <Stack direction="row" spacing={2}>{field('admin_first_name', 'First name')}{field('admin_last_name', 'Last name')}</Stack>
          <Typography variant="caption" color="text.secondary">
            A temporary password is generated and shown once. The administrator then creates every other login (registrar, faculty, students, examination cell, support…) for this organisation.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={!v.code || !v.name || !v.admin_username || !v.admin_email || create.isPending} onClick={() => create.mutate()}>Create organisation</Button>
      </DialogActions>
    </Dialog>
  );
}

export function OrganisationsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [made, setMade] = useState<Created | null>(null);
  const orgs = useQuery({ queryKey: ['organisations'], queryFn: () => api<{ results: Org[] }>('/security/organisations') });
  return (
    <Stack spacing={2}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <PageHeader title={user?.is_superuser ? 'Organisations' : 'My organisation'} icon={ApartmentIcon}
          subtitle={user?.is_superuser ? 'Create organisations and hand each one to its administrator' : 'People and accounts in your organisation'}
          crumbs={[{ label: 'Home', to: '/' }, { label: 'Administration' }, { label: 'Organisations' }]} />
        {user?.is_superuser && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreating(true)}>New organisation</Button>}
      </Stack>
      {!!orgs.error && <Alert severity="error">{errorMessage(orgs.error)}</Alert>}
      <Paper>
        {orgs.isFetching && <LinearProgress />}
        <Table size="small">
          <TableHead><TableRow><TableCell>Organisation</TableCell><TableCell>Administrators</TableCell><TableCell align="right">Accounts</TableCell><TableCell align="right">Students</TableCell><TableCell align="right">Staff</TableCell></TableRow></TableHead>
          <TableBody>
            {orgs.data?.results.map((o) => (
              <TableRow key={o.institution_id} hover>
                <TableCell><Typography variant="body2" sx={{ fontWeight: 600 }}>{o.institution_name}</Typography><Typography variant="caption" color="text.secondary">{o.institution_code}</Typography></TableCell>
                <TableCell>{o.administrators.length ? o.administrators.map((a) => <Chip key={a} size="small" label={a} sx={{ mr: 0.5 }} />) : <Typography variant="body2" color="text.secondary">none yet</Typography>}</TableCell>
                <TableCell align="right">{o.accounts}</TableCell><TableCell align="right">{o.students}</TableCell><TableCell align="right">{o.staff}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
      {creating && <CreateOrganisation onClose={() => setCreating(false)} onCreated={(c) => { setCreating(false); setMade(c); qc.invalidateQueries({ queryKey: ['organisations'] }); qc.invalidateQueries({ queryKey: ['users'] }); }} />}
      {made && (
        <Dialog open onClose={() => setMade(null)} fullWidth maxWidth="xs">
          <DialogTitle>{made.institution.name} is ready</DialogTitle>
          <DialogContent>
            <Alert severity="warning" sx={{ mb: 2 }}>Shown once. Share these with the administrator securely; they must change the password at first sign-in and use the <b>Organisation administrator</b> sign-in.</Alert>
            <Typography>Username</Typography>
            <Typography sx={{ fontFamily: 'monospace', fontSize: 18, userSelect: 'all', mb: 1 }}>{made.administrator.username}</Typography>
            <Typography>Temporary password</Typography>
            <Typography sx={{ fontFamily: 'monospace', fontSize: 18, userSelect: 'all' }}>{made.administrator.temporary_password}</Typography>
          </DialogContent>
          <DialogActions><Button onClick={() => setMade(null)}>Done</Button></DialogActions>
        </Dialog>
      )}
    </Stack>
  );
}
