import {request} from '../common-reference/api';
export type Row={id:string;version?:number;[key:string]:unknown};
export type Lookup={id:string;label:string};
export type Page<T>={count:number;next:string|null;results:T[]};
export type Mark={is_eligible:boolean;id:string;version:number;student_number:string;student_name:string;attendance_status_id:string|null;status_code:string|null;remarks:string};
export type Policy={id:string;rules:Record<string,{credit:string;denominator:string}>};
export type Register={session:Row;policy:Policy;rows:Mark[]};
export function command(operation:string,data:Record<string,unknown>,key:string){
 return request<Row>('/attendance/commands/'+operation+'/',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body:JSON.stringify(data)});
}
export async function choices(resource:string,section=''){
 const data=await request<Page<Lookup>>('/attendance/lookups/'+resource+'/?page_size=100'+(section?'&section_id='+section:''));
 if(data.next)throw new Error('More than 100 choices; narrow the section or use the controlled import.');
 return data.results;
}
