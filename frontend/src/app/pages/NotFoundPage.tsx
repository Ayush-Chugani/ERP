import { Button, Container, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <Container maxWidth="sm" sx={{ py: 8 }}>
      <Stack spacing={2} sx={{ textAlign: 'center' }}>
        <Typography variant="h4" component="h1">
          Page not found
        </Typography>
        <Typography color="text.secondary">
          The requested workspace view does not exist. Use the navigation or return to the dashboard.
        </Typography>
        <Button component={Link} to="/dashboard" variant="contained">
          Back to dashboard
        </Button>
      </Stack>
    </Container>
  );
}
