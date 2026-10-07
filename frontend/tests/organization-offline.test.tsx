import {afterEach,it,expect,vi} from 'vitest';
import {saveOfflineCopy,currentOfflineCopy,clearOfflineCopy} from '../src/pwa/offlineCopy';
afterEach(()=>{clearOfflineCopy();vi.useRealTimers();});
it('never exposes another user snapshot and expires after five minutes',()=>{
 vi.useFakeTimers();vi.setSystemTime(new Date('2026-09-19T12:00:00Z'));
 saveOfflineCopy({user_id:7,resource:'institutions',fetched_at:new Date().toISOString(),expires_at:'2026-09-19T12:05:00Z',truncated:false,records:[{institution_name:'Scoped institution'}]});
 expect(currentOfflineCopy(8)).toBeNull();expect(currentOfflineCopy()).toBeNull();expect(currentOfflineCopy(7)?.records).toHaveLength(1);
 vi.advanceTimersByTime(300001);expect(currentOfflineCopy(7)).toBeNull();
});
it('clears labels on reconnect and session expiration',()=>{
 const seed=()=>saveOfflineCopy({user_id:7,resource:'institutions',fetched_at:new Date().toISOString(),expires_at:new Date(Date.now()+300000).toISOString(),truncated:false,records:[]});
 seed();window.dispatchEvent(new Event('online'));expect(currentOfflineCopy(7)).toBeNull();
 seed();window.dispatchEvent(new Event('sims-session-expired'));expect(currentOfflineCopy(7)).toBeNull();
});
