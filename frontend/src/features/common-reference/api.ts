import { authenticatedFetch } from '../auth/session';
export class ApiError extends Error {
 constructor(public status:number, message:string, public details:Record<string,unknown>={}) {super(message);}
}
export async function request<T>(path:string,init:RequestInit={}):Promise<T> {
 let response:Response;
 try {response=await authenticatedFetch(path,init);} catch(error) {
  if(error instanceof DOMException && error.name==='AbortError') throw error;
  throw new ApiError(0,'Unable to reach the server. Check your connection. If you were saving, reload the list before retrying: the change may have reached the server.');
 }
 const data=await response.json().catch(()=>null);
 if(!response.ok) {
  if(response.status===401) window.dispatchEvent(new Event('sims-session-expired'));
  // Backend contract is the {"error":{...}} envelope, but plain DRF/Django
  // errors use {"detail":...}. Surface those cleanly instead of raw JSON.
  const detail = (data as {detail?: unknown} | null)?.detail;
  const detailText = typeof detail === 'string' ? detail
   : Array.isArray(detail) ? detail.map(String).join(' ') : '';
  const details = (data as {error?: {details?: Record<string,unknown>}} | null)?.error?.details
   || (detail !== undefined ? {detail} : {});
  throw new ApiError(response.status, (data as {error?: {message?: string}} | null)?.error?.message || detailText || `Request failed (${response.status}).`,details);
 }
 return data as T;
}
export function message(error:unknown) {return error instanceof Error ? error.message : 'Something went wrong. Please try again.';}
