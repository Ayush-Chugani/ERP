import {useCallback,useEffect,useRef,useState} from 'react';
import {PageHeader} from '../../components/feedback';
import {Alert,Box,Button,Chip,Divider,FormControl,InputLabel,LinearProgress,MenuItem,Paper,Select,Stack,Table,TableBody,TableCell,TableHead,TableRow,TextField,Typography} from '@mui/material';
import type {User} from '../common-reference/resources';
import {request,message} from '../common-reference/api';
import {authenticatedFetch} from '../auth/session';
import {allPages,command,type Lookup,type Row,type Occurrence} from './api';
import {AllocationImport} from './AllocationImport';
import {TimetableReports} from './TimetableReports';
import {AvailabilitySearch} from './AvailabilitySearch';
import {ReportDownload} from './ReportDownload';

type Field={name:string;label:string;type?:string;options?:string;optional?:boolean;value?:string};
type Action={operation:string;label:string;permission:string;fields:Field[]};
const id=(name:string,label:string,options?:string):Field=>({name,label,options});
const reason:Field={name:'reason',label:'Reason'};
const version:Field={name:'expected_version',label:'Current version',type:'number'};
const dates:Field[]=[{name:'effective_from',label:'First date',type:'date'},{name:'effective_to',label:'Last date',type:'date'}];
const sessionFields:Field[]=[id('course_offering_section_id','Course section','sections'),id('faculty_assignment_id','Faculty assignment','assignments'),id('room_id','Room','rooms'),id('time_slot_id','Time slot','time-slots'),{name:'day_of_week',label:'Weekday (Monday = 1)',type:'number'},...dates];
const actions:Action[]=[
 {operation:'amend-assignment',label:'Amend a planned allocation',permission:'manage_timetable',fields:[id('pk','Faculty assignment','assignments'),version,{name:'values.workload_hours',label:'Planned hours per week',type:'number'},{name:'values.start_date',label:'Assignment start',type:'date'},{name:'values.end_date',label:'Assignment end',type:'date'},reason]},
 {operation:'workload-override',label:'Authorize a temporary workload exception',permission:'override_workload',fields:[id('values.employee_id','Faculty member','employees'),{name:'values.effective_from',label:'First Monday',type:'date'},{name:'values.effective_to',label:'Last Sunday',type:'date'},{name:'values.weekly_limit',label:'Temporary weekly limit',type:'number'},reason]},
 {operation:'create-revision',label:'Create a draft revision',permission:'manage_timetable',fields:[id('offering_id','Programme and term','offerings'),{name:'name',label:'Timetable name'},reason]},
 {operation:'create-assignment',label:'Allocate faculty',permission:'manage_timetable',fields:[id('course_offering_section_id','Course section','sections'),id('employee_id','Faculty member','employees'),id('assignment_role','Role','roles'),{name:'workload_hours',label:'Planned hours per week',type:'number'},{name:'start_date',label:'Assignment start',type:'date'},{name:'end_date',label:'Assignment end',type:'date'},reason]},
 {operation:'transition-assignment',label:'Activate or close an allocation',permission:'manage_timetable',fields:[id('pk','Faculty assignment','assignments'),version,id('target','New status','assignment-statuses'),reason]},
 {operation:'save-session',label:'Schedule or reschedule a class',permission:'manage_timetable',fields:[id('revision_id','Draft revision','revisions'),version,{name:'pk',label:'Existing session to reschedule (optional)',options:'sessions',optional:true},...sessionFields.map(f=>({...f,name:'values.'+f.name})),reason]},
 {operation:'remove-session',label:'Remove a draft class',permission:'manage_timetable',fields:[id('revision_id','Draft revision','revisions'),id('pk','Session','sessions'),version,reason]},
 {operation:'transition-revision',label:'Submit, approve or publish a revision',permission:'manage_timetable',fields:[id('pk','Revision','revisions'),version,id('target','New status','revision-statuses'),reason]},
 {operation:'attest-availability',label:'Record resource availability',permission:'manage_timetable',fields:[{...id('room_id','Room (choose room or faculty)','rooms'),optional:true},{...id('employee_id','Faculty (choose room or faculty)','employees'),optional:true},{name:'day_of_week',label:'Weekday (Monday = 1)',type:'number'},...dates,{name:'start_time',label:'Available from',type:'time'},{name:'end_time',label:'Available until',type:'time'},reason]},
 {operation:'exception',label:'Cancel, move or substitute a published class',permission:'change_occurrence',fields:[id('occurrence_id','Published class','occurrences'),{name:'expected_sequence',label:'Current change sequence',type:'number',value:'0'},id('values.kind','Change type','exception-types'),{name:'values.date',label:'Effective date',type:'date'},{name:'values.start_time',label:'Start time',type:'time'},{name:'values.end_time',label:'End time',type:'time'},id('values.room_id','Room','rooms'),id('values.faculty_assignment_id','Faculty assignment','assignments'),reason]},
 {operation:'cancel-job',label:'Cancel a generation job',permission:'manage_timetable',fields:[id('pk','Generation job','jobs'),version,reason]},
 {operation:'accept-job',label:'Accept a generated candidate into a draft',permission:'manage_timetable',fields:[id('pk','Generation job','jobs'),version,{name:'candidate_index',label:'Candidate number (0, 1 or 2)',type:'number',value:'0'},reason]},
 {operation:'configure-policy',label:'Configure workload policy',permission:'configure_timetable',fields:[id('institution_id','Institution','institutions'),{...version,optional:true},{name:'values.weekly_limit',label:'Maximum teaching hours per week',type:'number'},{name:'values.require_competency',label:'Require current course competency',options:'booleans',value:'true'},reason]},
];
const initialDate=new Date().toISOString().slice(0,10);
const weekEnd=()=>{const d=new Date();d.setDate(d.getDate()+6);return d.toISOString().slice(0,10);};

export function TimetableApp({user}:{user:User}){
 const can=useCallback((permission:string)=>user.is_superuser||user.permissions.includes('teaching_timetable.'+permission),[user]);
 const [from,setFrom]=useState(initialDate),[to,setTo]=useState(weekEnd),[rows,setRows]=useState<Occurrence[]>([]);
 const [lookups,setLookups]=useState<Record<string,Lookup[]>>({}),[records,setRecords]=useState<Record<string,Row[]>>({});
 const [busy,setBusy]=useState(false),[failure,setFailure]=useState(''),[notice,setNotice]=useState(''),[online,setOnline]=useState(navigator.onLine);
 const [layout,setLayout]=useState('week'),[filter,setFilter]=useState(''),[filterKind,setFilterKind]=useState('employee_id');
 const [actionName,setActionName]=useState('create-revision'),[tab,setTab]=useState('schedule');
 const retry=useRef<{body:string;key:string}|null>(null);
 const load=useCallback(async()=>{
  setBusy(true);setFailure('');
  try{
   if(can('view_schedule'))setRows((await request<{results:Occurrence[]}>(`/timetable/occurrences/?date_from=${from}&date_to=${to}`)).results);
   if(can('manage_timetable')){
    const names=['offerings','sections','rooms','employees','time-slots','institutions','policies'];
    const lookupValues=await Promise.all(names.map(name=>allPages<Lookup>(`lookups/${name}/`)));
    setLookups(Object.fromEntries(names.map((name,index)=>[name,lookupValues[index]])));
    const resources=['assignments','revisions','sessions','jobs'];
    const values=await Promise.all(resources.map(name=>allPages<Row>(`${name}/`)));
    setRecords(Object.fromEntries(resources.map((name,index)=>[name,values[index]])));
   }
  }catch(error){setFailure(message(error));}finally{setBusy(false);}
 },[can,from,to]);
 useEffect(()=>{void load();},[load]);
 useEffect(()=>{const update=()=>setOnline(navigator.onLine);window.addEventListener('online',update);window.addEventListener('offline',update);return()=>{window.removeEventListener('online',update);window.removeEventListener('offline',update);};},[]);
 const label=(resource:string,value:unknown)=>lookups[resource]?.find(row=>row.id===String(value))?.label||String(value??'Unassigned');
 const options:Record<string,Lookup[]>={...lookups,
  roles:['PRIMARY_INSTRUCTOR','CO_INSTRUCTOR','LAB_INSTRUCTOR','TUTOR','COORDINATOR','OTHER'].map(v=>({id:v,label:v.replaceAll('_',' ')})),
  'assignment-statuses':['ACTIVE','COMPLETED','CANCELLED'].map(v=>({id:v,label:v})),
  'revision-statuses':['DRAFT','REVIEW',...(can('approve_timetable')?['APPROVED']:[]),...(can('publish_timetable')?['PUBLISHED','WITHDRAWN']:[]),'ARCHIVED'].map(v=>({id:v,label:v})),
  'exception-types':['CANCEL','MOVE','SUBSTITUTE'].map(v=>({id:v,label:v})),booleans:[{id:'true',label:'Yes'},{id:'false',label:'No'}],
  occurrences:rows.map(row=>({id:row.id,label:`${row.date} ${row.start_time} / change ${row.sequence}`})),
  ...Object.fromEntries(Object.entries(records).map(([name,items])=>[name,items.map(row=>({id:row.id,label:name==='assignments'?`${row.employee_label||label('employees',row.employee_id)} / ${row.course_label||label('sections',row.course_offering_section_id)} / ${row.assignment_status} / v${row.version}`:`#${row.id} ${row.status??''} / v${row.version}`}))])),
 };
 const action=actions.find(item=>item.operation===actionName)!;
 async function submit(operation:string,data:Record<string,unknown>){
  if(!online)return;
  setBusy(true);setFailure('');setNotice('');
  const body=JSON.stringify({operation,data});
  if(retry.current?.body!==body)retry.current={body,key:crypto.randomUUID()};
  try{const result=await command(operation,data,retry.current.key);retry.current=null;setNotice(`Saved successfully. Record ${result.id}${result.version?`, version ${result.version}`:''}.`);await load();}
  catch(error){setFailure(message(error));}finally{setBusy(false);}
 }
 function formSubmit(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();const data:Record<string,unknown>={};
  for(const field of action.fields){
   const raw=String(new FormData(event.currentTarget).get(field.name)??'');
   if(!raw&&field.optional)continue;
   const value=field.type==='number'?Number(raw):field.options==='booleans'?raw==='true':raw;
   if(field.name.startsWith('values.')){const nested=(data.values??{}) as Record<string,unknown>;nested[field.name.slice(7)]=value;data.values=nested;}else data[field.name]=value;
  }
  void submit(action.operation,data);
 }
 async function exportCsv(){
  try{const response=await authenticatedFetch(`/timetable/export/?date_from=${from}&date_to=${to}`);if(!response.ok)throw new Error('Export unavailable. Check your permissions.');const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download='timetable.csv';link.click();URL.revokeObjectURL(url);}catch(error){setFailure(message(error));}
 }
 const visible=rows.filter(row=>!filter||String(row[filterKind as keyof Occurrence])===filter);
 if(!can('view_schedule')&&!can('manage_timetable'))return <Alert severity="info">You do not have timetable access. Contact your institution administrator.</Alert>;
 return <Stack spacing={3}>
  <Box><Typography variant="overline" color="primary">Academic operations</Typography><PageHeader overline="Academic core" title="Teaching & timetable"/><Typography color="text.secondary">Plan teaching, resolve conflicts and publish a dependable schedule.</Typography></Box>
  {!online&&<Alert severity="warning">You are offline. Reconnect to load current schedules or make changes.</Alert>}
  {failure&&<Alert severity="error">{failure} Reload current records before changing a stale version.</Alert>}{notice&&<Alert severity="success">{notice}</Alert>}{busy&&<LinearProgress aria-label="Loading timetable"/>}
  <Stack direction="row" spacing={1}><Button variant={tab==='schedule'?'contained':'outlined'} onClick={()=>setTab('schedule')}>Published schedule</Button>{can('manage_timetable')&&<Button variant={tab==='planning'?'contained':'outlined'} onClick={()=>setTab('planning')}>Planning workspace</Button>}<Button onClick={()=>void load()} disabled={busy||!online}>Refresh</Button></Stack>
  {tab==='schedule'?<>
   <Stack direction={{xs:'column',sm:'row'}} spacing={2}>
    <TextField label="From" type="date" value={from} onChange={e=>setFrom(e.target.value)} slotProps={{inputLabel:{shrink:true}}}/><TextField label="To" type="date" value={to} onChange={e=>setTo(e.target.value)} slotProps={{inputLabel:{shrink:true}}}/>
    <TextField select label="View" value={layout} onChange={e=>setLayout(e.target.value)} sx={{minWidth:130}}><MenuItem value="week">Week grid</MenuItem><MenuItem value="list">Accessible list</MenuItem></TextField>
    <Button onClick={()=>window.print()}>Print</Button>{can('export_timetable')&&<Button onClick={()=>void exportCsv()} disabled={!online}>Download CSV</Button>}
   </Stack>
   <Stack direction="row" spacing={2}><TextField select label="Filter by" value={filterKind} onChange={e=>{setFilterKind(e.target.value);setFilter('');}} sx={{minWidth:160}}>{[['employee_id','Faculty'],['room_id','Room'],['class_section_id','Class section'],['batch_id','Batch']].map(([value,title])=><MenuItem key={value} value={value}>{title}</MenuItem>)}</TextField><TextField select label="Resource" value={filter} onChange={e=>setFilter(e.target.value)} sx={{minWidth:190}}><MenuItem value="">All visible resources</MenuItem>{Array.from(new Set(rows.map(row=>String(row[filterKind as keyof Occurrence]??'')))).filter(Boolean).map(value=><MenuItem key={value} value={value}>{filterKind==='employee_id'?label('employees',value):filterKind==='room_id'?label('rooms',value):value}</MenuItem>)}</TextField></Stack>
   {!busy&&!visible.length&&<Alert severity="info">No published classes in this date range. Drafts appear in the planning workspace.</Alert>}
   {layout==='list'?<Paper variant="outlined" sx={{overflowX:'auto'}}><Table aria-label="Published teaching schedule"><TableHead><TableRow>{['Date','Time','Course section','Faculty','Room','Change sequence'].map(text=><TableCell key={text}>{text}</TableCell>)}</TableRow></TableHead><TableBody>{visible.map(row=><TableRow key={row.id}><TableCell>{row.date}</TableCell><TableCell>{row.start_time.slice(0,5)}–{row.end_time.slice(0,5)}</TableCell><TableCell>{row.course_label||label('sections',row.course_offering_section_id)}</TableCell><TableCell>{row.employee_label||label('employees',row.employee_id)}</TableCell><TableCell>{row.room_label||label('rooms',row.room_id)}</TableCell><TableCell>{row.sequence}</TableCell></TableRow>)}</TableBody></Table></Paper>:<Box sx={{display:'grid',gridTemplateColumns:{xs:'1fr',md:'repeat(7,minmax(0,1fr))'},gap:1}}>{['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map((day,index)=><Paper variant="outlined" key={day} sx={{p:1.5,minHeight:160}}><Typography component="h2" variant="subtitle2">{day}</Typography><Divider sx={{my:1}}/>{visible.filter(row=>(new Date(row.date+'T12:00:00').getDay()+6)%7===index).map(row=><Box key={row.id} sx={{borderLeft:3,borderColor:'primary.main',pl:1,py:1,mb:1,bgcolor:'action.hover'}}><Typography variant="caption">{row.date}</Typography><Typography variant="subtitle2">{row.start_time.slice(0,5)}–{row.end_time.slice(0,5)}</Typography><Typography variant="body2">{row.course_label||label('sections',row.course_offering_section_id)}</Typography><Typography variant="caption" component="div">{row.room_label||label('rooms',row.room_id)} · {row.employee_label||label('employees',row.employee_id)}</Typography></Box>)}</Paper>)}</Box>}
  </>:<>
   <Paper variant="outlined" sx={{p:3}}><Stack spacing={2}><Typography variant="h6" component="h2">Planning actions</Typography><TextField select label="Action" value={actionName} onChange={e=>setActionName(e.target.value)}>{actions.filter(item=>can(item.permission)).map(item=><MenuItem key={item.operation} value={item.operation}>{item.label}</MenuItem>)}</TextField><Box component="form" key={actionName} onSubmit={formSubmit}><Box sx={{display:'grid',gridTemplateColumns:{xs:'1fr',md:'1fr 1fr'},gap:2}}>{action.fields.map(field=><TextField key={field.name} name={field.name} label={field.label} required={!field.optional} select={!!field.options} type={field.type||'text'} defaultValue={field.value||''} disabled={busy||!online} slotProps={{inputLabel:{shrink:true},htmlInput:field.type==='number'?{step:'any'}:{}}}>{field.options&&[<MenuItem key="empty" value="">Select…</MenuItem>,...(options[field.options]||[]).map(option=><MenuItem key={option.id} value={option.id}>{option.label}</MenuItem>)]}</TextField>)}</Box><Button type="submit" variant="contained" disabled={busy||!online} sx={{mt:2}}>Save {action.label.toLowerCase()}</Button></Box></Stack></Paper>
   <Generator options={options} revisions={records.revisions||[]} busy={busy||!online} submit={submit}/>
   <AllocationImport disabled={busy||!online} onSaved={load}/>
   <TimetableReports from={from} to={to} revisions={records.revisions||[]} disabled={busy||!online}/>
   {can('export_timetable')&&<ReportDownload from={from} to={to} disabled={busy||!online}/>}
   <AvailabilitySearch from={from} to={to} options={options} disabled={busy||!online}/>
   {['revisions','assignments','sessions','jobs'].map(resource=><Paper key={resource} variant="outlined" sx={{p:2,overflowX:'auto'}}><Typography variant="h6" component="h2" sx={{textTransform:'capitalize'}}>{resource}</Typography>{!records[resource]?.length?<Typography color="text.secondary">No {resource} yet.</Typography>:<Table size="small" aria-label={resource}><TableHead><TableRow><TableCell>Record</TableCell><TableCell>Version</TableCell><TableCell>Details</TableCell></TableRow></TableHead><TableBody>{records[resource]?.map(row=><TableRow key={row.id}><TableCell>#{row.id}</TableCell><TableCell>{row.version}</TableCell><TableCell>{resource==='assignments'?`${row.employee_label||label('employees',row.employee_id)} · ${row.assignment_role} · ${row.workload_hours} h/week · ${row.assignment_status}`:resource==='sessions'?`${row.course_label||label('sections',row.course_offering_section_id)} · ${row.room_label||label('rooms',row.room_id)} · day ${row.day_of_week} · revision ${row.revision_id}`:<><Chip size="small" label={String(row.status)}/>{resource==='jobs'&&<Typography variant="caption" component="div">{String((row.result as Record<string,unknown>)?.outcome??'')} · Candidate scores: {candidateSummary(row.result)} · {String((row.result as Record<string,unknown>)?.explanation??'')}</Typography>}</>}</TableCell></TableRow>)}</TableBody></Table>}</Paper>)}
  </>}
 </Stack>;
}

function Generator({options,revisions,busy,submit}:{options:Record<string,Lookup[]>;revisions:Row[];busy:boolean;submit:(operation:string,data:Record<string,unknown>)=>Promise<void>}){
 const [revision,setRevision]=useState(''),[assignments,setAssignments]=useState<string[]>([]),[rooms,setRooms]=useState<string[]>([]),[slots,setSlots]=useState<string[]>([]),[days,setDays]=useState<string[]>(['1']);
 function multi(label:string,items:Lookup[],values:string[],set:(values:string[])=>void){return <FormControl sx={{minWidth:180,flex:1}}><InputLabel>{label}</InputLabel><Select multiple label={label} value={values} onChange={e=>set(typeof e.target.value==='string'?e.target.value.split(','):e.target.value)}>{items.map(item=><MenuItem key={item.id} value={item.id}>{item.label}</MenuItem>)}</Select></FormControl>;}
 return <Paper variant="outlined" sx={{p:3}}><Stack component="form" spacing={2} onSubmit={event=>{event.preventDefault();const form=new FormData(event.currentTarget);const selected=revisions.find(row=>row.id===revision);if(!selected)return;const choices=assignments.map(assignmentId=>{const assignment=options.assignments.find(row=>row.id===assignmentId);const sectionId=String(form.get('section'));return rooms.flatMap(room=>slots.flatMap(slot=>days.map(day=>({course_offering_section_id:sectionId,faculty_assignment_id:assignment?.id,room_id:room,time_slot_id:slot,day_of_week:Number(day),effective_from:form.get('from'),effective_to:form.get('to')}))));});void submit('queue-job',{revision_id:revision,expected_version:selected.version,seed:0,choices,reason:form.get('reason')});}}>
  <Typography variant="h6" component="h2">Generate a candidate</Typography><Typography color="text.secondary">Choose permitted alternatives for a new class. Generation runs in the background; review its result before accepting it into a draft. Each selected assignment creates one requested session.</Typography>
  <TextField select label="Draft revision" value={revision} onChange={e=>setRevision(e.target.value)} required>{revisions.filter(row=>row.status==='DRAFT').map(row=><MenuItem key={row.id} value={row.id}>Revision #{row.id} / version {row.version}</MenuItem>)}</TextField>
  <TextField select name="section" label="Course section" defaultValue="" required>{options.sections?.map(row=><MenuItem key={row.id} value={row.id}>{row.label}</MenuItem>)}</TextField>
  <Stack direction={{xs:'column',md:'row'}} spacing={2}>{multi('Faculty assignments',options.assignments||[],assignments,setAssignments)}{multi('Rooms',options.rooms||[],rooms,setRooms)}{multi('Time slots',options['time-slots']||[],slots,setSlots)}{multi('Weekdays',['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map((label,index)=>({id:String(index+1),label})),days,setDays)}</Stack>
  <Stack direction={{xs:'column',md:'row'}} spacing={2}><TextField name="from" type="date" label="First date" required slotProps={{inputLabel:{shrink:true}}}/><TextField name="to" type="date" label="Last date" required slotProps={{inputLabel:{shrink:true}}}/><TextField name="reason" label="Reason" required fullWidth/></Stack>
  <Button type="submit" variant="outlined" disabled={busy||!assignments.length||!rooms.length||!slots.length||!days.length||rooms.length*slots.length*days.length>20}>Queue generation</Button>
 </Stack></Paper>;
}

function candidateSummary(value:unknown){
 const candidates=(value as {candidates?:{score:number}[]}|undefined)?.candidates;
 if(!Array.isArray(candidates)||!candidates.length)return 'No candidates yet';
 return candidates.map((candidate,index)=>`Candidate ${index}: ${candidate.score} idle minutes`).join(' / ');
}
