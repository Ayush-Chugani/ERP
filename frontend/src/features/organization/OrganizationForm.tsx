import {useEffect,useState} from 'react';
import {useForm,Controller} from 'react-hook-form';
import {z} from 'zod';
import {Dialog,DialogTitle,DialogContent,DialogActions,TextField,Button,Stack,Alert,MenuItem} from '@mui/material';
import {client,OrganizationError,type Resource,type Row} from './api';
import {ParentInput} from './ParentInput';
export function OrganizationForm({resource:r,record,onClose,onSaved}:{resource:Resource;record:Row|null;onClose:()=>void;onSaved:()=>void}){
 const {control,handleSubmit,formState:{isDirty},setError}=useForm<Row>({defaultValues:Object.fromEntries(r.fields.map(f=>[f.name,record?.[f.name]??f.default??(f.kind==='parent'?null:'')]))});
 const [failure,setFailure]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{const handler=(event:BeforeUnloadEvent)=>{if(isDirty){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',handler);return()=>window.removeEventListener('beforeunload',handler);},[isDirty]);
 useEffect(()=>{
  const guard=(event:MouseEvent)=>{
   const target=event.target instanceof Element?event.target.closest('a[href], [data-leave-editor]'):null;
   if(target&&(busy||isDirty&&!window.confirm('Discard unsaved changes?'))){event.preventDefault();event.stopPropagation();}
  };
  document.addEventListener('click',guard,true);return()=>document.removeEventListener('click',guard,true);
 },[isDirty,busy]);
 const close=()=>{if(!busy&&(!isDirty||window.confirm('Discard unsaved changes?')))onClose();};
 async function submit(data:Row){
  const shape:Record<string,z.ZodType>={};
  for(const f of r.fields){
   let validator:z.ZodType=f.kind==='number'||f.kind==='parent'?z.coerce.number().int().positive():f.choices.length?z.enum(f.choices.map(c=>c[0]) as [string,...string[]]):z.string().trim().min(f.required?1:0).max(f.max||1000);
   if(!f.required)validator=validator.nullable();
   if(data[f.name]==='')data[f.name]=f.required?'':null;
   shape[f.name]=validator;
  }
  for(const name of Object.keys(data))if(name.endsWith('_code')&&typeof data[name]==='string')data[name]=(data[name] as string).normalize('NFC').trim().toUpperCase();
  const parsed=z.object(shape).safeParse(data);
  if(!parsed.success){for(const issue of parsed.error.issues)setError(String(issue.path[0]),{message:issue.message});return;}
  setBusy(true);setFailure('');
  try{await client.request({url:`/organization/${r.path}/${record?record[r.id]+'/':''}`,method:record?'PATCH':'POST',data:parsed.data});onSaved();}
  catch(error){setFailure(error instanceof Error?error.message:'Save failed.');if(error instanceof OrganizationError)for(const [key,value]of Object.entries(error.details))setError(key,{message:String(value)});}
  finally{setBusy(false);}
 }
 return <Dialog open fullWidth maxWidth="sm" onClose={close} aria-labelledby="org-form-title"><form onSubmit={handleSubmit(submit)}><DialogTitle id="org-form-title">{record?'Edit':'Create'} {r.title}</DialogTitle><DialogContent><Stack spacing={2} sx={{pt:1}}>{failure&&<Alert severity="error">{failure}</Alert>}{r.fields.map(f=><Controller key={f.name} name={f.name} control={control} render={({field,fieldState})=><Stack>{f.kind==='parent'?<ParentInput field={f} value={field.value} onChange={field.onChange} disabled={busy||!!record&&f.name===r.parent+'_id'}/>:<TextField {...field} value={field.value??''} label={f.label} required={f.required} disabled={busy} select={!!f.choices.length} type={f.kind==='number'?'number':'text'} error={!!fieldState.error} helperText={fieldState.error?.message}>{f.choices.map(([value,name])=><MenuItem key={value} value={value}>{name}</MenuItem>)}</TextField>}{f.kind==='parent'&&fieldState.error&&<Alert severity="error">{fieldState.error.message}</Alert>}</Stack>}/>)}</Stack></DialogContent><DialogActions><Button disabled={busy} onClick={close}>Cancel</Button><Button type="submit" variant="contained" disabled={busy}>{busy?'Saving…':'Save'}</Button></DialogActions></form></Dialog>;
}
