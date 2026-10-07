const {test} = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
function session(fetch) {
  const source = fs.readFileSync('src/features/auth/session.ts','utf8').replace("import { API_BASE } from '../../lib/api';", "const API_BASE='/api/v1';");
  const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const context={exports:{},fetch,Headers,navigator:{},console};
  vm.runInNewContext(code,context);
  return context.exports;
}
const response=(status,data={})=>({status,ok:status>=200&&status<300,json:async()=>data});
test('parallel failures share one refresh and retry with memory token',async()=>{
  let refresh=0, requests=0;
  const client=session(async(url,options)=>{
    if(url.endsWith('/csrf/'))return response(200,{csrfToken:'csrf'});
    if(url.endsWith('/refresh/')){refresh++; await new Promise(r=>setTimeout(r,10));return response(200,{access:'new-access'});}
    requests++;
    assert.equal(options.cache,'no-store');
    return response(options.headers.get('Authorization')==='Bearer new-access'?200:401);
  });
  const results=await Promise.all([client.authenticatedFetch('/one/'),client.authenticatedFetch('/two/')]);
  assert.deepEqual(results.map(r=>r.status),[200,200]);assert.equal(refresh,1);assert.equal(requests,4);
});
test('persistent 401 retries only once',async()=>{
  let requests=0,refresh=0;
  const client=session(async url=>{
    if(url.endsWith('/csrf/'))return response(200,{csrfToken:'csrf'});
    if(url.endsWith('/refresh/')){refresh++;return response(200,{access:'token'});}
    requests++;return response(401);
  });
  assert.equal((await client.authenticatedFetch('/one/')).status,401);
  assert.equal(requests,2);assert.equal(refresh,1);
});
test('refresh failure does not retry protected resource',async()=>{
  let requests=0;
  const client=session(async url=>{
    if(url.endsWith('/csrf/'))return response(200,{csrfToken:'csrf'});
    if(url.endsWith('/refresh/'))return response(401);
    requests++;return response(401);
  });
  await client.authenticatedFetch('/one/');assert.equal(requests,1);
});

test('JSON writes keep their content type through an authentication retry',async()=>{
 const attempts=[];
 const client=session(async(url,options)=>{
  if(url.endsWith('/csrf/'))return response(200,{csrfToken:'csrf'});
  if(url.endsWith('/refresh/'))return response(200,{access:'new-access'});
  attempts.push(options);
  return response(attempts.length===1?401:200);
 });
 const body=JSON.stringify({year_code:'2026-27'});
 await client.authenticatedFetch('/calendar/academic-years/',{method:'POST',body});
 assert.equal(attempts.length,2);
 for(const attempt of attempts){assert.equal(attempt.headers.get('Content-Type'),'application/json');assert.equal(attempt.body,body);}
});

test('transport preserves explicit types and leaves non-JSON and multipart bodies alone',async()=>{
 const attempts=[];
 const client=session(async(url,options)=>{attempts.push(options);return response(200);});
 await client.authenticatedFetch('/one/',{method:'POST',headers:{'Content-Type':'application/merge-patch+json'},body:'{"name":"value"}'});
 await client.authenticatedFetch('/two/',{method:'POST',body:'plain text'});
 const form=new FormData();form.append('file','example');
 await client.authenticatedFetch('/three/',{method:'POST',body:form});
 await client.authenticatedFetch('/four/');
 assert.equal(attempts[0].headers.get('Content-Type'),'application/merge-patch+json');
 for(const attempt of attempts.slice(1))assert.equal(attempt.headers.has('Content-Type'),false);
 assert.equal(attempts[2].body,form);
});
