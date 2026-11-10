// Sammelt die Adressen der Original-Einreichungen (errp.eba.europa.eu/public-documents) aus der oeffentlichen Liste des
// EBA Pillar 3 Data Hub (EDAP, Seite "Official Data and Templates Visualisation" -> Submissions). Quartalsweise von Hand:
//   node p3dh_collect.js p3dh-submissions.json
// Es werden nur oeffentliche Seiten gelesen; kein Login, keine Umgehung von Zugangssperren.
const {chromium}=require('playwright');const fs=require('fs');
(async()=>{
 const b=await chromium.launch();const p=await b.newPage({viewport:{width:1800,height:1400}});
 await p.goto('https://edap-public.eba.europa.eu/Report/index/MTE1?rhversion=20260121164608-2',{waitUntil:'domcontentloaded',timeout:90000});
 const f=()=>p.frames().find(x=>x.url().includes('powerbi.com/reportEmbed'));
 for(let i=0;i<150&&!f();i++)await p.waitForTimeout(1000);
 let fr=f();if(!fr)throw Error('Power-BI-Rahmen nicht geladen');
 await fr.waitForSelector('[aria-label="Page navigation . Click here to follow"]',{timeout:120000});
 await fr.click('[aria-label="Page navigation . Click here to follow"]');
 await fr.waitForSelector('a[href*="public-documents"]',{timeout:120000});
 await p.waitForTimeout(15000);
 const seen=new Set();let still=0;
 for(let step=0;step<3000&&still<25;step++){
  const links=await fr.evaluate(()=>Array.from(document.querySelectorAll('a')).map(a=>a.href).filter(h=>h.includes('errp.eba.europa.eu/public-documents')));
  const before=seen.size;links.forEach(l=>seen.add(l));
  still=seen.size===before?still+1:0;
  // im Tabellenbereich nach unten scrollen
  await fr.evaluate(()=>{const el=Array.from(document.querySelectorAll('div')).filter(d=>d.scrollHeight>d.clientHeight+50&&getComputedStyle(d).overflowY!=='visible').sort((a,b)=>b.scrollHeight-a.scrollHeight)[0];if(el)el.scrollTop+=el.clientHeight*0.8;});
  await p.waitForTimeout(700);
  if(step%50===0)console.log('step',step,'links',seen.size);
 }
 // CODIS (EU KM1: Kapital, Anforderung, LCR) und FINDIS (EU CR1: notleidende Kredite).
 const codis=[...seen].filter(u=>u.includes('/public-documents/CODIS/')||u.includes('/public-documents/FINDIS/')).sort();
 fs.writeFileSync(process.argv[2]||'p3dh-submissions.json',JSON.stringify({schema:1,source:'EBA Pillar 3 data hub, EDAP Submissions list',listUrl:'https://edap-public.eba.europa.eu/Report/index/MTE1',retrievedAt:new Date().toISOString(),allSubmissions:seen.size,modules:['CODIS','FINDIS'],urls:codis},null,1)+'\n');
 console.log('total',seen.size);
 await b.close();
})();
