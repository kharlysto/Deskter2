// Runs the actual asset form submit handler, preview adapter, and rendering.
// Minimal DOM adapter: no claims about browser layout or native validation.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const storage=new Map();
function makeContext(blockStorage=false){
 const nodes=new Map();let activeForm;
 function base(){return {innerHTML:'',textContent:'',style:{},dataset:{},classList:{remove(){},toggle(){}},addEventListener(){},focus(){},closest(){return {style:{}}}}}
 function node(id){if(!nodes.has(id))nodes.set(id,base());return nodes.get(id)}
 const modal=node('modal');let html='';
 Object.defineProperty(modal,'innerHTML',{get(){return html},set(value){html=value;const primary={...base(),type:'submit',textContent:'Save changes'},cancel={...base(),type:'button'},error=base(),buttons=[cancel,primary],pricing={...base(),value:'one_time'},amount=base();
 const actions={querySelector(){return primary},insertBefore(b){buttons.splice(buttons.length-1,0,b)}};
 activeForm={values:{},addEventListener(){},querySelectorAll(){return buttons},querySelector(s){return s==='[type=submit]'?primary:null}};
 modal.querySelector=s=>s==='form'?activeForm:s==='.error'?error:s==='.dialog-actions'?actions:s==='[name=pricing]'?pricing:s==='[name=price]'?amount:s==='[type=submit]'?primary:null;
 }});
 modal.showModal=()=>modal.open=true;modal.close=()=>modal.open=false;
 class FormData{constructor(form){this.values=Object.entries(form.values)}[Symbol.iterator](){return this.values[Symbol.iterator]()}}
 const context=vm.createContext({__DESKTER_TEST__:true,location:{protocol:'file:'},localStorage:{getItem(k){if(blockStorage)throw Error('Blocked');return storage.get(k)||null},setItem(k,v){if(blockStorage)throw Error('Blocked');storage.set(k,v)}},FormData,Intl,console,setTimeout(){return 1},clearTimeout(){},document:{getElementById:node,addEventListener(){},querySelector(){return node('sidebar')},createElement(){return base()}}});
 vm.runInContext(source,context);
 return {run:s=>vm.runInContext(s,context),node,form:()=>activeForm,modal};
}
const values={title:'A complete offer',description:'Brand design and delivery for small businesses.',category:'Services',price:'₱1,250.50',pricing:'one_time',status:'draft'};
async function submit(c,status){const form=c.form();const button=c.modal.querySelector('.dialog-actions').querySelector('[type=submit]');button.dataset.status=status;return form.onsubmit({preventDefault(){},submitter:button,target:form})}
(async()=>{
 const c=makeContext();await c.run('load()');c.run('listingForm()');c.form().values={...values};await submit(c,'published');
 let item=c.run('state.listings.find(l=>l.title==="A complete offer")');assert(item);assert.equal(item.price,125050);assert.equal(item.status,'published');assert.equal(c.modal.open,false);assert.equal(c.run('view'),'Assets');
 const id=item.id;const reloaded=makeContext();await reloaded.run('load()');assert.equal(reloaded.run(`state.listings.find(l=>l.id===${id}).price`),125050);
 c.run(`listingForm(${id})`);c.form().values={...values,status:'archived'};await submit(c,'archived');assert.equal(c.run(`state.listings.find(l=>l.id===${id}).status`),'archived');
 c.run('listingForm()');c.form().values={...values,title:'Free offer',pricing:'free'};delete c.form().values.price;await submit(c,'published');assert.equal(c.run('state.listings.find(l=>l.title==="Free offer").price'),0);
 c.run('listingForm()');c.form().values={...values,title:'Broken amount',price:'1,2,3'};await submit(c,'published');assert.equal(c.modal.open,true);assert(c.modal.querySelector('.error').textContent.includes('Enter an amount'));assert(!c.run('state.listings.some(l=>l.title==="Broken amount")'));
 c.form().values.price='2000';await submit(c,'draft');assert.equal(c.run('state.listings.find(l=>l.title==="Broken amount").status'),'draft');
 c.run('listingForm()');c.form().values={...values,title:'Duplicate guard'};await Promise.all([submit(c,'published'),submit(c,'published')]);assert.equal(c.run('state.listings.filter(l=>l.title==="Duplicate guard").length'),1);
 const memory=makeContext(true);await memory.run('load()');memory.run('listingForm()');memory.form().values={...values,title:'Storage blocked'};await submit(memory,'published');assert(memory.run('state.listings.some(l=>l.title==="Storage blocked")'));assert.equal(memory.run('previewStorage'),false);
 console.log('Actual asset submit handlers: publish, draft, archive, free price, invalid-price recovery, reload persistence, duplicate guard, and storage failure passed.');
})().catch(e=>{console.error(e);process.exit(1)});
