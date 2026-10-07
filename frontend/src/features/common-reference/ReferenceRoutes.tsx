import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Alert, Box, LinearProgress } from '@mui/material';
import { resources, permitted } from './resources';
import { useAuth } from '../../lib/auth-context';

const ReferencePage = lazy(() => import('./ReferencePage').then((m) => ({ default: m.ReferencePage })));

/**
 * Mounted at `/reference/*`. Previous shell keyed ReferencePage by hash;
 * this uses real nested routes under the single root HashRouter.
 */
export function ReferenceRoutes() {
  const { user } = useAuth();
  if (!user) return <Alert severity="error">Sign in to view reference data.</Alert>;
  const visible = resources.filter((r) => permitted(user, r, 'view'));
  if (visible.length === 0) return <Alert severity="warning">No reference resources are visible for this account.</Alert>;
  return (
    <Suspense fallback={<Box sx={{ p: 4 }}><LinearProgress aria-label="Loading reference data" /></Box>}>
      <Routes>
        {visible.map((r) => (
          <Route key={r.path} path={r.path} element={<ReferencePage resource={r} user={user} />} />
        ))}
        <Route path="" element={<Navigate to={`/reference/${visible[0].path}`} replace />} />
        <Route path="*" element={<Navigate to={`/reference/${visible[0].path}`} replace />} />
      </Routes>
    </Suspense>
  );
}
