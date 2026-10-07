import React from 'react';
import {afterEach,beforeAll,afterAll,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {FeedbackApp} from '../src/features/feedback/FeedbackApp';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const server=setupServer();beforeAll(()=>server.listen({onUnhandledRequest:'error'}));afterAll(()=>server.close());afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
const student={user_id:1,username:'Student',is_superuser:false,permissions:['feedback.submit_feedback']};
function routes(){server.use(http.get('http://localhost/api/v1/feedback/available/',()=>HttpResponse.json({results:[{cycle_id:'1',name:'Course feedback',label:'Course A',anonymous:true,target:{course_offering_id:'5'}}]})),http.get('http://localhost/api/v1/feedback/cycles/1/questionnaire/',()=>HttpResponse.json({cycle_id:'1',name:'Course feedback',anonymous:true,items:[{id:'7',text:'Comments',response_type:'TEXT',is_required:true,text_limit:100,choices:[]}]})));}
async function choose(){fireEvent.mouseDown(await screen.findByRole('combobox',{name:'Feedback target'}));fireEvent.click(await screen.findByRole('option',{name:'Course feedback / Course A'}));await screen.findByLabelText(/Comments/);}
it('requires an explicit confirmation and preserves retry key after a network error',async()=>{
 routes();const keys:string[]=[];
 server.use(http.post('http://localhost/api/v1/feedback/cycles/1/submit/',async({request})=>{keys.push(request.headers.get('Idempotency-Key')||'');expect(await request.json()).toEqual({target:{course_offering_id:'5'},answers:{'7':{text_response:'Useful course'}}});return keys.length===1?HttpResponse.json({error:{message:'Network retry'}},{status:503}):HttpResponse.json({receipt:'opaque-receipt',status:'submitted'});}));
 render(<FeedbackApp user={student}/>);await choose();fireEvent.change(screen.getByLabelText(/Comments/),{target:{value:'Useful course'}});fireEvent.click(screen.getByRole('button',{name:'Review and submit feedback'}));expect(keys).toHaveLength(0);fireEvent.click(screen.getByRole('button',{name:'Submit feedback'}));await screen.findByText(/Network retry/);fireEvent.click(screen.getByRole('button',{name:'Submit feedback'}));await screen.findByText(/opaque-receipt/);expect(keys[0]).toBe(keys[1]);expect(keys[0]).not.toBe('');
});
it('does not submit required empty answers',async()=>{routes();render(<FeedbackApp user={student}/>);await choose();fireEvent.click(screen.getByRole('button',{name:'Review and submit feedback'}));expect(await screen.findByText(/Answer all required/)).toBeInTheDocument();expect(screen.queryByRole('dialog')).not.toBeInTheDocument();});
it('blocks offline submission and keeps staff controls hidden',async()=>{vi.spyOn(navigator,'onLine','get').mockReturnValue(false);routes();render(<FeedbackApp user={student}/>);await choose();expect(screen.getByRole('button',{name:'Review and submit feedback'})).toBeDisabled();expect(screen.queryByRole('combobox',{name:'Workspace'})).not.toBeInTheDocument();expect(screen.getByText(/Answers are not stored or queued/)).toBeInTheDocument();});
