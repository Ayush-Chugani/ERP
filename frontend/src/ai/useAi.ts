import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export type AiStatus = { enabled: boolean; model: string | null; features: string[] };

/** AI features are optional: nothing AI-related renders unless the server reports it as enabled. */
export function useAiStatus(): AiStatus {
  const q = useQuery({ queryKey: ['ai-status'], queryFn: () => api<AiStatus>('/ai/status'), staleTime: 5 * 60_000, retry: false });
  return q.data ?? { enabled: false, model: null, features: [] };
}
