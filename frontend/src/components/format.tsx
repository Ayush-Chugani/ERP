import { Button, Chip } from '@mui/material';
import { downloadFile } from '../api/client';
import type { ColumnMeta, Row } from '../api/types';

export const humanize = (v: unknown): string => {
  const t = String(v ?? '').replace(/_id$/, '').replace(/[_-]+/g, ' ').trim().toLowerCase();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : '';
};

const parseDate = (v: unknown): Date | null => {
  if (!v) return null;
  const s = String(v);
  const d = /^\d{4}-\d{2}-\d{2}$/.test(s) ? new Date(Number(s.slice(0, 4)), Number(s.slice(5, 7)) - 1, Number(s.slice(8, 10))) : new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
};

export const formatDate = (v: unknown): string => {
  const d = parseDate(v);
  return d ? d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
};
export const formatDateTime = (v: unknown): string => {
  const d = parseDate(v);
  return d ? `${formatDate(v)}, ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}` : '—';
};

const GOOD = /^(ACTIVE|APPROVED|VERIFIED|PUBLISHED|COMPLETED|ISSUED|RESOLVED|ACCEPTED|ELIGIBLE|SELECTED|ADMITTED|OPEN|PASS|PRESENT)$/;
const BAD = /^(REJECTED|CANCELLED|WITHDRAWN|TERMINATED|INELIGIBLE|EXPIRED|FAIL|ABSENT|DEAD|FAILED|DISABLED|LOCKED)$/;
const WARN = /^(PENDING|SUBMITTED|UNDER_REVIEW|RETURNED|DRAFT|PLANNED|SUSPENDED|ON_LEAVE|ON_BREAK|WAITLISTED|SCHEDULED)$/;

export function StatusChip({ value }: { value: unknown }) {
  const s = String(value ?? '');
  if (!s) return <>—</>;
  const color = GOOD.test(s) ? 'success' : BAD.test(s) ? 'error' : WARN.test(s) ? 'warning' : 'default';
  return <Chip size="small" label={humanize(s)} color={color} variant={color === 'default' ? 'outlined' : 'filled'} />;
}

/** Render one cell according to the column kind (foreign keys show their label, not the raw id). */
export function renderValue(col: ColumnMeta | undefined, row: Row, name: string) {
  const v = row[name];
  if (v === null || v === undefined || v === '') return '—';
  if (!col) return String(v);
  if (name === 'file_object_id') return <Button size="small" onClick={() => downloadFile(Number(v))}>Download file</Button>;
  if (col.references) return row.labels?.[name] ?? `#${String(v)}`;
  switch (col.kind) {
    case 'bool':
      return v ? 'Yes' : 'No';
    case 'date':
      return formatDate(v);
    case 'datetime':
      return formatDateTime(v);
    case 'enum':
      return <StatusChip value={v} />;
    case 'json':
      return <code>{JSON.stringify(v).slice(0, 80)}</code>;
    default:
      return col.name.endsWith('status') ? <StatusChip value={v} /> : String(v);
  }
}
