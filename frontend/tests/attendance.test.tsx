import React from 'react';
import {afterEach,beforeAll,afterAll,it,expect,vi} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {AttendanceApp} from '../src/features/attendance/AttendanceApp';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const server=setupServer();
beforeAll(()=>server.listen({onUnhandledRequest:'error'}));afterAll(()=>server.close());
afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
const reader={user_id:1,username:'Student',is_superuser:false,permissions:[]};
function empty(){server.use(http.get('http://localhost/api/v1/attendance/*',()=>HttpResponse.json({results:[],count:0,next:null})));}
it('keeps staff controls out of student self-service',async()=>{
 empty();render(<AttendanceApp user={reader}/>);
 expect(screen.getByRole('heading',{name:'Attendance & lesson plans'})).toBeInTheDocument();
 expect(screen.queryByRole('combobox',{name:'Section'})).not.toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Finalize register'})).not.toBeInTheDocument();
 await screen.findByRole('button',{name:'Submit correction request'});
});
it('disables correction submission while offline',async()=>{
 vi.spyOn(navigator,'onLine','get').mockReturnValue(false);empty();render(<AttendanceApp user={reader}/>);
 expect(screen.getByText(/Changes are not saved or queued/)).toBeInTheDocument();
 expect(await screen.findByRole('button',{name:'Submit correction request'})).toBeDisabled();
});
it('shows API permission failures without claiming an empty register',async()=>{
 server.use(http.get('http://localhost/api/v1/attendance/*',()=>HttpResponse.json({error:{message:'Verified account required'}},{status:404})));
 render(<AttendanceApp user={reader}/>);
 expect(await screen.findByText(/Verified account required/)).toBeInTheDocument();
});
