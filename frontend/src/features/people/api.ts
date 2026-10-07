import { request } from '../../lib/api-client';

export type Field = { name: string; label: string; required: boolean; nullable: boolean; kind: string; choices: string[] };
export type Resource = { path: string; title: string; fields: Field[]; can_create: boolean };
export type Row = Record<string, unknown> & { id: string; version: string; actions: string[]; masked_fields: string[] };
export type Page = { count: number; results: Row[] };

export const api = {
  metadata: () => request<{ resources: Resource[] }>('/people/metadata/'),
  list: (path: string, query: URLSearchParams, signal?: AbortSignal) =>
    request<Page>(`/people/${path}/?${query}`, { signal }),
  save: (path: string, row: Row | null, values: Record<string, unknown>) =>
    request<Row>(`/people/${path}/${row ? `${row.id}/` : ''}`, {
      method: row ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json', ...(row ? { 'If-Match': row.version } : {}) },
      body: JSON.stringify(values),
    }),
  action: (path: string, row: Row, action: string, values: Record<string, unknown>) =>
    request<Row>(`/people/${path}/${row.id}/${action}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'If-Match': row.version },
      body: JSON.stringify(values),
    }),
};
