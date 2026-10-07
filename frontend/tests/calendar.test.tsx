import React from 'react';
import {beforeAll,afterAll,afterEach,it,expect,vi} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {CalendarApp,CalendarForm} from '../src/features/academic-calendar/CalendarApp';
import type {CalendarResource} from '../src/features/academic-calendar/api';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const resource:CalendarResource={path:'academic-years',id:'academic_year_id',can_create:false,fields:[{name:'year_code',kind:'text',required:true,choices:[],max_length:9},{name:'start_date',kind:'date',required:true,choices:[],max_length:null},{name:'end_date',kind:'date',required:true,choices:[],max_length:null}]};
const row={academic_year_id:1,year_code:'2026-27',start_date:'2026-06-01',end_date:'2027-05-31',status:'PLANNED',actions:[],parent_label:null,timezone:null};
const server=setupServer(http.get('http://localhost/api/v1/calendar/metadata/',()=>HttpResponse.json({resources:[resource]})),http.get('http://localhost/api/v1/calendar/academic-years/',()=>HttpResponse.json({count:1,results:[row],next:null,previous:null})));
beforeAll(()=>server.listen({onUnhandledRequest:'error'}));
afterAll(()=>server.close());
afterEach(()=>{cleanup();server.resetHandlers();Object.defineProperty(navigator,'onLine',{configurable:true,value:true});});
it('shows shared calendar records without reader mutation controls',async()=>{location.hash='/calendar/academic-years';render(<CalendarApp/>);expect(await screen.findByText('2026-27')).toBeInTheDocument();expect(screen.queryByRole('button',{name:'Create'})).not.toBeInTheDocument();expect(screen.queryByRole('button',{name:'Edit'})).not.toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:'Details'}));expect(await screen.findByText('Calendar details')).toBeInTheDocument();});
it('preserves entered values and displays field errors',async()=>{server.use(http.post('http://localhost/api/v1/calendar/academic-years/',()=>HttpResponse.json({error:{message:'Invalid dates.',details:{end_date:['Must be after start.']}}},{status:400})));render(<CalendarForm resource={resource} record={null} onClose={()=>{}} onSaved={()=>{}}/>);fireEvent.change(screen.getByLabelText(/Year code/),{target:{value:'2026-27'}});fireEvent.change(screen.getByLabelText(/Start date/),{target:{value:'2026-06-01'}});fireEvent.change(screen.getByLabelText(/End date/),{target:{value:'2026-01-01'}});fireEvent.click(screen.getByRole('button',{name:'Save'}));expect(await screen.findByText('Must be after start.')).toBeInTheDocument();expect(screen.getByLabelText(/Year code/)).toHaveValue('2026-27');});
it('disables saving offline and does not claim a queued write',()=>{Object.defineProperty(navigator,'onLine',{configurable:true,value:false});render(<CalendarForm resource={resource} record={null} onClose={()=>{}} onSaved={()=>{}}/>);expect(screen.getByRole('button',{name:'Save'})).toBeDisabled();expect(screen.getByText(/will not be queued/)).toBeInTheDocument();});
it('sends URL filters and presents backend errors',async()=>{let search='';server.use(http.get('http://localhost/api/v1/calendar/academic-years/',({request})=>{search=new URL(request.url).searchParams.get('search')||'';return HttpResponse.json({error:{message:'Module unavailable.',details:{}}},{status:403});}));location.hash='/calendar/academic-years?search=2026';render(<CalendarApp/>);expect(await screen.findByText('Module unavailable.')).toBeInTheDocument();expect(search).toBe('2026');});

it('sends JSON content type and JSON bodies for create, update and lifecycle requests',async()=>{
 const {calendarApi}=await import('../src/features/academic-calendar/api');
 const seen:{method:string;contentType:string|null;body:unknown}[]=[];
 const capture=async({request}:{request:Request})=>{seen.push({method:request.method,contentType:request.headers.get('content-type'),body:await request.json()});return HttpResponse.json(row);};
 server.use(http.post('http://localhost/api/v1/calendar/academic-years/',capture),http.patch('http://localhost/api/v1/calendar/academic-years/1/',capture),http.post('http://localhost/api/v1/calendar/academic-years/1/close/',capture));
 await calendarApi.save(resource,null,{year_code:'2026-27'});
 await calendarApi.save(resource,row,{year_code:'2026-28'});
 await calendarApi.transition(resource,row,'close','Completed');
 expect(seen).toEqual([{method:'POST',contentType:'application/json',body:{year_code:'2026-27'}},{method:'PATCH',contentType:'application/json',body:{year_code:'2026-28'}},{method:'POST',contentType:'application/json',body:{reason:'Completed'}}]);
});
