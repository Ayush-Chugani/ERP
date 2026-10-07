import React from 'react';
import {afterEach,beforeAll,afterAll,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {StudentSupportApp} from '../src/features/student-support/StudentSupportApp';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const server=setupServer();beforeAll(()=>server.listen({onUnhandledRequest:'error'}));afterAll(()=>server.close());afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
const user={user_id:1,username:'Student',is_superuser:false,permissions:['student_support.submit_own_grievance','student_support.view_own_grievance']};
function routes(){server.use(http.get('http://localhost/api/v1/support/own-grievances/',()=>HttpResponse.json({results:[],next:null})),http.get('http://localhost/api/v1/support/categories/',()=>HttpResponse.json({results:[{id:'5',category_name:'Approved category'}],next:null})),http.get('http://localhost/api/v1/support/departments/',()=>HttpResponse.json({results:[],next:null})));}
it('submits only after confirmation and never accepts a student identity',async()=>{routes();let payload:unknown;
 server.use(http.post('http://localhost/api/v1/support/own-grievances/submit/',async({request})=>{payload=await request.json();return HttpResponse.json({id:'10'});}));
 render(<StudentSupportApp user={user}/>);await screen.findByText('No accessible records.');fireEvent.mouseDown(screen.getByRole('combobox',{name:'Category'}));fireEvent.click(await screen.findByRole('option',{name:'Approved category'}));fireEvent.change(screen.getByLabelText('Subject'),{target:{value:'Help requested'}});fireEvent.change(screen.getByLabelText('Description'),{target:{value:'Private request'}});fireEvent.click(screen.getByRole('button',{name:'Review and save'}));expect(payload).toBeUndefined();fireEvent.click(screen.getByRole('button',{name:'Confirm save'}));await screen.findByText('Saved.');expect(payload).toEqual({grievance_category_id:'5',subject:'Help requested',description:'Private request'});
},15000);
it('hides staff workflows from students',async()=>{routes();render(<StudentSupportApp user={user}/>);await screen.findByText('No accessible records.');fireEvent.mouseDown(screen.getByRole('combobox',{name:'Workspace'}));expect(screen.queryByRole('option',{name:'Staff grievance queue'})).not.toBeInTheDocument();expect(screen.queryByRole('option',{name:'Category administration'})).not.toBeInTheDocument();});
it('blocks offline writes without persisting narratives',async()=>{routes();vi.spyOn(navigator,'onLine','get').mockReturnValue(false);const spy=vi.spyOn(Storage.prototype,'setItem');render(<StudentSupportApp user={user}/>);await screen.findByText('No accessible records.');fireEvent.change(screen.getByLabelText('Description'),{target:{value:'Private draft'}});expect(screen.getByRole('button',{name:'Review and save'})).toBeDisabled();expect(spy).not.toHaveBeenCalled();});
