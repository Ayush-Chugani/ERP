import React from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

vi.mock('../src/features/auth/session', () => ({ authenticatedFetch: (path: string, init?: RequestInit) => fetch('http://localhost/api/v1' + path, init), login: vi.fn(), logout: vi.fn(), refreshSession: async () => false }));
vi.mock('../src/features/identity-access/SupportBanner', () => ({ SupportBanner: () => null }));
vi.mock('../src/pwa/PwaStatus', () => ({ PwaStatus: () => null }));
vi.mock('../src/features/common-reference/ReferenceRoutes', () => ({ ReferenceRoutes: () => <p>stub:ReferenceRoutes</p> }));
vi.mock('../src/features/organization/OrganizationApp', () => ({ OrganizationApp: () => <p>stub:OrganizationApp</p> }));
vi.mock('../src/features/people/PeopleApp', () => ({ PeopleApp: () => <p>stub:PeopleApp</p> }));
vi.mock('../src/features/curriculum/CurriculumApp', () => ({ CurriculumApp: () => <p>stub:CurriculumApp</p> }));
vi.mock('../src/features/academic-calendar/CalendarApp', () => ({ CalendarApp: () => <p>stub:CalendarApp</p> }));
vi.mock('../src/features/timetable/TimetableApp', () => ({ TimetableApp: () => <p>stub:TimetableApp</p> }));
vi.mock('../src/features/registration/RegistrationApp', () => ({ RegistrationApp: () => <p>stub:RegistrationApp</p> }));
vi.mock('../src/features/attendance/AttendanceApp', () => ({ AttendanceApp: () => <p>stub:AttendanceApp</p> }));
vi.mock('../src/features/assessments/AssessmentApp', () => ({ AssessmentApp: () => <p>stub:AssessmentApp</p> }));
vi.mock('../src/features/feedback/FeedbackApp', () => ({ FeedbackApp: () => <p>stub:FeedbackApp</p> }));
vi.mock('../src/features/student-support/StudentSupportApp', () => ({ StudentSupportApp: () => <p>stub:StudentSupportApp</p> }));
vi.mock('../src/features/documents-exit/DocumentsExitApp', () => ({ DocumentsExitApp: () => <p>stub:DocumentsExitApp</p> }));
vi.mock('../src/features/communication/CommunicationApp', () => ({ CommunicationApp: () => <p>stub:CommunicationApp</p> }));
vi.mock('../src/features/identity-access/SecurityApp', () => ({ SecurityApp: () => <p>stub:SecurityApp</p> }));
vi.mock('../src/features/evidence/EvidenceApp', () => ({ EvidenceApp: () => <p>stub:EvidenceApp</p> }));
vi.mock('../src/features/awards/AwardApp', () => ({ AwardApp: () => <p>stub:AwardApp</p> }));
vi.mock('../src/features/professional-contributions/ContributionApp', () => ({ ContributionApp: () => <p>stub:ContributionApp</p> }));
vi.mock('../src/features/professional-memberships/MembershipApp', () => ({ MembershipApp: () => <p>stub:MembershipApp</p> }));
vi.mock('../src/features/extracurricular/ExtracurricularApp', () => ({ ExtracurricularApp: () => <p>stub:ExtracurricularApp</p> }));
vi.mock('../src/features/cocurricular/CocurricularApp', () => ({ CocurricularApp: () => <p>stub:CocurricularApp</p> }));
vi.mock('../src/features/consultancy/ConsultancyApp', () => ({ ConsultancyApp: () => <p>stub:ConsultancyApp</p> }));
vi.mock('../src/features/funded-projects/FundedProjectsApp', () => ({ FundedProjectsApp: () => <p>stub:FundedProjectsApp</p> }));
vi.mock('../src/features/research-proposals/ResearchProposalsApp', () => ({ ResearchProposalsApp: () => <p>stub:ResearchProposalsApp</p> }));
vi.mock('../src/features/faculty-internships/InternshipsApp', () => ({ InternshipsApp: () => <p>stub:InternshipsApp</p> }));
vi.mock('../src/features/conferences/ConferencesApp', () => ({ ConferencesApp: () => <p>stub:ConferencesApp</p> }));
vi.mock('../src/features/admission/AdmissionsApp', () => ({ AdmissionsApp: () => <p>stub:AdmissionsApp</p> }));

import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../src/lib/auth-context';
import { getQueryClient } from '../src/lib/query';
import { AppRouter } from '../src/app/router';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterAll(() => server.close());
afterEach(() => { cleanup(); server.resetHandlers(); });

const ROUTES: Array<[string, string]> = [
  ['/reference', 'stub:ReferenceRoutes'],
  ['/organization', 'stub:OrganizationApp'],
  ['/people', 'stub:PeopleApp'],
  ['/curriculum', 'stub:CurriculumApp'],
  ['/calendar', 'stub:CalendarApp'],
  ['/timetable', 'stub:TimetableApp'],
  ['/registration', 'stub:RegistrationApp'],
  ['/attendance', 'stub:AttendanceApp'],
  ['/assessments', 'stub:AssessmentApp'],
  ['/admissions', 'stub:AdmissionsApp'],
  ['/feedback', 'stub:FeedbackApp'],
  ['/support', 'stub:StudentSupportApp'],
  ['/documents', 'stub:DocumentsExitApp'],
  ['/communication', 'stub:CommunicationApp'],
  ['/security', 'stub:SecurityApp'],
  ['/evidence', 'stub:EvidenceApp'],
  ['/awards', 'stub:AwardApp'],
  ['/professional-contributions', 'stub:ContributionApp'],
  ['/professional-memberships', 'stub:MembershipApp'],
  ['/extracurricular', 'stub:ExtracurricularApp'],
  ['/cocurricular', 'stub:CocurricularApp'],
  ['/consultancy', 'stub:ConsultancyApp'],
  ['/funded-projects', 'stub:FundedProjectsApp'],
  ['/research-proposals', 'stub:ResearchProposalsApp'],
  ['/faculty-internships', 'stub:InternshipsApp'],
  ['/conferences', 'stub:ConferencesApp'],
];

describe('route table', () => {
  it.each(ROUTES)('mounts %s for a superuser', async (path, stub) => {
    server.use(http.get('http://localhost/api/v1/auth/me/', () => HttpResponse.json({ user_id: 1, username: 'admin', permissions: [], is_superuser: true, groups: [] })));
    render(<QueryClientProvider client={getQueryClient()}><AuthProvider><MemoryRouter initialEntries={[path + '/x']}><AppRouter /></MemoryRouter></AuthProvider></QueryClientProvider>);
    expect(await screen.findByText(stub)).toBeInTheDocument();
  });
});
