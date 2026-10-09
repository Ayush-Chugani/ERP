import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AiAssistant } from '../src/ai/AiAssistant';
import { setAccessToken } from '../src/api/client';
import { authRoutes, mockApi, renderApp } from './helpers';

beforeEach(() => setAccessToken('tok'));

describe('AI assistant', () => {
  it('renders nothing when the server reports AI as disabled', async () => {
    mockApi({ ...authRoutes, 'GET /ai/status': { body: { enabled: false, model: null, features: [] } } });
    renderApp(<AiAssistant />);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByLabelText('Ask SIMS')).toBeNull();
  });

  it('asks a question through the API and shows the answer as plain text', async () => {
    const { calls } = mockApi({
      ...authRoutes,
      'GET /ai/status': { body: { enabled: true, model: 'm', features: ['assistant'] } },
      'POST /ai/assistant': { body: { answer: 'Open Attendance <b>not bold</b>' } },
    });
    renderApp(<AiAssistant />);
    await userEvent.click(await screen.findByLabelText('Ask SIMS'));
    await userEvent.type(screen.getByLabelText('Your question'), 'Where do I mark attendance?');
    await userEvent.click(screen.getByLabelText('Send question'));
    expect(await screen.findByText(/Open Attendance <b>not bold<\/b>/)).toBeInTheDocument();
    expect(calls.find((c) => c.path === '/ai/assistant')?.method).toBe('POST');
  });

  it('shows a clear error when the AI service is unavailable', async () => {
    mockApi({
      ...authRoutes,
      'GET /ai/status': { body: { enabled: true, model: 'm', features: [] } },
      'POST /ai/assistant': { status: 502, body: { error: { code: 'ai_unavailable', message: 'The AI service is unavailable.', details: {} } } },
    });
    renderApp(<AiAssistant />);
    await userEvent.click(await screen.findByLabelText('Ask SIMS'));
    await userEvent.type(screen.getByLabelText('Your question'), 'hello there');
    await userEvent.click(screen.getByLabelText('Send question'));
    await waitFor(() => expect(screen.getByText('The AI service is unavailable.')).toBeInTheDocument());
  });
});
