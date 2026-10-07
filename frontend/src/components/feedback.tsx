import { Alert, Box, Button, CircularProgress, Paper, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

export function PageHeader({
  overline,
  title,
  description,
  actions,
}: {
  overline: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      spacing={{ xs: 1.5, sm: 2 }}
      sx={{ justifyContent: 'space-between', alignItems: { xs: 'stretch', sm: 'flex-start' } }}
    >
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="overline" sx={{ color: 'text.secondary' }}>
          {overline}
        </Typography>
        <Typography component="h1" variant="h4" sx={{ overflowWrap: 'break-word', textWrap: 'balance' }}>
          {title}
        </Typography>
        {description && (
          <Typography color="text.secondary" sx={{ mt: 0.5, maxWidth: 720 }}>
            {description}
          </Typography>
        )}
      </Box>
      {actions && (
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ flexShrink: 0, alignItems: { xs: 'stretch', sm: 'center' } }}
        >
          {actions}
        </Stack>
      )}
    </Stack>
  );
}

export function ErrorAlert({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Alert severity="error" action={onRetry ? <Button onClick={onRetry}>Retry</Button> : undefined}>
      {message}
    </Alert>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <Paper sx={{ p: { xs: 3, sm: 4 }, textAlign: 'center', bgcolor: '#fafbfd' }}>
      <Typography variant="h6">{title}</Typography>
      {hint && (
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          {hint}
        </Typography>
      )}
    </Paper>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <Stack direction="row" spacing={2} sx={{ alignItems: 'center', justifyContent: 'center', p: 3 }} aria-label={label}>
      <CircularProgress size={20} />
      <Typography color="text.secondary">{label}</Typography>
    </Stack>
  );
}
