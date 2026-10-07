import {useEffect,useState} from 'react';
import {Alert,Box,Button,Chip,Dialog,DialogActions,DialogContent,DialogTitle,FormControlLabel,Checkbox,MenuItem,Paper,Stack,Table,TableBody,TableCell,TableContainer,TableHead,TableRow,TablePagination,TextField,Typography,LinearProgress} from '@mui/material';
import {ApiError,request,message} from './api';
import {label,maintainer,payload,permitted,type Resource,type RecordData,type User} from './resources';
import {ParentSelect} from './ParentSelect';
type Page={count:number;results:RecordData[]};
export function ReferencePage({resource:r,user}:{resource:Resource;user:User}) {
 const [data,setData]=useState<Page>({count:0,results:[]}),[search,setSearch]=useState(''),[active,setActive]=useState('true'),[ordering,setOrdering]=useState(r.id),[page,setPage]=useState(0),[size,setSize]=useState(25),[parent,setParent]=useState<number|null>(null),[uncategorized,setUncategorized]=useState(false);
 const [loading,setLoading]=useState(true),[failure,setFailure]=useState(''),[notice,setNotice]=useState(''),[revision,setRevision]=useState(0),[editing,setEditing]=useState<RecordData|null|undefined>(undefined),[toggle,setToggle]=useState<RecordData|null>(null),[saving,setSaving]=useState(false);
 useEffect(()=>{const controller=new AbortController();setLoading(true);setFailure('');
  const query=new URLSearchParams({search,is_active:active,ordering,page:String(page+1),page_size:String(size)});
  if(r.parent&&parent)query.set(r.parent.field,String(parent));
  if(uncategorized)query.set('uncategorized','true');
  const timer=setTimeout(()=>request<Page>(`/reference/${r.path}/?${query}`,{signal:controller.signal}).then(setData).catch(e=>{if(!controller.signal.aborted){setFailure(message(e));setData({count:0,results:[]});}}).finally(()=>{if(!controller.signal.aborted)setLoading(false);}),250);
  return()=>{clearTimeout(timer);controller.abort();};
 },[r.path,search,active,ordering,page,size,parent,uncategorized,revision]);
 async function open(row:RecordData) {setFailure('');try{setEditing(await request<RecordData>(`/reference/${r.path}/${row[r.id]}/`));}catch(e){setFailure(message(e));}}
 async function changeActive(){if(!toggle)return;setSaving(true);try{await request(`/reference/${r.path}/${toggle[r.id]}/`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({is_active:!toggle.is_active})});setToggle(null);setNotice('Active status updated.');setPage(0);setRevision(n=>n+1);}catch(e){setFailure(message(e));setToggle(null);}finally{setSaving(false);}}
 return <Stack spacing={3}>
 <Stack direction="row" sx={{justifyContent:"space-between",alignItems:"center"}}><Box><Typography variant="overline" color="text.secondary">Common reference</Typography><Typography component="h1" variant="h4">{r.title}</Typography></Box>{permitted(user,r,'add')&&<Button variant="contained" onClick={()=>setEditing(null)}>Add record</Button>}</Stack>
 <Typography color="text.secondary">Manage shared values used throughout SIMS. Changes apply across the platform.</Typography>
 {notice&&<Alert onClose={()=>setNotice('')}>{notice}</Alert>}{failure&&<Alert severity="error" action={<Button onClick={()=>setRevision(n=>n+1)}>Reload list</Button>}>{failure}</Alert>}
 <Paper variant="outlined" sx={{p:2}}><Stack spacing={2}>
 <Box sx={{display:'grid',gap:2,gridTemplateColumns:{xs:'1fr',md:'2fr 1fr 1fr'}}}>
 <TextField label={`Search ${r.title.toLowerCase()}`} value={search} onChange={e=>{setSearch(e.target.value.slice(0,150));setPage(0);}}/>
 <TextField select label="Visibility" value={active} onChange={e=>{setActive(e.target.value);setPage(0);}}><MenuItem value="true">Available for selection</MenuItem>{maintainer(user)&&<MenuItem value="false">Deactivated records</MenuItem>}{maintainer(user)&&<MenuItem value="all">All records</MenuItem>}</TextField>
 <TextField select label="Order by" value={ordering} onChange={e=>{setOrdering(e.target.value);setPage(0);}}>{[r.id,...r.fields.filter(f=>!f.boolean).map(f=>f.name)].flatMap(field=>[<MenuItem key={field} value={field}>{field===r.id?'ID':r.fields.find(f=>f.name===field)?.label} (ascending)</MenuItem>,<MenuItem key={'-'+field} value={'-'+field}>{field===r.id?'ID':r.fields.find(f=>f.name===field)?.label} (descending)</MenuItem>])}</TextField></Box>
 {r.parent&&!uncategorized&&<ParentSelect path={r.parent.path} value={parent} title={`Filter by ${r.parent.label.toLowerCase()}`} onChange={id=>{setParent(id);setPage(0);}}/>}
 {r.path==='castes'&&<FormControlLabel control={<Checkbox checked={uncategorized} onChange={e=>{setUncategorized(e.target.checked);setParent(null);setPage(0);}}/>} label="Uncategorized castes only"/>}
 </Stack></Paper>
 <Paper variant="outlined" sx={{overflow:'hidden'}}>{loading&&<LinearProgress aria-label="Loading reference records"/>}<TableContainer><Table aria-label={r.title} sx={{minWidth:650}}><TableHead><TableRow><TableCell>ID</TableCell><TableCell>Name / code</TableCell>{r.parent&&<TableCell>{r.parent.label}</TableCell>}<TableCell>Status</TableCell><TableCell align="right">Actions</TableCell></TableRow></TableHead><TableBody>
 {!loading&&data.results.length===0&&<TableRow><TableCell colSpan={r.parent?5:4}><Typography sx={{py:4,textAlign:'center'}}>{failure?'Records could not be loaded.':'No records match these filters.'}</Typography></TableCell></TableRow>}
 {!loading&&data.results.map(row=><TableRow key={String(row[r.id])}><TableCell>{row[r.id]}</TableCell><TableCell><Typography sx={{fontWeight:600}}>{label(r,row)}</Typography><Typography variant="body2" color="text.secondary">{r.fields.filter(f=>f.name.includes('code')).map(f=>row[f.name]).filter(Boolean).join(' · ')}</Typography></TableCell>{r.parent&&<TableCell>{row[r.parent.field.replace(/_id$/,'_label')]??'Uncategorized'}</TableCell>}<TableCell><Chip size="small" label={!row.is_active?'Deactivated':row.effective_active?'Available':'Parent unavailable'} color={row.effective_active?'success':'default'} variant="outlined"/></TableCell><TableCell align="right"><Button onClick={()=>open(row)}>{permitted(user,r,'change')?'Edit':'View'}</Button>{permitted(user,r,'change')&&<Button color={row.is_active?'warning':'primary'} onClick={()=>setToggle(row)}>{row.is_active?'Deactivate':'Reactivate'}</Button>}</TableCell></TableRow>)}
 </TableBody></Table></TableContainer><TablePagination component="div" count={data.count} page={page} rowsPerPage={size} rowsPerPageOptions={[10,25,50,100]} onPageChange={(_,p)=>setPage(p)} onRowsPerPageChange={e=>{setSize(Number(e.target.value));setPage(0);}}/></Paper>
 {editing!==undefined&&<Editor resource={r} record={editing} canWrite={permitted(user,r,editing?'change':'add')} close={()=>setEditing(undefined)} saved={()=>{setEditing(undefined);setNotice('Record saved.');setPage(0);setRevision(n=>n+1);}}/>}
 <Dialog open={!!toggle} onClose={()=>{if(!saving)setToggle(null);}} aria-labelledby="active-title"><DialogTitle id="active-title">{toggle?.is_active?'Deactivate':'Reactivate'} {toggle?label(r,toggle):''}?</DialogTitle><DialogContent><Typography>Deactivation preserves existing relationships. Records with inactive parents are excluded from new dropdown choices. Reactivation makes this record selectable only when its ancestors are active.</Typography></DialogContent><DialogActions><Button disabled={saving} onClick={()=>setToggle(null)}>Cancel</Button><Button disabled={saving} onClick={changeActive}>Confirm {toggle?.is_active?'deactivation':'reactivation'}</Button></DialogActions></Dialog>
 </Stack>;
}
function Editor({resource:r,record,canWrite,close,saved}:{resource:Resource;record:RecordData|null;canWrite:boolean;close:()=>void;saved:()=>void}) {
 const [values,setValues]=useState<RecordData>(()=>record?{...record}:Object.fromEntries(r.fields.map(f=>[f.name,f.boolean?true:'']))),[errors,setErrors]=useState<Record<string,unknown>>({}),[failure,setFailure]=useState(''),[busy,setBusy]=useState(false);
 const dirty=JSON.stringify(payload(r,values))!==JSON.stringify(payload(r,record||Object.fromEntries(r.fields.map(f=>[f.name,f.boolean?true:'']))));
 useEffect(()=>{const warn=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[dirty]);
 useEffect(()=>{
  const guard=(event:MouseEvent)=>{
   const target=event.target instanceof Element?event.target.closest('a[href], [data-leave-editor]'):null;
   if(target&&dirty&&!window.confirm('Discard unsaved changes?')){event.preventDefault();event.stopPropagation();}
  };
  document.addEventListener('click',guard,true);
  return()=>document.removeEventListener('click',guard,true);
 },[dirty]);
 function dismiss(){if(!busy&&(!dirty||window.confirm('Discard unsaved changes?')))close();}
 function update(name:string,value:RecordData[string]){setValues(v=>({...v,[name]:value}));setErrors(e=>({...e,[name]:undefined}));}
 async function submit(e:React.FormEvent){e.preventDefault();if(!canWrite||busy)return;setFailure('');setErrors({});if(r.parent&&!r.parent.optional&&!values[r.parent.field]){setErrors({[r.parent.field]:'Select a parent.'});return;}setBusy(true);
 try{await request(`/reference/${r.path}/${record?String(record[r.id])+'/':''}`,{method:record?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload(r,values))});saved();}catch(e){setFailure(message(e));if(e instanceof ApiError)setErrors(e.details);}finally{setBusy(false);}}
 return <Dialog open fullWidth maxWidth="sm" onClose={dismiss} aria-labelledby="editor-title"><Box component="form" onSubmit={submit}><DialogTitle id="editor-title">{record?(canWrite?'Edit':'View'):'Add'} {r.title.toLowerCase()} {record?`#${record[r.id]}`:''}</DialogTitle><DialogContent><Stack spacing={2} sx={{pt:1}}>
 {failure&&<Alert severity="error">{failure} {errors.non_field_errors?String(errors.non_field_errors):''}</Alert>}
 {record&&!record.effective_active&&<Alert severity="info">This record is unavailable for new selections. Its historical relationships are preserved.</Alert>}
 <Box component="fieldset" disabled={!canWrite||busy} sx={{border:0,p:0,m:0,minWidth:0}}><Stack spacing={2}>
 {r.parent&&<><ParentSelect disabled={!canWrite||busy} path={r.parent.path} value={Number(values[r.parent.field])||null} onChange={id=>update(r.parent!.field,id)} title={r.parent.label+(r.parent.optional?' (optional)':'')} error={errors[r.parent.field]?String(errors[r.parent.field]):undefined}/>{r.parent.optional&&<Typography variant="caption">Clear the social category to mark this caste as uncategorized.</Typography>}</>}
 {r.fields.map(f=>f.boolean?<FormControlLabel key={f.name} control={<Checkbox checked={values[f.name]===true} onChange={e=>update(f.name,e.target.checked)}/>} label={f.label}/>:<TextField key={f.name} label={f.label} required={!f.optional} value={values[f.name]??''} onChange={e=>update(f.name,e.target.value)} error={!!errors[f.name]} helperText={errors[f.name]?String(errors[f.name]):`Maximum ${f.max} characters${f.optional?' · Optional':''}`} multiline={f.name==='description'} minRows={f.name==='description'?3:undefined}/>)}</Stack></Box>
 </Stack></DialogContent><DialogActions><Button onClick={dismiss} disabled={busy}>{canWrite?'Cancel':'Close'}</Button>{canWrite&&<Button variant="contained" type="submit" disabled={busy}>{busy?'Saving…':'Save record'}</Button>}</DialogActions></Box></Dialog>;
}
