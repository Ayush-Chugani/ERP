import { Component, type ReactNode } from 'react';
import { Alert, Button, Container } from '@mui/material';

type State = { error: Error | null };

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error): void {
    // Visible log for production triage; backend detail stays server-side.
    console.error('[SIMS] UI error boundary', error);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <Container maxWidth="sm" sx={{ py: 8 }}>
          <Alert
            severity="error"
            action={
              <Button
                onClick={() => {
                  this.setState({ error: null });
                  window.location.hash = '#/dashboard';
                  window.location.reload();
                }}
              >
                Reload workspace
              </Button>
            }
          >
            Something went wrong loading this view. Your session is preserved — reload to continue.
          </Alert>
        </Container>
      );
    }
    return this.props.children;
  }
}
