import {request} from '../common-reference/api';
export type Page<T> = {count:number;next:string|null;results:T[]};
export type Lookup = {id:string;label:string;offering_id?:string};
export type Row = {id:string;version:number;[key:string]:unknown};
export type Occurrence = {id:string;session_id:string;course_offering_section_id:string;class_section_id:string;batch_id:string|null;employee_id:string;room_id:string;date:string;start_time:string;end_time:string;sequence:number;course_label?:string;employee_label?:string;room_label?:string};
export type Result = {id:string;version:number|null;resource:string};
export async function allPages<T>(path:string):Promise<T[]> {
 const result:T[]=[];
 for(let page=1;page<=50;page++){
  const data=await request<Page<T>>(`/timetable/${path}${path.includes('?')?'&':'?'}page=${page}&page_size=100`);
  result.push(...data.results);
  if(!data.next)return result;
 }
 throw new Error('Too many records for this workspace. Narrow the selected scope.');
}
export function command(operation:string,data:Record<string,unknown>,key:string){
 return request<Result>(`/timetable/commands/${operation}/`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body:JSON.stringify(data)});
}
