import { useMemo, useState } from 'react';
import {
  Alert, Box, Button, Checkbox, Chip, FormControlLabel, List, ListItemButton, ListItemText, Paper, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, errorMessage } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import RolesIcon from '@mui/icons-material/VpnKeyOutlined';

type Role = { role_id: number; role_code: string; role_name: string; role_level: string; is_system_role: boolean; permissions: number };
type RoleDetail = Role & { description: string | null; permissions: { code: string; effect: 'ALLOW' | 'DENY' }[] };
type Perm = { code: string; name: string; sensitive: boolean };

export function RolesPage() {
  const qc = useQueryClient();
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<{ results: Role[] }>('/security/roles') });
  const [selected, setSelected] = useState<number | null>(null);
  const [filter, setFilter] = useState('');
  const [draft, setDraft] = useState<Set<string> | null>(null);
  const detail = useQuery({
    queryKey: ['role', selected], enabled: selected !== null,
    queryFn: async () => { const d = await api<RoleDetail>(`/security/roles/${selected}`); setDraft(new Set(d.permissions.filter((p) => p.effect === 'ALLOW').map((p) => p.code))); return d; },
  });
  const perms = useQuery({ queryKey: ['permissions'], queryFn: () => api<{ results: Perm[] }>('/security/permissions'), staleTime: 10 * 60_000 });
  const save = useMutation({
    mutationFn: () => api(`/security/roles/${selected}/permissions`, { method: 'PUT', body: { allow: [...(draft ?? [])], deny: [] } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['roles'] }); qc.invalidateQueries({ queryKey: ['role', selected] }); },
  });
  // The ALL-resource permissions are the ones roles are built from; per-resource codes are available to power users.
  const visible = useMemo(() => (perms.data?.results ?? []).filter((p) => p.code.includes('.ALL.') && p.code.toLowerCase().includes(filter.toLowerCase())), [perms.data, filter]);
  const byModule = useMemo(() => { const m: Record<string, Perm[]> = {}; for (const p of visible) (m[p.code.split('.')[0]] ??= []).push(p); return m; }, [visible]);
  const isSuper = detail.data?.role_code === 'SUPER_ADMIN';

  return (
    <Stack spacing={2}>
      <PageHeader title="Roles and permissions" subtitle="Review and adjust what each role allows" icon={RolesIcon} crumbs={[{ label: 'Home', to: '/' }, { label: 'Administration' }, { label: 'Roles' }]} />
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '300px 1fr' }, gap: 2 }}>
        <Paper sx={{ maxHeight: '75vh', overflow: 'auto' }}>
          <List dense>
            {roles.data?.results.map((r) => (
              <ListItemButton key={r.role_id} selected={selected === r.role_id} onClick={() => setSelected(r.role_id)}>
                <ListItemText primary={r.role_name} secondary={`${r.role_code} · ${r.role_level.toLowerCase()} · ${r.permissions} permissions`} />
              </ListItemButton>
            ))}
          </List>
        </Paper>
        <Paper sx={{ p: 2 }}>
          {!selected && <Typography color="text.secondary">Select a role to review or change what it allows.</Typography>}
          {detail.data && draft && (
            <Stack spacing={2}>
              <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <div><Typography variant="h6">{detail.data.role_name}</Typography><Typography variant="body2" color="text.secondary">{detail.data.description}</Typography></div>
                <Button variant="contained" disabled={save.isPending || isSuper} onClick={() => save.mutate()}>Save permissions</Button>
              </Stack>
              {isSuper && <Alert severity="info">SUPER_ADMIN always holds every permission and cannot be edited.</Alert>}
              {!!save.error && <Alert severity="error">{errorMessage(save.error)}</Alert>}
              {save.isSuccess && <Alert severity="success">Saved. Changes apply within seconds.</Alert>}
              <TextField placeholder="Filter permissions…" value={filter} onChange={(e) => setFilter(e.target.value)} />
              <Box sx={{ maxHeight: '55vh', overflow: 'auto' }}>
                {Object.entries(byModule).map(([mod, items]) => (
                  <Box key={mod} sx={{ mb: 1.5 }}>
                    <Typography variant="overline">{mod.replaceAll('_', ' ')}</Typography>
                    <Stack direction="row" sx={{ flexWrap: 'wrap' }}>
                      {items.map((p) => (
                        <FormControlLabel key={p.code} sx={{ width: 150 }} disabled={isSuper}
                          control={<Checkbox size="small" checked={draft.has(p.code)} onChange={(e) => { const n = new Set(draft); (e.target.checked ? n.add(p.code) : n.delete(p.code)); setDraft(n); }} />}
                          label={<Typography variant="body2">{p.code.split('.').pop()?.toLowerCase()}{p.sensitive && <Chip size="small" color="warning" label="!" sx={{ ml: 0.5, height: 16 }} />}</Typography>} />
                      ))}
                    </Stack>
                  </Box>
                ))}
              </Box>
            </Stack>
          )}
        </Paper>
      </Box>
    </Stack>
  );
}
