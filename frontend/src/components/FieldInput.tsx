import { useState } from 'react';
import { Autocomplete, FormControlLabel, MenuItem, Switch, TextField } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ColumnMeta } from '../api/types';
import { FileField } from './FileField';
import { humanize } from './format';

type Option = { id: number | string; label: string };

function LookupField({ col, value, label, onChange, error }: {
  col: ColumnMeta; value: unknown; label?: string; onChange: (v: unknown) => void; error?: string;
}) {
  const [input, setInput] = useState('');
  const path = col.references!.path;
  const options = useQuery({
    queryKey: ['lookup', path, input],
    queryFn: () => api<{ results: Option[] }>(`/lookups/${path}`, { query: { q: input || undefined, limit: 30 } }),
    staleTime: 30_000,
  });
  const selected = value === null || value === undefined || value === '' ? null : { id: value as number, label: label ?? `#${String(value)}` };
  const list = options.data?.results ?? [];
  const merged = selected && !list.some((o) => String(o.id) === String(selected.id)) ? [selected, ...list] : list;
  return (
    <Autocomplete
      options={merged}
      value={selected}
      loading={options.isLoading}
      isOptionEqualToValue={(a, b) => String(a.id) === String(b.id)}
      getOptionLabel={(o) => o.label}
      onInputChange={(_, v, reason) => reason === 'input' && setInput(v)}
      onChange={(_, o) => onChange(o ? o.id : null)}
      renderInput={(p) => (
        <TextField {...p} label={col.label} required={col.required} error={!!error} helperText={error} />
      )}
    />
  );
}

export function FieldInput({ col, value, label, onChange, error }: {
  col: ColumnMeta; value: unknown; label?: string; onChange: (v: unknown) => void; error?: string;
}) {
  const common = { label: col.label, required: col.required, error: !!error, helperText: error };
  if (col.name === 'file_object_id') {
    return <FileField label={col.label} value={value} required={col.required} onChange={onChange} />;
  }
  if (col.references) return <LookupField col={col} value={value} label={label} onChange={onChange} error={error} />;
  const text = value === null || value === undefined ? '' : String(value);
  switch (col.kind) {
    case 'bool':
      return <FormControlLabel control={<Switch checked={!!value} onChange={(e) => onChange(e.target.checked)} />} label={col.label} />;
    case 'enum':
      return (
        <TextField {...common} select value={text} onChange={(e) => onChange(e.target.value || null)}>
          {!col.required && <MenuItem value="">—</MenuItem>}
          {(col.choices ?? []).map((c) => (
            <MenuItem key={c} value={c}>{humanize(c)}</MenuItem>
          ))}
        </TextField>
      );
    case 'int':
      return <TextField {...common} type="number" value={text} onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />;
    case 'decimal':
      return <TextField {...common} value={text} inputMode="decimal" onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)} />;
    case 'date':
      return <TextField {...common} type="date" slotProps={{ inputLabel: { shrink: true } }} value={text} onChange={(e) => onChange(e.target.value || null)} />;
    case 'datetime':
      return <TextField {...common} type="datetime-local" slotProps={{ inputLabel: { shrink: true } }} value={text.slice(0, 16)} onChange={(e) => onChange(e.target.value ? new Date(e.target.value).toISOString() : null)} />;
    case 'time':
      return <TextField {...common} type="time" slotProps={{ inputLabel: { shrink: true } }} value={text} onChange={(e) => onChange(e.target.value || null)} />;
    case 'json':
      return (
        <TextField {...common} multiline minRows={3} value={typeof value === 'string' ? value : value ? JSON.stringify(value, null, 2) : ''}
          onChange={(e) => {
            try { onChange(e.target.value ? JSON.parse(e.target.value) : null); } catch { onChange(e.target.value); }
          }} />
      );
    case 'text':
      return <TextField {...common} multiline minRows={3} value={text} slotProps={{ htmlInput: { maxLength: col.max_length ?? undefined } }} onChange={(e) => onChange(e.target.value)} />;
    default:
      return <TextField {...common} value={text} slotProps={{ htmlInput: { maxLength: col.max_length ?? undefined } }} onChange={(e) => onChange(e.target.value)} />;
  }
}
