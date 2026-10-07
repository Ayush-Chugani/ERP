import { HashRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { AuthProvider } from '../lib/auth-context';
import { getQueryClient } from '../lib/query';
import { theme } from './theme';
import { AppRouter } from './router';

/**
 * Production app shell wiring.
 * - Single HashRouter at the root (static hosting safe; no nested routers)
 * - Single shared QueryClient (was: one per feature mount)
 * - AuthProvider restores /auth/me/ once; PWA + layout live inside AppShell
 * Backend is untouched — all calls go to same-origin /api/v1.
 */
export function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={getQueryClient()}>
        <AuthProvider>
          <HashRouter>
            <AppRouter />
          </HashRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
