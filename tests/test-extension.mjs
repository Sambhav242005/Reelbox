import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const values={},events={},requests=[],created=[],navigated=[],removed=[],known=new Set();
const event=name=>({addListener:fn=>events[name]=fn});
const chrome={
 storage:{local:{get:async keys=>Object.fromEntries(keys.filter(k=>k in values).map(k=>[k,structuredClone(values[k])])),set:async obj=>Object.assign(values,structuredClone(obj))}},
 tabs:{query:async()=>[{id:5,url:'https://www.instagram.com/tester/saved/'}],
  create:async args=>{const tab={id:100+created.length,...args};created.push(tab);return tab;},
  update:async(id,args)=>navigated.push({id,...args}),remove:async id=>removed.push(id),onRemoved:event('removed')},
 scripting:{executeScript:async()=>[{result:'synthetic-local-token'}]},
 cookies:{getAll:async()=>[{name:'sessionid',value:'synthetic-session-secret',domain:'.instagram.com'}]},
 action:{setBadgeText:async()=>{}},alarms:{create:async()=>{},onAlarm:event('alarm')},
 runtime:{onMessage:event('message'),onInstalled:event('install'),onStartup:event('startup')}
};
async function fakeFetch(url,options){
 assert.ok(url.startsWith('http://127.0.0.1:8765/api/'));
 const body=options?.body?JSON.parse(options.body):null;requests.push({url,body});
 let value={ok:true};
 if(url.endsWith('/extension-state'))value={request:'0'};
 if(url.endsWith('/ingest')){let added=0;for(const i of body.items)if(!known.has(i.url)){known.add(i.url);added++;}value={added};}
 return {ok:true,json:async()=>value};
}
const source=await readFile('app/extension/worker.js','utf8');
function load(){vm.runInNewContext(source,{chrome,fetch:fakeFetch,URL,Intl,Date,AbortSignal,setTimeout,console});}
function message(msg,sender={}){return new Promise(resolve=>{assert.equal(events.message(msg,sender,resolve),true);});}
load();
assert.equal((await message({type:'pair'})).ok,true);
assert.equal(values.savedUrl,'https://www.instagram.com/tester/saved/');
assert.equal(values.run.tabId,101);
assert.ok(requests.some(r=>r.url.endsWith('/extension-session')));
assert.ok(!JSON.stringify(values).includes('synthetic-session-secret'));
const sender={tab:{id:101},frameId:0,url:values.savedUrl};
const before=requests.filter(r=>r.url.endsWith('/ingest')).length;
assert.equal((await message({type:'batch',items:[{url:'https://www.instagram.com/p/one/'}]}, {...sender,tab:{id:8}})).allowed,false);
assert.equal(requests.filter(r=>r.url.endsWith('/ingest')).length,before);
await message({type:'batch',items:[{url:'https://www.instagram.com/p/one/'}],collections:['https://www.instagram.com/tester/saved/all-posts/','https://evil.test/tester/saved/']},sender);
await message({type:'done',partial:false,collectionEvidence:1},sender);
assert.equal(navigated.at(-1).url,'https://www.instagram.com/tester/saved/all-posts/');
load(); // Service worker restart preserves the scan using chrome.storage.
sender.url=navigated.at(-1).url;
assert.equal((await message({type:'hello'},sender)).allowed,true);
await message({type:'batch',items:[{url:'https://www.instagram.com/p/one/'}],collections:[]},sender);
await message({type:'done',partial:false,collectionEvidence:0},sender);
assert.equal(values.run,null);assert.ok(values.lastDay);assert.ok(removed.includes(101));
const count=created.length;await message({type:'sync'});assert.equal(created.length,count+1); // Explicit sync forces a new scan.
console.log('Extension checks passed: pairing, local-only session transfer, sender validation, collection traversal, worker restart, deduplication and explicit sync.');
