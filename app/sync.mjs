import { chromium } from 'playwright-core';
import { mkdir, readFile, writeFile, open, unlink, stat, utimes, rename } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = dirname(fileURLToPath(import.meta.url));
const data = process.env.REELBOX_DATA || join(root, 'data');
const login = process.argv.includes('--login');
const force = process.argv.includes('--force');
const capture = process.argv.includes('--capture');
const endpoint = 'http://127.0.0.1:8765';
const configFile = join(data,'sync-config.json');
const statusFile = join(data,'sync-status.json');
const profile = join(data,'api-anything','profile');
const lockFile = join(data,'sync.lock');
const day = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Calcutta', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date());
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));

async function readJson(path, fallback) {
  try { return JSON.parse(await readFile(path,'utf8')); }
  catch (e) { if(e.code === 'ENOENT') return fallback; throw e; }
}
async function save(path, value) {
  const temp=path+'.tmp';
  await writeFile(temp,JSON.stringify(value,null,2), {mode:0o600});
  await rename(temp,path);
}
function savedPage(url) {
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && u.hostname === 'www.instagram.com' && /^\/[^/]+\/saved(?:\/|$)/.test(u.pathname);
  } catch {return false;}
}
export function directPost(url) {
  try {
    const u = new URL(url);
    const match = /^\/(?:p|reel|reels)\/([\w-]+)\/?$/.exec(u.pathname);
    return u.hostname === 'www.instagram.com' && match ? `https://www.instagram.com/p/${match[1]}/` : null;
  } catch {return null;}
}
async function api(path, token, body) {
  const response = await fetch(endpoint+path, {method:body ? 'POST':'GET',
    headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},
    body:body ? JSON.stringify(body):undefined, signal:AbortSignal.timeout(30000)});
  const value = await response.json();
  if(!response.ok) throw new Error(value.error || `Local API failed: ${response.status}`);
  return value;
}
async function cookiesFile(context) {
  const cookies = await context.cookies('https://www.instagram.com');
  const session = cookies.find(c=>c.name === 'sessionid' && c.value && (c.expires < 0 || c.expires > Date.now()/1000));
  if(!session) throw new Error('Instagram session expired. Run Sign in to Instagram again.');
  const lines = ['# Netscape HTTP Cookie File', '# Private local Instagram session. Do not share.'];
  for(const c of cookies) {
    const domain = (c.httpOnly ? '#HttpOnly_' : '') + c.domain;
    lines.push([domain,c.domain.startsWith('.')?'TRUE':'FALSE',c.path,c.secure?'TRUE':'FALSE',
      Math.max(0,Math.floor(c.expires)),c.name,c.value].join('\t'));
  }
  const path = join(data,'instagram-cookies.txt');
  await writeFile(path,lines.join('\n')+'\n', {mode:0o600});
  return path;
}

async function setup(context) {
  const page = context.pages()[0] || await context.newPage();
  await page.goto('https://www.instagram.com/',{waitUntil:'domcontentloaded'});
  console.log('Sign in in Edge, then open your profile > Saved. No password is stored by Reelbox.');
  const deadline = Date.now()+20*60*1000;
  while(Date.now()<deadline) {
    if(page.isClosed()) throw new Error('Setup closed before Saved was opened.');
    if(savedPage(page.url())) {
      const cookiePath = await cookiesFile(context);
      await save(configFile,{saved_url:page.url(),profile});
      const bootstrap = await fetch(endpoint+'/api/bootstrap').then(r=>r.json());
      await api('/api/settings',bootstrap.token,{browser:'edge',cookies_file:cookiePath});
      await save(statusFile,{state:'paired',message:'Signed in. Daily sync is ready.',updated:Date.now()});
      console.log('Saved page paired. Closing the automation Edge window.');
      await delay(2000);
      return;
    }
    await delay(1000);
  }
  throw new Error('Setup timed out. Run login again when you are ready.');
}

async function scan(context, config, token) {
  const page = context.pages()[0] || await context.newPage();
  const visited = new Set();
  const pages = [config.saved_url];
  const discovered = new Map();
  const known = new Set((await api('/api/known',token)).map(directPost));
  let added = 0;
  let capped = false;
  let evidenceLinks = 0;
  const owner = new URL(config.saved_url).pathname.split('/')[1];
  while(pages.length && visited.size<100) {
    const url = pages.shift();
    if(visited.has(url)) continue;
    visited.add(url);
    await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
    await delay(4000);
    if(!savedPage(page.url())) throw new Error('Instagram redirected away from Saved. Sign in again or clear its challenge.');
    await cookiesFile(context);
    let stable = 0;
    let lastSignature = '';
    let reachedEnd = false;
    for(let round=0;round<150;round++) {
      await utimes(lockFile,new Date(),new Date());
      // Scope to the Saved main content: never collect feed/profile recommendation links.
      const snapshot = await page.evaluate(()=>{
        const main = document.querySelector('main');
        if(!main) return {links:[],signature:'',hasMain:false};
        const links = [...main.querySelectorAll('a[href]')].map(a=>({url:a.href,title:a.querySelector('img')?.alt || ''}));
        const scrollables = [...main.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+100 && /auto|scroll/.test(getComputedStyle(e).overflowY));
        const scroller = scrollables.sort((a,b)=>b.clientHeight-a.clientHeight)[0] || document.scrollingElement;
        const signature = links.map(a=>a.url).join('|')+':'+scroller.scrollHeight+':'+scroller.scrollTop;
        scroller.scrollTop = scroller.scrollHeight;
        return {links,signature,hasMain:true};
      });
      if(!snapshot.hasMain && round>8) throw new Error('Saved content did not load. Instagram may require sign-in or a challenge.');
      for(const link of snapshot.links) {
        const post = directPost(link.url);
        if(post || savedPage(link.url)) evidenceLinks++;
        if(post && !known.has(post)) discovered.set(post,{url:post,title:link.title});
        if(savedPage(link.url)) {
          const collection = new URL(link.url);
          collection.search=''; collection.hash='';
          if(collection.pathname.startsWith(`/${owner}/saved/`) && !visited.has(collection.href) && !pages.includes(collection.href)) pages.push(collection.href);
        }
      }
      stable = snapshot.signature === lastSignature ? stable+1 : 0;
      lastSignature = snapshot.signature;
      if(discovered.size) {
        const batch = [...discovered.values()].slice(0,100);
        added += (await api('/api/ingest',token,{items:batch})).added;
        for(const item of batch) {known.add(item.url); discovered.delete(item.url);}
      }
      await save(statusFile,{state:'syncing',message:`Scanning saved page ${visited.size}. ${added} new posts queued.`,added,updated:Date.now()});
      if(stable>=6 && snapshot.hasMain) {reachedEnd=true;break;}
      await delay(1800);
    }
    if(!reachedEnd) capped=true;
    await delay(2000);
  }
  if(pages.length) capped=true;
  if(!evidenceLinks) throw new Error('No saved links were found. The library may be empty, Instagram may require a challenge, or its page layout may have changed.');
  return {added,capped,pages:visited.size};
}

async function main() {
  await mkdir(data,{recursive:true});
  let handle;
  try {
    const info = await stat(lockFile).catch(()=>null);
    if(info && Date.now()-info.mtimeMs>30*60*1000) await unlink(lockFile);
    handle = await open(lockFile,'wx');
  } catch(e) {if(e.code==='EEXIST') {console.log('Sync already running.'); return;} throw e;}
  let context;
  let status={};
  try {
    status = await readJson(statusFile,{});
    if(!login && !force && status.last_success_day===day) {console.log('Already synced today.');return;}
    const config = await readJson(configFile,null);
    if(!login && !config) {
      await save(statusFile,{state:'needs_login',message:'Open Settings and choose Sign in to Instagram.',updated:Date.now()});
      console.log('One-time Instagram sign-in required.'); return;
    }
    if(capture) {
      if(!config || !savedPage(config.saved_url)) throw new Error('Pair a Saved page first.');
      process.env.API_ANYTHING_HOME=join(data,'api-anything');
      process.env.API_ANYTHING_BROWSER='edge';
      const {capturePage,closeBrowser} = await import('api-anything');
      const captured = await capturePage({url:config.saved_url});
      await closeBrowser();
      console.log(`API Anything captured ${captured.exchanges.length} requests locally. No saved-post operation has been learned yet.`);
      return;
    }
    context = await chromium.launchPersistentContext(profile,{
      channel:'msedge',headless:!login,viewport:{width:1440,height:1000}});
    if(login) {await setup(context); await context.close(); context=null; return;}
    if(!savedPage(config.saved_url)) throw new Error('Invalid Saved page in sync settings.');
    const bootstrap = await fetch(endpoint+'/api/bootstrap',{signal:AbortSignal.timeout(10000)}).then(r=>r.json());
    const cookiePath = await cookiesFile(context);
    await api('/api/settings',bootstrap.token,{browser:'edge',cookies_file:cookiePath});
    const result = await scan(context,config,bootstrap.token);
    await save(statusFile,{state:result.capped?'partial':'complete',...result,
      message:result.capped?'Scan reached its limit. More posts may remain; run sync again.':`${result.added} new posts queued.`,
      last_success_day:result.capped ? status.last_success_day : day,updated:Date.now()});
    console.log(JSON.stringify(result));
  } catch(e) {
    await save(statusFile,{state:'error',message:e.message.slice(0,500),last_success_day:status.last_success_day,updated:Date.now()});
    console.error(e.message); process.exitCode=1;
  } finally {
    if(context) await context.close();
    await handle.close(); await unlink(lockFile).catch(()=>{});
  }
}
if(process.argv[1] && fileURLToPath(import.meta.url)===process.argv[1]) await main();
