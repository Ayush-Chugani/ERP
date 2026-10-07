import {useEffect,useState} from 'react';
import {Alert,Button} from '@mui/material';
import {request,message} from '../common-reference/api';
export function SupportBanner(){
 const [session,setSession]=useState<{session_id:string;target_user_id:number;expires_at:string}|null>(null),[failure,setFailure]=useState('');
 useEffect(()=>{let alive=true;const refresh=()=>request<{support_session:typeof session}>('/security/context/').then(data=>{if(alive)setSession(data.support_session);}).catch(()=>{if(alive)setSession(null);});void refresh();const timer=setInterval(refresh,30000);window.addEventListener('sims-support-session',refresh);return()=>{alive=false;clearInterval(timer);window.removeEventListener('sims-support-session',refresh);};},[]);
 if(!session)return null;
 return <Alert severity="warning" action={<Button onClick={async()=>{try{await request(`/security/support-sessions/${session.session_id}/`,{method:'DELETE'});setSession(null);}catch(e){setFailure(message(e));}}}>End session</Button>}>Read-only support session for user {session.target_user_id}, until {new Date(session.expires_at).toLocaleString()}. Only integrated support views use this identity. {failure}</Alert>;
}
