// Runs the actual frontend pricing functions without external dependencies.
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
let script=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const context=vm.createContext({__DESKTER_TEST__:true,location:{protocol:'file:'},document:{addEventListener(){},getElementById(){return {addEventListener(){}}}},Intl,console});
vm.runInContext(script,context);
for(const [input,expected] of [['1250.50',125050],['0.01',1],['1.10',110],['999999.99',99999999]])assert.equal(vm.runInContext(`centavos('${input}')`,context),expected);
for(const input of ['-1','1.001','NaN','1e3','', '1,00','0','1000000.01'])assert.throws(()=>vm.runInContext(`centavos('${input}')`,context));
for(const input of ['1,250.50','₱1,250.50','PHP 1250.50',' 1250.50 '])assert.equal(vm.runInContext(`centavos('${input}')`,context),125050);
for(const [mode,expected] of [['quote','Request a quote'],['free','Free'],['monthly','₱1,250.50 / month'],['yearly','₱1,250.50 / year'],['starting_at','From ₱1,250.50'],['one_time','₱1,250.50']])assert.equal(vm.runInContext(`priceLabel({pricing:'${mode}',price:125050})`,context),expected);
assert.equal(vm.runInContext(`esc('<img src=x onerror=alert(1)>')`,context),'&lt;img src=x onerror=alert(1)&gt;');
console.log('Pricing conversion, formatting, rejection, and HTML escaping passed.');
