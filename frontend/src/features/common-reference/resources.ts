export type User = {user_id:number;username:string; permissions:string[]; is_superuser:boolean};
export type RecordData = Record<string, string | number | boolean | null>;
export type Field = {name:string; label:string; max?:number; optional?:boolean; boolean?:boolean};
export type Resource = {path:string; title:string; model:string; id:string; fields:Field[]; parent?:{path:string; field:string; label:string; optional?:boolean}};
const text=(name:string,label:string,max:number,optional=false):Field=>({name,label,max,optional});
export const resources:Resource[] = [
 {path:'countries',title:'Countries',model:'country',id:'country_id',fields:[text('iso_code','ISO code',2),text('country_name','Country name',100)]},
 {path:'states',title:'States',model:'state',id:'state_id',fields:[text('state_code','State code',10),text('state_name','State name',100)],parent:{path:'countries',field:'country_id',label:'Country'}},
 {path:'genders',title:'Genders',model:'gender',id:'gender_id',fields:[text('gender_code','Gender code',20),text('gender_name','Gender name',50)]},
 {path:'blood-groups',title:'Blood groups',model:'bloodgroup',id:'blood_group_id',fields:[text('blood_group_code','Blood group code',5)]},
 {path:'religions',title:'Religions',model:'religion',id:'religion_id',fields:[text('religion_code','Religion code',20,true),text('religion_name','Religion name',100)]},
 {path:'social-categories',title:'Social categories',model:'socialcategory',id:'social_category_id',fields:[text('category_code','Category code',20),text('category_name','Category name',100)]},
 {path:'castes',title:'Castes',model:'caste',id:'caste_id',fields:[text('caste_code','Caste code',30,true),text('caste_name','Caste name',150)],parent:{path:'social-categories',field:'social_category_id',label:'Social category',optional:true}},
 {path:'sub-castes',title:'Sub-castes',model:'subcaste',id:'sub_caste_id',fields:[text('sub_caste_code','Sub-caste code',30,true),text('sub_caste_name','Sub-caste name',150)],parent:{path:'castes',field:'caste_id',label:'Caste'}},
 {path:'admission-categories',title:'Admission categories',model:'admissioncategory',id:'admission_category_id',fields:[text('category_code','Category code',30),text('category_name','Category name',100),text('description','Description',500,true)]},
 {path:'document-types',title:'Document types',model:'documenttype',id:'document_type_id',fields:[text('document_code','Document code',30),text('document_name','Document name',100),{name:'requires_verification',label:'Requires verification',boolean:true}]},
];
export function permitted(user:User,resource:Resource,operation:string) {
 return user.is_superuser || (user.permissions.includes(`common_reference.${operation}_${resource.model}`) && (operation==='view' || user.permissions.includes('common_reference.maintain_reference')));
}
export function maintainer(user:User) {return user.is_superuser || user.permissions.includes('common_reference.maintain_reference');}
export function label(resource:Resource,row:RecordData) {return String(row[resource.fields.find(f=>f.name.endsWith('_name'))?.name || resource.fields[0].name] ?? row[resource.id]);}
export function payload(resource:Resource,values:RecordData) {
 const result:RecordData={};
 for(const field of resource.fields) result[field.name]=field.boolean ? values[field.name]===true : (field.optional && !String(values[field.name]??'').trim() ? null : String(values[field.name]??''));
 if(resource.parent) result[resource.parent.field]=values[resource.parent.field] ? Number(values[resource.parent.field]) : null;
 return result;
}
