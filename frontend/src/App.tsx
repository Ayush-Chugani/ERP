import { OrganisationsPage } from './pages/admin/OrganisationsPage';
import { OwnerDashboardPage } from './pages/admin/OwnerDashboardPage';
import { useState } from 'react';
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router';
import { CssBaseline, CircularProgress, Box, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, can, useAuth } from './api/auth';
import { ApiError } from './api/client';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Shell } from './layout/Shell';
import { AccountPage } from './pages/AccountPage';
import { AttendancePage } from './pages/AttendancePage';
import { FeedbackPage } from './pages/FeedbackPage';
import { MarksPage } from './pages/MarksPage';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { ResourceDetailPage } from './pages/ResourceDetailPage';
import { ResourceListPage } from './pages/ResourceListPage';
import { AuditPage } from './pages/admin/AuditPage';
import { JobsPage } from './pages/admin/JobsPage';
import { RolesPage } from './pages/admin/RolesPage';
import { UsersPage } from './pages/admin/UsersPage';
import { theme } from './theme';

export const makeClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false,
        retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
      },
    },
  });

function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Box sx={{ display: 'grid', placeItems: 'center', minHeight: '100vh' }}><CircularProgress aria-label="Loading" /></Box>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (user.must_change_password && location.pathname !== '/account') return <Navigate to="/account" replace />;
  return <Outlet />;
}

/** Client-side guard mirroring the nav item's visibility; the server still enforces every permission. */
export function RequirePermission({ permission, superuser }: { permission?: string; superuser?: boolean }) {
  const { user } = useAuth();
  const allowed = superuser ? !!user?.is_superuser : !!permission && can(user, permission);
  return allowed ? <Outlet /> : <Navigate to="/" replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route index element={<DashboardPage />} />
          <Route path="w/:key" element={<WorkspacePage />} />
          <Route path="r/:module/:slug" element={<ResourceListPage />} />
          <Route path="r/:module/:slug/:id" element={<ResourceDetailPage />} />
          <Route path="attendance/sessions/:id" element={<AttendancePage />} />
          <Route path="assessments/events/:id/marks" element={<MarksPage />} />
          <Route path="feedback" element={<FeedbackPage />} />
          <Route path="account" element={<AccountPage />} />
          <Route element={<RequirePermission superuser />}>
            <Route path="owner" element={<OwnerDashboardPage />} />
          </Route>
          <Route element={<RequirePermission permission="IAM.USERS.READ" />}>
            <Route path="admin/organisations" element={<OrganisationsPage />} />
            <Route path="admin/users" element={<UsersPage />} />
          </Route>
          <Route element={<RequirePermission permission="IAM.ROLES.READ" />}>
            <Route path="admin/roles" element={<RolesPage />} />
          </Route>
          <Route element={<RequirePermission permission="AUDIT.AUDIT_LOG.READ" />}>
            <Route path="admin/audit" element={<AuditPage />} />
          </Route>
          <Route element={<RequirePermission permission="IAM.OPERATIONS.CONFIGURE" />}>
            <Route path="admin/jobs" element={<JobsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}

export function App() {
  const [client] = useState(makeClient);
  return (
    <ErrorBoundary>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <QueryClientProvider client={client}>
          <BrowserRouter>
            <AuthProvider>
              <AppRoutes />
            </AuthProvider>
          </BrowserRouter>
        </QueryClientProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
