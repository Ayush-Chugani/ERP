/**
 * Persistent offline copy store.
 * Improvement over the previous in-memory-only copy: survives reload,
 * scoped per user, 5-minute TTL, cleared on online/session-expiry/sign-out.
 * `offlineCopy.ts` remains as a backward-compatible re-export shim.
 */
import { OFFLINE_COPY_TTL_MS } from '../lib/config';

export type OfflineCopy = {
  user_id: number;
  resource: string;
  fetched_at: string;
  expires_at: string;
  truncated: boolean;
  records: Record<string, unknown>[];
};

const KEY = 'sims.offline-copy.v1';
const listeners = new Set<() => void>();
let memory: OfflineCopy | null = null;
let channel: BroadcastChannel | null = null;

if (typeof BroadcastChannel !== 'undefined') {
  channel = new BroadcastChannel('sims-offline-identity');
  channel.onmessage = () => {
    memory = null;
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* storage may be unavailable */
    }
    listeners.forEach((fn) => fn());
  };
}

function readStored(): OfflineCopy | null {
  if (memory) return memory;
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    memory = JSON.parse(raw) as OfflineCopy;
    return memory;
  } catch {
    return null;
  }
}

export function clearOfflineCopy(): void {
  memory = null;
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  listeners.forEach((fn) => fn());
  channel?.postMessage('clear');
}

export function saveOfflineCopy(value: OfflineCopy): void {
  const stamped: OfflineCopy = {
    ...value,
    fetched_at: value.fetched_at || new Date().toISOString(),
    expires_at: value.expires_at || new Date(Date.now() + OFFLINE_COPY_TTL_MS).toISOString(),
  };
  memory = stamped;
  try {
    localStorage.setItem(KEY, JSON.stringify(stamped));
  } catch {
    /* private mode — memory fallback still works for the tab */
  }
  listeners.forEach((fn) => fn());
}

export function currentOfflineCopy(userId?: number): OfflineCopy | null {
  const copy = readStored();
  if (!copy) return null;
  // Strict per-user scoping (matches legacy contract): undefined never matches.
  if (copy.user_id !== userId) return null;
  if (Date.parse(copy.expires_at) <= Date.now()) {
    clearOfflineCopy();
    return null;
  }
  return copy;
}

export function subscribeOffline(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', clearOfflineCopy);
  window.addEventListener('sims-session-expired', clearOfflineCopy);
}
