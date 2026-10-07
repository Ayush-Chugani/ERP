import React from 'react';
import {afterEach,beforeAll,afterAll,describe,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {RegistrationApp} from '../src/features/registration/RegistrationApp';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const server=setupServer();
beforeAll(()=>server.listen({onUnhandledRequest:'error'}));
afterAll(()=>server.close());
afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
const reader={user_id:1,username:'Student',is_superuser:false,permissions:[]};
const staff={...reader,username:'Registrar',permissions:['term_registration.manage_registration']};
function empty(){server.use(http.get('http://localhost/api/v1/registration/*',()=>HttpResponse.json({results:[],count:0,next:null})));}
describe('Registration workspace',()=>{
 it('shows personal registrations without staff controls',async()=>{
  empty();render(<RegistrationApp user={reader}/>);
  expect(await screen.findByText('No registrations found.')).toBeInTheDocument();
  expect(screen.queryByRole('heading',{name:'Registration actions'})).not.toBeInTheDocument();
  expect(screen.getByRole('table',{name:'Registration records'})).toBeInTheDocument();
 });
 it('disables changes offline',async()=>{
  vi.spyOn(navigator,'onLine','get').mockReturnValue(false);empty();render(<RegistrationApp user={staff}/>);
  expect(screen.getByText(/never queued/)).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Save action'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'Apply reviewed import'})).toBeDisabled();
  await screen.findByText('No registrations found.');
 });
 it('shows scoped API failures',async()=>{
  server.use(http.get('http://localhost/api/v1/registration/*',()=>HttpResponse.json({error:{message:'Verified account required'}},{status:404})));
  render(<RegistrationApp user={reader}/>);
  expect(await screen.findByRole('alert')).toHaveTextContent(/Verified account required/);
 });
 it('keeps import application disabled until preview succeeds',async()=>{
  empty();render(<RegistrationApp user={staff}/>);
  await screen.findByText('No registrations found.');
  expect(screen.getByRole('button',{name:'Preview import'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'Apply reviewed import'})).toBeDisabled();
  expect(screen.getByLabelText('Programme filter')).toBeInTheDocument();
 });
});
it('preserves the idempotency key when retrying an unchanged failed command',async()=>{
 const keys:string[]=[];
 server.use(http.get('http://localhost/api/v1/registration/*',({request})=>HttpResponse.json({results:new URL(request.url).pathname.endsWith('/terms/')?[{id:'7',version:1,label:'Student 7'}]:[],count:1,next:null})));
 server.use(http.post('http://localhost/api/v1/registration/commands/correct-roll/',async({request})=>{
  keys.push(request.headers.get('Idempotency-Key')||'');
  expect(await request.json()).toEqual({pk:'7',expected_version:1,roll_number:'R7',reason:'Correct legacy roll'});
  return keys.length===1?HttpResponse.json({error:{message:'Concurrent update; retry unchanged.'}},{status:409}):HttpResponse.json({id:'7',version:2,resource:'studenttermregistration'});
 }));
 render(<RegistrationApp user={staff}/>);
 await screen.findByText('No registrations found.');
 fireEvent.mouseDown(screen.getByRole('combobox',{name:'Action'}));
 fireEvent.click(screen.getByRole('option',{name:'Correct roll number'}));
 fireEvent.mouseDown(screen.getByRole('combobox',{name:'Term registration'}));
 fireEvent.click(await screen.findByRole('option',{name:'Student 7 (v1)'}));
 fireEvent.change(screen.getByLabelText(/Current version/),{target:{value:'1'}});
 fireEvent.change(screen.getByLabelText(/Roll number/),{target:{value:'R7'}});
 fireEvent.change(screen.getByLabelText(/Reason/),{target:{value:'Correct legacy roll'}});
 fireEvent.click(screen.getByRole('button',{name:'Save action'}));
 await screen.findByText(/Concurrent update; retry unchanged/);
 fireEvent.click(screen.getByRole('button',{name:'Save action'}));
 await screen.findByText('Saved record 7.');
 expect(keys).toHaveLength(2);expect(keys[0]).not.toBe('');expect(keys[1]).toBe(keys[0]);
});
it('previews the imported batch before enabling apply',async()=>{
 const modes:boolean[]=[];const keys:string[]=[];
 empty();
 server.use(http.post('http://localhost/api/v1/registration/import/parse/',()=>HttpResponse.json({rows:[{operation:'create-draft',data:{offering_id:'1',enrolment_id:'2'}}]})));
 server.use(http.post('http://localhost/api/v1/registration/bulk/',async({request})=>{
  const data=await request.json() as {dry_run:boolean};modes.push(data.dry_run);keys.push(request.headers.get('Idempotency-Key')||'');
  return HttpResponse.json({results:[{id:'1',version:1}],dry_run:data.dry_run});
 }));
 const view=render(<RegistrationApp user={staff}/>);
 await screen.findByText('No registrations found.');
 const file=new File(['operation,data'], 'mapped.csv',{type:'text/csv'});
 Object.defineProperty(file,'text',{value:async()=> 'operation,data\ncreate-draft,"{}"'});
 fireEvent.change(view.container.querySelector('input[type=file]')!,{target:{files:[file]}});
 await screen.findByLabelText('Imported CSV review');
 expect(screen.getByRole('button',{name:'Apply reviewed import'})).toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'Preview import'}));
 await screen.findByText('Preview passed for 1 rows.');
 fireEvent.click(screen.getByRole('button',{name:'Apply reviewed import'}));
 await screen.findByText('Applied 1 rows.');
 expect(modes).toEqual([true,false]);expect(keys[1]).toBe(keys[0]);
 expect(screen.getByRole('button',{name:'Apply reviewed import'})).toBeDisabled();
});
