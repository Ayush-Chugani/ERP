import React from 'react';
import {afterEach,beforeAll,afterAll,describe,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {PeopleApp} from '../src/features/people/PeopleApp';
import {PeopleForm} from '../src/features/people/PeopleForm';
import type {Resource,Row} from '../src/features/people/api';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const resource:Resource={path:'students',title:'Students',can_create:true,fields:[{name:'student_number',label:'Student number',required:true,nullable:false,kind:'text',choices:[]},{name:'display_name',label:'Display name',required:true,nullable:false,kind:'text',choices:[]}]};
const server=setupServer();beforeAll(()=>server.listen({onUnhandledRequest:'error'}));afterAll(()=>server.close());afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
describe('People forms',()=>{
 it('preserves values on a stale version and uses JSON with the original string version',async()=>{
  let type='',version='';server.use(http.patch('http://localhost/api/v1/people/students/9007199254740993/',({request})=>{type=request.headers.get('content-type')||'';version=request.headers.get('if-match')||'';return HttpResponse.json({error:{message:'Record changed. Reload.',details:{}}},{status:409});}));
  const row:Row={id:'9007199254740993',version:'6',actions:['change'],masked_fields:[],student_number:'S1',display_name:'Student'};
  render(<PeopleForm resource={resource} row={row} onClose={()=>{}} onSaved={()=>{}}/>);
  fireEvent.change(screen.getByLabelText(/Display name/),{target:{value:'Edited name'}});fireEvent.click(screen.getByRole('button',{name:'Save'}));
  expect(await screen.findByText(/Record changed/)).toBeInTheDocument();expect(screen.getByLabelText(/Display name/)).toHaveValue('Edited name');expect(type).toBe('application/json');expect(version).toBe('6');
 });
 it('disables writes while offline without clearing entered values',()=>{
  vi.spyOn(navigator,'onLine','get').mockReturnValue(false);
  render(<PeopleForm resource={resource} row={null} onClose={()=>{}} onSaved={()=>{}}/>);
  expect(screen.getByRole('button',{name:'Save'})).toBeDisabled();expect(screen.getByText(/Personal records are not cached/)).toBeInTheDocument();
 });
 it('does not render masked sensitive fields',()=>{
  const sensitive:Resource={...resource,fields:[...resource.fields,{name:'notes',label:'Restricted notes',required:false,nullable:true,kind:'text',choices:[]}]};
  render(<PeopleForm resource={sensitive} row={{id:'1',version:'1',actions:['change'],masked_fields:['notes'],student_number:'S1',display_name:'Student'}} onClose={()=>{}} onSaved={()=>{}}/>);
  expect(screen.queryByLabelText('Restricted notes')).not.toBeInTheDocument();
 });
});

it('links an employee profile to the scoped extra-curricular activity timeline',async()=>{
 window.history.replaceState(null,'','#/people/employees');
 server.use(http.get('*/people/metadata/',()=>HttpResponse.json({resources:[{path:'employees',title:'Employees',fields:[],can_create:false}]})),http.get('*/people/employees/',()=>HttpResponse.json({count:1,results:[{id:'9007199254740993',version:'1',display_name:'Faculty member',actions:[],masked_fields:[]}]})));
 render(<PeopleApp/>);
 fireEvent.click(await screen.findByRole('button',{name:'Details'}));
 expect(await screen.findByRole('link',{name:'Professional memberships'})).toHaveAttribute('href','#/professional-memberships?employee=9007199254740993');
 expect(await screen.findByRole('link',{name:'Awards and recognitions'})).toHaveAttribute('href','#/awards?employee=9007199254740993');
 expect(await screen.findByRole('link',{name:'Extra-curricular activity timeline'})).toHaveAttribute('href','#/extracurricular?employee=9007199254740993');
 cleanup();window.history.replaceState(null,'','#/people');
});
