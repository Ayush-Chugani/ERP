import { useEffect, useState } from 'react';
import { Link, Route, Routes, useParams, useSearchParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  TextField,
  Typography,
} from '@mui/material';
import { ApiError, message, request } from '../common-reference/api';
import { PageHeader, EmptyState, ErrorAlert } from '../../components/feedback';
import { SEARCH_DEBOUNCE_MS, PAGINATION } from '../../lib/config';

type Row = Record<string, unknown> & { id?: string | number };
type Page<T> = { count: number; results: T[] };

const RESOURCES = [
  { path: 'applicants', title: 'Applicants', description: 'Prospective student records awaiting application.' },
  { path: 'applications', title: 'Applications', description: 'Admission applications with fee-clearance, admit and lifecycle transitions.' },
  { path: 'enrolments', title: 'Enrolments', description: 'Student programme enrolments and status history.' },
  { path: 'history', title: 'Status history', description: 'Read-only enrolment status transitions.' },
] as const;

/**
 * Admissions & enrolment workspace (backend: api/v1/admissions/).
 * Previously missing from the frontend — now wired with the same
 * list/detail/command pattern as the other lifecycle modules.
 */
const rowId = (row: Record<string, unknown>) =>
  row.id ?? row.pk ?? row.application_id ?? row.admission_applicant_id ?? row.enrolment_id ?? row.enrolment_status_history_id;
const rowStatus = (row: Record<string, unknown>) =>
  row.status ?? row.application_status ?? row.enrolment_status ?? row.new_status;

export function AdmissionsApp() {
  return (
    <Routes>
      <Route index element={<Overview />} />
      <Route path=":resource" element={<ResourceView />} />
      <Route path="*" element={<Overview />} />
    </Routes>
  );
}

function Overview() {
  return (
    <Stack spacing={3}>
      <PageHeader
        overline="Student lifecycle"
        title="Admissions and enrolment"
        description="Track applicants through application, fee clearance, admission and programme enrolment. Writes honour admission policies and reference validation."
      />
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' } }}>
        {RESOURCES.map((r) => (
          <Paper key={r.path} sx={{ p: 3 }}>
            <Typography variant="h6">{r.title}</Typography>
            <Typography color="text.secondary" sx={{ mb: 2 }}>{r.description}</Typography>
            <Button component={Link} to={r.path}>Open {r.title.toLowerCase()}</Button>
          </Paper>
        ))}
      </Box>
    </Stack>
  );
}

function ResourceView() {
  const { resource } = useParams();
  const meta = RESOURCES.find((r) => r.path === resource) || RESOURCES[0];
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get('search') || '');
  const [rows, setRows] = useState<Row[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState('');
  const [revision, setRevision] = useState(0);
  const page = Math.max(0, Number(params.get('page') || 1) - 1);
  const size = Math.min(PAGINATION.maxPageSize, Number(params.get('page_size') || PAGINATION.defaultPageSize));

  useEffect(() => {
    const t = setTimeout(() => {
      const next = new URLSearchParams(params);
      if (search) next.set('search', search);
      else next.delete('search');
      next.delete('page');
      setParams(next, { replace: true });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setFailure('');
    const query = new URLSearchParams(params);
    query.set('page', String(page + 1));
    query.set('page_size', String(size));
    request<Page<Row>>(`/admissions/${meta.path}/?${query}`, { signal: controller.signal })
      .then((data) => {
        setRows(data.results);
        setCount(data.count);
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setFailure(message(e) + (e instanceof ApiError ? ` ${JSON.stringify(e.details)}` : ''));
          setRows([]);
          setCount(0);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [meta.path, params, page, size, revision]);

  return (
    <Stack spacing={3}>
      <PageHeader
        overline="Admissions"
        title={meta.title}
        description={meta.description}
        actions={<Button component={Link} to="/admissions">All admissions</Button>}
      />
      {failure && <ErrorAlert message={failure} onRetry={() => setRevision((n) => n + 1)} />}
      <Paper sx={{ p: 2 }}>
        <TextField
          fullWidth
          label={`Search ${meta.title.toLowerCase()}`}
          value={search}
          onChange={(e) => setSearch(e.target.value.slice(0, 150))}
        />
      </Paper>
      <Paper sx={{ overflow: 'hidden' }}>
        {loading && <LinearProgress aria-label={`Loading ${meta.title}`} />}
        <TableContainer>
          <Table aria-label={meta.title} sx={{ minWidth: 640 }}>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Summary</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {!loading && rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3}>
                    <EmptyState title="No records match these filters." hint="Adjust the search or contact admissions if a record should exist." />
                  </TableCell>
                </TableRow>
              )}
              {rows.map((row, i) => (
                <TableRow key={String(rowId(row) ?? i)}>
                  <TableCell>{String(rowId(row) ?? '—')}</TableCell>
                  <TableCell>
                    <Typography sx={{ fontWeight: 600 }}>
                      {String(row.display_name ?? row.applicant_name ?? row.application_number ?? row.enrolment_number ?? row.id ?? 'Record')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {[row.programme_name, row.application_date ?? row.admission_date ?? row.effective_date, row.eligibility_status, row.reason].filter(Boolean).map(String).join(' · ')}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {rowStatus(row) ? <Chip size="small" label={String(rowStatus(row)).replaceAll('_', ' ')} variant="outlined" /> : <Typography color="text.secondary">—</Typography>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={count}
          page={page}
          rowsPerPage={size}
          rowsPerPageOptions={[...PAGINATION.pageSizeOptions]}
          onPageChange={(_, p) => { const n = new URLSearchParams(params); n.set('page', String(p + 1)); setParams(n); }}
          onRowsPerPageChange={(e) => { const n = new URLSearchParams(params); n.set('page_size', e.target.value); n.delete('page'); setParams(n); }}
        />
      </Paper>
    </Stack>
  );
}
