import { OrganisationsPage } from './pages/admin/OrganisationsPage';
import { OwnerDashboardPage } from './pages/admin/OwnerDashboardPage';
import { useState } from 'react';
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router';
import { CssBaseline, CircularProgress, Box, ThemeProvider, Typography, Button } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './api/auth';
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

function NotFound() {
  return (
    <Box sx={{ textAlign: 'center', py: 8 }}>
      <Typography variant="h4">Page not found</Typography>
      <Typography color="text.secondary" sx={{ my: 2 }}>The page you are looking for does not exist, or you do not have access to it.</Typography>
      <Button href="/" variant="contained">Go to dashboard</Button>
    </Box>
  );
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
          <Route path="owner" element={<OwnerDashboardPage />} />
          <Route path="admin/organisations" element={<OrganisationsPage />} />
          <Route path="admin/users" element={<UsersPage />} />
          <Route path="admin/roles" element={<RolesPage />} />
          <Route path="admin/audit" element={<AuditPage />} />
          <Route path="admin/jobs" element={<JobsPage />} />
          <Route path="*" element={<NotFound />} />
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
