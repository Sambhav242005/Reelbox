const status=document.querySelector('#status');
async function action(type){const buttons=[...document.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);try{const result=await chrome.runtime.sendMessage({type});if(!result?.ok)throw new Error(result?.error || 'Could not connect');const state=await chrome.runtime.sendMessage({type:'status'});status.textContent=state.message;}catch(e){status.textContent=e.message;}finally{buttons.forEach(b=>b.disabled=false);}}
document.querySelector('#pair').addEventListener('click',()=>action('pair'));
document.querySelector('#sync').addEventListener('click',()=>action('sync'));
(async()=>{try{const state=await chrome.runtime.sendMessage({type:'status'});status.textContent=state.message;}catch(e){status.textContent=e.message;}})();
