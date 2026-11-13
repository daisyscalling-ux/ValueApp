export function capitalRequirementPresentation(c:any,now=Date.now()){
 const r=c?.capitalRequirement,actual=c?.metrics?.cet1_ratio?.value;
 const age=now-Date.parse(r?.sourceVerifiedAt),today=new Date(now).toISOString().slice(0,10);
 if(r?.state!=='available'||r.method!=='fed-cet1-requirement-v1'||r.rssdId!==c.rssdId||r.holdingName!==c.holdingName||r.comparisonPeriod!==c.period||r.unit!=='fraction'||!Number.isFinite(age)||age<0||age>7*86400000||typeof r.reviewExpires!=='string'||today>r.reviewExpires||r.applicableFrom>c.period||c.period>r.reviewExpires||typeof actual!=='number'||!Number.isFinite(actual)||typeof r.value!=='number'||!Number.isFinite(r.value)||r.value<=0||r.value>1)return null;
 return {...r,headroomPercentagePoints:(actual-r.value)*100};
}
const el=(tag:string,text:string,cls='')=>{const e=document.createElement(tag);e.textContent=text;e.className=cls;return e};
export function renderCapitalRequirement(root:HTMLElement,c:any){
 const r=capitalRequirementPresentation(c);if(!r)return;
 const n=(v:number)=>v.toLocaleString('de-DE',{maximumFractionDigits:2});
 root.append(el('strong','CET1-Anforderung '+n(r.value*100)+' % · Abstand '+(r.headroomPercentagePoints>=0?'+':'')+n(r.headroomPercentagePoints)+' Prozentpunkte'));
 root.append(el('p',r.headroomPercentagePoints>=0?'Die gemeldete Quote liegt über dieser CET1-Anforderung. Der Abstand ist ein Kapitalpolster, aber keine Aussage zur Zahlungsfähigkeit oder zur Sicherheit der Aktie.':'Die gemeldete Quote liegt unter dieser CET1-Anforderung. Stichtag, aktuelle Meldungen und regulatorische Änderungen prüfen.','sub'));
 const d=el('details','');d.append(el('summary','Zusammensetzung und Gültigkeit'),el('p','Mindestquote '+n(r.minimumBps/100)+' % + Stresspuffer '+n(r.stressBufferBps/100)+' % + Systemrelevanz-Zuschlag '+n(r.gsibBps/100)+' %.'),el('p','Vergleich zum Berichtsdatum '+c.period+'. Quelle geprüft: '+new Date(r.sourceVerifiedAt).toLocaleDateString('de-DE')+'. Spätestens nach '+r.reviewExpires+' erneut zu prüfen.'));
 const a=el('a','Federal Reserve · Originaltabelle') as HTMLAnchorElement;a.href='https://www.federalreserve.gov/publications/files/large-bank-capital-requirements-20260624.pdf';a.target='_blank';a.rel='noopener noreferrer';d.append(a,el('p','Nur CET1: weitere Kapitalquoten, Liquidität und Kreditqualität bleiben eigenständige Prüfungen.','sub'));root.append(d);
}
