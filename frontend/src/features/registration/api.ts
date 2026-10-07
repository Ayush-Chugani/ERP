import {request} from '../common-reference/api';
export type Row={id:string;version?:number;label?:string;[name:string]:unknown};
export type Page={count:number;next:string|null;results:Row[]};
export const getPage=(path:string)=>request<Page>('/registration/'+path);
export function command(operation:string,data:Record<string,unknown>,key:string){
 return request<Row>('/registration/commands/'+operation+'/',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body:JSON.stringify(data)});
}
export function bulk(rows:unknown[],dry_run:boolean,key:string){
 return request<{results:Row[];dry_run:boolean}>('/registration/bulk/',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body:JSON.stringify({rows,dry_run})});
}
export type Field={name:string;label:string;source?:string;choices?:string[];type?:string;optional?:boolean};
const id=(name:string,label:string,source:string,optional=false):Field=>({name,label,source,optional});
const text=(name:string,label:string,optional=false):Field=>({name,label,optional});
const number=(name:string,label:string,optional=false):Field=>({name,label,type:'number',optional});
const date:Field={name:'effective_date',label:'Effective date',type:'date'};
const reason=text('reason','Reason');
const version=number('expected_version','Current version');
const offering=id('programme_term_offering_id','Term offering','offerings');
const transition=(source:string,choices:string[]):Field[]=>[id('pk','Record',source),version,{name:'target',label:'New status',choices},reason];
export const forms:Record<string,{label:string;permission:string;fields:Field[]}>={
 'amend-course-capacity':{label:'Update course capacity',permission:'manage_registration',fields:[id('pk','Course offering','courses'),version,number('capacity','Capacity'),reason]},
 'correct-roll':{label:'Correct roll number',permission:'manage_registration',fields:[id('pk','Term registration','terms'),version,text('roll_number','Roll number'),reason]},
 'configure-policy':{label:'Configure credit policy',permission:'configure_registration',fields:[id('programme_id','Programme','lookup:programmes'),number('minimum_credits','Minimum credits'),number('maximum_credits','Maximum credits'),{...version,optional:true},reason]},
 'create-offering':{label:'Create term offering',permission:'manage_registration',fields:[id('programme_id','Programme','lookup:programmes'),id('academic_term_id','Academic term','lookup:terms'),id('curriculum_scheme_id','Curriculum scheme','lookup:schemes'),id('semester_id','Semester','lookup:semesters'),id('specialization_id','Specialization','lookup:specializations',true),reason]},
 'transition-offering':{label:'Progress term offering',permission:'manage_registration',fields:transition('offerings',['REGISTRATION_OPEN','ACTIVE','COMPLETED','CANCELLED'])},
 'save-section':{label:'Create or update section',permission:'manage_registration',fields:[id('pk','Existing section (leave empty to create)','sections',true),{...version,optional:true},{...offering,optional:true},text('section_code','Section code',true),text('section_name','Section name',true),number('capacity','Capacity',true),{name:'is_active',label:'Active',choices:['true','false'],optional:true},id('home_room_id','Home room','lookup:rooms',true),reason]},
 'save-batch':{label:'Create or update batch',permission:'manage_registration',fields:[id('pk','Existing batch (leave empty to create)','batches',true),{...version,optional:true},id('class_section_id','Class section','sections',true),text('batch_code','Batch code',true),text('batch_name','Batch name',true),number('capacity','Capacity',true),{name:'is_active',label:'Active',choices:['true','false'],optional:true},reason]},
 'approve-progression':{label:'Approve student progression',permission:'approve_progression',fields:[id('enrolment_id','Enrolment','lookup:enrolments'),id('offering_id','Term offering','offerings'),number('offering_version','Offering version'),number('enrolment_version','Enrolment version'),reason]},
 'create-draft':{label:'Create term registration',permission:'manage_registration',fields:[id('enrolment_id','Enrolment','lookup:enrolments'),id('offering_id','Term offering','offerings'),id('section_id','Class section','sections',true),id('batch_id','Batch','batches',true)]},
 'allocate':{label:'Allocate or transfer class',permission:'manage_registration',fields:[id('pk','Term registration','terms'),version,id('section_id','Destination section','sections',true),id('batch_id','Destination batch','batches',true),{name:'automatic',label:'Allocation method',choices:['false','true']},{...date,optional:true},reason]},
 'transition-term':{label:'Progress term registration',permission:'manage_registration',fields:[id('registration_id','Term registration','terms'),version,{name:'target',label:'New status',choices:['REGISTERED','APPROVED','CANCELLED','COMPLETED']},reason]},
 'create-course':{label:'Create course offering',permission:'manage_registration',fields:[offering,id('curriculum_course_id','Curriculum course','lookup:curriculum-courses',true),id('course_id','Catalog course','lookup:catalog-courses'),text('offering_code','Offering code'),number('registration_capacity','Course capacity',true),reason]},
 'transition-course':{label:'Progress course offering',permission:'manage_registration',fields:transition('courses',['OPEN','ACTIVE','COMPLETED','CANCELLED'])},
 'create-mapping':{label:'Map course to class',permission:'manage_registration',fields:[id('course_offering_id','Course offering','courses'),id('class_section_id','Class section','sections'),id('class_batch_id','Batch','batches',true),{name:'session_type',label:'Session type',choices:['LECTURE','TUTORIAL','PRACTICAL','PROJECT','SEMINAR','OTHER']},reason]},
 'register-course':{label:'Register student for course',permission:'manage_registration',fields:[id('term_id','Term registration','terms'),id('course_id','Course offering','courses'),{name:'registration_type',label:'Registration type',choices:['REGULAR','ELECTIVE','BACKLOG','REPEAT','IMPROVEMENT','AUDIT','CREDIT_TRANSFER']},reason]},
 'transition-registration':{label:'Progress course registration',permission:'manage_registration',fields:[...transition('registrations',['APPROVED','DROPPED','WITHDRAWN','COMPLETED']),date]},
 'assign-roster':{label:'Assign or transfer roster',permission:'manage_registration',fields:[id('registration_id','Course registration','registrations'),id('mapping_id','Session mapping','mappings'),version,date,reason]},
};
