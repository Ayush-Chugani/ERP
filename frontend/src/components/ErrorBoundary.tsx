import { Component, type ReactNode } from 'react';
import { Alert, Button, Stack } from '@mui/material';

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <Stack spacing={2} sx={{ p: 4, maxWidth: 520, mx: 'auto' }}>
        <Alert severity="error">Something went wrong while displaying this page.</Alert>
        <Button variant="contained" onClick={() => location.reload()}>Reload</Button>
      </Stack>
    );
  }
}
