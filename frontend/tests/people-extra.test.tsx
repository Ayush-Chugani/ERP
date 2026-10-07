import React from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

vi.mock('../src/features/auth/session', () => ({
  authenticatedFetch: (path: string, init?: RequestInit) => fetch('http://localhost/api/v1' + path, init),
}));

import { PeopleApp } from '../src/features/people/PeopleApp';
import { PeopleForm } from '../src/features/people/PeopleForm';
import type { Field, Resource, Row } from '../src/features/people/api';
import { getQueryClient } from '../src/lib/query';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  cleanup();
  getQueryClient().clear();
  server.resetHandlers();
  vi.restoreAllMocks();
});
const base = 'http://localhost/api/v1';
const f = (name: string, kind: string, over: Partial<Field> = {}): Field => ({ name, label: name, required: false, nullable: false, kind, choices: [], ...over });

const resource: Resource = {
  path: 'students',
  title: 'Students',
  can_create: true,
  fields: [
    f('student_number', 'text', { label: 'Number', required: true }),
    f('active', 'boolean', { label: 'Active' }),
    f('score', 'decimal', { label: 'Score' }),
    f('rank', 'integer', { label: 'Rank' }),
    f('born', 'date', { label: 'Born' }),
    f('status', 'text', { label: 'Status', choices: ['A', 'B'] }),
    f('note', 'text', { label: 'Note', nullable: true }),
    f('gender_id', 'id', { label: 'Gender' }),
  ],
};

describe('PeopleForm', () => {
  it('validates each field kind and saves a clean payload', async () => {
    let body: Record<string, unknown> = {};
    server.use(
      http.get(`${base}/people/choices/students/gender_id/`, ({ request }) => {
        const page = new URL(request.url).searchParams.get('page');
        return HttpResponse.json({ results: [{ id: page === '2' ? '8' : '7', label: page === '2' ? 'Other' : 'Female' }], has_more: page === '1' });
      }),
      http.post(`${base}/people/students/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: '1' }, { status: 201 });
      }),
    );
    const saved = vi.fn();
    render(<PeopleForm resource={resource} row={null} onClose={() => {}} onSaved={saved} />);
    fireEvent.change(screen.getByLabelText(/Number/), { target: { value: 'S9' } });
    fireEvent.change(screen.getByLabelText(/Score/), { target: { value: 'abc' } });
    fireEvent.change(screen.getByLabelText(/Born/), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText(/Rank/), { target: { value: '3.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Enter a decimal number.')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Score/), { target: { value: '12.5' } });
    fireEvent.change(screen.getByLabelText(/Rank/), { target: { value: '3' } });
    fireEvent.click(screen.getByLabelText('Active'));
    fireEvent.mouseDown(screen.getByRole('combobox', { name: /Status/ }));
    fireEvent.click(await screen.findByRole('option', { name: 'A' }));
    const gender = screen.getByRole('combobox', { name: /Gender/ });
    fireEvent.mouseDown(gender);
    fireEvent.click(await screen.findByRole('option', { name: 'Female' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(saved).toHaveBeenCalled());
    expect(body).toMatchObject({ student_number: 'S9', score: '12.5', rank: 3, active: true, status: 'A', note: null, gender_id: '7' });
  });

  it('maps server field errors, skips immutable ids on edit, and guards discards', async () => {
    server.use(
      http.get(`${base}/people/choices/students/gender_id/`, () => HttpResponse.json({ error: { message: 'Lookup down' } }, { status: 500 })),
      http.patch(`${base}/people/students/5/`, () => HttpResponse.json({ error: { message: 'Invalid', details: { student_number: ['Duplicate', 'again'], other: 'x' } } }, { status: 400 })),
    );
    const onClose = vi.fn();
    const row: Row = { id: '5', version: '2', actions: ['change'], masked_fields: [], student_number: 'S5', gender_id: '3' };
    render(<PeopleForm resource={resource} row={row} onClose={onClose} onSaved={() => {}} />);
    expect(await screen.findByText(/Lookup down/)).toBeInTheDocument();
    expect(screen.getByDisplayValue('S5')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Number/), { target: { value: 'S6' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText(/Duplicate again/)).toBeInTheDocument();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalled();
    const link = document.createElement('a');
    link.href = '#x';
    document.body.appendChild(link);
    confirm.mockReturnValueOnce(false);
    const event = new MouseEvent('click', { bubbles: true, cancelable: true });
    link.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    const unload = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(unload);
    expect(unload.defaultPrevented).toBe(true);
    link.remove();
  });
});

describe('PeopleApp workspace', () => {
  const rows: Row[] = [
    { id: '1', version: '1', display_name: 'Asha', student_number: 'S1', primary_email: 'a@x.test', student_status: 'ACTIVE', actions: ['change', 'transition'], masked_fields: ['notes'] },
    { id: '2', version: '1', agency_name: 'Agency', is_active: false, actions: ['transition'], masked_fields: [] },
  ];
  const meta = (resources = [{ path: 'students', title: 'Students', can_create: true, fields: [] as Field[] }, { path: 'employee-addresses', title: 'Employee Addresss', can_create: false, fields: [] as Field[] }, { path: 'agencies', title: 'External Agencys', can_create: false, fields: [] as Field[] }]) =>
    http.get(`${base}/people/metadata/`, () => HttpResponse.json({ resources }));
  const mount = (path = '/people/students') => render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/people/*" element={<PeopleApp />} /></Routes>
    </MemoryRouter>,
  );

  it('searches, shows details, and changes status with a reason', async () => {
    let status: unknown;
    server.use(
      meta(),
      http.get(`${base}/people/students/`, () => HttpResponse.json({ count: 2, results: rows })),
      http.post(`${base}/people/students/1/status/`, async ({ request }) => { status = await request.json(); return HttpResponse.json(rows[0]); }),
    );
    mount();
    expect(await screen.findByText('Asha')).toBeInTheDocument();
    expect(screen.getByText('Employee Addresses')).toBeInTheDocument();
    expect(screen.getByText('External Agencies')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Search by name/), { target: { value: 'ash' } });
    fireEvent.click(screen.getAllByRole('button', { name: 'Details' })[0]);
    const detail = await screen.findByRole('dialog');
    expect(within(detail).getByText(/Some confidential fields are hidden/)).toBeInTheDocument();
    fireEvent.click(within(detail).getByRole('button', { name: 'Close' }));
    fireEvent.click((await screen.findAllByRole('button', { name: 'Change status' }))[0]);
    const confirm = await screen.findByRole('dialog');
    fireEvent.mouseDown(within(confirm).getByRole('combobox'));
    fireEvent.click(await screen.findByRole('option', { name: 'SUSPENDED' }));
    fireEvent.change(within(confirm).getByLabelText(/Reason/), { target: { value: 'Policy' } });
    fireEvent.click(within(confirm).getByRole('button', { name: 'Confirm' }));
    await waitFor(() => expect(status).toEqual({ reason: 'Policy', status: 'SUSPENDED' }));
  });

  it('shows failures, empty scope and offline state', async () => {
    server.use(meta(), http.get(`${base}/people/students/`, () => HttpResponse.json({ error: { message: 'Scope denied' } }, { status: 403 })));
    mount();
    expect(await screen.findByText('Scope denied')).toBeInTheDocument();
    cleanup();
    getQueryClient().clear();
    server.use(meta([]));
    mount();
    expect(await screen.findByText(/No people resources are available/)).toBeInTheDocument();
    cleanup();
    getQueryClient().clear();
    server.use(http.get(`${base}/people/metadata/`, () => HttpResponse.json({ error: { message: 'Meta down' } }, { status: 500 })));
    mount();
    expect(await screen.findByText('Meta down')).toBeInTheDocument();
  });

  it('opens create and edit, and reports a failed status change', async () => {
    server.use(
      meta([{ path: 'students', title: 'Students', can_create: true, fields: [f('student_number', 'text', { label: 'Number', required: true })] }]),
      http.get(`${base}/people/students/`, () => HttpResponse.json({ count: 1, results: [rows[0]] })),
      http.post(`${base}/people/students/1/status/`, () => HttpResponse.json({ error: { message: 'Not allowed' } }, { status: 409 })),
    );
    mount();
    await screen.findByText('Asha');
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));
    expect(await screen.findByText('Create Students')).toBeInTheDocument();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    fireEvent.click(screen.getAllByRole('button', { name: 'Edit' })[0]);
    expect(await screen.findByText('Edit Students')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    fireEvent.click((await screen.findAllByRole('button', { name: 'Change status' }))[0]);
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/Reason/), { target: { value: 'x' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm' }));
    expect(await within(dialog).findAllByText('Not allowed')).not.toHaveLength(0);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
  });

  it('handles set-primary, activation and offline mode', async () => {
    server.use(
      meta([{ path: 'employee-addresses', title: 'Employee Addresses', can_create: false, fields: [] }]),
      http.get(`${base}/people/employee-addresses/`, () => HttpResponse.json({ count: 1, results: [{ id: '4', version: '1', is_primary: false, actions: ['transition'], masked_fields: [] }] })),
      http.post(`${base}/people/employee-addresses/4/set-primary/`, () => HttpResponse.json({})),
    );
    mount('/people/employee-addresses');
    fireEvent.click(await screen.findByRole('button', { name: 'Set primary' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/closed atomically/)).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText(/Reason/), { target: { value: 'ok' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    window.dispatchEvent(new Event('offline'));
    expect(await screen.findByText(/Offline\. Personal data is unavailable/)).toBeInTheDocument();
  });
});
