import {useState,useEffect} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Autocomplete,TextField,Button,Stack,Alert} from '@mui/material';
import {get,title,type Row,type Field} from './api';
export function ParentInput({field,value,onChange,disabled}:{field:Field;value:unknown;onChange:(v:unknown)=>void;disabled:boolean}){
 const [search,setSearch]=useState(''),[term,setTerm]=useState(''),[page,setPage]=useState(1),[options,setOptions]=useState<Row[]>([]);
 useEffect(()=>{const t=setTimeout(()=>{setTerm(search);setPage(1);},250);return()=>clearTimeout(t);},[search]);
 const base=field.reference?'/reference/':'/organization/';
 const list=useQuery({queryKey:['org-parent',base,field.parent,term,page],queryFn:({signal})=>get<{results:Row[];next:string|null}>(`${base}${field.parent}/?search=${encodeURIComponent(term)}&page=${page}`,signal),retry:false});
 useEffect(()=>{if(list.data)setOptions(old=>page===1?list.data.results:[...old,...list.data.results]);},[list.data,page]);
 const detail=useQuery({queryKey:['org-parent-detail',base,field.parent,value],enabled:!!value,queryFn:({signal})=>get<Row>(`${base}${field.parent}/${value}/`,signal),retry:false});
 const id=(row:Row)=>row[field.name]??row[Object.keys(row).find(k=>k.endsWith('_id'))!];
 const selected=detail.data||null;
 const rows=selected&&!options.some(row=>id(row)===id(selected))?[selected,...options]:options;
 return <Stack spacing={1}><Autocomplete<Row> disabled={disabled} options={rows} value={selected} filterOptions={x=>x} loading={list.isFetching} isOptionEqualToValue={(a,b)=>id(a)===id(b)} getOptionLabel={row=>title(row)+(row.effective_active===false?' (unavailable)':'')} onChange={(_,row)=>onChange(row?id(row):null)} onInputChange={(_,text,reason)=>{if(reason==='input')setSearch(text);}} renderInput={params=><TextField {...params} label={field.label} required={field.required}/>}/>{list.data?.next&&<Button onClick={()=>setPage(p=>p+1)} disabled={list.isFetching}>More choices</Button>}{(list.error||detail.error)&&<Alert severity="error">Parent choices are unavailable or outside your scope.</Alert>}</Stack>;
}
