/* Live state comes only from the authenticated processing response. */
const flowCards = new Map(), flowSeen = new Map();
let flowBusy = false, flowBatch, flowFocusedReel, flowLatest, flowObservedAt=0, flowPolledAt=0;
const flowDuration = seconds => seconds == null ? 'Not measured' : `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
function renderProcessing(processing) {
 const metrics = processing.metrics;
 let board = processing.board;
 if (!board || !metrics) return;
 if (processing.observed_at && processing.observed_at < flowObservedAt) return;
 flowObservedAt = processing.observed_at || flowObservedAt;
 flowLatest = processing;
 board = {...board, unorganized:[...board.unorganized], organizing:[...board.organizing], organized:[...board.organized]};
 if (flowFocusedReel) {
  flowFocusedReel = [...board.unorganized,...board.organizing,...board.organized].find(r=>r.id===flowFocusedReel.id) || flowFocusedReel;
  const lane = flowFocusedReel.status === 'ready' && flowFocusedReel.boxes.length ? 'organized' : flowFocusedReel.status === 'queued' ? 'unorganized' : !terminal(flowFocusedReel.status) && flowFocusedReel.status !== 'waiting_model' ? 'organizing' : null;
  if (lane) board[lane] = [flowFocusedReel,...board[lane].filter(r=>r.id!==flowFocusedReel.id)];
 }
 const panel = $('#processing-flow'); panel.hidden = false;
 if (flowBatch !== processing.batch_id) { flowSeen.clear(); flowBatch = processing.batch_id; }
 $('#flow-state').textContent = processing.stopped ? 'Paused by you' : processing.waiting_reason ? 'Waiting for model' : processing.paused ? 'Ready for your review' : board.counts.organizing ? 'Organizing on this computer' : 'Your library, in order';
 const control = $('#flow-control');control.hidden = !(processing.stopped || board.counts.unorganized || board.counts.organizing);control.textContent = processing.stopped ? 'Resume processing' : 'Stop processing';control.dataset.action = processing.stopped ? 'resume' : 'stop';
 const values = {'run-organized':metrics.measured ? String(metrics.organized) : 'Not measured', 'run-elapsed':flowDuration(metrics.elapsed_seconds),
  'run-speed':metrics.reels_per_minute == null ? 'Not measured' : `${metrics.reels_per_minute.toFixed(1)} / min`, 'run-median':metrics.median_seconds == null ? 'Not measured' : `${metrics.median_seconds.toFixed(1)}s`};
 for (const [id, value] of Object.entries(values)) if ($('#'+id).textContent !== value) $('#'+id).textContent = value;
 $('#flow-measurement').textContent = metrics.measured ? `Run ${metrics.batch_id} · ${metrics.tracked} unique reels started · wall time includes pauses and retries` : 'Timings begin with new processing. Existing reels have no historical speed measurement.';
 $('#flow-exceptions').textContent = `${board.counts.review} need review · ${board.counts.waiting} waiting for model · ${board.counts.errors} errors`;
 const oldPositions = new Map([...flowCards].map(([id, node]) => [id, node.getBoundingClientRect()]));
 const keep = new Set(); let announced = '';
 for (const lane of ['unorganized','organizing','organized']) {
  $('#flow-count-'+lane).textContent = board.counts[lane];
  const host = $('#flow-'+lane);
  for (const reel of board[lane]) {
   keep.add(reel.id);
   let card = flowCards.get(reel.id);
   if (!card) { card = document.createElement('div'); card.className = 'flow-card'; card.dataset.flowId = reel.id; flowCards.set(reel.id,card); }
   const previous = flowSeen.get(reel.id);
   if (previous && previous !== lane && lane === 'organized') { card.dataset.arrived = String(Date.now()); announced = `${reel.title} organized in ${reel.boxes[0]?.name || 'its folder'}.`; }
   card.classList.toggle('just-organized', lane === 'organized' && Date.now() - Number(card.dataset.arrived || 0) < 12000);
   const state = lane === 'organized' ? reel.boxes[0]?.name || 'Organized' : lane === 'unorganized' ? 'Waiting for analysis' : statusLabel(reel);
   const following = flowFocusedReel?.id === reel.id;
   card.classList.toggle('following', following);
   const signature = JSON.stringify([reel,state,following]);
   if (card.dataset.signature !== signature) {
    card.dataset.signature = signature;
    card.innerHTML = `<button class="flow-open" data-flow-reel="${esc(reel.id)}" aria-label="Open ${esc(reel.title)}">${reel.thumbnail ? `<img src="${esc(reel.thumbnail)}" alt="" width="42" height="52">` : '<span class="flow-placeholder">'+icon+'</span>'}<span><strong>${esc(reel.title)}</strong><small>${following?'Following · ':''}${esc(state)}</small></span></button>${lane === 'organized' && reel.boxes[0] ? `<button class="flow-folder" data-box="${reel.boxes[0].id}" aria-label="Open folder ${esc(state)}">↗</button>` : `<button class="flow-folder" data-flow-follow="${esc(reel.id)}" aria-pressed="${following}" aria-label="${following?'Stop following':'Follow'} this reel">◎</button>`}`;
   }
   host.appendChild(card); flowSeen.set(reel.id,lane);
  }
  host.querySelector('.flow-empty')?.remove();
  if (!board[lane].length) { const empty = document.createElement('p'); empty.className = 'flow-empty'; empty.textContent = ({unorganized:'Nothing waiting.',organizing:'New work appears here.',organized:'Finished reels land in their folders.'})[lane];host.appendChild(empty); }
 }
 for (const [id,node] of flowCards) if (!keep.has(id)) { node.remove(); flowCards.delete(id); }
 if (!matchMedia('(prefers-reduced-motion: reduce)').matches && panel.getClientRects().length) {
  for (const [id,node] of flowCards) {
   const before = oldPositions.get(id), after = node.getBoundingClientRect();
   if (before && before.width && after.width && (Math.abs(before.x-after.x)>1 || Math.abs(before.y-after.y)>1)) node.animate([{transform:`translate(${before.x-after.x}px,${before.y-after.y}px)`,opacity:.7},{transform:'translate(0,0)',opacity:1}],{duration:650,easing:'cubic-bezier(.2,.7,.2,1)'});
  }
 }
 if (announced) $('#flow-announcement').textContent = announced;
}
document.addEventListener('click', event => {
 const card = event.target.closest('[data-flow-reel]');
 if (card) showReel(card.dataset.flowReel).catch(error => toast(error.message));
 const follow = event.target.closest('[data-flow-follow]');
 if (follow) {
  flowFocusedReel = flowFocusedReel?.id === follow.dataset.flowFollow ? null : [...flowLatest.board.unorganized,...flowLatest.board.organizing].find(r=>r.id===follow.dataset.flowFollow);
  renderProcessing(flowLatest);
 }
});
setInterval(async () => {
 if (!token || document.hidden || flowBusy) return;
 const working=flowLatest && !flowLatest.stopped && !flowLatest.paused && (flowLatest.board.counts.unorganized || flowLatest.board.counts.organizing);
 if (!working && Date.now()-flowPolledAt<2000) return;
 flowPolledAt=Date.now();
 flowBusy = true;
 try {
  const processing = await api('/processing');
  if (flowFocusedReel) flowFocusedReel = await api('/reels/'+encodeURIComponent(flowFocusedReel.id));
  renderProcessing(processing); $('#flow-error').hidden = true;
 }
 catch { $('#flow-error').hidden = false; }
 finally { flowBusy = false; }
}, 500);

$('#flow-control').addEventListener('click',event=>controlProcessing(event.currentTarget.dataset.action,event.currentTarget));
