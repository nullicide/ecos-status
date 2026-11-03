'use strict';
/* ECOS Status v2.1: independent observed ECOS services, signup readiness and coverage. */
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

  // Only ECOS endpoint checks and its own public configuration can support a
  // customer-facing signal; never present provider status as feature availability.
  const SERV=[
    {title:'ECOS public information',category:'DISCOVER ECOS',audience:'Customers and evaluators',
     description:'Explore the platform, published capabilities and product information.',
     check:'Public homepage HTTP response',key:'website',url:'https://www.energycontrolos.com/'},
    {title:'Enterprise sign-in entry',category:'ACCOUNT ACCESS',audience:'Registered users',
     description:'Reach the ECOS sign-in screen to begin a protected session. Credentials and MFA are not tested.',
     check:'Sign-in page HTTP response',key:'access',url:'https://app.energycontrolos.com/login/'},
    {title:'Account registration page',category:'ACCOUNT ACCESS',audience:'New evaluators',
     description:'Reach the application form to request individual ECOS access. Submissions are not tested.',
     check:'Registration page HTTP response',key:'requests',url:'https://www.energycontrolos.com/request-access/'},
    {title:'New account intake',category:'IDENTITY & APPROVAL',audience:'Prospective customers',
     description:'Create an identity, verify email, and request review before receiving permissions.',
     check:'Public registration configuration only',key:'readiness',url:'https://www.energycontrolos.com/request-access/'},
    {title:'Project workspace',category:'COORDINATION',audience:'Approved project teams',
     description:'Project context, assigned records and controlled collaboration after sign-in.',
     check:'No independent functional check',key:null,url:null},
    {title:'Energy-control documentation',category:'WORK RECORDS',audience:'Energy marshals and field teams',
     description:'Documentary isolation, verification and handover references; not live energy-state assurance.',
     check:'No independent functional check',key:null,url:null},
    {title:'Notifications and tasks',category:'WORKFLOW AWARENESS',audience:'Authorized workspace users',
     description:'In-app coordination notices, evidence requests and follow-up items where available.',
     check:'No independent functional check',key:null,url:null}
  ];
  function experienceSignal(id,status,readinessReport){
    if(id==='readiness'){
      if(!readinessReport || !fresh(readinessReport.checked_at) || readinessReport.schema!==1)
        return ['unknown','Unverified'];
      return readinessReport.state==='ready'?['operational','Intake configured']:
        readinessReport.state==='not_accepting'?['degraded','Intake closed']:['unknown','Unverified'];
    }
    if(!id)return ['unknown','Not independently tested'];
    if(!status || !fresh(status.checked_at) || status.schema!==1 || Date.now()-Date.parse(status.checked_at)>25*60000)
      return ['unknown','Check not current'];
    const value=status.components?.[id]?.state;
    return value==='operational'?['operational','Page reachable']:
      value==='outage'?['outage','Page unavailable']:
      value==='degraded'?['degraded','Inconsistent response']:['unknown','Unverified'];
  }
  function experiences(status,readinessReport){
    const root=$('experienceGrid');if(!root)return;
    root.innerHTML=SERV.map((s,i)=>{
      const [kind,label]=experienceSignal(s.key,status,readinessReport);
      const labelRow=s.url?'<a href="'+esc(s.url)+'">Open service ↗</a>':'<span>Authenticated features</span>';
      return '<article class="v2-experience">'+
        '<div class="v2-experience-top"><span class="v2-experience-category">'+esc(String(i+1).padStart(2,'0')+' / '+s.category)+'</span>'+
        tag(kind,label)+'</div><h3>'+esc(s.title)+'</h3><p>'+esc(s.description)+'</p>'+
        '<div class="v2-experience-meta"><small>'+esc(s.audience)+' · '+esc(s.check)+'</small>'+labelRow+'</div></article>';
    }).join('');
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
      read('./data/readiness.json'), read('./data/status.json')
    ]);
    const registration=results[0].status==='fulfilled'?results[0].value:null;
    const status=results[1].status==='fulfilled'?results[1].value:null;
    readiness(registration);
    experiences(status,registration);
    coverage(status);
    if(results[1].status!=='fulfilled' && $('coverageSummary'))
      $('coverageSummary').textContent='Monitoring coverage is unavailable.';
  }
  refresh();
  setInterval(refresh,60000);
})();
