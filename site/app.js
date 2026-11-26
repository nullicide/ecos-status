'use strict';
(() => {
 const names={platform:'ECOS Platform',identity:'Identity & Access',academy:'ECOS Academy',public_website:'Public Website',investor:'Investor Portal',
  website:'Public website (retired check)',operating_picture:'Operating picture (retired check)',standards:'Standards (retired check)',signup:'Create account (retired check)',enterprise:'Project inquiry (retired check)',access:'Sign-in page (retired check)',requests:'Previous Request Access URL (retired)',monitoring:'Status monitoring'};
 const ids=['platform','identity','academy','public_website','investor'];
 const descriptions={platform:'Project workspaces',identity:'Account access and sign-in',academy:'Learning and assessments',public_website:'Public website delivery',investor:'Investor access and documents'};
 const labels={operational:'Operational',degraded:'Degraded performance',partial:'Partial outage',outage:'Major outage',maintenance:'Scheduled maintenance',unknown:'Not yet verified',unavailable:'Monitoring unavailable'};
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const el=id=>document.getElementById(id);
 const date=s=>{const d=new Date(s||'');return Number.isFinite(d.getTime())?d.toLocaleString(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}):'Not available'};
 function history(rows,id){
  let ok=0,fail=0,days=0,unknown=0;const cells=[],observations=[];
  for(let n=89;n>=0;n--){
   const d=new Date();d.setUTCDate(d.getUTCDate()-n);const k=d.toISOString().slice(0,10);
   const row=rows[k]?.[id]||{},a=Number(row.operational||0),b=Number(row.outage||0)+Number(row.partial||0),c=Number(row.degraded||0),u=Number(row.unknown||0);
   ok+=a;fail+=b+c;unknown+=u;if(a+b+c)days++;
   const label=k+': '+(a+b+c+u?a+' operational, '+c+' degraded, '+b+' outage, '+u+' unverified':'no verified observations');
   if(a+b+c+u)observations.push(label);
   cells.push('<span class="day '+(b?'bad':c?'partial':a&&!u?'good':'none')+'" title="'+esc(label)+'"></span>');
  }
  return {ok,fail,days,unknown,cells:cells.join(''),summary:observations.join('; ')||'No verified observations'};
 }
 function incident(i,archived=false){
  const state=i.ended_at?'Resolved':archived?'Historical / retired check':(i.status||'Investigating');
  return '<article class="timeline-item"><div class="timeline-date">'+esc(date(i.started_at))+'</div><div class="timeline-main"><strong>'+esc(i.title)+'</strong><p>'+esc(i.detail||'')+'</p><p>'+esc(names[i.component]||i.component||'Service')+'</p>'+
   (i.updates||[]).slice().reverse().map(u=>'<p class="incident-update"><strong>'+esc(date(u.at))+' — '+esc(u.status)+'</strong> '+esc(u.detail||'')+'</p>').join('')+
   '<span class="timeline-status '+(i.ended_at||archived?'':'open')+'">'+esc(state)+'</span></div></article>';
 }
 function render(payload){
  const version=payload.monitoring_version===2,now=Date.now(),checked=version?Date.parse(payload.checked_at||''):NaN;
  const age=now-checked,stale=Number.isFinite(checked)&&(age>90*60000||age< -5*60000),delayed=!stale&&Number.isFinite(checked)&&age>25*60000;
  const fresh=Number.isFinite(checked)&&!stale&&!delayed;
  const raw=version?payload.components||{}:{};
  const incidents=(payload.incidents||[]).slice().sort((a,b)=>String(b.started_at).localeCompare(String(a.started_at)));
  const active=incidents.filter(i=>!i.ended_at&&(ids.includes(i.component)||i.component==='monitoring'));
  const maintenance=(payload.maintenance||[]).filter(m=>ids.includes(m.component)&&!m.completed_at&&Date.parse(m.ends_at)>now);
  const states={};
  for(const id of ids){
   let state=raw[id]?.state||'unknown';
   if(!Object.hasOwn(labels,state))state='unknown';
   if(!fresh)state=payload.unavailable||stale||delayed?'unavailable':'unknown';
   else if(active.some(i=>i.component===id&&i.origin==='manual')&&!['outage','partial'].includes(state))state='partial';
   else if(maintenance.some(m=>m.component===id&&Date.parse(m.starts_at)<=now)&&!['outage','partial'].includes(state))state='maintenance';
   states[id]=state;
  }
  const all=Object.values(states);
  const global=payload.unavailable||stale||delayed?'unavailable':all.includes('outage')?'outage':all.includes('partial')?'partial':all.includes('degraded')?'degraded':all.includes('maintenance')?'maintenance':all.every(s=>s==='operational')?'operational':'unknown';
  const box=el('globalStatus');box.dataset.state=global;
  el('globalTitle').textContent=delayed?'Monitoring delayed':global==='unknown'?(fresh?'Limited service verification':'Monitoring not yet verified'):global==='operational'?'All verified services operational':global==='outage'?'Service disruption detected':labels[global];
  el('globalDetail').textContent=!fresh?(Number.isFinite(checked)?'Last report is not current. Missing observations do not indicate service downtime.':payload.unavailable?'No monitoring source could be retrieved. Current service availability is unknown.':'No service-level report is available yet.'):'Current external observations; untested functions remain unknown. See service details.';
  el('globalTime').textContent=Number.isFinite(checked)?'LAST REPORT '+date(payload.checked_at):'NO SERVICE REPORT';
  el('lastChecked').textContent=Number.isFinite(checked)?date(payload.checked_at)+(stale?' · Stale':delayed?' · Delayed':''):'No report';
  el('componentList').innerHTML=ids.map(id=>{
   const s=states[id],p=raw[id],h=history(version?payload.service_state_daily||{}:{},id),total=h.ok+h.fail;
   const complete=p?.coverage_complete===true;
   const metric=complete&&total?(100*h.ok/total).toFixed(2)+'% sampled operational':'Insufficient data';
   return '<article class="component service-card"><div class="service-heading"><div class="component-title"><span class="state-dot '+s+'" aria-hidden="true"></span><strong>'+esc(names[id])+'</strong></div><span class="state-label '+s+'">'+esc(delayed?'Monitoring delayed':labels[s])+'</span></div><p>'+esc(descriptions[id])+'</p><div class="history-row"><div class="history-top"><span>Availability history</span><strong class="service-metric">'+metric+'</strong></div><div class="days" role="img" aria-label="'+esc(names[id]+': '+h.summary)+'">'+h.cells+'</div><div class="history-foot"><span class="history-window-desktop">90-day window</span><span class="history-window-mobile">Last 30 days · 90-day totals</span><span>'+h.days+' observed '+(h.days===1?'day':'days')+'</span></div></div></article>';
  }).join('');
  const archived=version?payload.archived_monitoring?.daily:payload.daily;
  const sums={};for(const row of Object.values(archived||{}))for(const [id,count] of Object.entries(row)){const s=sums[id]||={ok:0,fail:0};s.ok+=Number(count.ok||0);s.fail+=Number(count.fail||0);}
  el('retiredHistory').innerHTML='<h3>Archived webpage observations</h3>'+(Object.keys(sums).length?Object.entries(sums).map(([id,c])=>'<p>'+esc(names[id]||id)+': '+c.ok+'/'+(c.ok+c.fail)+' checks passed</p>').join(''):'<p>No archive loaded.</p>');
  el('probeDetails').innerHTML='<h3>Latest technical checks</h3>'+(version?Object.entries(payload.probes||{}).map(([id,p])=>'<p>'+esc(id.replaceAll('_',' '))+': '+(p.passed?'Passed':'Failed')+(fresh?'':' (last report, not current)')+'</p>').join(''):'<p>No current probe report.</p>');
  el('activeIncidents').innerHTML=active.length?active.map(i=>incident(i)).join(''):'<div class="loading-item">'+(fresh?'No active incidents published.':'No current incident report verified.')+'</div>';
  const past=incidents.filter(i=>!active.includes(i));
  el('incidentList').innerHTML=past.length?past.map(i=>incident(i,!ids.includes(i.component)&&i.component!=='monitoring')).join(''):'<div class="loading-item">No historical incidents in loaded report.</div>';
  el('maintenanceList').innerHTML=maintenance.length?maintenance.map(m=>'<article class="timeline-item"><div class="timeline-date">'+esc(date(m.starts_at))+'</div><div class="timeline-main"><strong>'+esc(m.title)+'</strong><p>'+esc(m.detail||'')+'</p><p>'+esc(names[m.component])+' · Ends '+esc(date(m.ends_at))+'</p></div></article>').join(''):'<div class="loading-item">No upcoming maintenance published.</div>';
  const oldMaintenance=(payload.maintenance||[]).filter(m=>!maintenance.includes(m));
  if(oldMaintenance.length)el('incidentList').insertAdjacentHTML('beforeend','<details class="methodology"><summary>Historical maintenance</summary>'+oldMaintenance.map(m=>'<p>'+esc(m.title)+' · '+esc(date(m.starts_at))+' to '+esc(date(m.ends_at))+'</p>').join('')+'</details>');
 }
 const sources=['https://raw.githubusercontent.com/nullicide/ecos-status/main/site/data/status.json','https://nullicide.github.io/ecos-status/data/service-status-v2.json','./data/status.json'];
 let last=null,loading=false;
 async function fetchReport(source){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
  try{const res=await fetch(source+'?at='+Date.now(),{cache:'no-store',signal:controller.signal});if(!res.ok)return null;
   const j=await res.json(),t=Date.parse(j.published_at||j.checked_at||'');
   if(j.schema!==1||!j.components||!j.daily||!Number.isFinite(t)||t>Date.now()+5*60000)return null;
   return j;
  }catch{return null}finally{clearTimeout(timer)}
 }
 async function load(){
  if(loading)return;loading=true;
  try{const reports=(await Promise.all(sources.map(fetchReport))).filter(Boolean);if(last)reports.push(last);
   reports.sort((a,b)=>(b.monitoring_version===2)-(a.monitoring_version===2)||Date.parse(b.published_at||b.checked_at)-Date.parse(a.published_at||a.checked_at));
   last=reports[0]||null;render(last||{unavailable:true});
  }finally{loading=false}
 }
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
