import React from 'react';
import {afterEach,beforeAll,afterAll,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {ConferencesApp} from '../src/features/conferences/ConferencesApp';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const server=setupServer();
beforeAll(()=>server.listen({onUnhandledRequest:'error'}));afterAll(()=>server.close());
afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
function routes(permissions:string[]=[]){server.use(
 http.get('*/conferences/lookups/',()=>HttpResponse.json({permissions})),
 http.get('*/conferences/activities/',()=>HttpResponse.json({count:1,next:null,results:[{staff_activity:1,paper_title:'<img src=x onerror=alert(1)>',employee_name:'Synthetic'}]})),
 http.get('*/conferences/events/',()=>HttpResponse.json({count:0,next:null,results:[]})),
 http.get('*/conferences/lookups/:name/',()=>HttpResponse.json({count:0,next:null,results:[]}))
);}
it('renders scholarly text safely and disables unauthorized creation',async()=>{routes();const {container}=render(<ConferencesApp/>);await screen.findByText('<img src=x onerror=alert(1)>');expect(container.querySelector('img')).toBeNull();expect(screen.getByRole('button',{name:'Add activity'})).toBeDisabled();});
it('does not submit or persist offline activity drafts',async()=>{routes(['ACTIVITY.CREATE']);vi.spyOn(navigator,'onLine','get').mockReturnValue(false);const saved=vi.spyOn(Storage.prototype,'setItem');render(<ConferencesApp/>);await screen.findByText('You are offline. Changes cannot be submitted. No edits are queued.');expect(screen.getByRole('button',{name:'Add activity'})).toBeDisabled();expect(saved).not.toHaveBeenCalled();});
it('opens a permitted event form and requires no raw JSON editing',async()=>{routes(['EVENT.CREATE']);render(<ConferencesApp/>);await screen.findByText('Synthetic');fireEvent.click(screen.getByRole('button',{name:'Conference events'}));fireEvent.click(await screen.findByRole('button',{name:'Add event'}));expect(await screen.findByRole('dialog')).toBeInTheDocument();expect(screen.getByLabelText('conference title')).toBeInTheDocument();expect(screen.getByLabelText('start date')).toBeInTheDocument();});
it('submits a valid event through the authenticated client',async()=>{routes(['EVENT.CREATE']);let saved:Record<string,unknown>|null=null;server.use(http.post('*/conferences/events/',async({request})=>{saved=await request.json() as Record<string,unknown>;return HttpResponse.json({conference_event_id:'12'}); }));render(<ConferencesApp/>);await screen.findByText('Synthetic');fireEvent.click(screen.getByRole('button',{name:'Conference events'}));fireEvent.click(await screen.findByRole('button',{name:'Add event'}));fireEvent.change(await screen.findByLabelText('conference title'),{target:{value:'Conference demo'}});fireEvent.change(screen.getByLabelText('start date'),{target:{value:'2026-10-01'}});fireEvent.change(screen.getByLabelText('end date'),{target:{value:'2026-10-02'}});fireEvent.click(screen.getByRole('button',{name:'Save'}));await screen.findByText('Saved.');expect(saved).toMatchObject({conference_title:'Conference demo',start_date:'2026-10-01',end_date:'2026-10-02',is_active:true});});
