const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const vm=require('node:vm');
function load(path,context={}) {
 const code=ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const sandbox={exports:{},...context};vm.runInNewContext(code,sandbox);return sandbox.exports;
}
const contract=load('src/features/common-reference/resources.ts');
test('all ten resources have explicit permissions and writable payloads',()=>{
 assert.equal(contract.resources.length,10);
 for(const r of contract.resources){
  const reader={permissions:[`common_reference.view_${r.model}`],is_superuser:false};
  assert.equal(contract.permitted(reader,r,'view'),true);
  assert.equal(contract.permitted(reader,r,'change'),false);
  const scoped={permissions:[`common_reference.change_${r.model}`],is_superuser:false};
  assert.equal(contract.permitted(scoped,r,'change'),false);
  scoped.permissions.push('common_reference.maintain_reference');
  assert.equal(contract.permitted(scoped,r,'change'),true);
  const values=Object.fromEntries(r.fields.map(f=>[f.name,f.boolean?false:'Example']));
  values[r.id]=88;values.effective_active=true;values.is_active=false;
  if(r.parent)values[r.parent.field]='42';
  const body=contract.payload(r,values);
  assert.equal(r.id in body,false);assert.equal('effective_active' in body,false);assert.equal('is_active' in body,false);
  if(r.parent)assert.equal(body[r.parent.field],42);
 }
});
test('optional blanks and uncategorized parent remain null; verification remains boolean',()=>{
 const caste=contract.resources.find(r=>r.path==='castes');
 const body=contract.payload(caste,{caste_name:'Example',caste_code:'  ',social_category_id:null});
 assert.equal(body.caste_code,null);assert.equal(body.social_category_id,null);
 const document=contract.resources.find(r=>r.path==='document-types');
 assert.equal(contract.payload(document,{requires_verification:false}).requires_verification,false);
});
test('final 401 triggers session expiration and retains safe API error details',async()=>{
 const events=[];
 const api=load('src/features/common-reference/api.ts',{require:()=>({authenticatedFetch:async()=>({ok:false,status:401,json:async()=>({error:{message:'Expired',details:{}}})})}),window:{dispatchEvent:e=>events.push(e.type)},Event,DOMException});
 await assert.rejects(api.request('/reference/countries/'),e=>e.status===401&&e.message==='Expired');
 assert.deepEqual(events,['sims-session-expired']);
});
test('validation errors preserve fields and failed mutations are never automatically retried',async()=>{
 let calls=0;
 const api=load('src/features/common-reference/api.ts',{require:()=>({authenticatedFetch:async()=>{calls++;return {ok:false,status:400,json:async()=>({error:{message:'Request validation failed.',details:{country_name:['Duplicate']}}})};}}),window:{dispatchEvent:()=>{}},Event,DOMException});
 await assert.rejects(api.request('/reference/countries/',{method:'POST'}),e=>e.details.country_name[0]==='Duplicate');
 assert.equal(calls,1);
});
test('network failures warn that mutation outcome can be uncertain',async()=>{
 const api=load('src/features/common-reference/api.ts',{require:()=>({authenticatedFetch:async()=>{throw new TypeError('offline');}}),window:{dispatchEvent:()=>{}},Event,DOMException});
 await assert.rejects(api.request('/reference/countries/',{method:'POST'}),e=>e.status===0&&e.message.includes('may have reached the server'));
});
