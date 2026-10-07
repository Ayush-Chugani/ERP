import React from 'react';
import {afterEach,beforeAll,afterAll,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {SecurityApp} from '../src/features/identity-access/SecurityApp';
import {SupportBanner} from '../src/features/identity-access/SupportBanner';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const server=setupServer();beforeAll(()=>server.listen({onUnhandledRequest:'error'}));afterAll(()=>server.close());afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
function routes(admin=true){server.use(http.get('*/security/context/',()=>HttpResponse.json({can_administer:admin,can_audit:false})),http.get('*/security/users/',()=>HttpResponse.json({results:[],next:null,count:0})));}
it('hides security mutations when the server reports no administrative authority',async()=>{routes(false);render(<SecurityApp/>);await screen.findByText('No matching records.');expect(screen.queryByRole('button',{name:'Review change'})).not.toBeInTheDocument();});
it('never queues offline security changes or stores credentials',async()=>{routes();vi.spyOn(navigator,'onLine','get').mockReturnValue(false);const store=vi.spyOn(Storage.prototype,'setItem');render(<SecurityApp/>);expect(await screen.findByRole('button',{name:'Review change'})).toBeDisabled();expect(store).not.toHaveBeenCalled();});
it('shows a persistent support identity warning and ends only that session',async()=>{let ended=false;server.use(http.get('*/security/context/',()=>HttpResponse.json({support_session:{session_id:'session-1',target_user_id:71,expires_at:'2026-09-26T00:00:00Z'}})),http.delete('*/security/support-sessions/session-1/',()=>{ended=true;return new HttpResponse(null,{status:204});}));render(<SupportBanner/>);await screen.findByText(/Read-only support session for user 71/);fireEvent.click(screen.getByRole('button',{name:'End session'}));await vi.waitFor(()=>expect(ended).toBe(true));});
