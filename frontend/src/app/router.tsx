import { Suspense, lazy, type ReactElement } from 'react';
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Alert, Box, Button, LinearProgress, Stack, Typography } from '@mui/material';
import { useAuth } from '../lib/auth-context';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { AppShell } from './layout';
import { NAV_ITEMS, visibleNav } from './navigation';
import { PasswordChange } from '../features/identity-access/PasswordChange';

// Lazy feature routes — one HashRouter at main.tsx level; no nested routers.
const ReferenceRoutes = lazy(() => import('../features/common-reference/ReferenceRoutes').then((m) => ({ default: m.ReferenceRoutes })));
const OrganizationApp = lazy(() => import('../features/organization/OrganizationApp').then((m) => ({ default: m.OrganizationApp })));
const PeopleApp = lazy(() => import('../features/people/PeopleApp').then((m) => ({ default: m.PeopleApp })));
const CurriculumApp = lazy(() => import('../features/curriculum/CurriculumApp').then((m) => ({ default: m.CurriculumApp })));
const CalendarApp = lazy(() => import('../features/academic-calendar/CalendarApp').then((m) => ({ default: m.CalendarApp })));
const TimetableApp = lazy(() => import('../features/timetable/TimetableApp').then((m) => ({ default: m.TimetableApp })));
const RegistrationApp = lazy(() => import('../features/registration/RegistrationApp').then((m) => ({ default: m.RegistrationApp })));
const AttendanceApp = lazy(() => import('../features/attendance/AttendanceApp').then((m) => ({ default: m.AttendanceApp })));
const AssessmentApp = lazy(() => import('../features/assessments/AssessmentApp').then((m) => ({ default: m.AssessmentApp })));
const FeedbackApp = lazy(() => import('../features/feedback/FeedbackApp').then((m) => ({ default: m.FeedbackApp })));
const StudentSupportApp = lazy(() => import('../features/student-support/StudentSupportApp').then((m) => ({ default: m.StudentSupportApp })));
const DocumentsExitApp = lazy(() => import('../features/documents-exit/DocumentsExitApp').then((m) => ({ default: m.DocumentsExitApp })));
const CommunicationApp = lazy(() => import('../features/communication/CommunicationApp').then((m) => ({ default: m.CommunicationApp })));
const SecurityApp = lazy(() => import('../features/identity-access/SecurityApp').then((m) => ({ default: m.SecurityApp })));
const EvidenceApp = lazy(() => import('../features/evidence/EvidenceApp').then((m) => ({ default: m.EvidenceApp })));
const AwardApp = lazy(() => import('../features/awards/AwardApp').then((m) => ({ default: m.AwardApp })));
const ContributionApp = lazy(() => import('../features/professional-contributions/ContributionApp').then((m) => ({ default: m.ContributionApp })));
const MembershipApp = lazy(() => import('../features/professional-memberships/MembershipApp').then((m) => ({ default: m.MembershipApp })));
const ExtracurricularApp = lazy(() => import('../features/extracurricular/ExtracurricularApp').then((m) => ({ default: m.ExtracurricularApp })));
const CocurricularApp = lazy(() => import('../features/cocurricular/CocurricularApp').then((m) => ({ default: m.CocurricularApp })));
const ConsultancyApp = lazy(() => import('../features/consultancy/ConsultancyApp').then((m) => ({ default: m.ConsultancyApp })));
const FundedProjectsApp = lazy(() => import('../features/funded-projects/FundedProjectsApp').then((m) => ({ default: m.FundedProjectsApp })));
const ResearchProposalsApp = lazy(() => import('../features/research-proposals/ResearchProposalsApp').then((m) => ({ default: m.ResearchProposalsApp })));
const InternshipsApp = lazy(() => import('../features/faculty-internships/InternshipsApp').then((m) => ({ default: m.InternshipsApp })));
const ConferencesApp = lazy(() => import('../features/conferences/ConferencesApp').then((m) => ({ default: m.ConferencesApp })));
const AdmissionsApp = lazy(() => import('../features/admission/AdmissionsApp').then((m) => ({ default: m.AdmissionsApp })));

function Loading() {
  return (
    <Box sx={{ p: 4 }}>
      <LinearProgress aria-label="Loading workspace view" />
    </Box>
  );
}

function RequireAuth({ children }: { children: ReactElement }) {
  const { user, checking } = useAuth();
  const location = useLocation();
  if (checking) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if ((user as { must_change_password?: boolean }).must_change_password && location.pathname !== '/dashboard') {
    return (
      <AppShell>
        <PasswordChange onChanged={() => window.location.reload()} />
      </AppShell>
    );
  }
  const entry = NAV_ITEMS.find((item) => location.pathname === item.path || location.pathname.startsWith(`${item.path}/`));
  if (entry && !visibleNav(user).includes(entry)) return <NoAccess title={entry.title} />;
  return children;
}

function NoAccess({ title }: { title: string }) {
  return (
    <Stack spacing={2} sx={{ maxWidth: 560 }}>
      <Typography component="h1" variant="h4">Access restricted</Typography>
      <Alert severity="info">Your role does not include {title}. If you need it, ask an administrator to update your access.</Alert>
      <Box>
        <Button component={Link} to="/dashboard" variant="contained">Back to dashboard</Button>
      </Box>
    </Stack>
  );
}

/** Injects the authenticated user into legacy feature apps that take a `user` prop. */
function UserRoute({ Component }: { Component: (props: { user: never }) => ReactElement }) {
  const { user, checking } = useAuth();
  if (checking) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return <Component user={user as never} />;
}

export function AppRouter() {
  const { user, checking } = useAuth();
  if (checking) return <Loading />;
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  return (
    <AppShell>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<RequireAuth><DashboardPage /></RequireAuth>} />
          <Route path="/reference/*" element={<RequireAuth><ReferenceRoutes /></RequireAuth>} />
          <Route path="/organization/*" element={<RequireAuth><OrganizationApp /></RequireAuth>} />
          <Route path="/people/*" element={<RequireAuth><PeopleApp /></RequireAuth>} />
          <Route path="/curriculum/*" element={<RequireAuth><CurriculumApp /></RequireAuth>} />
          <Route path="/calendar/*" element={<RequireAuth><CalendarApp /></RequireAuth>} />
          <Route path="/timetable/*" element={<RequireAuth><UserRoute Component={TimetableApp as unknown as (props: { user: never }) => ReactElement} /></RequireAuth>} />
          <Route path="/registration/*" element={<RequireAuth><UserRoute Component={RegistrationApp as unknown as (props: { user: never }) => ReactElement} /></RequireAuth>} />
          <Route path="/attendance/*" element={<RequireAuth><UserRoute Component={AttendanceApp as unknown as (props: { user: never }) => ReactElement} /></RequireAuth>} />
          <Route path="/assessments/*" element={<RequireAuth><UserRoute Component={AssessmentApp as unknown as (props: { user: never }) => ReactElement} /></RequireAuth>} />
          <Route path="/admissions/*" element={<RequireAuth><AdmissionsApp /></RequireAuth>} />
          <Route path="/feedback/*" element={<RequireAuth><UserRoute Component={FeedbackApp as unknown as (props: { user: never }) => ReactElement} /></RequireAuth>} />
          <Route path="/support/*" element={<RequireAuth><UserRoute Component={StudentSupportApp as unknown as (props: { user: never }) => ReactElement} /></RequireAuth>} />
          <Route path="/documents/*" element={<RequireAuth><UserRoute Component={DocumentsExitApp as unknown as (props: { user: never }) => ReactElement} /></RequireAuth>} />
          <Route path="/communication/*" element={<RequireAuth><UserRoute Component={CommunicationApp as unknown as (props: { user: never }) => ReactElement} /></RequireAuth>} />
          <Route path="/security/*" element={<RequireAuth><SecurityApp /></RequireAuth>} />
          <Route path="/evidence/*" element={<RequireAuth><EvidenceApp /></RequireAuth>} />
          <Route path="/awards/*" element={<RequireAuth><AwardApp /></RequireAuth>} />
          <Route path="/professional-contributions/*" element={<RequireAuth><ContributionApp /></RequireAuth>} />
          <Route path="/professional-memberships/*" element={<RequireAuth><MembershipApp /></RequireAuth>} />
          <Route path="/extracurricular/*" element={<RequireAuth><ExtracurricularApp /></RequireAuth>} />
          <Route path="/cocurricular/*" element={<RequireAuth><CocurricularApp /></RequireAuth>} />
          <Route path="/consultancy/*" element={<RequireAuth><ConsultancyApp /></RequireAuth>} />
          <Route path="/funded-projects/*" element={<RequireAuth><FundedProjectsApp /></RequireAuth>} />
          <Route path="/research-proposals/*" element={<RequireAuth><ResearchProposalsApp /></RequireAuth>} />
          <Route path="/faculty-internships/*" element={<RequireAuth><InternshipsApp /></RequireAuth>} />
          <Route path="/conferences/*" element={<RequireAuth><ConferencesApp /></RequireAuth>} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
