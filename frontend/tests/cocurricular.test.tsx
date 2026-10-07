import React from 'react';
import {afterEach,beforeAll,afterAll,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent,waitFor,within} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {CocurricularApp} from '../src/features/cocurricular/CocurricularApp';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const server=setupServer();
beforeAll(()=>server.listen({onUnhandledRequest:'error'}));afterAll(()=>server.close());
afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
const detail={staff_activity:'12',version:'token',event_name:'<img src=x onerror=alert(1)>',employee_name:'Faculty',category_name:'Industry',status:'DRAFT',can_edit:true,can_archive:true,actions:['submit'],evidence:[],history:[]};
function routes(create=false){server.use(
 http.get('*/cocurricular/lookups/',()=>HttpResponse.json({can_create:create,default_mine:false,categories:['OTHER']})),
 http.get('*/cocurricular/activities/',()=>HttpResponse.json({count:1,next:null,results:[detail]})),
 http.get('*/cocurricular/activities/12/timeline/',()=>HttpResponse.json({count:1,next:null,results:[{changed_at:'2026-09-25',from_status:null,to_status:'DRAFT',remarks:'Draft created'}]})),
 http.get('*/cocurricular/activities/12/',()=>HttpResponse.json(detail)),
 http.get('*/cocurricular/lookups/:name/',()=>HttpResponse.json({count:1,next:null,results:[{id:'1',label:'Choice'}]}))
);}
it('renders text safely and hides unauthorized creation',async()=>{routes();const {container}=render(<CocurricularApp/>);await screen.findAllByText(detail.event_name);expect(container.querySelector('img')).toBeNull();expect(screen.queryByRole('button',{name:'New activity'})).not.toBeInTheDocument();});
it('keeps offline writes disabled without persisting private drafts',async()=>{routes(true);vi.spyOn(navigator,'onLine','get').mockReturnValue(false);const saved=vi.spyOn(Storage.prototype,'setItem');render(<CocurricularApp/>);expect(await screen.findByRole('button',{name:'New activity'})).toBeDisabled();expect(screen.getByText(/Offline: saving/)).toBeInTheDocument();expect(saved).not.toHaveBeenCalled();});
it('offers labelled form fields and dependent geography inputs',async()=>{routes(true);render(<CocurricularApp/>);fireEvent.click(await screen.findByRole('button',{name:'New activity'}));const dialog=await screen.findByRole('dialog');expect(within(dialog).getByLabelText('contribution details')).toBeEnabled();expect(within(dialog).getByLabelText('achievement award')).toBeInTheDocument();expect(within(dialog).getByLabelText('context date *')).toBeInTheDocument();});
it('retries an ambiguous create response with the same key and body',async()=>{routes(true);const attempts:{key:string|null;body:string}[]=[];server.use(http.post('*/cocurricular/activities/',async({request})=>{attempts.push({key:request.headers.get('Idempotency-Key'),body:await request.text()});return attempts.length===1?HttpResponse.error():HttpResponse.json(detail,{status:201});}));render(<CocurricularApp/>);fireEvent.click(await screen.findByRole('button',{name:'New activity'}));fireEvent.change(await screen.findByLabelText('event name *'),{target:{value:'New activity'}});fireEvent.click(screen.getByRole('button',{name:'Save draft'}));await screen.findAllByText(/Unable to reach the server/);fireEvent.click(screen.getByRole('button',{name:'Save draft'}));await waitFor(()=>expect(attempts).toHaveLength(2));expect(attempts[0]).toEqual(attempts[1]);expect(attempts[0].key).toBeTruthy();await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());},15000);
it('uses the version and a stable retry key for workflow submission',async()=>{routes();const calls:{key:string|null;body:unknown}[]=[];server.use(http.post('*/cocurricular/activities/12/workflow/',async({request})=>{calls.push({key:request.headers.get('Idempotency-Key'),body:await request.json()});return calls.length===1?HttpResponse.error():HttpResponse.json({...detail,status:'SUBMITTED',actions:[]});}));render(<CocurricularApp/>);fireEvent.click(await screen.findByRole('button',{name:'View'}));fireEvent.click(await screen.findByRole('button',{name:'submit'}));fireEvent.click(screen.getByRole('button',{name:'Confirm',exact:true}));await screen.findAllByText(/Unable to reach/);fireEvent.click(screen.getByRole('button',{name:'Confirm',exact:true}));await waitFor(()=>expect(calls).toHaveLength(2));expect(calls[0]).toEqual(calls[1]);expect(calls[0].body).toEqual({action:'submit',remarks:'',version:'token'});});

it('supports the country-state dependency and preserves all event fields on save',async()=>{
 routes(true);
 const saved:unknown[]=[];
 server.use(http.get('*/cocurricular/lookups/:name/',({params,request})=>{
  const name=String(params.name);
  if(name==='states')expect(new URL(request.url).searchParams.get('country')).toBe('1');
  return HttpResponse.json({count:1,next:null,results:[{id:'1',label:name+' option'}]});
 }),http.post('*/cocurricular/activities/',async({request})=>{saved.push(await request.json());return HttpResponse.json(detail,{status:201});}));
 render(<CocurricularApp/>);
 fireEvent.click(await screen.findByRole('button',{name:'New activity'}));
 const dialog=await screen.findByRole('dialog');
 expect(within(dialog).getByRole('combobox',{name:'state'})).toHaveAttribute('aria-disabled','true');
 async function choose(label:string,option:string){
  fireEvent.mouseDown(within(dialog).getByRole('combobox',{name:label}));
  fireEvent.click(await screen.findByRole('option',{name:option}));
 }
 await choose('employee assignment','assignments option');
 await choose('cocurricular category','categories option');
 await choose('country','countries option');
 await choose('state','states option');
 await choose('organizer','organizers option');
 await choose('institution organization','organizations option');
 for(const [label,value] of Object.entries({'event name *':'Student innovation fair','context date *':'2026-01-01','event date':'2026-01-01','venue name':'Main hall','city':'Pune','achievement award':'Recognition','contribution details':'Faculty coordination'}))
  fireEvent.change(within(dialog).getByLabelText(label),{target:{value}});
 fireEvent.click(within(dialog).getByRole('button',{name:'Save draft'}));
 await waitFor(()=>expect(saved).toHaveLength(1));
 expect(saved[0]).toMatchObject({context:{employee_assignment_id:'1',context_date:'2026-01-01'},activity:{event_name:'Student innovation fair',cocurricular_category_id:'1',country_id:'1',state_id:'1',organizer_id:'1',institution_organization_id:'1',event_date:'2026-01-01',venue_name:'Main hall',city:'Pune',achievement_award:'Recognition',contribution_details:'Faculty coordination'}});
 await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
},15000);
