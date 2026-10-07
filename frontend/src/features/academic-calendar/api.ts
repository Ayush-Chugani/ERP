import {request} from '../common-reference/api';
export type CalendarRow = Record<string, string | number | boolean | null | string[]> & {actions:string[]};
export type CalendarField = {name:string;kind:'text'|'number'|'date'|'time'|'boolean'|'choice'|'parent';required:boolean;choices:[string,string][];max_length:number|null};
export type CalendarResource = {path:string;id:string;fields:CalendarField[];can_create:boolean};
export type Page<T> = {count:number;results:T[];next:string|null;previous:string|null};
export const calendarApi = {
 metadata:(signal?:AbortSignal)=>request<{resources:CalendarResource[]}>('/calendar/metadata/',{signal}),
 list:(path:string,query:string,signal?:AbortSignal)=>request<Page<CalendarRow>>(`/calendar/${path}/?${query}`,{signal}),
 save:(resource:CalendarResource,record:CalendarRow|null,values:Record<string,unknown>)=>request<CalendarRow>(`/calendar/${resource.path}/${record?`${record[resource.id]}/`:''}`,{method:record?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)}),
 transition:(resource:CalendarResource,record:CalendarRow,action:string,reason:string)=>request<CalendarRow>(`/calendar/${resource.path}/${record[resource.id]}/${action.replaceAll('_','-')}/`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason})}),
};
export const label=(value:string)=>value.replaceAll('_',' ').replaceAll('-',' ').replace(/^./,letter=>letter.toUpperCase());

