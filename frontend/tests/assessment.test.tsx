import React from 'react';
import {afterEach,beforeAll,afterAll,it,expect,vi} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {AssessmentApp} from '../src/features/assessments/AssessmentApp';
import {parseMarkPaste} from '../src/features/assessments/paste';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const server=setupServer();beforeAll(()=>server.listen({onUnhandledRequest:'error'}));afterAll(()=>server.close());afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
const student={user_id:1,username:'Student',is_superuser:false,permissions:[]};
it('shows only published self-service data and no staff actions',async()=>{
 server.use(http.get('http://localhost/api/v1/assessments/mine/',()=>HttpResponse.json({results:[{id:'1',course_code:'C1',course_title:'Test course',grade_letter:'A',grade_point:'9',credits_earned:'3',result_status:'PASS'}]})));
 render(<AssessmentApp user={student}/>);expect(await screen.findByText('PASS')).toBeInTheDocument();expect(screen.queryByLabelText('Workspace')).not.toBeInTheDocument();expect(screen.queryByRole('button',{name:'publish result'})).not.toBeInTheDocument();
});
it('shows access failure without claiming there are no results',async()=>{
 server.use(http.get('http://localhost/api/v1/assessments/mine/',()=>HttpResponse.json({error:{message:'Verified identity required'}},{status:404})));
 render(<AssessmentApp user={student}/>);expect(await screen.findByText('Verified identity required')).toBeInTheDocument();expect(screen.queryByText('No published results found.')).not.toBeInTheDocument();
});
it('shows offline state',async()=>{
 vi.spyOn(navigator,'onLine','get').mockReturnValue(false);server.use(http.get('http://localhost/api/v1/assessments/mine/',()=>HttpResponse.json({results:[]})));
 render(<AssessmentApp user={student}/>);expect(screen.getByText(/Offline: changes/)).toBeInTheDocument();await screen.findByText('No published results found.');
});
it('validates pasted students, duplicates and formula-like input',()=>{
 const roster=[{course_registration_id:'1',student_number:'S1'}];
 expect(parseMarkPaste('S1\tPRESENT\t80\tChecked',roster)[0].marks_obtained).toBe('80');
 expect(()=>parseMarkPaste('S2\tPRESENT\t80',roster)).toThrow();
 expect(()=>parseMarkPaste('S1\tPRESENT\t=80',roster)).toThrow();
 expect(()=>parseMarkPaste('S1\tPRESENT\t80\nS1\tABSENT',roster)).toThrow();
});
