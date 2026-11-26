'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {AxeBuilder}=require('@axe-core/playwright');
const ids=['platform','identity','academy','public_website','investor'];
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const at=new Date().toISOString(),today=at.slice(0,10);
  const report={schema:1,monitoring_version:2,checked_at:at,published_at:at,first_checked_at:at,
   components:Object.fromEntries(ids.map(id=>[id,{state:id==='public_website'?'operational':'unknown',required_passed:1,required_total:1}])),
   daily:{[today]:Object.fromEntries(ids.map(id=>[id,{ok:1,fail:0}]))},
   archived_monitoring:{daily:{'2026-10-24':{website:{ok:467,fail:0}}}},
   incidents:[],maintenance:[],probes:{}};
  for(const width of [320,390,768,1440]){
   const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
   const page=await context.newPage();
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/data/status.json*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify(report)}));
   await page.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
   assert.equal(await page.locator('.component').count(),5);
   assert.equal(await page.locator('.history-row').count(),5);
   assert.equal(await page.locator('#globalStatus').getAttribute('data-state'),'unknown');
   assert.match(await page.locator('#componentList').innerText(),/Not yet verified/);
   assert.doesNotMatch(await page.locator('#historyList').innerText(),/467/);
   assert.match(await page.locator('#retiredHistory').textContent(),/467\/467/);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),width+' overflow');
   assert.equal(await page.locator('.history-row').first().locator('.day:visible').count(),width<=680?30:90);
   await page.locator('#openSubscribe').click();
   assert.equal(await page.locator('#subscribeDialog').isVisible(),true);
   await page.keyboard.press('Escape');
   assert.equal(await page.locator('#subscribeDialog').isVisible(),false);
   const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
   assert.deepEqual(axe.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
   assert.deepEqual(errors,[]);await context.close();console.log('IRI-001 verified '+width);
  }
  const p=await browser.newPage();
  const stale={...report,checked_at:new Date(Date.now()-120*60000).toISOString(),published_at:new Date(Date.now()-120*60000).toISOString()};
  await p.route('**/data/status.json*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify(stale)}));
  await p.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
  assert.equal(await p.locator('#globalStatus').getAttribute('data-state'),'unavailable');
  await p.close();
  const missing=await browser.newPage();
  await missing.route('**/data/status.json*',r=>r.abort());
  await missing.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
  assert.equal(await missing.locator('#globalStatus').getAttribute('data-state'),'unavailable');
  await missing.close();
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
