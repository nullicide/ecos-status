'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const instance=await chromium.launch({headless:true});
 try{
  for(const width of [320,375,768,1440]){
   const page=await instance.newPage({viewport:{width,height:900},reducedMotion:'reduce'});
   const errors=[];let providerRequests=0;
   page.on('pageerror',e=>errors.push(e.message));
   page.on('request',req=>{if(req.url().includes('/data/dependencies.json'))providerRequests++;});
   const at=new Date().toISOString();const today=at.slice(0,10);
   await page.route('**/data/status.json*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({
     schema:1,checked_at:at,first_checked_at:at,
     components:{website:{state:'operational',last_success_at:at},
       access:{state:'operational',last_success_at:at},
       requests:{state:'operational',last_success_at:at}},
     daily:{[today]:{website:{ok:1,fail:0},access:{ok:1,fail:0},requests:{ok:1,fail:0}}},
     incidents:[],maintenance:[]
   })}));
   const response=await page.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
   assert.equal(response.status(),200);
   for(const id of ['components','history','incidents','maintenance','subscribe'])
      assert.equal(await page.locator('#'+id).count(),1,'Public section '+id);
   assert.equal(await page.locator('.component').count(),3,'Three monitored public services');
   assert.equal(await page.locator('.history-row').count(),3,'Three uptime histories');
   for(const id of ['readiness','experiences','coverageSummary'])
      assert.equal(await page.locator('#'+id).count(),0,'Removed panel '+id);
   assert.equal(await page.locator('script[src*="status-v2"]').count(),0);
   const dimensions=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
   if(dimensions.document>dimensions.viewport+1){
     const offenders=await page.evaluate(()=>[...document.querySelectorAll('body *')].map(e=>({
       tag:e.tagName.toLowerCase(),className:typeof e.className==='string'?e.className:'',
       id:e.id,scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,
       rect:e.getBoundingClientRect().toJSON()
     })).filter(x=>x.rect.right>innerWidth+1).slice(0,18));
     console.error('Overflow offenders:',JSON.stringify(offenders));
   }
   assert.ok(dimensions.document<=dimensions.viewport+1,
    width+'px horizontal overflow '+JSON.stringify(dimensions));
   assert.deepEqual(errors,[],width+'px JavaScript runtime errors');
   console.log('ECOS Status v2 passed at '+width+'px');
   await page.close();
  }
 }finally{await instance.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
