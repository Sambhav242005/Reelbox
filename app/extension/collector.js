(async()=>{
 const send=async message=>{const result=await chrome.runtime.sendMessage(message);if(!result?.ok)throw new Error(result?.error || 'Extension disconnected');return result;};
 const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 try{
  const hello=await send({type:'hello'});if(!hello.allowed)return;
  await pause(4000);
  let previous='',stable=0,collectionEvidence=0,started=false;
  const seen=new Set();
  for(let round=0;round<150;round++){
   const main=document.querySelector('main');
   if(!main){if(round>8)throw new Error('Instagram Saved did not load.');await pause(2000);continue;}
   const elements=[...main.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+100 && /auto|scroll/.test(getComputedStyle(e).overflowY));
   const scroller=elements.sort((a,b)=>b.clientHeight-a.clientHeight)[0] || document.scrollingElement;
   if(!started){
    window.scrollTo(0,0);for(const element of elements)element.scrollTop=0;
    scroller.scrollTop=0;started=true;await pause(1200);continue;
   }
   const items=[],collections=[];
   const links=[...main.querySelectorAll('a[href]')].sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top || a.getBoundingClientRect().left-b.getBoundingClientRect().left);
   for(const a of links){
    const url=new URL(a.href);if(url.protocol!=='https:' || url.hostname!=='www.instagram.com')continue;
    const match=/^\/(?:p|reel|reels)\/([\w-]+)\/?$/.exec(url.pathname);
    if(match){const post='https://www.instagram.com/p/'+match[1]+'/';if(!seen.has(post)){
     const image=a.querySelector('img');
     // Alt text is source title evidence, not a fabricated full caption.
     items.push({url:post,title:image?.alt || '',cover_url:image?.currentSrc || image?.src || '',caption:'',creator:''});seen.add(post);
    }}
    if(/^\/[^/]+\/saved\//.test(url.pathname)){url.search='';url.hash='';collections.push(url.href);collectionEvidence++;}
   }
   const signature=seen.size+':'+scroller.scrollHeight+':'+scroller.scrollTop;
   stable=signature===previous?stable+1:0;previous=signature;
   // Batches keep the service worker awake and persist progress between page loads.
   for(let offset=0;offset<Math.max(1,items.length);offset+=100)await send({type:'batch',items:items.slice(offset,offset+100),collections});
   if(stable>=6){await send({type:'done',partial:false,collectionEvidence});return;}
   scroller.scrollTop=Math.min(scroller.scrollHeight,scroller.scrollTop+Math.max(200,scroller.clientHeight*.8));
   await pause(1800);
  }
  await send({type:'done',partial:true,collectionEvidence});
 }catch(e){try{await chrome.runtime.sendMessage({type:'error',message:e.message});}catch{}}
})();
