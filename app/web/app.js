const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="3"/><path d="m10 8 5 4-5 4Z"/></svg>';
const terminal = status => ['ready','review','failed'].includes(status);
let token='', boxes=[], reels=[], selectedId='', filter='all', boxFilter='', limit=100, listVersion=0, detailVersion=0, detailSignature='', refreshing=false, toastTimer, listController;
let notificationSignature='';
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6500);}
async function api(path,body,signal){const response=await fetch('/api'+path,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal});const data=await response.json();if(!response.ok)throw new Error(data.error || 'Request failed');return data;}
function modeLabel(r){return r.analysis_mode==='caption_cover'?'Quickly understood':r.analysis_mode==='video_sampled'?'Video analyzed':'Waiting for analysis';}
function basisLabel(a){return ({caption_and_cover:'Based on caption and cover',caption_only:'Based on available caption and title',cover_only:'Based on cover only',sampled_frames:'Based on sampled video frames',sampled_frames_and_speech:'Based on sampled video frames and speech'})[a?.evidence_basis] || 'Based on stored video evidence';}
function statusLabel(r){if(r.status==='review' && r.analysis?.video_approval_required)return 'Video approval needed';if(r.status==='waiting_model')return 'Waiting for model';if(r.status==='reading' && r.metadata_attempts)return `Retrieving info ${r.metadata_attempts}/10`;return r.status==='failed'?'Processing error':r.status==='review'?'Needs review':!terminal(r.status)?r.status==='queued'?'Queued':r.status.charAt(0).toUpperCase()+r.status.slice(1):modeLabel(r);}
function settings(open=true){document.body.classList.remove('nav-open');$('#menu-toggle').setAttribute('aria-expanded','false');$('#settings').hidden=!open;document.body.classList.toggle('show-settings',open);if(open)$('#settings-title').scrollIntoView({block:'start'});}
const folderIcon='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3Z"/></svg>';
let showAllFolders=false, browseScroll=0, folderSignature='', librarySignature='';
function renderBoxes(){
 const signature=JSON.stringify([boxes,boxFilter,filter,showAllFolders,$('#query').value]);if(signature===folderSignature)return;folderSignature=signature;
 $('#box-count').textContent=boxes.length;
 const selectedBox=boxes.find(b=>String(b.id)===boxFilter);const activeMatch=boxes.find(b=>b.matching && b.matching.state!=='done');const matchBox=selectedBox?.matching?selectedBox:activeMatch;const matching=matchBox?.matching;
 $('#folder-match-status').hidden=!matching;
 if(matching)$('#folder-match-status').textContent=matching.state==='done'?`${matchBox.name}: added ${matching.added} matching reels. Original folders preserved.`:`${matchBox.name}: checking saved reels (${matching.scanned}/${matching.total}), ${matching.added} added. ${matching.paused?'Matching is paused. Resume processing to continue.':matching.error || 'Original folders stay unchanged.'}`;
 $('#folder-total').textContent=boxes.length;$('#folder-grid').dataset.expanded=String(showAllFolders);
 $('#box-nav').innerHTML=boxes.map(b=>`<button data-box="${b.id}" aria-pressed="${String(b.id)===boxFilter}"><span class="folder-nav-label">${folderIcon}${esc(b.name)}</span><span>${b.count}</span></button>`).join('') || '<p class="small muted">Folders appear as your reels are understood.</p>';
 const featured=[...boxes].sort((a,b)=>b.count-a.count);
 $('#folder-grid').innerHTML=(showAllFolders?featured:featured.slice(0,6)).map((b,i)=>`<button class="folder-tile tone-${i%6}" data-box="${b.id}" aria-label="Open ${esc(b.name)}, ${b.count} reels"><span class="folder-shape">${folderIcon}<span class="folder-arrow" aria-hidden="true">&#8599;</span><strong>${esc(b.name)}</strong><span class="folder-bottom"><span>${b.count} saved ${b.count===1?'idea':'ideas'}</span><span class="folder-stamp">R / ${String(i+1).padStart(2,'0')}</span></span></span></button>`).join('');
 $('#all-folders').hidden=boxes.length<=6;
 $('#all-folders').setAttribute('aria-expanded',String(showAllFolders));
 $('#all-folders').textContent=showAllFolders?'Show fewer folders':'View all '+boxes.length+' folders';
 $('#folder-section').hidden=!boxes.length || !!boxFilter || filter!=='all' || !!$('#query').value.trim();
}
function renderList(){
 $('#library').setAttribute('aria-busy','false');
 const signature=JSON.stringify([reels,selectedId,filter,boxFilter,limit,boxes.find(b=>String(b.id)===boxFilter)?.matching?.state]);if(signature===librarySignature){renderBoxes();return;}librarySignature=signature;
 $('#result-count').textContent=reels.length+(reels.length>=limit?'+':'');
 $('#load-more').hidden=reels.length<limit || limit>=1000;
 $('#list-empty').hidden=!!reels.length;
 $('#list-empty').textContent=filter!=='all' || boxFilter || $('#query').value?'No saves match this view. Try another filter or search.':'Your saved ideas will appear here. Open Connection & settings to connect Instagram or add a reel.';
 const matchingBox=boxes.find(b=>String(b.id)===boxFilter);if(!reels.length && matchingBox?.matching && matchingBox.matching.state!=='done')$('#list-empty').textContent='Looking for matching saved reels. They will appear here as they are found.';
 $('#library').innerHTML=reels.map(r=>`<button class="reel-row" data-reel="${esc(r.id)}" aria-current="${r.id===selectedId}" aria-label="Open ${esc(r.title || 'Saved reel')}"><span class="card-media">${r.thumbnail?`<img src="${esc(r.thumbnail)}" width="360" height="270" alt="" loading="lazy">`:`<span class="mini-placeholder">${icon}<span>Cover unavailable</span></span>`}<span class="card-open" aria-hidden="true">&#8599;</span><span class="card-basis">${r.analysis_mode==='video_sampled'?'Video analyzed':r.analysis_mode==='caption_cover'?'Caption & cover':'Awaiting analysis'}</span></span><span class="row-copy"><span class="card-topic">${esc(r.boxes?.[0]?.name || (r.status==='review'?'Needs review':r.status==='failed'?'Processing error':'Saved idea'))}${r.boxes?.length>1?`<span class="extra-folders" title="${esc(r.boxes.slice(1).map(b=>b.name).join(', '))}"> +${r.boxes.length-1}</span>`:''}</span><span class="row-title">${esc(r.title || 'Saved reel')}</span><small><span>${esc(r.creator || 'Instagram')}</span><span class="card-state ${r.status}">${r.status==='ready'?'Ready':esc(statusLabel(r))}</span></small></span></button>`).join('');
 renderBoxes();
}
async function loadReels(){
 const version=++listVersion;
 listController?.abort();listController=new AbortController();
 const params=new URLSearchParams({limit:String(limit)});
 if(boxFilter)params.set('box',boxFilter);
 if(['caption_cover','video_sampled'].includes(filter))params.set('mode',filter);
 else if(filter!=='all')params.set('status',filter);
 const q=$('#query').value.trim();if(q){params.set('q',q);if($('#semantic').checked)params.set('semantic','1');}
 $('#library').setAttribute('aria-busy','true');
 try{
  const result=await api('/reels?'+params,undefined,listController.signal);
  if(version!==listVersion)return;
  reels=result;$('#list-error').hidden=true;
  if(!reels.some(r=>r.id===selectedId)){
   selectedId=reels[0]?.id || '';detailSignature='';
   if(selectedId)await showReel(selectedId,false);
   else {++detailVersion;if(filter!=='all' || boxFilter || q)$('#detail').innerHTML='<div class="welcome"><h2>No matching saves.</h2><p>Choose another topic or search to find your next idea.</p></div>';else $('#detail').innerHTML='<div class="welcome"><h2>A place for your saved ideas.</h2><p>Open Connection & settings to connect your Instagram Saved page or add a reel.</p><button id="connect-button" class="button primary">Connect Instagram</button></div>';}
  }else await showReel(selectedId,false);
  if(version===listVersion)renderList();
 }catch(e){if(e.name!=='AbortError' && version===listVersion){$('#list-error').hidden=false;$('#list-error').textContent=e.message;$('#library').setAttribute('aria-busy','false');}}
}
async function showReel(id,focus=true){
 const version=++detailVersion;
 selectedId=id;
 const r=await api('/reels/'+encodeURIComponent(id));
 if(version!==detailVersion)return;const position=reels.findIndex(item=>item.id===id);$('#previous-reel').disabled=position<=0;$('#next-reel').disabled=position<0 || position>=reels.length-1;$('#reel-position').textContent=position>=0?`${position+1} / ${reels.length}`:'';
 if(focus){browseScroll=window.scrollY;settings(false);document.body.classList.add('show-detail');document.body.classList.remove('nav-open');$('#menu-toggle').setAttribute('aria-expanded','false');}
 const signature=JSON.stringify([r,boxes]);
 if(signature!==detailSignature){
  detailSignature=signature;
  const a=r.analysis,active=!terminal(r.status),canAssign=!!a && terminal(r.status);
  $('#detail').innerHTML=`<article class="reel-detail"><div class="detail-top"><span class="breadcrumb">${esc(r.creator || 'Instagram saved reel')}${r.boxes?.length?`<span class="detail-folder-label">${folderIcon}${r.boxes.map(b=>esc(b.name)).join(' / ')}</span>`:''}</span><button class="text-button" id="edit-topic" ${boxFilter?'':'hidden'}>Edit topic box</button></div><div class="detail-grid"><figure class="cover">${r.thumbnail?`<img src="${esc(r.thumbnail)}" alt="Cover for ${esc(r.title || 'saved reel')}" width="360" height="480">`:`<div class="cover-empty">${icon}<span>No cover available</span></div>`}<figcaption>${a?esc(basisLabel(a)):'Awaiting analysis'}${a?.sampled_frames?`<br>${a.sampled_frames} frames sampled across ${Math.round(a.duration || 0)} seconds`:''}</figcaption></figure><div class="detail-body"><span class="badge ${r.status==='failed'?'failed':r.status==='review'?'review':''}">${esc(statusLabel(r))}</span><h2 id="detail-title">${esc(r.title || 'Saved reel')}</h2><p class="summary summary-preview">${esc(a?.summary || 'This reel is waiting to be understood. Caption and cover are checked first; video analysis requires your approval when more evidence is needed.')}</p>${a?.summary?'<button class="text-button" id="full-summary" aria-expanded="false">Read full summary</button>':''}<p class="evidence-label">${a?esc((a.summary_kind?.endsWith('_preview')?({caption_preview:'Caption preview',transcript_preview:'Transcript preview',source_title_preview:'Source title preview'})[a.summary_kind]+' - ':'')+basisLabel(a)):'No analysis evidence yet'}</p>${r.missing_info?.length?`<p class="error-message">Missing information: ${r.missing_info.map(esc).join(', ')}. Retrieval attempts: ${r.metadata_attempts}/10.</p>`:''}${a?.video_approval_required?`<p class="processing" role="status">Video analysis needs your approval. ${esc(a.video_approval_reason || 'More context is needed.')} No video will be downloaded until you approve.</p>`:''}${r.error?`<p class="error-message">${esc(r.error)}${a?'<br>Your previous analysis is preserved below.':''}</p>`:''}${active?`<p class="processing" role="status">${esc(statusLabel(r))}... ${a?'Your previous result remains available.':''}</p>`:''}<div class="actions"><a class="button primary" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">Open original</a><button class="button" id="analyze-video" ${active?'disabled':''}>${active?'Processing...':a?.video_approval_required?'Approve video analysis':'Analyze video'}</button>${r.status==='failed'?'<button class="button" id="retry-reel">Retry</button>':''}${r.missing_info?.length?`<button class="button" id="retry-info" ${active?'disabled':''}>Retry missing info</button>`:''}</div>${a?`<div class="tags">${(a.tags || []).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>${a.key_ideas?.length?`<h3>Ideas to keep</h3><ul>${a.key_ideas.map(v=>`<li>${esc(v)}</li>`).join('')}</ul>`:''}<details class="assignment-details"><summary>Organize in folders</summary><p class="small muted">Choose as many folders as you like. Saving keeps these selections during future reanalysis.</p><form id="assign-form"><div class="box-checks">${boxes.map(b=>`<label><input name="reel-box" type="checkbox" value="${b.id}" ${r.boxes.some(x=>x.id===b.id)?'checked':''} ${canAssign?'':'disabled'}>${esc(b.name)}</label>`).join('') || '<span class="small muted">Create a box in the sidebar to assign this reel.</span>'}</div><button type="submit" class="text-button" ${canAssign?'':'disabled'}>Save folders</button></form><p class="small muted">${esc(a.box_reason || '')}</p></details>${a.uncertainties?.length?`<h3>Needs a closer look</h3><ul>${a.uncertainties.map(v=>`<li>${esc(v)}</li>`).join('')}</ul>`:''}${a.warnings?.length?`<p class="small muted">${a.warnings.map(esc).join('<br>')}</p>`:''}<details><summary>Evidence & processing</summary><p>${esc(basisLabel(a))}. ${a.sampled_frames?'Temporal samples can miss brief events.':'The video has not been analyzed for this result.'}</p><p>Vision: ${esc(a.model===null?'Not used (source preview)':a.model || 'Legacy analysis')}<br>Decisions: ${esc(a.decision_model || 'Legacy categorizer')}</p>${a.transcript?.length?`<h3>Speech transcript</h3>${a.transcript.map(s=>`<p><b>${s.start}s</b> ${esc(s.text)}</p>`).join('')}`:`<p>${a.sampled_frames?'No speech transcript available.':'Speech has not been transcribed.'}</p>`}${(a.frames || []).map(f=>`<p><b>${f.second}s</b> ${esc(f.observations)}<br>Visible text: ${esc(f.visible_text)}</p>`).join('')}<p>Model scores are heuristics; they do not guarantee accuracy.</p></details>`:''}</div></div></article>`;
 }
 document.querySelectorAll('[data-reel]').forEach(b=>b.setAttribute('aria-current',String(b.dataset.reel===id)));
 if(focus){window.scrollTo(0,0);$('#detail').focus({preventScroll:true});}
}
async function refresh(){
 if(refreshing)return;refreshing=true;
 try{
  const [newBoxes,health,sync,notifications,processing]=await Promise.all([api('/boxes'),api('/health'),api('/sync-status'),api('/notifications'),api('/processing')]);
  if(typeof renderProcessing==='function')renderProcessing(processing);
  const batchSize=processing.batch_size;
  $('#batch-panel').hidden=false;
  const progress=`Batch ${processing.batch_id}: ${processing.completed}/${batchSize || 'unlimited'} reels finished. ${processing.queued} queued.`;
  $('#batch-status').textContent=processing.stopped?`Processing stopped. ${progress} Resume when ready. An in-flight request may finish before cleanup.`:processing.waiting_reason?`Waiting for ${processing.waiting_model || 'Ollama'}. ${processing.waiting_reason} Work stays queued; model availability is checked with backoff. ${progress}`:processing.paused?`Batch ${processing.batch_id}: ${processing.completed}/${batchSize} reels finished. Paused for your verification. ${processing.queued} queued. Continue when you are ready.`:`${progress}${processing.in_flight?` ${processing.in_flight} in progress.`:''}${batchSize?' Processing will pause at the limit.':''}`;
  $('#continue-batch').hidden=!processing.paused || processing.stopped;
  $('#stop-processing').hidden=!!processing.stopped;
  $('#resume-processing').hidden=!processing.stopped && !processing.waiting_reason;
  $('#resume-processing').textContent=processing.stopped?'Resume processing':'Retry models now';
  $('#continue-batch').textContent=`Continue next ${batchSize}`;
  if(document.activeElement!==$('#batch-size'))$('#batch-size').value=String(batchSize);
  const notices=JSON.stringify(notifications);
  if(notices!==notificationSignature){
   notificationSignature=notices;$('#notifications').hidden=!notifications.length || !document.body.classList.contains('show-notifications');
   $('#notification-button').hidden=!notifications.length;
   $('#notification-button').textContent=`Notifications (${notifications.length})`;
   $('#notifications').innerHTML=notifications.length?'<div class="section-heading"><h2>Some reel information is still missing</h2><button class="text-button" id="close-notifications">Close</button></div>'+notifications.map(n=>`<div><h3>${esc(n.title || 'Saved reel')}</h3><p>${esc(n.message)}</p><div class="actions"><button class="button" data-notice-reel="${esc(n.reel_id)}">View reel</button><button class="text-button" data-dismiss-notice="${n.id}">Dismiss notification</button></div></div>`).join(''):'';
  }
  boxes=newBoxes;renderBoxes();
  const counts=health.counts;
  $('#total').textContent=Object.values(counts).reduce((a,b)=>a+b,0);
  $('#quick-count').textContent=health.modes.caption_cover || 0;$('#video-count').textContent=health.modes.video_sampled || 0;
  $('#review-count').textContent=counts.review || 0;$('#failed-count').textContent=counts.failed || 0;
  const queue=Object.entries(counts).filter(([s])=>!terminal(s)).reduce((n,[,v])=>n+v,0);
  $('#queue-status').textContent=processing.stopped?'Processing stopped':processing.waiting_reason?'Waiting for model':processing.paused?'Paused for verification':queue?`${queue} queued / processing`:processing.folder_matching?'Matching folders':'Library up to date';
  $('#connection-text').textContent=health.ollama!=='ready'?`Ollama: ${health.ollama}. Start Ollama and check your models in settings.`:sync.message || 'Connect the browser extension to bring in your saved reels.';
  $('#vision-model').textContent=health.model;$('#decision-model').textContent=health.decision_model;
  await loadReels();
 }catch(e){$('#connection-text').textContent='Local app unavailable. Start Reelbox and try again.';}finally{refreshing=false;}
}
function changeFilter(next,box=''){
 filter=next;boxFilter=box;limit=100;document.body.classList.remove('show-detail','show-settings','nav-open','show-folder-editor');$('#menu-toggle').setAttribute('aria-expanded','false');$('#settings').hidden=true;
 $('#library').scrollTop=0;
 document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(!box && b.dataset.filter===filter)));
 $('#list-title').textContent=box?boxes.find(b=>String(b.id)===box)?.name || 'Topic box':({all:'All saves',caption_cover:'Quickly understood',video_sampled:'Video analyzed',review:'Needs review',failed:'Processing errors'})[filter];
 $('#folder-description').hidden=!box;$('#folder-description').textContent=box?boxes.find(b=>String(b.id)===box)?.description || 'Saved ideas in this folder.':'';renderBoxes();loadReels();
}
async function queueAnalysis(path,button){button.disabled=true;try{const result=await api(path,{id:selectedId});toast(result.queued?(path==='/retry-info'?'Information retrieval queued, up to 10 attempts. Your analysis is preserved.':'Analysis queued. Your previous result stays available.'):'This reel is already processing.');detailSignature='';await refresh();}catch(e){toast(e.message);button.disabled=false;}}
function editBox(box){$('#box-editor').hidden=false;$('#box-editor-title').textContent=box?'Edit folder':'Create folder';$('#box-id').value=box?.id || '';$('#box-name').value=box?.name || '';$('#box-description').value=box?.description || '';document.body.classList.add('show-detail','show-folder-editor');$('#box-name').focus();}
document.addEventListener('click',e=>{
 const notice=e.target.closest('[data-notice-reel]');if(notice)showReel(notice.dataset.noticeReel).catch(err=>toast(err.message));
 const dismiss=e.target.closest('[data-dismiss-notice]');if(dismiss){dismiss.disabled=true;api('/notifications/dismiss',{id:Number(dismiss.dataset.dismissNotice)}).then(()=>refresh()).catch(err=>{toast(err.message);dismiss.disabled=false;});}
 const reel=e.target.closest('[data-reel]');if(reel)showReel(reel.dataset.reel).catch(err=>toast(err.message));
 const topic=e.target.closest('[data-box]');if(topic)changeFilter('all',topic.dataset.box===boxFilter?'':topic.dataset.box);
 const f=e.target.closest('[data-filter]');if(f)changeFilter(f.dataset.filter);
 const button=e.target.closest('button');if(!button)return;
 if(button.id==='connect-button')settings();
 if(button.id==='close-notifications'){document.body.classList.remove('show-notifications','show-detail');$('#notifications').hidden=true;$('#notification-button').focus();}
 if(button.id==='back-library'){$('#box-editor').hidden=true;document.body.classList.remove('show-detail','show-notifications','show-folder-editor');$('#notifications').hidden=true;window.scrollTo(0,browseScroll);$('#library [aria-current=true]')?.focus({preventScroll:true});}
 if(button.id==='analyze-video')queueAnalysis('/analyze-video',button);
 if(button.id==='retry-reel')queueAnalysis('/retry',button);
 if(button.id==='retry-info')queueAnalysis('/retry-info',button);
 if(button.id==='edit-topic')editBox(boxes.find(b=>String(b.id)===boxFilter));
 if(button.id==='full-summary'){const expanded=button.getAttribute('aria-expanded')==='true';button.setAttribute('aria-expanded',String(!expanded));button.textContent=expanded?'Read full summary':'Short summary';$('.summary').classList.toggle('summary-preview',expanded);}
});
document.addEventListener('submit',async e=>{
 if(e.target.id!=='assign-form')return;e.preventDefault();const button=e.submitter;button.disabled=true;
 try{await api('/reel-boxes',{id:selectedId,box_ids:[...document.querySelectorAll('[name=reel-box]:checked')].map(i=>Number(i.value))});toast('Topic boxes updated.');detailSignature='';await refresh();}catch(err){toast(err.message);}finally{button.disabled=false;}
});
$('#settings-button').addEventListener('click',()=>settings());
$('#batch-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;try{await api('/processing',{action:'configure',batch_size:Number($('#batch-size').value)});toast('Processing limit updated.');await refresh();}catch(err){toast(err.message);}finally{button.disabled=false;}});
$('#continue-batch').addEventListener('click',async e=>{const button=e.currentTarget;button.disabled=true;try{await api('/processing',{action:'continue'});toast('Next batch started. Processing will pause again at the limit.');await refresh();}catch(err){toast(err.message);}finally{button.disabled=false;}});
$('#notification-button').addEventListener('click',()=>{settings(false);document.body.classList.add('show-detail');document.body.classList.add('show-notifications');$('#notifications').hidden=false;$('#notifications').scrollIntoView({block:'start'});});
$('#close-settings').addEventListener('click',()=>{settings(false);$('#settings-button').focus();});
$('#search-form').addEventListener('submit',e=>{e.preventDefault();document.body.classList.remove('show-detail','show-settings');$('#settings').hidden=true;limit=100;loadReels();});
$('#query').addEventListener('search',()=>{if(!$('#query').value)loadReels();});
$('#load-more').addEventListener('click',()=>{limit=Math.min(1000,limit+100);loadReels();});
$('#semantic').addEventListener('change',()=>{if($('#query').value.trim())loadReels();});
$('#sync-button').addEventListener('click',async e=>{const button=e.currentTarget;button.disabled=true;try{const result=await api('/sync',{mode:'force'});toast(result.message);}catch(err){toast(err.message);}finally{button.disabled=false;}});
$('#test-models').addEventListener('click',async e=>{const button=e.currentTarget;button.disabled=true;$('#model-result').textContent='Testing with synthetic evidence...';try{await api('/model-check',{});$('#model-result').textContent='Both models responded successfully.';}catch(err){$('#model-result').textContent=err.message;}finally{button.disabled=false;}});
$('#copy-token').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(token);toast('API token copied.');}catch{$('#api-token').type='text';$('#api-token').select();toast('Copy the selected token.');}});
$('#add-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;try{const result=await api('/ingest',{items:[{url:$('#reel-url').value}]});toast(result.added?'Reel queued.':'This reel is already in your library.');$('#reel-url').value='';await refresh();}catch(err){toast(err.message);}finally{button.disabled=false;}});
$('#new-box').addEventListener('click',()=>editBox());
$('#close-box').addEventListener('click',()=>{$('#box-editor').hidden=true;document.body.classList.remove('show-detail','show-folder-editor');});
$('#box-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;try{const result=await api('/boxes',{id:$('#box-id').value || undefined,name:$('#box-name').value,description:$('#box-description').value});$('#box-editor').hidden=true;toast('Folder saved. Matching existing reels in the background; original folders are preserved.');await refresh();changeFilter('all',String(result.id));}catch(err){toast(err.message);}finally{button.disabled=false;}});
(async()=>{try{token=(await fetch('/api/bootstrap').then(r=>{if(!r.ok)throw new Error('Local app rejected the connection');return r.json();})).token;$('#api-token').value=token;$('#api-base').textContent=location.origin+'/api';await refresh();setInterval(()=>{if(!document.hidden && !document.querySelector('#query:focus') && !document.querySelector('#box-editor:not([hidden])'))refresh();},6000);}catch(e){$('#connection-text').textContent='Could not connect to the local app. Start Reelbox and reload.';toast(e.message);}})();

document.querySelector('.skip-link').addEventListener('click',e=>{e.preventDefault();settings(false);document.body.classList.add('show-detail');$('#detail').focus();});

async function controlProcessing(action,button){button.disabled=true;try{await api('/processing',{action});toast(action==='stop'?'Processing stopped. Queue and progress are preserved.':'Processing resumed. Waiting work will retry when models are available.');await refresh();}catch(e){toast(e.message);}finally{button.disabled=false;}}
$('#stop-processing').addEventListener('click',e=>controlProcessing('stop',e.currentTarget));
$('#resume-processing').addEventListener('click',e=>controlProcessing('resume',e.currentTarget));

$('#all-folders').addEventListener('click',()=>{showAllFolders=!showAllFolders;renderBoxes();});
for(const mode of ['grid','list'])$('#'+mode+'-view').addEventListener('click',()=>{
 document.body.classList.toggle('list-layout',mode==='list');
 try{localStorage.setItem('reelbox-view',mode);}catch{} $('#grid-view').setAttribute('aria-pressed',String(mode==='grid'));$('#list-view').setAttribute('aria-pressed',String(mode==='list'));
});
$('#menu-toggle').addEventListener('click',()=>{const open=document.body.classList.toggle('nav-open');$('#menu-toggle').setAttribute('aria-expanded',String(open));});
let savedTheme;try{savedTheme=localStorage.getItem('reelbox-theme');}catch{}
function applyTheme(theme){document.documentElement.dataset.theme=theme;$('#theme-toggle').setAttribute('aria-label','Switch to '+(theme==='dark'?'light':'dark')+' theme');}
applyTheme(savedTheme || 'light');
$('#theme-toggle').addEventListener('click',()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';applyTheme(theme);try{localStorage.setItem('reelbox-theme',theme);}catch{}});
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'){if(!$('#settings').hidden)settings(false);else if(document.body.classList.contains('show-detail'))$('#back-library').click();document.body.classList.remove('nav-open','show-notifications');$('#menu-toggle').setAttribute('aria-expanded','false');$('#notifications').hidden=true;}
 if((e.ctrlKey || e.metaKey) && e.key==='k'){e.preventDefault();settings(false);document.body.classList.remove('show-detail');$('#query').focus();}
});

try{if(localStorage.getItem('reelbox-view')==='list')$('#list-view').click();}catch{}

for(const [id,step] of [['previous-reel',-1],['next-reel',1]])$('#'+id).addEventListener('click',()=>{const next=reels[reels.findIndex(r=>r.id===selectedId)+step];if(next)showReel(next.id).catch(err=>toast(err.message));});
