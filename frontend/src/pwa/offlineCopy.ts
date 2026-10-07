/** Backward-compatible shim — canonical store lives in `./offline`. */
export {
  clearOfflineCopy,
  currentOfflineCopy,
  saveOfflineCopy,
  subscribeOffline,
  type OfflineCopy,
} from './offline';
