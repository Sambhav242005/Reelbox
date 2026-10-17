/** Discover, rehearse, then record a real isolated run. No account/browser profile. */
import {chromium} from '../app/node_modules/playwright-core/index.mjs';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';

const mode=process.argv[2] || '--discover';
assert.ok(['--discover','--rehearse','--record'].includes(mode));
const base=process.env.REELBOX_DEMO_URL || 'http://127.0.0.1:8770';
assert.equal(new URL(base).hostname,'127.0.0.1');
assert.notEqual(new URL(base).port,'8765','Never record/control the original installation.');
const output=path.resolve('work/demo/recording');await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const context=await browser.newContext({bypassCSP:true,viewport:{width:1280,height:720},...(mode==='--record'?{recordVideo:{dir:output,size:{width:1280,height:720}}}:{})});
const page=await context.newPage(), errors=[], events=[];
page.on('pageerror',error=>errors.push(error.message));
const started=Date.now();
const mark=(name,data={})=>events.push({name,seconds:(Date.now()-started)/1000,...data});
const pause=ms=>page.waitForTimeout(ms);
async function visible(selector,label){const locator=page.locator(selector).first();await locator.waitFor({state:'visible',timeout:15000});assert.ok(await locator.isVisible(),label);return locator;}
async function click(selector,label,delay=800){const el=await visible(selector,label);await el.scrollIntoViewIfNeeded();const box=await el.boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2,{steps:14});await pause(350);await el.click();await pause(delay);}
async function subtitle(text){await page.locator('#demo-subtitle').evaluate((el,text)=>el.textContent=text,text);}
async function inject(){
 await page.addStyleTag({content:`body{padding-bottom:64px}body:not(.show-detail) .search-toolbar{display:none}#browse-intro{padding-top:20px;padding-bottom:12px}#browse-intro h1{font-size:33px}.intro-copy,.library-mark{display:none}.processing-flow{margin-top:12px}.reel-list>.reel-row:nth-child(n+21){display:none}#demo-subtitle{position:fixed;bottom:18px;left:15%;right:5%;z-index:999998;background:#14251ff2;color:#fff;text-align:center;border-radius:8px;padding:13px 18px;font:500 17px 'Segoe UI',sans-serif;pointer-events:none}#demo-scope{position:fixed;top:0;left:0;right:0;z-index:999997;background:#204b38;color:#fff;padding:7px 15px;text-align:center;font:11px 'Segoe UI',sans-serif;pointer-events:none}.topbar{margin-top:28px}`});
 await page.evaluate(()=>{
  const cursor=document.createElement('div');cursor.id='demo-cursor';cursor.innerHTML='<svg width="24" height="24" viewBox="0 0 24 24"><path d="M5 3L19 12L12 13L9 20L5 3Z" fill="white" stroke="black" stroke-width="1.5" stroke-linejoin="round"/></svg>';cursor.style.cssText='position:fixed;left:10px;top:10px;z-index:999999;pointer-events:none;filter:drop-shadow(1px 1px 2px #0005)';document.body.append(cursor);document.addEventListener('mousemove',e=>{cursor.style.transform=`translate(${e.clientX-10}px,${e.clientY-10}px)`;});
  for(const [id,text] of [['demo-subtitle',''],['demo-scope','20 featured reels · 50 measured · Cached captions + covers · fresh local AI · Instagram retrieval excluded']]){const el=document.createElement('div');el.id=id;el.textContent=text;document.body.append(el);}
 });
}
try {
 await page.goto(base);await visible('#processing-flow','Processing panel');await inject();
 await page.waitForFunction(()=>document.querySelectorAll('#library [data-reel]').length===50);
 const bootstrap=await page.request.get(base+'/api/bootstrap');const {token}=await bootstrap.json();
 const state=async()=>{const response=await page.request.get(base+'/api/processing',{headers:{Authorization:'Bearer '+token}});assert.ok(response.ok());return response.json();};
 const before=await state();
 if(mode!=='--record'){
  const fields=await page.locator('input,select,textarea,button,summary,a').evaluateAll(elements=>elements.filter(el=>el.getClientRects().length).map(el=>({tag:el.tagName,id:el.id,role:el.getAttribute('role'),text:el.textContent.trim().slice(0,65),placeholder:el.getAttribute('placeholder')})));
  await writeFile(path.join(output,'field-map.json'),JSON.stringify(fields,null,2));
  for(const selector of ['#flow-unorganized','#flow-organizing','#flow-organized','#run-speed','#run-median','#flow-unorganized [data-flow-reel]'])await visible(selector,selector);
  if(mode==='--rehearse'){
   await click('#flow-unorganized [data-flow-reel]','Unorganized reel');await visible('#detail-title','Reel detail');await click('#back-library','Back to library');
   await click('#box-nav [data-box]','Topic folder');await visible('#folder-description','Folder description');await click('[data-filter="all"]','All saves');
   await page.locator('#batch-panel').evaluate(el=>el.open=true);await visible('#resume-processing','Resume');
   await page.locator('#batch-panel').evaluate(el=>el.open=false);
   assert.equal((await state()).stopped,before.stopped,'Rehearsal must not start work');
   assert.equal((await state()).metrics.measured,false,'Benchmark must remain unstarted');
   await writeFile(path.join(output,'rehearsal-passed.json'),JSON.stringify({passed:true,checks:8,errors}));
  }
  await page.screenshot({path:path.join(output,mode==='--discover'?'discovery.png':'rehearsal.png'),fullPage:false});
  console.log(mode+' passed; field map and screenshot saved.');
 }else{
  const rehearsal=JSON.parse(await readFile(path.join(output,'rehearsal-passed.json'),'utf8'));assert.ok(rehearsal.passed);
  assert.equal(before.metrics.measured,false,'Refuse to replay a measured run as fresh inference.');
  assert.ok(before.stopped);
  const manifest=JSON.parse(await readFile('work/demo/manifest.json','utf8'));
  const trackedId=manifest.showcase_ids[0];
  mark('entry');await subtitle('Saved reels. Finally organized.');await pause(4000);
  await subtitle('Step 1 - Follow one idea through the pipeline');
  await click(`[data-flow-follow="${trackedId}"]`,'Follow one reel',600);
  await click('#flow-control','Resume isolated processing',400);mark('resume');
  await subtitle('Step 2 — Real local AI. Live progress.');mark('processing-visible');
  let firstSuccess='', snapshot;
  const deadline=Date.now()+45*60*1000;
  while(Date.now()<deadline){
   snapshot=await state();
   if(!firstSuccess && snapshot.metrics.organized>0 && (await (await page.request.get(base+'/api/reels/'+trackedId,{headers:{Authorization:'Bearer '+token}})).json()).status==='ready'){
    firstSuccess=trackedId;
    mark('first-organized',{id:firstSuccess});await subtitle('The same reel, now in its topic folder.');
    const target=page.locator(`[data-flow-id="${firstSuccess}"]`);
    await target.waitFor({state:'visible',timeout:10000});const box=await target.boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2,{steps:12});await pause(3500);mark('transition-end');
    await subtitle('Live metrics count successful organization separately.');
   }
   if(snapshot.metrics.tracked===50 && snapshot.metrics.finished_at){mark('run-finished',{metrics:snapshot.metrics});break;}
   await pause(1500);
  }
  assert.ok(snapshot?.metrics.finished_at,'Run exceeded the recording deadline; no success claim is allowed.');
  assert.ok(firstSuccess,'No successful example to demonstrate.');
  await pause(2500);
  const current=await state();const card=(await (await page.request.get(base+'/api/reels/'+firstSuccess,{headers:{Authorization:'Bearer '+token}})).json());
  await subtitle('Step 3 — Find the idea in its folder.');
  await click(`[data-flow-id="${card.id}"] [data-box]`,'Completed topic folder',1300);mark('folder');
  await click(`#library [data-reel="${card.id}"]`,'Organized reel detail',1300);
  await visible('.evidence-label','Evidence provenance');await subtitle('Caption + cover evidence. No video downloaded.');await pause(2500);mark('detail');
  await click('#back-library','Return to collection');await click('[data-filter="all"]','All saves');
  await page.evaluate(()=>window.scrollTo({top:0,behavior:'smooth'}));await pause(1300);
  const metric=current.metrics;
  await subtitle(`${metric.organized}/50 organized · ${metric.review} review · ${metric.errors} errors · ${metric.reels_per_minute?.toFixed(1) || '0'} reels/min`);mark('results');await pause(4000);
  await subtitle('Reelbox · github.com/Sambhav242005/Reelbox');await pause(3500);mark('end');
 }
 assert.deepEqual(errors,[],'Browser errors');
}finally{
 await context.close();
 if(mode==='--record') {await page.video().saveAs(path.join(output,'reelbox-raw.webm'));await writeFile(path.join(output,'events.json'),JSON.stringify(events,null,2));console.log('Raw recording and event timeline saved.');}
 await browser.close();
}
