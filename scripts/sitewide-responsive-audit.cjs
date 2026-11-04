/* ECOS read-only site-wide responsive audit.
 * No form submissions, no authenticated access, no production writes.
 * Run from ecos-web repository root against the local static site, plus public origins.
 */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const LOCAL = 'http://127.0.0.1:8765';
const pages = [
 "/",
 "/404.html"
];
const widths = [
 ['iPhone 12 mini',360,780],['iPhone standard',390,844],
 ['iPad mini portrait',744,1133],['iPad portrait',820,1180],
 ['iPad landscape',1024,768],['laptop 13in',1280,800],['desktop',1920,1080]
];
const external = [
 "https://www.energycontrolos.com/",
 "https://app.energycontrolos.com/login/",
 "https://status.energycontrolos.com/"
];
const results=[];let checks=0;let errors=0;
function localExists(href){
 try {
  if(!href || href.startsWith('#') || /^(https?:|mailto:|tel:|javascript:|data:)/i.test(href))return true;
  const clean=decodeURIComponent(href.split(/[?#]/)[0]);
  if(!clean || clean==='/')return true;
  const disk=path.join(process.cwd(),'site',clean.startsWith('/')?clean.slice(1):clean);
  return fs.existsSync(disk)||fs.existsSync(path.join(disk,'index.html'))||fs.existsSync(disk+'.html');
 }catch{return true}
}
function log(level,item){console.log('ECOS_AUDIT '+JSON.stringify({level,...item}));}
async function audit(browser,url,label,w,h,live=false){
 const context=await browser.newContext({viewport:{width:w,height:h},deviceScaleFactor:live?1:(w<=390?3:1),isMobile:w<=390,hasTouch:w<=1024,ignoreHTTPSErrors:false});
 const page=await context.newPage();
 const jsErrors=[],badResponses=[];
 page.on('pageerror',e=>jsErrors.push(String(e).slice(0,170)));
 page.on('response',r=>{if(r.status()>=400&&!/\/api\/|\/cdn-cgi\//.test(r.url()))badResponses.push({code:r.status(),url:r.url().slice(0,110)});});
 let item={label,width:w,height:h,url,live,issues:[],flags:[]};
 try{
  const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:17000});
  item.http=response?.status()||null; item.finalUrl=page.url();
  await page.waitForTimeout(live?750:300);
  const dom=await page.evaluate(()=>{
   const doc=document.documentElement,body=document.body;
   const vw=innerWidth;
   const offenders=Array.from(document.querySelectorAll('body *')).filter(el=>{
     const cs=getComputedStyle(el),r=el.getBoundingClientRect();
     return r.width>4&&r.height>4&&cs.display!=='none'&&cs.visibility!=='hidden'&&!el.closest('[hidden]')&&r.right>vw+4&&r.left<vw+5&&cs.position!=='fixed';
   }).sort((a,b)=>a.getBoundingClientRect().right-b.getBoundingClientRect().right).slice(-6).map(el=>{
     const r=el.getBoundingClientRect();
     return {tag:el.tagName.toLowerCase(),class:String(el.className).slice(0,90),text:(el.textContent||'').trim().slice(0,50),right:Math.round(r.right),width:Math.round(r.width)};
   });
   const links=Array.from(document.querySelectorAll('a[href]')).filter(a=>a.getClientRects().length).map(a=>({href:a.getAttribute('href'),label:(a.getAttribute('aria-label')||a.textContent||'').trim().slice(0,100)}));
   const buttons=Array.from(document.querySelectorAll('button')).filter(b=>b.getClientRects().length).map(b=>{
     const r=b.getBoundingClientRect();return {name:(b.getAttribute('aria-label')||b.textContent||'').trim().slice(0,50),w:Math.round(r.width),h:Math.round(r.height)};
   });
   const nav=Array.from(document.querySelectorAll('nav,header')).filter(el=>el.getClientRects().length).map(x=>{const r=x.getBoundingClientRect();return {tag:x.tagName.toLowerCase(),width:Math.round(r.width),scroll:Math.round(x.scrollWidth),client:Math.round(x.clientWidth)};}).slice(0,8);
   const viewport=document.querySelector('meta[name=viewport]')?.content||'';
   return {width:Math.round(doc.scrollWidth),bodyWidth:Math.round(body?.scrollWidth||0),clientWidth:doc.clientWidth,offenders,links,buttons,nav,viewport,title:document.title,headings:[...document.querySelectorAll('h1')].map(h=>h.textContent.trim().slice(0,90))};
  });
  item.title=dom.title;item.scrollWidth=dom.width;item.documentWidth=dom.clientWidth;item.viewportMeta=dom.viewport;item.h1=dom.headings;item.nav=dom.nav;
  if(dom.width>w+3){item.issues.push('HORIZONTAL_OVERFLOW '+(dom.width-w)+'px');item.offenders=dom.offenders;}
  if(dom.nav.some(n=>n.scroll>n.client+5))item.flags.push('NAV_INTERNAL_OVERFLOW');
  if(!dom.viewport.includes('width=device-width'))item.issues.push('MISSING_VIEWPORT_META');
  if(dom.headings.length===0&&!/Redirecting/.test(dom.title))item.flags.push('NO_H1');
  const empty=dom.links.filter(l=>!l.label&&!/^\s*#/.test(l.href||''));if(empty.length)item.flags.push('UNLABELED_LINKS '+empty.length);
  const tiny=dom.buttons.filter(b=>b.w>0&&b.h>0&&b.w<28&&b.h<28);if(tiny.length)item.flags.push('VERY_SMALL_BUTTONS '+tiny.length);
  if(!live&&w===360){const broken=dom.links.filter(l=>!localExists(l.href));if(broken.length){item.flags.push('LOCAL_LINKS_TO_MISSING_FILES');item.brokenLinks=broken.slice(0,8)}}
  if(jsErrors.length){item.flags.push('JS_ERRORS '+jsErrors.length);item.jsErrors=[...new Set(jsErrors)].slice(0,3)}
  if(badResponses.length){item.flags.push('HTTP_ASSET_ERRORS '+badResponses.length);item.badResponses=badResponses.slice(0,4);}
  if(response?.status()>=400)item.issues.push('HTTP '+response.status());
  if(w===360&&!live){
    const menu=page.locator('button[aria-controls],button[aria-label*="menu" i],button.menu-toggle').first();
    if(await menu.count()){
      const before=await menu.getAttribute('aria-expanded');
      try{
       await menu.click({timeout:1200});
       await page.waitForTimeout(150);
       const after=await menu.getAttribute('aria-expanded');
       if(before==='false'&&after!=='true')item.flags.push('MOBILE_MENU_DID_NOT_OPEN');
       item.menuToggle={before,after};
      }catch(e){item.flags.push('MOBILE_MENU_NOT_CLICKABLE');}
    }
  }
  if(item.issues.length&&w<=390&&!live){
    const name=label.replace(/[^a-z0-9]/ig,'_').slice(0,40);
    try{await page.screenshot({path:'audit-screens/'+name+'_'+w+'.png',fullPage:true,timeout:5000})}catch{}
  }
 }catch(e){item.issues.push('NAVIGATION_ERROR');item.error=String(e).slice(0,220);}
 await context.close();checks++;if(item.issues.length)errors++;
 results.push(item);
 if(item.issues.length||item.flags.length)log(item.issues.length?'ISSUE':'REVIEW',item);
}
(async()=>{
 fs.mkdirSync('audit-screens',{recursive:true});
 const browser=await chromium.launch({headless:true});
 for(const [device,w,h] of widths){
  for(const route of pages)await audit(browser,LOCAL+route,route,w,h);
 }
 for(const link of external){
  for(const [device,w,h] of [widths[0],widths[3],widths[5]])
   await audit(browser,link,link.replace(/^https:\/\//,''),w,h,true);
 }
 await browser.close();
 const rollup=results.reduce((a,x)=>{
  if(x.issues.length||x.flags.length){a[x.label]??={issues:0,flags:0,views:[]};a[x.label].issues+=x.issues.length;a[x.label].flags+=x.flags.length;a[x.label].views.push({w:x.width,issues:x.issues,flags:x.flags})}
  return a;
 },{});
 const data={date:new Date().toISOString(),checks,issueViews:errors,sitePages:pages.length,remotePages:external.length,viewports:widths.map(x=>({name:x[0],width:x[1],height:x[2]})),rollup,results};
 fs.writeFileSync('audit-responsive.json',JSON.stringify(data,null,2));
 console.log('ECOS_AUDIT_SUMMARY '+JSON.stringify({checks,issueViews:errors,rollup}));
})().catch(e=>{console.error('ECOS_AUDIT_FATAL',e);process.exit(1)});
