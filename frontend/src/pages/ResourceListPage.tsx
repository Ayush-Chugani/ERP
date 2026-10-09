import { useState } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router';
import {
  Alert, Box, Button, Chip, InputAdornment, LinearProgress, MenuItem, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TablePagination, TableRow, TableSortLabel, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DownloadIcon from '@mui/icons-material/FileDownloadOutlined';
import InboxIcon from '@mui/icons-material/InboxOutlined';
import SearchIcon from '@mui/icons-material/Search';
import { useQuery } from '@tanstack/react-query';
import { api, errorMessage, qs } from '../api/client';
import { useResourceMeta } from '../api/hooks';
import type { Page, Row } from '../api/types';
import { humanize, renderValue } from '../components/format';
import { PageHeader } from '../components/PageHeader';
import { AiFilterBox } from '../ai/AiPanels';
import { ResourceForm } from '../components/ResourceForm';
import { WORKSPACES, iconForResource, workspaceOf } from '../layout/navConfig';

export function ResourceListPage() {
  const { module = '', slug = '' } = useParams();
  const path = `${module}/${slug}`;
  const navigate = useNavigate();
  const [sp, setSp] = useSearchParams();
  const meta = useResourceMeta(path);
  const [creating, setCreating] = useState(false);
  const page = Number(sp.get('page') || 1);
  const size = Number(sp.get('size') || 25);
  const ordering = sp.get('ordering') || '';
  const search = sp.get('q') || '';
  const filters = Object.fromEntries([...sp.entries()].filter(([k]) => k.startsWith('f.')).map(([k, v]) => [k.slice(2), v]));

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(patch)) (v === null || v === '' ? next.delete(k) : next.set(k, v));
    if (!('page' in patch)) next.delete('page');
    setSp(next, { replace: true });
  };

  const list = useQuery({
    queryKey: ['list', path, page, size, ordering, search, filters],
    queryFn: () => api<Page<Row>>(`/${path}`, { query: { page, page_size: size, ordering: ordering || undefined, search: search || undefined, ...filters } }),
    placeholderData: (prev) => prev,
    enabled: !!meta.data,
  });

  if (meta.isLoading) return <LinearProgress />;
  if (meta.error || !meta.data) return <Navigate to="/" replace />;       // a page this role cannot open simply is not there
  const m = meta.data;
  const ws = WORKSPACES.find((w) => w.key === workspaceOf(m));
  const cols = m.list_columns.map((n) => m.columns.find((c) => c.name === n)).filter(Boolean) as typeof m.columns;
  const enumFilters = m.columns.filter((c) => c.kind === 'enum' && c.choices && c.choices.length <= 12).slice(0, 2);
  const active = Object.entries(filters);

  const exportCsv = async () => {
    const text = await api<string>(`/${path}/export${qs({ search, ...filters })}`, { raw: true });
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
    Object.assign(document.createElement('a'), { href: url, download: `${m.table}.csv` }).click();
    URL.revokeObjectURL(url);
  };

  return (
    <Box>
      <PageHeader
        title={m.title} icon={iconForResource(m)}
        subtitle={list.data ? `${list.data.count} records` : ' '}
        crumbs={[{ label: 'Home', to: '/' }, ...(ws ? [{ label: ws.title, to: `/w/${ws.key}` }] : []), { label: m.title }]}
        actions={<>
          {m.can.export && <Button variant="outlined" startIcon={<DownloadIcon />} onClick={exportCsv}>Export</Button>}
          {m.can.create && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreating(true)}>New</Button>}
        </>}
      />

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ alignItems: { md: 'center' } }}>
          {m.searchable && (
            <TextField placeholder="Search…" value={search} onChange={(e) => set({ q: e.target.value })} sx={{ maxWidth: { md: 360 } }}
              slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> } }} />
          )}
          {enumFilters.map((c) => (
            <TextField key={c.name} select label={c.label} value={filters[c.name] ?? ''} onChange={(e) => set({ [`f.${c.name}`]: e.target.value })} sx={{ maxWidth: { md: 220 } }}>
              <MenuItem value="">All</MenuItem>
              {c.choices!.map((v) => <MenuItem key={v} value={v}>{humanize(v)}</MenuItem>)}
            </TextField>
          ))}
          <AiFilterBox path={path} onApply={(f) => {
            const next = new URLSearchParams();
            if (f.search) next.set('q', f.search);
            if (f.ordering) next.set('ordering', f.ordering);
            for (const [k, v] of Object.entries(f.filters)) next.set(`f.${k}`, v);
            setSp(next, { replace: true });
          }} />
          {active.length > 0 && (
            <Stack direction="row" spacing={1}>
              {active.map(([k, v]) => <Chip key={k} size="small" color="primary" label={`${humanize(k)}: ${humanize(v)}`} onDelete={() => set({ [`f.${k}`]: null })} />)}
            </Stack>
          )}
        </Stack>
      </Paper>

      {list.error && <Alert severity="error" sx={{ mb: 2 }}>{errorMessage(list.error)}</Alert>}
      <Paper sx={{ overflow: 'hidden' }}>
        {list.isFetching && <LinearProgress />}
        <TableContainer sx={{ maxHeight: '65vh' }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                {cols.map((c) => (
                  <TableCell key={c.name} sortDirection={ordering.replace('-', '') === c.name ? (ordering.startsWith('-') ? 'desc' : 'asc') : false}>
                    <TableSortLabel active={ordering.replace('-', '') === c.name} direction={ordering.startsWith('-') ? 'desc' : 'asc'}
                      onClick={() => set({ ordering: ordering === c.name ? `-${c.name}` : c.name })}>
                      {c.label}
                    </TableSortLabel>
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {list.data?.results.map((row) => (
                <TableRow key={String(row[m.primary_key])} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/r/${path}/${row[m.primary_key]}`)}>
                  {cols.map((c) => <TableCell key={c.name} sx={{ py: 1.25 }}>{renderValue(c, row, c.name)}</TableCell>)}
                </TableRow>
              ))}
              {list.data && list.data.results.length === 0 && (
                <TableRow>
                  <TableCell colSpan={cols.length}>
                    <Stack sx={{ py: 6, alignItems: 'center' }} spacing={1}>
                      <InboxIcon sx={{ fontSize: 48, color: 'text.disabled' }} />
                      <Typography color="text.secondary">Nothing here yet.</Typography>
                      {m.can.create && <Button size="small" variant="outlined" startIcon={<AddIcon />} onClick={() => setCreating(true)}>Add the first one</Button>}
                    </Stack>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination component="div" count={list.data?.count ?? 0} page={page - 1} rowsPerPage={size}
          rowsPerPageOptions={[10, 25, 50, 100]} onPageChange={(_, p) => set({ page: String(p + 1) })}
          onRowsPerPageChange={(e) => set({ size: e.target.value, page: null })} />
      </Paper>

      {creating && <ResourceForm meta={m} onClose={() => setCreating(false)}
        onSaved={(row) => { setCreating(false); if (row[m.primary_key] !== undefined) navigate(`/r/${path}/${row[m.primary_key]}`); }} />}
    </Box>
  );
}
