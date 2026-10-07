import {request} from '../common-reference/api';
export type Row=Record<string,unknown>&{id:string;version:string;label:string;actions:string[];institution_id:string|null};
export type Field={name:string;kind:'parent'|'text'|'number'|'decimal'|'date'|'boolean'|'choice';required:boolean;choices:[string,string][];max_length:number|null;default:unknown};
export type Resource={path:string;fields:Field[];can_create:boolean;can_export:boolean};
export type Page<T>={results:T[];count:number;next:string|null};
export const label=(name:string)=>name.replaceAll('_',' ').replaceAll('-',' ').replace(/^./,s=>s.toUpperCase());
export const api={
 metadata:(signal?:AbortSignal)=>request<{resources:Resource[]}>('/curriculum/metadata/',{signal}),
 list:(path:string,query:string,signal?:AbortSignal)=>request<Page<Row>>(`/curriculum/${path}/?${query}`,{signal}),
 detail:(path:string,id:string)=>request<Row>(`/curriculum/${path}/${id}/`),
 save:(path:string,row:Row|null,values:Record<string,unknown>)=>request<Row>(`/curriculum/${path}/${row?row.id+'/':''}`,{method:row?'PATCH':'POST',headers:{'Content-Type':'application/json',...(row?{'If-Match':row.version}:{})},body:JSON.stringify(values)}),
 action:<T=Row>(path:string,row:Row,action:string,body:unknown)=>request<T>(`/curriculum/${path}/${row.id}/${action}/`,{method:'POST',headers:{'Content-Type':'application/json','If-Match':row.version},body:JSON.stringify(body)}),
};
