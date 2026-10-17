const BASE='http://127.0.0.1:8765/api';
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Calcutta',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const saved=url=>{try{const u=new URL(url);return u.protocol==='https:' && u.hostname==='www.instagram.com' && /^\/[^/]+\/saved(?:\/|$)/.test(u.pathname);}catch{return false;}};
async function config(){return chrome.storage.local.get(['token','savedUrl','run','lastDay','handledRequest','message','retryAfter']);}
async function api(path,body){const {token}=await config();if(!token)throw new Error('Connect a Saved page first.');const r=await fetch(BASE+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(15000)});const data=await r.json();if(!r.ok)throw new Error(data.error || 'Local API unavailable');return data;}
async function report(state,message){await chrome.storage.local.set({message});try{await api('/extension-status',{state,message});}catch{}await chrome.action.setBadgeText({text:state==='error'?'!':state==='syncing'?'…':''});}
async function sendSession(){const cookies=await chrome.cookies.getAll({domain:'instagram.com'});await api('/extension-session',{cookies});}
async function pair(){
 const [active]=await chrome.tabs.query({active:true,currentWindow:true});if(!saved(active?.url))throw new Error('Open your Instagram Saved page in this browser, then connect it.');
 // Read the token only from a local dashboard tab, with the user's explicit Connect action.
 const local=await chrome.tabs.create({url:'http://127.0.0.1:8765/',active:false});
 try{
  let token='';
  for(let i=0;i<30;i++){
   await new Promise(r=>setTimeout(r,250));
   try{const result=await chrome.scripting.executeScript({target:{tabId:local.id},func:()=>document.querySelector('#api-token')?.value || ''});token=result[0]?.result || '';}catch{}
   if(token)break;
  }
  if(!token)throw new Error('Start Reelbox locally, then connect again.');
  await chrome.storage.local.set({token,savedUrl:active.url,handledRequest:'0'});
  await sendSession();await report('paired','Connected to your normal browser.');
 }finally{await chrome.tabs.remove(local.id).catch(()=>{});}
 await start(true);
}
async function start(force=false){
 const c=await config();if(!c.token || !saved(c.savedUrl))return;
 if(!force && c.retryAfter>Date.now())return;
 if(c.run && Date.now()-c.run.beat<20*60*1000)return;
 if(c.run){await chrome.storage.local.set({run:null});await chrome.tabs.remove(c.run.tabId).catch(()=>{});}
 const state=await api('/extension-state');
 if(!force && c.lastDay===today() && c.handledRequest===state.request)return;
 await sendSession();
 const tab=await chrome.tabs.create({url:'about:blank',active:false});
 await chrome.storage.local.set({run:{tabId:tab.id,queue:[],visited:[c.savedUrl],owner:new URL(c.savedUrl).pathname.split('/')[1],added:0,evidence:0,position:0,started:Date.now(),partial:false,beat:Date.now()},handledRequest:state.request,retryAfter:0});
 await report('syncing','Scanning Instagram Saved in your normal browser…');
 await chrome.tabs.update(tab.id,{url:c.savedUrl});
}
async function nextPage(run){
 if(run.queue.length && run.visited.length<100){
  const url=run.queue.shift();run.visited.push(url);run.beat=Date.now();await chrome.storage.local.set({run});await chrome.tabs.update(run.tabId,{url});return;
 }
 if(!run.evidence)throw new Error('No saved links found. Saved may be empty or Instagram may need attention.');
 const partial=run.partial || run.queue.length>0;
 await chrome.storage.local.set({run:null,...(!partial?{lastDay:today()}: {})});
 await report(partial?'partial':'complete',partial?`${run.added} posts queued; scan reached its limit.`:`${run.added} new posts queued from your normal browser.`);
 await chrome.tabs.remove(run.tabId).catch(()=>{});
}
async function receive(msg,sender){
 if(msg.type==='pair' && !sender.tab)return pair();
 if(msg.type==='sync' && !sender.tab)return start(true);
 if(msg.type==='status' && !sender.tab){const c=await config();return {connected:!!c.token,message:c.message || 'Open Instagram Saved and connect this page.'};}
 const c=await config(),run=c.run;
 if(!run || sender.tab?.id!==run.tabId || sender.frameId!==0)return {allowed:false};
 if(!saved(sender.url)){
  if(msg.type==='hello')throw new Error('Instagram redirected away from Saved. Sign in or clear its challenge in this browser.');
  return {allowed:false};
 }
 if(msg.type==='hello')return {allowed:true};
 if(msg.type==='batch'){
  if(!Array.isArray(msg.items) || msg.items.length>300)throw new Error('Invalid collection batch');
  run.beat=Date.now();run.evidence+=msg.items.length;
  run.started ||= Date.now();run.position ||= 0;
  if(msg.items.length){
   const items=msg.items.map((item,index)=>({...item,scan_started:run.started,saved_position:run.position+index}));
   run.added+=(await api('/ingest',{items})).added;run.position+=items.length;
  }
  for(const url of (msg.collections || []).slice(0,100)){
   if(saved(url) && new URL(url).pathname.startsWith('/'+run.owner+'/saved/') && !run.visited.includes(url) && !run.queue.includes(url))run.queue.push(url);
  }
  await chrome.storage.local.set({run});
  return {ok:true};
 }
 if(msg.type==='done'){run.partial ||= !!msg.partial;run.evidence+=msg.collectionEvidence || 0;await nextPage(run);return {ok:true};}
 if(msg.type==='error')throw new Error(String(msg.message).slice(0,300));
 return {allowed:false};
}
async function fail(error){const c=await config();await chrome.storage.local.set({run:null,retryAfter:Date.now()+60*60*1000});await report('error',error.message);if(c.run)await chrome.tabs.remove(c.run.tabId).catch(()=>{});}
chrome.runtime.onMessage.addListener((msg,sender,respond)=>{(async()=>{try{const value=await receive(msg,sender);respond({ok:true,...value});}catch(e){await fail(e);respond({ok:false,error:e.message});}})();return true;});
async function schedule(){await chrome.alarms.create('reelbox-check',{periodInMinutes:1});try{await start();}catch(e){await report('error',e.message);}}
chrome.runtime.onInstalled.addListener(()=>{schedule().catch(()=>{});});
chrome.runtime.onStartup.addListener(()=>{schedule().catch(()=>{});});
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==='reelbox-check')start().catch(e=>report('error',e.message));});
chrome.tabs.onRemoved.addListener(tabId=>{(async()=>{const c=await config();if(c.run?.tabId===tabId){await chrome.storage.local.set({run:null});await report('error','The sync tab closed before the scan completed.');}})().catch(()=>{});});
