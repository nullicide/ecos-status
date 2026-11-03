'use strict';
/* ECOS Status v2: read-only readiness, Cloudflare upstream and observation coverage.
   Public provider data is produced by monitor_v2.py, never queried with credentials. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const format = value => {
    if (!value || !Number.isFinite(Date.parse(value))) return 'Not available';
    return new Date(value).toLocaleString(undefined, {
      year:'numeric', month:'short', day:'numeric',
      hour:'numeric', minute:'2-digit', timeZoneName:'short'
    });
  };
  const age = value => value ? Date.now() - Date.parse(value) : Infinity;
  const fresh = value => Number.isFinite(age(value)) && age(value) >= -300000 && age(value) <= 90*60000;
  const tag = (state,text) => '<span class="v2-state v2-state--'+state+'">'+esc(text)+'</span>';
  const safeHref = url =>
    typeof url === 'string' &&
    (/^https:\/\/www\.cloudflarestatus\.com\//.test(url) ||
      /^https:\/\/stspg\.io\//.test(url)) ? url : 'https://www.cloudflarestatus.com/';
  const serviceState = state => ({
    operational:['operational','Operational'],
    degraded_performance:['degraded','Degraded'],
    partial_outage:['outage','Partial outage'],
    major_outage:['outage','Major outage'],
    under_maintenance:['maintenance','Maintenance'],
  })[state] || ['unknown','Unverified'];

  function readiness(data) {
    const root = $('readinessPanel');
    if (!root) return;
    const valid = data?.schema === 1 && fresh(data.checked_at);
    const state = valid ? data.state : 'unverified';
    const labels = {
      ready: ['operational','Configuration ready'],
      not_accepting: ['degraded','Not accepting registrations'],
      unverified: ['unknown','Not verified']
    };
    const [kind,label] = labels[state] || labels.unverified;
    const detail = state === 'ready'
      ? 'The public registration configuration reports enabled. This does not test completed signups, email verification, sign-in or account approval.'
      : state === 'not_accepting'
        ? 'Registration is not accepting applications at the latest configuration check. This is not an ECOS website outage.'
        : 'The external configuration check was unavailable or has become stale. No registration outcome can be inferred.';
    root.innerHTML = '<div class="v2-readiness-head"><div><span class="v2-eyebrow">PUBLIC ACCOUNT REGISTRATION</span><h3>Registration configuration</h3></div>'+
      tag(kind,label)+'</div><p>'+esc(detail)+'</p>'+
      '<div class="v2-meta"><span>Checked: '+esc(format(data?.checked_at))+'</span>'+
      '<a href="https://www.energycontrolos.com/request-access/">Open registration <span aria-hidden="true">↗</span></a></div>';
  }

  function dependencies(data) {
    const root = $('dependencyGrid'), banner = $('dependencyStatus');
    const incidents = $('providerIncidents');
    if (!root || !banner || !incidents) return;
    const valid = data?.schema === 1 && data?.fetch_status === 'ok' && fresh(data.checked_at);
    const list = Array.isArray(data?.components) ? data.components : [];
    const items = list.length ? list : [
      'Workers Builds','Pages','Workers','D1','Turnstile','Authoritative DNS','API'
    ].map(name=>({name,status:'unknown'}));
    root.innerHTML = items.map(item=>{
      const [kind,label] = valid ? serviceState(item.status) : ['unknown','Not verified'];
      return '<div class="v2-dependency"><span class="v2-dependency-name">'+esc(item.name)+'</span>'+
        tag(kind,label)+'</div>';
    }).join('');
    banner.innerHTML = (valid
      ? 'Cloudflare provider report · Checked '+esc(format(data.checked_at))
      : 'Cloudflare provider status is unavailable or stale. The last stored snapshot is not live evidence.')+
      ' <a href="https://www.cloudflarestatus.com/" target="_blank" rel="noopener noreferrer">Official provider status ↗</a>';
    const rows = valid && Array.isArray(data?.incidents) ? data.incidents : [];
    incidents.innerHTML = rows.length ? rows.slice(0,8).map(i=>
      '<article class="v2-provider-incident"><div>'+tag('degraded',String(i.status||'Active incident'))+
      '<span class="v2-incident-time">'+esc(format(i.updated_at))+'</span></div>'+
      '<h3>'+esc(i.name)+'</h3><p>'+esc(i.detail||'See the provider incident for current details.')+'</p>'+
      '<a target="_blank" rel="noopener noreferrer" href="'+esc(safeHref(i.url))+'">View Cloudflare update ↗</a></article>'
    ).join('') : '<p class="v2-empty">'+(valid
      ? 'No unresolved Cloudflare incidents are associated with the selected dependency components.'
      : 'Provider incidents cannot currently be verified.')+'</p>';
    $('dependencyScope').textContent = 'Cloudflare reports its own infrastructure condition. This does not establish ECOS application availability, geographic reachability, or the success of sign-in and registration.';
  }

  function coverage(data) {
    const root = $('coverageSummary');
    if (!root) return;
    const days = data?.daily || {};
    const components = ['website','access','requests'];
    const ids = ['Public website','Enterprise access','Request Access'];
    const now = new Date();
    const keys = [];
    for(let i=89;i>=0;i--){
      const d = new Date(now); d.setUTCDate(d.getUTCDate()-i);
      keys.push(d.toISOString().slice(0,10));
    }
    const rows = components.map((id,index)=>{
      let passed=0, failed=0, sampledDays=0;
      for(const key of keys){
        const item = days[key]?.[id] || {};
        const ok = Number(item.ok),bad=Number(item.fail);
        if (!Number.isSafeInteger(ok) || !Number.isSafeInteger(bad) || ok < 0 || bad < 0) continue;
        passed += ok;failed += bad;
        if(ok+bad>0)sampledDays++;
      }
      const total=passed+failed;
      const last = data?.components?.[id]?.last_success_at;
      return '<div class="v2-coverage-row"><strong>'+ids[index]+'</strong>'+
        '<div><span>'+sampledDays+' / 90 sampled calendar days</span>'+
        '<span>'+total+' observed HTTP checks</span>'+
        '<span>Last recorded success: '+esc(format(last))+'</span></div></div>';
    }).join('');
    root.innerHTML = '<div class="v2-coverage-head"><span>OBSERVATION COVERAGE / ROLLING 90 DAYS</span>'+
      '<span>Only completed checks count</span></div>'+rows+
      '<p class="v2-coverage-caveat">A 90-day chart is a display window, not a claim that 90 days of service have been monitored. Missing observations remain uncounted. Check success is not an uptime SLA.</p>';
  }

  async function read(path) {
    const response = await fetch(path+'?at='+Date.now(),{cache:'no-store'});
    if (!response.ok) throw Error('Status report unavailable');
    return await response.json();
  }
  async function refresh() {
    const results = await Promise.allSettled([
      read('./data/readiness.json'), read('./data/dependencies.json'), read('./data/status.json')
    ]);
    readiness(results[0].status==='fulfilled'?results[0].value:null);
    dependencies(results[1].status==='fulfilled'?results[1].value:null);
    coverage(results[2].status==='fulfilled'?results[2].value:null);
    if(results[2].status!=='fulfilled' && $('coverageSummary'))
      $('coverageSummary').textContent='Monitoring coverage is unavailable.';
  }
  refresh();
  setInterval(refresh,60000);
})();
