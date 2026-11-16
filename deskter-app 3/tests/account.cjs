const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../account.html'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
function setup(register){
 const nodes=new Map();function node(id){if(!nodes.has(id))nodes.set(id,{textContent:'',innerHTML:'',focus(){},setAttribute(k,v){this[k]=v}});return nodes.get(id)}
 const form=node('accountForm');form.elements={name:{value:'Avery Lee'},email:{value:'avery@example.test'},password:{value:'a-unique-password',type:'password'}};form.addEventListener=()=>{};
 let result={ok:true,headers:{get:()=> 'application/json'},json:async()=>({ok:true})},requests=[],target=null;
 class FormData{constructor(){this.data=Object.entries(form.elements).filter(([,v])=>!v.disabled).map(([k,v])=>[k,v.value])}[Symbol.iterator](){return this.data[Symbol.iterator]()}}
 const context=vm.createContext({FormData,AbortController,TypeError,setTimeout,clearTimeout,document:{getElementById:node},location:{pathname:register?'/register':'/login',assign(url){target=url}},fetch:async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});return result}});
 vm.runInContext(source,context);return {node,form,requests,target:()=>target,setResult:r=>{result=r}};
}
(async()=>{
 for(const register of [false,true]){const c=setup(register);assert.equal(c.form.elements.name.disabled,!register);assert.equal(c.form.elements.password.autocomplete,register?'new-password':'current-password');await c.form.onsubmit({preventDefault(){}});assert.equal(c.requests[0].url,register?'/api/register':'/api/login');assert.equal(c.target(),'/app');assert.equal('name' in c.requests[0].body,register)}
 const fail=setup(false);fail.setResult({ok:false,headers:{get:()=> 'application/json'},json:async()=>({error:'Incorrect email or password'})});await fail.form.onsubmit({preventDefault(){}});assert.equal(fail.target(),null);assert(fail.node('error').textContent.includes('Incorrect'));assert.equal(fail.node('submit').disabled,false);assert.equal(fail.form.elements.email.value,'avery@example.test');
 fail.node('showPassword').onclick({target:fail.node('showPassword')});assert.equal(fail.form.elements.password.type,'text');
 console.log('Dedicated account pages: login/register payloads, redirect, password toggle, and error recovery passed.');
})().catch(e=>{console.error(e);process.exit(1)});
