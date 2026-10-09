import { useQuery } from '@tanstack/react-query';
import { api } from './client';
import type { MetaGroups, ResourceMeta } from './types';

export const useMeta = () =>
  useQuery({ queryKey: ['meta'], queryFn: () => api<MetaGroups>('/meta'), staleTime: 5 * 60_000 });

export const useResourceMeta = (path: string) =>
  useQuery({ queryKey: ['meta', path], queryFn: () => api<ResourceMeta>(`/meta/${path}`), staleTime: 5 * 60_000 });
