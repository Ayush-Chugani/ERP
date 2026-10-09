import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { Box, Breadcrumbs, Link, Stack, Typography } from '@mui/material';
import NavigateNext from '@mui/icons-material/NavigateNext';
import type { Icon } from '../layout/navConfig';

export type Crumb = { label: string; to?: string };

/** Consistent page title block: breadcrumbs, icon tile, title, subtitle and primary actions. */
export function PageHeader({ title, subtitle, icon: IconCmp, crumbs, actions, chip }: {
  title: string; subtitle?: ReactNode; icon?: Icon; crumbs?: Crumb[]; actions?: ReactNode; chip?: ReactNode;
}) {
  return (
    <Stack spacing={1.5} sx={{ mb: 3 }}>
      {crumbs && crumbs.length > 0 && (
        <Breadcrumbs separator={<NavigateNext fontSize="small" />} aria-label="Breadcrumb">
          {crumbs.map((c, i) =>
            c.to && i < crumbs.length - 1 ? (
              <Link key={c.label} component={RouterLink} to={c.to} underline="hover" color="text.secondary" variant="body2">{c.label}</Link>
            ) : (
              <Typography key={c.label} variant="body2" color="text.primary" sx={{ fontWeight: 600 }}>{c.label}</Typography>
            ),
          )}
        </Breadcrumbs>
      )}
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ alignItems: { md: 'center' }, justifyContent: 'space-between' }}>
        <Stack direction="row" spacing={2} sx={{ alignItems: 'center', minWidth: 0 }}>
          {IconCmp && (
            <Box sx={{ width: 48, height: 48, borderRadius: 3, display: 'grid', placeItems: 'center', flexShrink: 0,
              bgcolor: 'action.selected', color: 'primary.main' }}>
              <IconCmp />
            </Box>
          )}
          <Box sx={{ minWidth: 0 }}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <Typography variant="h4" component="h1" sx={{ overflowWrap: 'anywhere' }}>{title}</Typography>
              {chip}
            </Stack>
            {subtitle && <Typography color="text.secondary" variant="body2" component="div">{subtitle}</Typography>}
          </Box>
        </Stack>
        {actions && <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>{actions}</Stack>}
      </Stack>
    </Stack>
  );
}
