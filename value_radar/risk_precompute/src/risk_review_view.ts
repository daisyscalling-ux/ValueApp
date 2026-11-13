const el=(tag:string,text:string,cls='')=>{const e=document.createElement(tag);e.textContent=text;e.className=cls;return e};
const fresh=(v:any,now:number,days:number)=>typeof v==='string'&&Number.isFinite(Date.parse(v))&&Date.parse(v)<=now&&now-Date.parse(v)<=days*86400000;
const ratio=(v:any)=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
export function reviewedPresentation(data:any,now=Date.now()){
 const r=data?.reviewedRisk,symbol=data?.snapshotSymbol;
 if(r?.schema!==1||!fresh(r.generatedAt,now,1.5)||!fresh(data.generatedAt,now,1.5)||typeof symbol!=='string')return null;
 const events=(Array.isArray(r.events)?r.events:[]).filter((d:any)=>d.symbol===symbol&&['confirmed_event','not_subject_of_tagged_event'].includes(d.state)&&fresh(d.reviewedAt,now,30)&&Number.isFinite(Date.parse(d.expiresAt))&&Date.parse(d.expiresAt)>now&&Date.parse(d.expiresAt)-Date.parse(d.reviewedAt)<=30*86400000);
 const c=r.bankCredit,parent=data.balance?.bankCapital;
 const validCredit=c?.state==='available'&&c.symbol===symbol&&(data.balance?.profile==='bank'||data.balance?.profile==='specialist_financial'&&parent?.scope==='listed_consolidated_holding')&&parent?.state==='available'&&['period','rssdId','sourceFileSha256'].every(k=>c[k]===parent[k])&&fresh(c.period,now,180)&&ratio(c.ratio)&&Number.isInteger(c.peerCount)&&c.peerCount>=0;
 return {events,solicitations:Number.isInteger(r.legalSolicitationCount)&&r.legalSolicitationCount>=0?r.legalSolicitationCount:0,credit:validCredit?c:null};
}
function link(root:HTMLElement,url:any){try{const u=new URL(url);if(u.protocol!=='https:'||u.username||u.password)return;const a=el('a','Quelle öffnen') as HTMLAnchorElement;a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';root.append(a)}catch{}}
export function renderReviewedRisk(root:HTMLElement,data:any){
 const p=reviewedPresentation(data);if(!p)return;
 if(p.events.length||p.solicitations){
  const box=el('div','','risk-evidence-summary');box.append(el('h4','Geprüfte Ereignisse'));
  for(const d of p.events){
   const detail=el('details','');detail.append(el('summary',d.state==='confirmed_event'?'Belegtes Ereignis · '+d.headline:'Zuordnung korrigiert · Ereignis betrifft eine andere Firma'));
   detail.append(el('p',String(d.rationale||'')));
   if(d.counterContext)detail.append(el('p','Einordnung: '+d.counterContext,'sub'));
   detail.append(el('p','Geprüft: '+String(d.reviewedAt).slice(0,10)+' · erneute Prüfung spätestens '+String(d.expiresAt).slice(0,10),'sub'));
   if(d.sourceAccess==='indexed_official_release')detail.append(el('p','Offizieller Meldungstext über den Webindex geprüft; direkter Seitenabruf war nicht verfügbar.','sub'));
   if(d.sourceAccess==='provider_headline_only')detail.append(el('p','Nur die Zuordnung in der Überschrift geprüft; kein vollständiger Artikel geprüft.','sub'));
   link(detail,d.sourceUrl);box.append(detail);
  }
  if(p.solicitations)box.append(el('p',`${p.solicitations} Kanzlei-/Fristenhinweise gebündelt. Wiederholte Aufrufe belegen weder mehrere unabhängige Risiken noch einen neuen Schaden.`,'sub'));
  box.append(el('p',p.events.some((d:any)=>d.state==='confirmed_event')?'Belegt ist das Ereignis, nicht seine künftige Kurswirkung. Kein automatischer Score-Zuschlag.':'Diese Hinweise bestätigen kein neues Risiko. Kein automatischer Score-Zuschlag.','sub'));root.append(box);
 }
 if(p.credit){
  const c=p.credit,box=el('div','','risk-evidence-summary'),pct=(v:number)=>(v*100).toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})+' %';
  box.append(el('h4','Kreditqualität · Vergleich derselben Berichtsperiode'),el('strong',pct(c.ratio)+' auffällige Kredite'));
  if(c.peerCount>=5&&ratio(c.peerMedian)){
   const delta=c.ratio-c.peerMedian;box.append(el('p',`${Math.abs(delta)<1e-12?'Auf Höhe des':delta>0?'Über dem':'Unter dem'} Vergleichsmedian von ${pct(c.peerMedian)} · ${c.peerCount} andere Bankkonzerne`));
  }else box.append(el('p','Zu wenige andere Bankkonzerne für einen belastbaren Median.','sub'));
  box.append(el('p','Ein niedrigerer Anteil ist bei vergleichbaren Kreditportfolios günstiger. Die Quote zeigt bereits auffällige Kredite, nicht den erwarteten Verlust.','sub'));
  const d=el('details','');d.append(el('summary','Berechnung, Grenzen und Quelle'),el('p','Ohne Zinsvereinnahmung oder mindestens 90 Tage überfällig, geteilt durch Gesamtkredite. Stichtag: '+c.period+'. Gleiche US-Meldedefinition; eigene Holding und doppelte Notierungen zählen nicht als Vergleichsunternehmen.'),el('p','Kreditarten, Sicherheiten, Garantien und Trends unterscheiden sich. Kein pauschales Gut-/Schlecht-Urteil und keine Gleichsetzung mit internationalen NPL-Quoten.','sub'));link(d,c.sourceUrl);box.append(d);root.append(box);
 }
}
