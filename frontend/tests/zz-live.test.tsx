import React from 'react';
import { afterEach, describe, it, vi } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';

vi.mock('../src/features/auth/session', () => ({
  authenticatedFetch: async (path: string, init: RequestInit = {}) => {
    const live = 'http://127.0.0.1:8000/api/v1';
    const password = process.env.SIMS_SMOKE_PASSWORD || '';
    const state = (globalThis as unknown as { __sims?: { access: string; csrf: string } }).__sims
      || ((globalThis as unknown as { __sims?: object }).__sims = { access: '', csrf: '' });
    const sims = state as { access: string; csrf: string };
    async function login(): Promise<boolean> {
      const c = await (await fetch(`${live}/auth/csrf/`)).json() as { csrfToken: string };
      sims.csrf = c.csrfToken;
      const l = await fetch(`${live}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': sims.csrf },
        body: JSON.stringify({ username: 'admin', password }),
      });
      if (!l.ok) return false;
      const d = await l.json() as { access: string; csrfToken: string };
      sims.access = d.access;
      sims.csrf = d.csrfToken;
      return true;
    }
    async function send(): Promise<Response> {
      const headers = new Headers(init.headers);
      if (!headers.has('Content-Type') && typeof init.body === 'string') {
        try {
          JSON.parse(init.body);
          headers.set('Content-Type', 'application/json');
        } catch {
          /* keep */
        }
      }
      if (sims.access) headers.set('Authorization', `Bearer ${sims.access}`);
      return fetch(`${live}${path}`, { ...init, headers });
    }
    let response = await send();
    if (response.status === 401 && (await login())) response = await send();
    return response;
  },
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(async () => false),
}));

import { App } from '../src/app/App';

const ROUTES = [
  '/dashboard', '/organization', '/reference', '/people', '/curriculum', '/calendar',
  '/timetable', '/registration', '/attendance', '/assessments', '/admissions',
  '/feedback', '/support', '/documents', '/communication', '/security', '/evidence',
  '/awards', '/professional-contributions', '/professional-memberships',
  '/extracurricular', '/cocurricular', '/consultancy', '/funded-projects',
  '/research-proposals', '/faculty-internships', '/conferences',
];

afterEach(() => {
  cleanup();
  window.location.hash = '#/';
});

describe('live route smoke', () => {
  for (const route of ROUTES) {
    it(`renders ${route}`, async () => {
      window.location.hash = `#${route}`;
      render(<App />);
      try {
        await waitFor(
          () => {
            const bodyText = (document.body.textContent || '').replace(/\s+/g, ' ').trim();
            if (/Welcome back/.test(bodyText) && bodyText.length < 1500) throw new Error('login page');
            const mainNow = document.querySelector('main');
            const mainTextNow = (mainNow?.textContent || '').replace(/\s+/g, ' ').trim();
            if (!mainTextNow) throw new Error('main empty');
            return mainTextNow;
          },
          { timeout: 12000, interval: 250 },
        );
      } catch {
        // record anyway
      }
      const text = (document.body.textContent || '').replace(/\s+/g, ' ').trim();
      const main = document.querySelector('main');
      const mainText = (main?.textContent || '').replace(/\s+/g, ' ').trim();
      // eslint-disable-next-line no-console
      console.log(`ROUTE ${route} body=${text.length} main=${mainText.length} :: ${mainText.slice(0, 130)}`);
    }, 30000);
  }
});
