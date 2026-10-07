import {useState} from 'react';
import {Alert,Button,Stack} from '@mui/material';
import {authenticatedFetch} from '../auth/session';
import {message} from '../common-reference/api';
export function ReportDownload({from,to,disabled}:{from:string;to:string;disabled:boolean}){
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function download(){setBusy(true);setError('');try{const response=await authenticatedFetch(`/timetable/workload/export/?date_from=${from}&date_to=${to}`);if(!response.ok)throw new Error('Workload export unavailable. Check your permissions.');const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download='workload.csv';link.click();URL.revokeObjectURL(url);}catch(e){setError(message(e));}finally{setBusy(false);}}
 return <Stack>{error&&<Alert severity="error">{error}</Alert>}<Button disabled={disabled||busy} onClick={()=>void download()}>Download workload CSV</Button></Stack>;
}
