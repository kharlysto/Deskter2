// Exercise rendering of actual UI code with a minimal DOM adapter.
// This is not a substitute for a browser layout or interaction test.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',style:{},classList:{remove(){},toggle(){}},addEventListener(){},showModal(){this.open=true},close(){this.open=false}});return nodes.get(id)}
const context=vm.createContext({__DESKTER_TEST__:true,document:{getElementById:node,addEventListener(){},querySelector(){return node('sidebar')}},location:{protocol:'http:'},Intl,console,setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1],context);
const run=s=>vm.runInContext(s,context);
run(`state={user:{id:1,name:'Seller',email:'test@example.test'},listings:[{id:1,owner:1,title:'Private draft',category:'Services',description:'Private description',price:100,status:'draft',pricing:'one_time',seller:'Seller'},{id:2,owner:2,title:'Public <offer>',category:'Products',description:'<script>alert(1)</script>',price:125050,status:'published',pricing:'monthly',seller:'Other seller'},{id:3,owner:2,title:'Quote offer',category:'Services',description:'Request a quote',price:0,status:'published',pricing:'quote',seller:'Other seller'}],saved:[2],following:[2],leads:[],sent:[]};render()`);
assert(!node('grid').innerHTML.includes('Private draft'));
assert(node('grid').innerHTML.includes('Public &lt;offer&gt;'));
assert(!node('grid').innerHTML.includes('<script>'));
assert(node('grid').innerHTML.includes('₱1,250.50 / month'));
run(`go('Assets')`);assert(node('grid').innerHTML.includes('Private draft'));assert(!node('grid').innerHTML.includes('Public &lt;offer&gt;'));
run(`go('Saved')`);assert(node('grid').innerHTML.includes('Public &lt;offer&gt;'));assert(!node('grid').innerHTML.includes('Quote offer'));
run(`go('Discover');max=200000;cards()`);assert(!node('grid').innerHTML.includes('Quote offer'));
for(const view of ['Following','Analytics','Leads','Profile','Settings','Deskter Ads','Campaigns','Admin Center'])run(`go('${view}')`);
run(`go('Campaigns')`);assert(node('content').innerHTML.includes('/growth'));
run(`state.listings[1].sponsored=1;go('Discover')`);assert(node('grid').innerHTML.includes('SPONSORED'));
run(`details(2)`);assert(node('modal').innerHTML.includes('&lt;script&gt;'));assert(node('modal').open);
run(`storefront(2)`);assert(node('modal').innerHTML.includes('2 published assets'));
run(`state.user=null;go('Profile')`);assert(node('content').innerHTML.includes('Sign in'));
console.log('UI rendering, navigation, ownership filters, quote filtering, detail views, and escaping passed.');
