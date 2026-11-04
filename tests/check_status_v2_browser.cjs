'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');

const live=['website','operating_picture','standards','signup','enterprise','access'];
(async()=>{
 const instance=await chromium.launch({headless:true});
 try{
  for(const width of [320,360,375,390,744,768,820,1024,1280,1440,1920]){
   const page=await instance.newPage({viewport:{width,height:900},reducedMotion:'reduce'});
   const errors=[];let providerRequests=0;
   page.on('pageerror',e=>errors.push(e.message));
   page.on('request',req=>{if(req.url().includes('/data/dependencies.json'))providerRequests++;});
   const at=new Date().toISOString(),today=at.slice(0,10);
   const components=Object.fromEntries(live.map(id=>[id,{state:'operational',last_success_at:at}]));
   components.requests={state:'degraded',last_success_at:at}; // historical, not live
   const daily=Object.fromEntries(live.map(id=>[id,{ok:1,fail:0}]));
   daily.requests={ok:4,fail:2};
   await page.route('**/data/status.json*',r=>r.fulfill({
    contentType:'application/json',body:JSON.stringify({
     schema:1,checked_at:at,first_checked_at:'2026-10-24T03:34:31Z',
     components,daily:{[today]:daily},incidents:[],maintenance:[]
    })
   }));
   const response=await page.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
   assert.equal(response.status(),200);
   for(const id of ['components','history','incidents','maintenance','subscribe'])
    assert.equal(await page.locator('#'+id).count(),1,'Public section '+id);
   assert.equal(await page.locator('.component').count(),6,'Six current ECOS monitored pages');
   assert.equal(await page.locator('.history-row').count(),6,'Six independent monitored histories');
   const componentLabels=await page.locator('.component-target').allTextContents();
   assert.deepEqual(componentLabels.map(s=>s.trim()),
    ['Public website','Operating picture','Standards & governance','Create account','Enterprise access inquiry','Application sign-in']);
   const links=await page.locator('.component-target').evaluateAll(nodes=>nodes.map(n=>n.href));
   assert.ok(links.includes('https://www.energycontrolos.com/create-account/'));
   assert.ok(links.includes('https://www.energycontrolos.com/enterprise-access/'));
   assert.ok(links.includes('https://app.energycontrolos.com/login/'));
   assert.equal(await page.locator('#retiredHistory').isVisible(),true);
   assert.match(await page.locator('#retiredHistory').innerText(),/Previous Request Access URL/);
   assert.match(await page.locator('#retiredHistory').innerText(),/4\/6 historic HTTP checks passed/);
   assert.doesNotMatch(await page.locator('#componentList').innerText(),/Previous Request Access URL/);
   assert.doesNotMatch(await page.locator('#historyList').innerText(),/Previous Request Access URL/);
   assert.match(await page.locator('#globalTitle').innerText(),/All monitored endpoints reachable/);
   assert.equal(await page.locator('.history-row').filter({hasText:'Enterprise access inquiry'}).locator('.history-description').innerText(),
    'HTTP checks · 1/1 successful · Early monitoring data');
   for(const id of ['readiness','experiences','coverageSummary'])
    assert.equal(await page.locator('#'+id).count(),0,'Removed panel '+id);
   const signin=page.locator('.site-header .nav-links .status-signin');
   assert.equal(await signin.count(),1,'Canonical sign-in link in status header');
   assert.equal(await signin.getAttribute('href'),'https://app.energycontrolos.com/login/');
   assert.ok(await signin.isVisible(),width+'px sign-in control remains visible');
   assert.ok(await page.locator('.site-header .nav-links .back-link').isVisible(),width+'px platform return is visible');
   const navBounds=await signin.boundingBox();
   assert.ok(navBounds&&navBounds.x>=-1&&navBounds.x+navBounds.width<=width+1,
     width+'px sign-in link fits within viewport');
   const dimensions=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
   if(dimensions.document>dimensions.viewport+1){
    const offenders=await page.evaluate(()=>[...document.querySelectorAll('body *')].map(e=>({
      tag:e.tagName.toLowerCase(),className:typeof e.className==='string'?e.className:'',
      id:e.id,rect:e.getBoundingClientRect().toJSON()
    })).filter(x=>x.rect.right>innerWidth+1).slice(0,12));
    console.error('Overflow offenders:',JSON.stringify(offenders));
   }
   assert.ok(dimensions.document<=dimensions.viewport+1,width+'px horizontal overflow '+JSON.stringify(dimensions));
   assert.deepEqual(errors,[],width+'px JavaScript runtime errors');
   assert.equal(providerRequests,0,'No hidden provider data dependency');
   console.log('ECOS status pages and historical isolation passed at '+width+'px');
   await page.close();
  }
  // Prior monitoring state cannot make an unobserved new service look green.
  const page=await instance.newPage();
  const at=new Date().toISOString(),today=at.slice(0,10);
  await page.route('**/data/status.json*',r=>r.fulfill({
   contentType:'application/json',body:JSON.stringify({
    checked_at:at,first_checked_at:'2026-10-24T03:34:31Z',
    components:{website:{state:'operational'},access:{state:'operational'},requests:{state:'operational'}},
    daily:{[today]:{requests:{ok:467,fail:0},website:{ok:467,fail:0},access:{ok:467,fail:0}}},
    incidents:[],maintenance:[]
   })
  }));
  await page.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
  assert.notEqual(await page.locator('#globalStatus').getAttribute('data-state'),'operational',
   'Old successes must not be counted as new enterprise-page uptime');
  assert.match(await page.locator('.history-row').filter({hasText:'Enterprise access inquiry'}).innerText(),
   /No HTTP checks recorded/);
  assert.match(await page.locator('#retiredHistory').innerText(),/467\/467 historic/);
  await page.close();
  console.log('PASS: legacy checks do not transfer to new enterprise access');
 }finally{await instance.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
