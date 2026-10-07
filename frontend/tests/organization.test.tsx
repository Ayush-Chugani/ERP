import React from 'react';
import {afterEach,describe,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {beforeAll,afterAll} from 'vitest';
import {Workspace} from '../src/features/organization/OrganizationApp';
import {OrganizationForm} from '../src/features/organization/OrganizationForm';
import type {Resource} from '../src/features/organization/api';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const resource:Resource={path:'universities',title:'Universities',id:'university_id',parent:null,can_create:false,can_manage:false,count:1,fields:[{name:'university_code',label:'University code',required:true,max:30,kind:'text',choices:[],parent:null,reference:false},{name:'university_name',label:'University name',required:true,max:200,kind:'text',choices:[],parent:null,reference:false}]};
const row={university_id:1,university_name:'Sample University',university_code:'SAMPLE',is_active:true,effective_active:true,can_change:false};
const server=setupServer(http.get('http://localhost/api/v1/organization/metadata/',()=>HttpResponse.json({resources:[resource],user_id:1})),http.get('http://localhost/api/v1/organization/universities/',()=>HttpResponse.json({count:1,results:[row]})));
beforeAll(()=>server.listen({onUnhandledRequest:'error'}));
afterEach(()=>{cleanup();server.resetHandlers();});afterAll(()=>server.close());
function mount(url='/organization/universities'){const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[url]}><Routes><Route path="/organization/:resource" element={<Workspace/>}/></Routes></MemoryRouter></QueryClientProvider>);}
describe('organization workspace',()=>{
 it('renders scoped records without management controls for a reader',async()=>{mount();expect(await screen.findByText('Sample University')).toBeInTheDocument();expect(screen.queryByRole('button',{name:'Edit'})).not.toBeInTheDocument();expect(screen.queryByRole('button',{name:/Create/})).not.toBeInTheDocument();});
 it('passes URL filters through to server and displays errors',async()=>{let search='';server.use(http.get('http://localhost/api/v1/organization/universities/',({request})=>{search=new URL(request.url).searchParams.get('search')||'';return HttpResponse.json({error:{message:'Scope unavailable',details:{}}},{status:403});}));mount('/organization/universities?search=alpha');expect(await screen.findByText('Scope unavailable')).toBeInTheDocument();expect(search).toBe('alpha');});
 it('shows an empty state for an empty scope',async()=>{server.use(http.get('http://localhost/api/v1/organization/universities/',()=>HttpResponse.json({count:0,results:[]})));mount();expect(await screen.findByText(/No records in your permitted scope/)).toBeInTheDocument();});
 it('displays server field errors and preserves form values',async()=>{server.use(http.post('http://localhost/api/v1/organization/universities/',()=>HttpResponse.json({error:{message:'Request validation failed.',details:{university_code:['Already used.']}}},{status:400})));render(<OrganizationForm resource={{...resource,can_create:true}} record={null} onClose={()=>{}} onSaved={()=>{}}/>);fireEvent.change(screen.getByLabelText(/University code/),{target:{value:'SAMPLE'}});fireEvent.change(screen.getByLabelText(/University name/),{target:{value:'Sample'}});fireEvent.click(screen.getByRole('button',{name:'Save'}));expect(await screen.findByText('Already used.')).toBeInTheDocument();expect(screen.getByLabelText(/University name/)).toHaveValue('Sample');});
});
