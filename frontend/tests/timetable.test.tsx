import React from 'react';
import {afterEach,beforeAll,afterAll,describe,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {http,HttpResponse} from 'msw';
import {setupServer} from 'msw/node';
import {TimetableApp} from '../src/features/timetable/TimetableApp';
vi.mock('../src/features/auth/session',()=>({authenticatedFetch:(path:string,init?:RequestInit)=>fetch('http://localhost/api/v1'+path,init)}));
const server=setupServer();
beforeAll(()=>server.listen({onUnhandledRequest:'error'}));
afterAll(()=>server.close());
afterEach(()=>{cleanup();server.resetHandlers();vi.restoreAllMocks();});
const reader={user_id:1,username:'Faculty',is_superuser:false,permissions:['teaching_timetable.view_schedule']};
describe('Timetable workspace',()=>{
 it('keeps planning controls out of personal read-only schedules',async()=>{
  server.use(http.get('http://localhost/api/v1/timetable/occurrences/',()=>HttpResponse.json({results:[]})));
  render(<TimetableApp user={reader}/>);
  expect(await screen.findByText(/No published classes/)).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Planning workspace'})).not.toBeInTheDocument();
  expect(screen.getByRole('heading',{name:'Teaching & timetable'})).toBeInTheDocument();
 });
 it('offers a labelled table alternative to the week grid',async()=>{
  server.use(http.get('http://localhost/api/v1/timetable/occurrences/',()=>HttpResponse.json({results:[{id:'1',date:'2026-09-21',start_time:'09:00:00',end_time:'10:00:00',course_offering_section_id:'2',employee_id:'3',room_id:'4',sequence:0}]})));
  render(<TimetableApp user={reader}/>);
  await screen.findByText('09:00–10:00');
  fireEvent.mouseDown(screen.getByRole('combobox',{name:'View'}));
  fireEvent.click(screen.getByRole('option',{name:'Accessible list'}));
  expect(screen.getByRole('table',{name:'Published teaching schedule'})).toBeInTheDocument();
 });
 it('disables refresh when offline and explains why',async()=>{
  vi.spyOn(navigator,'onLine','get').mockReturnValue(false);
  server.use(http.get('http://localhost/api/v1/timetable/occurrences/',()=>HttpResponse.json({results:[]})));
  render(<TimetableApp user={reader}/>);
  expect(screen.getByText(/You are offline/)).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Refresh'})).toBeDisabled();
  await screen.findByText(/No published classes/);
 });
 it('shows denied access without requesting timetable records',()=>{
  render(<TimetableApp user={{...reader,permissions:[]}}/>);
  expect(screen.getByText(/You do not have timetable access/)).toBeInTheDocument();
 });
});
