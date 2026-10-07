const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ts=require('typescript');
let policy;
const code=ts.transpileModule(fs.readFileSync('vite.config.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
vm.runInNewContext(code,{exports:{},require:name=>name==='vite'?{defineConfig:x=>x}:name==='vite-plugin-pwa'?{VitePWA:x=>{policy=x;return {};}}:()=>({})});
test('worker never serves shell fallback for API or admin navigation',()=>{
 for(const path of ['/api','/api/v1/auth/me/','/api/v1/reference/countries/','/admin','/admin/login/'])assert.ok(policy.workbox.navigateFallbackDenylist.some(rule=>rule.test(path)));
 assert.equal(policy.workbox.runtimeCaching.length,1);
 assert.equal(policy.workbox.runtimeCaching[0].handler,'NetworkOnly');
 assert.equal(policy.workbox.skipWaiting,false);
 assert.equal(policy.registerType,'prompt');
 assert.equal(policy.injectRegister,false);
});
test('manifest icons have correct actual dimensions and no domain data is precached',()=>{
 for(const icon of policy.manifest.icons){
  const png=fs.readFileSync('public'+icon.src);
  assert.equal(`${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`,icon.sizes);
 }
 assert.equal(policy.workbox.globPatterns.some(pattern=>pattern.includes('json')),false);
 assert.equal(policy.devOptions.enabled,false);
});
