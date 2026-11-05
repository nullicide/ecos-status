'use strict';
(() => {
 const DISPLAY={
  website:'Public website',operating_picture:'Operating picture',standards:'Standards & governance',
  signup:'Create account',enterprise:'Enterprise access inquiry',
  access:'Application sign-in',requests:'Previous Request Access URL (retired)'
 };
 const DESC={
  website:'Homepage, capabilities and interactive demo page reachability',
  operating_picture:'Public infrastructure lifecycle and operating-picture page',
  standards:'Public standards and governance reference',
  signup:'Individual registration page; registration and email verification are not tested',
  enterprise:'Enterprise inquiry page; form submission and delivery are not tested',
  access:'Application sign-in page; authentication and workspace access are not tested'
 };
 const HREF={
  website:'https://www.energycontrolos.com/',
  operating_picture:'https://www.energycontrolos.com/operating-picture/',
  standards:'https://www.energycontrolos.com/standards/',
  signup:'https://www.energycontrolos.com/create-account/',
  enterprise:'https://www.energycontrolos.com/enterprise-access/',
  access:'https://app.energycontrolos.com/login/'
 };
 const LABEL={operational:'Operational',degraded:'Intermittent response',outage:'Unavailable',unknown:'Not currently verified',maintenance:'Maintenance'};
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const el=id=>document.getElementById(id);
 const date=s=>{if(!s)return 'Not available';const d=new Date(s);return Number.isFinite(d.getTime())?d.toLocaleString(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}):'Not available'};
 const dayKey=(d)=>d.toISOString().slice(0,10);
 const monitoredOrder=['website','operating_picture','standards','signup','enterprise','access'];
 function global(state,report,title){const box=el('globalStatus');box.dataset.state=state;const headline={operational:'All monitored endpoints reachable',degraded:'Some endpoints need attention',outage:'Service disruption detected',unknown:'Monitoring unavailable'};el('globalTitle').textContent=title||headline[state];el('globalDetail').textContent=report||'No verified monitoring result is available.';}
 function historyCells(rows,id){let success=0,fail=0;const now=new Date();const cells=[];let observedDays=0;for(let n=89;n>=0;n--){let d=new Date(now);d.setUTCDate(d.getUTCDate()-n);const k=dayKey(d),v=rows[k]?.[id]||{},ok=v.ok||0,bad=v.fail||0,total=ok+bad;success+=ok;fail+=bad;if(total)observedDays++;const cls=total===0?'none':bad===0?'good':ok===0?'bad':'partial';cells.push(`<span class="day ${cls}" aria-label="${esc(k)}: ${total?ok+' passed, '+bad+' failed':'no observations'}" title="${esc(k)}: ${total?ok+' passed, '+bad+' failed':'no observations'}"></span>`)}return {cells:cells.join(''),success,fail,observedDays};}
 function render(payload){
  const now=Date.now(),checked=payload.checked_at?Date.parse(payload.checked_at):NaN;
  // Scheduled checks may arrive later than their nominal 5-minute cadence.
  // Keep a late last-known result visible in amber without presenting it as live green.
  const age=now-checked;
  const stale=!Number.isFinite(checked)||age>90*60*1000||age< -5*60*1000;
  const delayed=!stale&&age>25*60*1000;
  const raw=payload.components||{};const statuses=monitoredOrder.map(id=>stale?'unknown':raw[id]?.state||'unknown');
  const anyOut=statuses.includes('outage'),anyDeg=statuses.includes('degraded'),allOk=statuses.every(s=>s==='operational');
  const measured=anyOut?'outage':anyDeg?'degraded':allOk?'operational':'unknown';
  const state=stale?'unknown':delayed?(measured==='outage'?'outage':'degraded'):measured;
  global(state,stale?'The last external monitoring report is older than 90 minutes or unavailable. Historical observations are retained, but current health is unverified.':delayed?'The most recent external check was '+date(payload.checked_at)+'. Scheduled monitoring is delayed; the last known results are shown below, not confirmed current.':state==='operational'?'All listed public pages returned the expected HTML in the latest external checks. This does not verify registrations, inquiries, authentication, operational workflows or electrical safety.':state==='outage'?'At least one monitored endpoint failed repeated external availability checks. See incidents below.':state==='degraded'?'A monitored endpoint has returned inconsistent responses or is recovering.':'Some endpoints have not yet completed a verified check.',delayed&&state!=='outage'?'Monitoring delayed':stale&&Number.isFinite(checked)?'Monitoring data unavailable':undefined);
  el('lastChecked').textContent=stale?'Not current':new Date(payload.checked_at).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',timeZoneName:'short'})+(delayed?' · Delayed':'');el('globalTime').textContent=stale?'LAST REPORT UNAVAILABLE':(delayed?'LAST CHECK (DELAYED) ':'CHECKED ')+date(payload.checked_at).toUpperCase();
  el('componentList').innerHTML=monitoredOrder.map(id=>{const verified=raw[id]?.state||'unknown';const s=stale?'unknown':delayed&&verified!=='outage'?'degraded':verified;const title=delayed&&s!=='outage'?'Last check delayed':LABEL[s]||LABEL.unknown;return `<article class="component"><div><div class="component-title"><span class="state-dot ${esc(s)}" aria-hidden="true"></span><a class="component-target" href="${esc(HREF[id])}" target="_blank" rel="noopener noreferrer" aria-label="Open ${esc(DISPLAY[id])} in a new tab">${esc(DISPLAY[id])}</a></div><p>${esc(DESC[id])}</p></div><span class="state-label ${esc(s)}">${esc(title)}</span></article>`}).join('');
  const hist=payload.daily||{};
  el('historyList').innerHTML=monitoredOrder.map(id=>{const h=historyCells(hist,id),total=h.success+h.fail;const first=payload.first_checked_at?Date.parse(payload.first_checked_at):NaN;const ageHours=Number.isFinite(first)?(now-first)/36e5:0;const early=ageHours<24||total<200;const pct=total>0?(100*h.success/total).toFixed(2)+'%':'—';const statusText=total?'HTTP checks · '+h.success+'/'+total+' successful'+(early?' · Early monitoring data':''):'No HTTP checks recorded for this page yet';return `<div class="history-row"><div class="history-top"><strong>${esc(DISPLAY[id])}</strong><span class="history-pct">${esc(pct)}</span></div><p class="history-description">${esc(statusText)}</p><div class="days" role="img" aria-label="90-day HTTP check history for ${esc(DISPLAY[id])}; latest 30 days shown on small screens">${h.cells}</div><div class="history-foot"><span class="history-window-desktop">90-day window</span><span class="history-window-mobile">Last 30 days · 90-day totals</span><span>${h.observedDays} monitored ${h.observedDays===1?'day':'days'} · Today</span></div></div>`}).join('');
  // Preserve the old request-access URL's 467 earlier checks as legacy history;
  // its counts are intentionally never assigned to the new enterprise form.
  const legacy=historyCells(hist,'requests'),oldChecks=legacy.success+legacy.fail;
  const archive=el('retiredHistory');
  if(archive){
   archive.hidden=oldChecks===0;
   archive.innerHTML=oldChecks?
    '<div class="retired-top"><strong>Previous Request Access URL</strong><span>RETIRED MONITOR</span></div>'+
    '<p>Historical checks for the old /request-access/ URL are retained. This URL is no longer actively monitored, and its check history is not counted toward the new Enterprise access page.</p>'+
    '<small>'+legacy.success+'/'+oldChecks+' historic HTTP checks passed · '+legacy.observedDays+' observed days in the rolling window</small>':'';
  }
  const entries=(payload.incidents||[]).slice().sort((a,b)=>String(b.started_at).localeCompare(String(a.started_at))).slice(0,20);
  el('incidentList').innerHTML=entries.length?entries.map(i=>`<article class="timeline-item"><div class="timeline-date">${esc(date(i.started_at))}</div><div class="timeline-main"><strong>${esc(i.title)}</strong><p>${esc(i.detail||'')}</p><p>Component: ${esc(DISPLAY[i.component]||i.component||'Service')} · ${i.ended_at?'Resolved '+esc(date(i.ended_at)):'Update in progress'}</p>${(i.updates||[]).slice().reverse().slice(0,8).map(u=>`<p class="incident-update"><strong>${esc(date(u.at))} — ${esc(u.status)}</strong> ${esc(u.detail||'')}</p>`).join('')}<span class="timeline-status ${i.ended_at?'':'open'}">${i.ended_at?'Resolved':esc(i.status||'Investigating')}</span></div></article>`).join(''):'<div class="loading-item">No incidents have been published in the monitoring history.</div>';
  const maintenance=(payload.maintenance||[]).slice().sort((a,b)=>String(a.starts_at).localeCompare(String(b.starts_at))).filter(m=>!m.completed_at && Date.parse(m.ends_at||m.starts_at)>(now-24*3600*1000)).slice(0,8);
  el('maintenanceList').innerHTML=maintenance.length?maintenance.map(m=>`<article class="timeline-item"><div class="timeline-date">${esc(date(m.starts_at))}</div><div class="timeline-main"><strong>${esc(m.title)}</strong><p>${esc(m.detail||'')}</p><p>Expected end: ${esc(date(m.ends_at))} · Component: ${esc(DISPLAY[m.component]||'Multiple services')}</p><span class="timeline-status">Scheduled</span></div></article>`).join(''):'<div class="loading-item">No maintenance windows have been published.</div>';
 }
 async function load(){try{const r=await fetch('./data/status.json?at='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('No report');const j=await r.json();render(j)}catch(e){render({components:{},incidents:[],maintenance:[],daily:{}})}}
 // RSS subscription disclosure: a feed reader subscribes, not this static website.
 function initSubscription(){
  const trigger=el('openSubscribe'),dialog=el('subscribeDialog'),close=el('closeSubscribe');
  const input=el('subscribeFeedUrl'),copy=el('copySubscribeUrl'),feedback=el('subscribeFeedback');
  if(!trigger||!dialog||!input||!copy)return;
  // Without dialog support, the anchor continues to the valid RSS document.
  if(typeof dialog.showModal!=='function')return;
  trigger.addEventListener('click',event=>{event.preventDefault();feedback.textContent='';dialog.showModal();});
  close?.addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
  copy.addEventListener('click',async()=>{
   let copied=false;
   const value=input.value;
   try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);copied=true;}}
   catch(_e){}
   if(!copied){
    input.focus();input.select();
    try{copied=Boolean(document.execCommand?.('copy'));}catch(_e){}
   }
   feedback.textContent=copied?'RSS link copied. Add it to your preferred feed reader.':'Select and copy the RSS address above into your feed reader.';
   if(!copied){input.focus();input.select();}
  });
 }
 initSubscription();
 load();setInterval(load,60000);
})();
