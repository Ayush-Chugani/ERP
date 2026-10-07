import { useEffect, useState } from 'react';
import { Alert, Box, Button, Dialog, Stack, Typography } from '@mui/material';
import { clearOfflineCopy, currentOfflineCopy, subscribeOffline } from './offline';

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

/**
 * PWA status surface: offline gate, update prompt, install prompt.
 * Fixed vs previous version: no 1s re-render interval; expiry-driven timer only.
 */
export function PwaStatus({ userId }: { userId?: number }) {
  const [copyTick, setCopyTick] = useState(0);
  const copy = currentOfflineCopy(userId);
  const [offline, setOffline] = useState(
    typeof navigator !== 'undefined' ? !navigator.onLine : false,
  );
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);
  const [install, setInstall] = useState<InstallEvent | null>(null);
  const [error, setError] = useState('');

  useEffect(() => subscribeOffline(() => setCopyTick((n) => n + 1)), []);

  // Re-render once when the saved copy expires so the offline dialog clears itself.
  useEffect(() => {
    if (!copy) return;
    const ms = Date.parse(copy.expires_at) - Date.now();
    if (!(ms > 0)) return;
    const timer = setTimeout(() => setCopyTick((n) => n + 1), Math.min(ms + 500, 5 * 60 * 1000 + 1000));
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copy?.expires_at, copyTick]);

  useEffect(() => {
    const online = () => setOffline(false);
    const off = () => setOffline(true);
    const offer = (e: Event) => {
      e.preventDefault();
      setInstall(e as InstallEvent);
    };
    const installed = () => setInstall(null);
    window.addEventListener('online', online);
    window.addEventListener('offline', off);
    window.addEventListener('beforeinstallprompt', offer);
    window.addEventListener('appinstalled', installed);
    let alive = true;
    if (import.meta.env.PROD && 'serviceWorker' in navigator) {
      navigator.serviceWorker
        .register('/sw.js', { updateViaCache: 'none' })
        .then((reg) => {
          const check = () => {
            if (alive && reg.waiting && navigator.serviceWorker.controller) setRegistration(reg);
          };
          check();
          reg.installing?.addEventListener('statechange', check);
          reg.addEventListener('updatefound', () =>
            reg.installing?.addEventListener('statechange', check),
          );
        })
        .catch(() => {
          if (alive) setError('Offline installation is unavailable. You can continue using the online application.');
        });
    }
    return () => {
      alive = false;
      window.removeEventListener('online', online);
      window.removeEventListener('offline', off);
      window.removeEventListener('beforeinstallprompt', offer);
      window.removeEventListener('appinstalled', installed);
    };
  }, []);

  function update(): void {
    if (!registration?.waiting || !window.confirm('Save your work in every SIMS tab first. Update and reload this tab now?')) return;
    navigator.serviceWorker.addEventListener('controllerchange', () => window.location.reload(), { once: true });
    registration.waiting.postMessage({ type: 'SKIP_WAITING' });
  }

  return (
    <Stack spacing={1}>
      <Dialog open={offline} fullScreen aria-label="Offline">
        <Box role="alert" sx={{ position: 'fixed', inset: 0, zIndex: 2000, bgcolor: 'background.default', display: 'grid', placeItems: 'center', p: 3 }}>
          <Stack spacing={2} sx={{ maxWidth: 460 }}>
            <Typography component="h1" variant="h4">You are offline</Typography>
            <Typography>
              Connect to the internet to load or save records. An explicitly saved read-only copy may be
              viewed below until it expires. Any open form stays in memory while this tab remains open.
            </Typography>
            {copy && (
              <Stack spacing={1}>
                <Typography variant="h6">Saved {copy.resource}</Typography>
                <Typography variant="caption">
                  Stale read-only copy from {new Date(copy.fetched_at).toLocaleString()}; expires{' '}
                  {new Date(copy.expires_at).toLocaleTimeString()}. Permission changes cannot be checked offline.
                </Typography>
                <Box sx={{ maxHeight: '45vh', overflow: 'auto' }}>
                  {copy.records.map((row, index) => (
                    <Typography key={index}>
                      {Object.entries(row).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`).join(' | ')}
                    </Typography>
                  ))}
                </Box>
                {copy.truncated && <Typography>First 100 records only.</Typography>}
                <Button onClick={clearOfflineCopy}>Clear offline copy</Button>
              </Stack>
            )}
            <Button variant="contained" onClick={() => { if (navigator.onLine) setOffline(false); }}>
              Check connection
            </Button>
          </Stack>
        </Box>
      </Dialog>
      {registration && (
        <Alert severity="info" action={<Button onClick={update}>Update</Button>}>
          A SIMS update is ready. Save your work before updating.
        </Alert>
      )}
      {install && (
        <Alert
          severity="info"
          action={
            <Button
              onClick={async () => {
                try {
                  await install.prompt();
                  await install.userChoice;
                  setInstall(null);
                } catch {
                  setError('Installation could not be started. Use your browser installation menu.');
                }
              }}
            >
              Install
            </Button>
          }
        >
          Install SIMS for quick access from your device.
        </Alert>
      )}
      {error && (
        <Alert severity="warning" onClose={() => setError('')}>
          {error}
        </Alert>
      )}
    </Stack>
  );
}
