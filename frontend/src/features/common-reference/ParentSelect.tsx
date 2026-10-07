import {useEffect,useState} from 'react';
import {Autocomplete,TextField,Button,Stack,Alert} from '@mui/material';
import {request,message} from './api';
import {resources,label,type RecordData} from './resources';
export function ParentSelect({path,value,onChange,title,error,disabled=false}:{path:string;value:number|null;onChange:(id:number|null)=>void;title:string;error?:string;disabled?:boolean}) {
 const resource=resources.find(r=>r.path===path)!;
 const [rows,setRows]=useState<RecordData[]>([]),[selected,setSelected]=useState<RecordData|null>(null);
 const [search,setSearch]=useState(''),[page,setPage]=useState(1),[more,setMore]=useState(false),[loading,setLoading]=useState(false),[failure,setFailure]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{const control=new AbortController();setFailure('');setSelected(null);
  if(value) request<RecordData>(`/reference/${path}/${value}/`,{signal:control.signal}).then(setSelected).catch(e=>{if(!control.signal.aborted)setFailure(message(e));});
  return()=>control.abort();
 },[path,value,retry]);
 useEffect(()=>{const control=new AbortController();setLoading(true);setFailure('');
  const timer=setTimeout(()=>{request<{results:RecordData[];next:string|null}>(`/reference/${path}/?search=${encodeURIComponent(search)}&page=${page}&page_size=25`,{signal:control.signal}).then(data=>{setRows(old=>page===1?data.results:[...old,...data.results]);setMore(!!data.next);}).catch(e=>{if(!control.signal.aborted)setFailure(message(e));}).finally(()=>{if(!control.signal.aborted)setLoading(false);});},250);
  return()=>{clearTimeout(timer);control.abort();};
 },[path,search,page,retry]);
 const options=selected&&!rows.some(r=>r[resource.id]===selected[resource.id])?[selected,...rows]:rows;
 return <Stack spacing={1}><Autocomplete<RecordData> disabled={disabled} options={options} value={selected} loading={loading} filterOptions={x=>x}
  isOptionEqualToValue={(a,b)=>a[resource.id]===b[resource.id]}
  getOptionLabel={row=>`${label(resource,row)}${row.effective_active?'':' (unavailable)'}`}
  onInputChange={(_,text,reason)=>{if(reason==='input'||reason==='clear'){setSearch(text);setPage(1);}}}
  onChange={(_,row)=>{setSelected(row);onChange(row?Number(row[resource.id]):null);}}
  renderInput={params=><TextField {...params} label={title} error={!!error} helperText={error||'Search available choices. The current historical choice is retained.'}/>}/>
 {more&&<Button size="small" onClick={()=>setPage(p=>p+1)} disabled={loading}>Load more {title.toLowerCase()} choices</Button>}
 {failure&&<Alert severity="error" action={<Button onClick={()=>setRetry(n=>n+1)}>Retry</Button>}>{failure}</Alert>}</Stack>;
}
