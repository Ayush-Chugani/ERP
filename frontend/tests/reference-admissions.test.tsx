import React from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

vi.mock('../src/features/auth/session', () => ({
  authenticatedFetch: (path: string, init?: RequestInit) => fetch('http://localhost/api/v1' + path, init),
}));

import { AdmissionsApp } from '../src/features/admission/AdmissionsApp';
import { ReferencePage } from '../src/features/common-reference/ReferencePage';
import { ReferenceRoutes } from '../src/features/common-reference/ReferenceRoutes';
import { ParentSelect } from '../src/features/common-reference/ParentSelect';
import { label, maintainer, payload, permitted, resources } from '../src/features/common-reference/resources';
import { allPages, idempotencyKey } from '../src/lib/api-client';
import { allPages as timetablePages, command } from '../src/features/timetable/api';
import { AuthProvider } from '../src/lib/auth-context';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  cleanup();
  server.resetHandlers();
  vi.restoreAllMocks();
});
const base = 'http://localhost/api/v1';
const superuser = { is_superuser: true, permissions: [] as string[] };

describe('AdmissionsApp', () => {
  const at = (path: string) => (
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/admissions/*" element={<AdmissionsApp />} /></Routes>
    </MemoryRouter>
  );
  it('shows the overview with links to each workspace', () => {
    render(at('/admissions'));
    expect(screen.getByText('Admissions and enrolment')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Open/ })).toHaveLength(4);
    cleanup();
    render(at('/admissions/unknown/deep'));
    expect(screen.getByText('Admissions and enrolment')).toBeInTheDocument();
  });
  it('lists applications, pages and searches', async () => {
    const urls: string[] = [];
    server.use(http.get(`${base}/admissions/applications/`, ({ request }) => {
      urls.push(new URL(request.url).search);
      return HttpResponse.json({
        count: 60,
        results: [
          { application_id: '5', application_number: 'APP-1', programme_name: 'B.E. CSE', application_date: '2026-01-02', eligibility_status: 'ELIGIBLE', application_status: 'ADMITTED' },
          { display_name: 'Named', reason: 'why' },
          {},
        ],
      });
    }));
    render(at('/admissions/applications'));
    expect(await screen.findByText('APP-1')).toBeInTheDocument();
    expect(screen.getByText(/B.E. CSE · 2026-01-02 · ELIGIBLE/)).toBeInTheDocument();
    expect(screen.getByText('ADMITTED')).toBeInTheDocument();
    expect(screen.getByText('Named')).toBeInTheDocument();
    expect(screen.getByText('Record')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Search applications/), { target: { value: 'asha' } });
    await waitFor(() => expect(urls.some((u) => u.includes('search=asha'))).toBe(true));
    fireEvent.change(screen.getByLabelText(/Search applications/), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /next page/i }));
    await waitFor(() => expect(urls.some((u) => u.includes('page=2'))).toBe(true));
    fireEvent.mouseDown(screen.getByRole('combobox', { name: /rows per page/i }));
    fireEvent.click(await screen.findByRole('option', { name: '50' }));
    await waitFor(() => expect(urls.some((u) => u.includes('page_size=50'))).toBe(true));
  });
  it('shows an empty state and retryable errors', async () => {
    let fail = true;
    server.use(http.get(`${base}/admissions/history/`, () => (fail
      ? HttpResponse.json({ error: { message: 'Denied', details: { why: 'scope' } } }, { status: 403 })
      : HttpResponse.json({ count: 0, results: [] }))));
    render(at('/admissions/history'));
    expect(await screen.findByText(/Denied/)).toBeInTheDocument();
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('No records match these filters.')).toBeInTheDocument();
    cleanup();
    server.use(http.get(`${base}/admissions/enrolments/`, () => HttpResponse.error()));
    render(at('/admissions/enrolments'));
    expect(await screen.findByText(/Unable to reach the server/)).toBeInTheDocument();
  });
});

describe('common reference helpers', () => {
  it('evaluates permissions, labels and payloads', () => {
    const [countries, states, , , religions, , castes, , , documents] = resources;
    expect(permitted(superuser as never, countries, 'add')).toBe(true);
    const viewer = { is_superuser: false, permissions: ['common_reference.view_country'] };
    expect(permitted(viewer as never, countries, 'view')).toBe(true);
    expect(permitted(viewer as never, countries, 'add')).toBe(false);
    const writer = { is_superuser: false, permissions: ['common_reference.add_country', 'common_reference.maintain_reference'] };
    expect(permitted(writer as never, countries, 'add')).toBe(true);
    expect(maintainer(writer as never)).toBe(true);
    expect(maintainer(viewer as never)).toBe(false);
    expect(label(countries, { country_name: 'India', country_id: 1 })).toBe('India');
    expect(label(countries, { country_id: 9 })).toBe('9');
    expect(payload(states, { state_code: 'KA', state_name: 'Karnataka', country_id: '2' })).toEqual({ state_code: 'KA', state_name: 'Karnataka', country_id: 2 });
    expect(payload(states, { state_code: 'KA', state_name: 'K' }).country_id).toBeNull();
    expect(payload(religions, { religion_code: ' ', religion_name: 'R' }).religion_code).toBeNull();
    expect(payload(documents, { document_code: 'D', document_name: 'N', requires_verification: true }).requires_verification).toBe(true);
    expect(payload(castes, {}).social_category_id).toBeNull();
  });
  it('pages through allPages helpers and reports oversized collections', async () => {
    server.use(http.get(`${base}/things/`, ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get('page'));
      return HttpResponse.json({ count: 3, next: page < 2 ? 'next' : null, results: [{ n: page }] });
    }), http.get(`${base}/timetable/rooms/`, ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get('page'));
      return HttpResponse.json({ count: 3, next: page < 2 ? 'next' : null, results: [{ n: page }] });
    }), http.get(`${base}/timetable/endless/`, () => HttpResponse.json({ count: 1, next: 'more', results: [] })),
    http.get(`${base}/endless/`, () => HttpResponse.json({ count: 1, next: 'more', results: [] })),
    http.post(`${base}/timetable/commands/publish/`, async ({ request }) => HttpResponse.json({ id: '1', version: 2, resource: request.headers.get('idempotency-key') })));
    expect(await allPages('/things/')).toEqual([{ n: 1 }, { n: 2 }]);
    expect(await timetablePages('rooms/')).toEqual([{ n: 1 }, { n: 2 }]);
    await expect(allPages('/endless/?x=1', 2)).rejects.toThrow(/Too many records/);
    await expect(timetablePages('endless/?x=1')).rejects.toThrow(/Too many records/);
    expect((await command('publish', { a: 1 }, 'key-1')).resource).toBe('key-1');
    expect(idempotencyKey()).toMatch(/[0-9a-f-]{20,}/);
    const original = globalThis.crypto;
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: {} });
    expect(idempotencyKey()).toMatch(/^\d+-\d+$/);
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: original });
  });
});

describe('ReferencePage', () => {
  const countries = resources[0];
  const states = resources[1];
  const listCountries = (rows = [{ country_id: 1, country_name: 'India', iso_code: 'IN', is_active: true, effective_active: true }]) =>
    http.get(`${base}/reference/countries/`, () => HttpResponse.json({ count: rows.length, results: rows }));

  it('lists records and filters, with a read-only viewer', async () => {
    let query = '';
    server.use(http.get(`${base}/reference/countries/`, ({ request }) => {
      query = new URL(request.url).search;
      return HttpResponse.json({ count: 1, results: [{ country_id: 1, country_name: 'India', iso_code: 'IN', is_active: true, effective_active: true }] });
    }));
    render(<ReferencePage resource={countries} user={{ is_superuser: false, permissions: ['common_reference.view_country'] } as never} />);
    expect(await screen.findByText('India')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Add/ })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Search countries/), { target: { value: 'ind' } });
    await waitFor(() => expect(query).toContain('search=ind'));
    fireEvent.mouseDown(screen.getByRole('combobox', { name: /Order by/ }));
    fireEvent.click(await screen.findByRole('option', { name: /Country name \(descending\)/ }));
    await waitFor(() => expect(query).toContain('ordering=-country_name'));
  });

  it('creates, edits, deactivates and reports server failures as a maintainer', async () => {
    let created: unknown;
    server.use(
      listCountries(),
      http.post(`${base}/reference/countries/`, async ({ request }) => { created = await request.json(); return HttpResponse.json({ country_id: 2 }, { status: 201 }); }),
      http.get(`${base}/reference/countries/1/`, () => HttpResponse.json({ country_id: 1, country_name: 'India', iso_code: 'IN', is_active: true, effective_active: false })),
      http.patch(`${base}/reference/countries/1/`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        if ('is_active' in body) return HttpResponse.json({});
        return HttpResponse.json({ error: { message: 'Invalid', details: { iso_code: 'Taken', non_field_errors: 'Oops' } } }, { status: 400 });
      }),
    );
    render(<ReferencePage resource={countries} user={superuser as never} />);
    await screen.findByText('India');
    fireEvent.click(screen.getByRole('button', { name: 'Add record' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/ISO code/), { target: { value: 'FR' } });
    fireEvent.change(within(dialog).getByLabelText(/Country name/), { target: { value: 'France' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /Save record/ }));
    expect(await screen.findByText('Record saved.')).toBeInTheDocument();
    expect(created).toEqual({ iso_code: 'FR', country_name: 'France' });

    fireEvent.click(screen.getByRole('button', { name: /^Edit/ }));
    const edit = await screen.findByRole('dialog');
    expect(within(edit).getByText(/unavailable for new selections/)).toBeInTheDocument();
    fireEvent.change(within(edit).getByLabelText(/ISO code/), { target: { value: 'ZZ' } });
    fireEvent.click(within(edit).getByRole('button', { name: /Save record/ }));
    expect(await within(edit).findByText(/Invalid/)).toBeInTheDocument();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    fireEvent.click(within(edit).getByRole('button', { name: /Cancel|Close/ }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    fireEvent.click(await screen.findByRole('button', { name: /Deactivate/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Confirm deactivation/ }));
    expect(await screen.findByText('Active status updated.')).toBeInTheDocument();
  });

  it('reports list and detail failures', async () => {
    server.use(http.get(`${base}/reference/countries/`, () => HttpResponse.json({ error: { message: 'Down' } }, { status: 500 })));
    render(<ReferencePage resource={countries} user={superuser as never} />);
    expect(await screen.findByText('Down')).toBeInTheDocument();
    expect(screen.getByText('Records could not be loaded.')).toBeInTheDocument();
    server.use(listCountries(), http.get(`${base}/reference/countries/1/`, () => HttpResponse.json({ error: { message: 'Gone' } }, { status: 404 })));
    fireEvent.click(screen.getByRole('button', { name: 'Reload list' }));
    fireEvent.click(await screen.findByRole('button', { name: /^Edit/ }));
    expect(await screen.findByText('Gone')).toBeInTheDocument();
  });

  it('filters child resources by parent and offers parent selection', async () => {
    server.use(
      http.get(`${base}/reference/states/`, () => HttpResponse.json({ count: 1, results: [{ state_id: 2, state_name: 'Karnataka', state_code: 'KA', country_id: 1, parent_label: 'India', is_active: true, effective_active: true }] })),
      http.get(`${base}/reference/countries/`, () => HttpResponse.json({ count: 2, next: 'n', results: [{ country_id: 1, country_name: 'India', iso_code: 'IN', effective_active: true }] })),
    );
    render(<ReferencePage resource={states} user={superuser as never} />);
    expect(await screen.findByText('Karnataka')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Add record' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/State code/), { target: { value: 'KA' } });
    fireEvent.change(within(dialog).getByLabelText(/State name/), { target: { value: 'Karnataka' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /Save record/ }));
    expect(await within(dialog).findByText('Select a parent.')).toBeInTheDocument();
  });

  it('toggles uncategorized castes', async () => {
    let seen = '';
    server.use(http.get(`${base}/reference/castes/`, ({ request }) => { seen = new URL(request.url).search; return HttpResponse.json({ count: 0, results: [] }); }));
    render(<ReferencePage resource={resources[6]} user={superuser as never} />);
    fireEvent.click(await screen.findByLabelText('Uncategorized castes only'));
    await waitFor(() => expect(seen).toContain('uncategorized=true'));
  });
});

describe('ParentSelect', () => {
  it('searches, loads more, selects and retries', async () => {
    let fail = true;
    server.use(
      http.get(`${base}/reference/countries/5/`, () => HttpResponse.json({ country_id: 5, country_name: 'Chosen', effective_active: false })),
      http.get(`${base}/reference/countries/`, ({ request }) => {
        if (fail) return HttpResponse.json({ error: { message: 'Lookup failed' } }, { status: 500 });
        const page = new URL(request.url).searchParams.get('page');
        return HttpResponse.json({ results: [{ country_id: page === '2' ? 8 : 7, country_name: page === '2' ? 'Second' : 'First', effective_active: true }], next: page === '1' ? 'n' : null });
      }),
    );
    const onChange = vi.fn();
    render(<ParentSelect path="countries" value={5} onChange={onChange} title="Country" error="Needs one" />);
    expect(await screen.findByText('Lookup failed')).toBeInTheDocument();
    expect(screen.getByText('Needs one')).toBeInTheDocument();
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    fireEvent.click(await screen.findByRole('button', { name: /Load more country choices/ }));
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'sec' } });
    fireEvent.mouseDown(input);
    fireEvent.click(await screen.findByRole('option', { name: 'First' }));
    expect(onChange).toHaveBeenCalledWith(7);
    fireEvent.click(screen.getByLabelText('Clear'));
    expect(onChange).toHaveBeenCalledWith(null);
  });
});

describe('ReferenceRoutes', () => {
  const wrap = (user: unknown, path = '/reference') => {
    server.use(http.get(`${base}/auth/me/`, () => (user ? HttpResponse.json(user) : HttpResponse.json({}, { status: 401 }))));
    server.use(http.get(`${base}/reference/countries/`, () => HttpResponse.json({ count: 0, results: [] })));
    return render(
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes><Route path="/reference/*" element={<ReferenceRoutes />} /></Routes>
        </MemoryRouter>
      </AuthProvider>,
    );
  };
  it('asks anonymous users to sign in, warns when nothing is visible, and redirects to the first resource', async () => {
    wrap(null);
    expect(await screen.findByText(/Sign in to view reference data/)).toBeInTheDocument();
    cleanup();
    wrap({ user_id: 1, username: 'x', is_superuser: false, permissions: [] });
    expect(await screen.findByText(/No reference resources are visible/)).toBeInTheDocument();
    cleanup();
    wrap({ user_id: 1, username: 'x', is_superuser: true, permissions: [] }, '/reference/whatever');
    expect(await screen.findByRole('heading', { name: 'Countries' })).toBeInTheDocument();
  });
});
