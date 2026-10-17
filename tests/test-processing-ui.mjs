import {chromium} from '../app/node_modules/playwright-core/index.mjs';
import assert from 'node:assert/strict';
const base=process.env.REELBOX_DEMO_URL || 'http://127.0.0.1:8770';
assert.notEqual(new URL(base).port,'8765');
const browser=await chromium.launch({channel:'msedge',headless:true});
const errors=[];
try {
 for(const reduced of [false,true]){
  const context=await browser.newContext({viewport:{width:1280,height:900},reducedMotion:reduced?'reduce':'no-preference'});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  const bootstrap=await (await page.request.get(base+'/api/bootstrap')).json();
  const real=await (await page.request.get(base+'/api/processing',{headers:{Authorization:'Bearer '+bootstrap.token}})).json();
  const record=[...real.board.unorganized,...real.board.organizing,...real.board.organized][0];assert.ok(record);
  const example={...record,id:record.id,title:'A measured processing example',status:'queued',boxes:[]};
  let state={...real,metrics:{measured:false,tracked:0,organized:0,batch_id:1,elapsed_seconds:null,reels_per_minute:null,median_seconds:null},board:{counts:{unorganized:1,organizing:0,organized:0,review:1,waiting:2,errors:3},unorganized:[example],organizing:[],organized:[]}};
  await page.route('**/api/processing',route=>route.fulfill({json:state}));
  await page.goto(base);await page.locator('#processing-flow').waitFor({state:'visible'});
  assert.equal(await page.locator('#run-speed').textContent(),'Not measured');
  assert.match(await page.locator('#flow-exceptions').textContent(),/1 need review · 2 waiting for model · 3 errors/);
  assert.equal(await page.locator('#flow-unorganized [data-flow-id]').count(),1);
  state.board={...state.board,counts:{...state.board.counts,unorganized:0,organizing:1},unorganized:[],organizing:[{...example,status:'summarizing'}]};
  await page.waitForFunction(()=>document.querySelectorAll('#flow-organizing [data-flow-id]').length===1);
  assert.match(await page.locator('#flow-organizing').textContent(),/Summarizing/);
  state.metrics={...state.metrics,measured:true,tracked:1,organized:1,elapsed_seconds:20,reels_per_minute:3,median_seconds:20};
  state.board={...state.board,counts:{...state.board.counts,organizing:0,organized:1},organizing:[],organized:[{...example,status:'ready',boxes:[{id:1,name:'Example folder'}]}]};
  await page.waitForFunction(()=>document.querySelector('#run-organized').textContent==='1');
  assert.equal(await page.locator('#run-speed').textContent(),'3.0 / min');
  assert.equal(await page.locator('#run-median').textContent(),'20.0s');
  assert.match(await page.locator('#flow-announcement').textContent(),/Example folder/);
  assert.equal(await page.locator('#flow-unorganized [data-flow-id]').count(),0);
  if(reduced)assert.equal(await page.locator('#flow-organized .flow-card').evaluate(el=>el.getAnimations().length),0);
  for(const width of [1280,390]){
   await page.setViewportSize({width,height:900});
   for(const theme of ['light','dark']){
    await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
    assert.ok(await page.locator('#processing-flow').isVisible());
   }
  }
  await context.close();
 }
 assert.deepEqual(errors,[]);console.log('Processing UI passed: server-confirmed transitions, separate outcomes, metrics, themes, mobile and reduced motion.');
}finally{await browser.close();}
