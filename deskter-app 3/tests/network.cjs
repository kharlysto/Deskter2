const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
let response;
const context=vm.createContext({__DESKTER_TEST__:true,location:{protocol:'http:'},document:{addEventListener(){},getElementById(){return {addEventListener(){}}}},AbortController,TypeError,setTimeout,clearTimeout,fetch:async()=>{if(response instanceof Error)throw response;return response}});
vm.runInContext(source,context);
(async()=>{
 response={ok:true,headers:{get:()=> 'text/html'}};
 await assert.rejects(vm.runInContext("api('state')",context),/not connected to the Deskter server/);
 response={ok:false,status:401,headers:{get:()=> 'application/json'},json:async()=>({error:'Please sign in first'})};
 await assert.rejects(vm.runInContext("api('state')",context),e=>e.status===401&&/sign in/.test(e.message));
 response=new TypeError('Failed to fetch');await assert.rejects(vm.runInContext("api('state')",context),/Cannot reach the server/);
 response=Object.assign(new Error('Timeout'),{name:'AbortError'});await assert.rejects(vm.runInContext("api('state')",context),/server took too long/);
 response={ok:true,headers:{get:()=> 'application/json'},json:async()=>({ok:true})};assert.equal((await vm.runInContext("api('listings',{title:'test'})",context)).ok,true);
 console.log('API success, static-server HTML response, authorization, network failure, and timeout messages passed.');
})().catch(e=>{console.error(e);process.exit(1)});
