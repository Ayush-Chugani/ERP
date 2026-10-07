import { QueryClient } from '@tanstack/react-query';

let client: QueryClient | null = null;

/** Shared QueryClient — one per app lifetime (was: one per feature mount). */
export function getQueryClient(): QueryClient {
  if (!client) {
    client = new QueryClient({
      defaultOptions: {
        queries: { retry: false, staleTime: 15_000, refetchOnWindowFocus: false },
        mutations: { retry: false },
      },
    });
  }
  return client;
}
