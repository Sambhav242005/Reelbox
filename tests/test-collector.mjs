import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';

const sent=[], scrolls=[], reads=[];
const scroller={scrollTop:1200,scrollHeight:2000,clientHeight:600};
const link=(id,top)=>({href:`https://www.instagram.com/reel/${id}/`,
 getBoundingClientRect:()=>({top,left:0}),querySelector:()=>({alt:id,currentSrc:`https://s.cdninstagram.com/${id}.jpg`})});
const main={querySelectorAll:selector=>{
 if(selector==='*')return [];
 reads.push(scroller.scrollTop);
 return [link('bottom',500),link('top',0)];
}};
const document={querySelector:()=>main,scrollingElement:scroller};
const chrome={runtime:{sendMessage:async message=>{sent.push(message);return {ok:true,allowed:true};}}};
const source=await readFile('app/extension/collector.js','utf8');
await vm.runInNewContext(source,{chrome,document,window:{scrollTo:(x,y)=>{scrolls.push(y);scroller.scrollTop=y;}},
 URL,getComputedStyle:()=>({overflowY:'auto'}),setTimeout:fn=>{fn();return 1;}});
assert.equal(scrolls[0],0);
assert.equal(reads[0],0,'Collector must reset restored scroll before reading links');
const first=sent.find(message=>message.type==='batch' && message.items.length);
assert.deepEqual(Array.from(first.items,item=>item.url),['https://www.instagram.com/p/top/','https://www.instagram.com/p/bottom/']);
assert.ok(first.items[0].cover_url.endsWith('/top.jpg'));
assert.ok(reads.includes(480),'Collector should scroll incrementally instead of jumping to bottom');
assert.ok(sent.some(message=>message.type==='done'));
console.log('Collector checks passed: starts at top, visual row order, thumbnail metadata, incremental scrolling and completion.');
