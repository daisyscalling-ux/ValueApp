const base='https://api.roic.ai/v3.0.0';
type Row=Record<string,unknown>;
export const rows=(v:unknown):Row[]=>Array.isArray(v)?v.filter(x=>x&&typeof x==='object'):v&&typeof v==='object'?['data','results','rows','tickers'].flatMap(k=>Array.isArray((v as Row)[k])?rows((v as Row)[k]):[]):[];
const one=(v:unknown):Row=>rows(v)[0]??(v&&typeof v==='object'&&'data' in v&&typeof (v as Row).data==='object'?(v as Row).data as Row:v&&typeof v==='object'?v as Row:{});
async function read(url:string,headers:Record<string,string>,fetcher:typeof fetch){
 const stage=url.includes('/tickers/')?'Symbolauflösung':url.includes('/company/profile/')?'Unternehmensprofil':url.includes('/company/news/')?'Nachrichten':'Datenabruf';
 let r:Response;try{r=await fetcher(url,{headers,signal:AbortSignal.timeout(15000),redirect:'error'})}catch(e){throw Error('ROIC '+stage+': '+(e instanceof Error&&/timeout|abort/i.test(e.name)?'Zeitlimit erreicht.':'Verbindung fehlgeschlagen.'))}
 if(!r.ok)throw Error('Datenanbieter HTTP '+r.status+' · '+stage);
 try{return await r.json()}catch(e){throw Error('ROIC '+stage+': '+(e instanceof Error&&/timeout|abort/i.test(e.name)?'Zeitlimit beim Lesen der Antwort erreicht.':'Antwort ist kein gültiges JSON.'))}
}
export async function resolveCompany(input:string,key:string,fetcher:typeof fetch=fetch){
 if(!key)throw Error('ROIC_API_KEY nicht konfiguriert.');
 const raw=input.trim().toUpperCase();if(!raw||raw.length>100)throw Error('Ungültige Unternehmenssuche.');
 const suffix=raw.match(/\.(DE|F|T|HK|L|PA|AS|SW|NS|BO|CO|ST|HE|OL|MI|MC)$/)?.[1];
 const query=suffix?raw.slice(0,-suffix.length-1):raw.split(':').pop()!;
 const countries:Record<string,string>={DE:'DE',F:'DE',T:'JP',HK:'HK',L:'GB',PA:'FR',AS:'NL',SW:'CH',NS:'IN',BO:'IN',CO:'DK',ST:'SE',HE:'FI',OL:'NO',MI:'IT',MC:'ES'};
 const norm=(v:unknown)=>String(v??'').toUpperCase().replace(/[^A-Z0-9]/g,'');
 const all=rows(await read(base+'/tickers/search?query='+encodeURIComponent(query),{Authorization:'Bearer '+key},fetcher));
 const matches=all.filter(r=>r.type==='stock'&&(raw.includes(':')||r.is_primary===true)&&(raw.includes(':')?String(r.symbol).toUpperCase()===raw:norm(String(r.symbol).split(':').pop())===norm(query)||norm(r.name??r.company_name)===norm(raw))&&(!suffix||r.listing_country_code===countries[suffix]));
 // Prefer the US primary listing only for a plain US-style symbol, never for foreign suffixes.
 const us=!suffix&&!raw.includes(':')?matches.filter(r=>r.listing_country_code==='US'||/^(NASDAQ|NYSE|AMEX):/.test(String(r.symbol))):[];
 const chosen=us.length===1?us:matches;if(chosen.length!==1)throw Error('Notierung nicht eindeutig. Bitte Börse:TICKER oder das genaue Börsensuffix verwenden.');
 return chosen[0];
}
export async function companyNews(input:string,key:string,fetcher:typeof fetch=fetch){
 if(!key)throw Error('ROIC_API_KEY nicht konfiguriert.');
 const originalFetch=fetcher,total=AbortSignal.timeout(25000);
 fetcher=(url,options)=>originalFetch(url,{...options,signal:AbortSignal.any([total,...(options?.signal?[options.signal]:[])])});
 const raw=input.trim().toUpperCase();
 const validId=/^(?:[A-Z]{2}[A-Z0-9]{9}[0-9]|[0-9]{1,10})$/;
 let symbol=raw,id='';
 if(validId.test(raw))id=raw;
 else if(/^(NASDAQ|NYSE|AMEX):[A-Z][A-Z0-9.-]{0,10}$/.test(raw))id=raw.split(':')[1];
 else {
  const listing=await resolveCompany(input,key,fetcher);symbol=String(listing.symbol);
  const identifier=(r:Row)=>[r.isin,r.cik].map(v=>String(v??'').trim()).find(v=>validId.test(v))||'';
  id=identifier(listing);
  if(!id){const profile=one(await read(base+'/company/profile/'+encodeURIComponent(symbol),{Authorization:'Bearer '+key},fetcher));id=identifier(profile)}
  if(!id)throw Error('ROIC liefert keine eindeutige ISIN/CIK für den Nachrichtenabruf.');
 }
 const url='https://api.roic.ai/v2/company/news/'+encodeURIComponent(id)+'?limit=8&apikey='+encodeURIComponent(key);
 const data=await read(url,{},fetcher),safe=(v:unknown)=>{try{const u=new URL(String(v));return ['https:','http:'].includes(u.protocol)?u.href:null}catch{return null}};
 const news=rows(data).map(r=>({titel:String(r.title??r.headline??''),datum:String(r.published_date??r.date??''),quelle:String(r.site??r.source??'ROIC'),url:safe(r.article_url??r.url),text:typeof r.article_text==='string'?r.article_text.slice(0,400):null})).filter(r=>r.titel&&r.url).sort((a,b)=>b.datum.localeCompare(a.datum));
 return {news,ticker:symbol,identifier:id,grund:news.length?undefined:'ROIC hat für diese ISIN/CIK keine Nachrichten geliefert.'};
}
export async function candidateData(input:string,key:string,finnhubKey?:string,fetcher:typeof fetch=fetch){
 const listing=await resolveCompany(input,key,fetcher),symbol=String(listing.symbol),issues:string[]=[],raw:Row={};
 const today=new Date().toISOString().slice(0,10),until=new Date(Date.now()+120*86400000).toISOString().slice(0,10);
 const paths:Record<string,string>={quote:'stock-prices/latest/',profile:'company/profile/',income:'fundamental/income-statement/',balance:'fundamental/balance-sheet/',cashflow:'fundamental/cash-flow/'};
 const calendar=read(base+'/calendar/earnings?identifier='+encodeURIComponent(symbol)+'&date.gte='+today+'&date.lte='+until+'&order=asc&limit=10',{Authorization:'Bearer '+key},fetcher).catch(()=>null);
 await Promise.all(Object.entries(paths).map(async([name,path])=>{try{raw[name]=await read(base+'/'+path+encodeURIComponent(symbol)+(['income','balance','cashflow'].includes(name)?'?period_type=annual&limit=3':''),{Authorization:'Bearer '+key},fetcher)}catch{issues.push(name+': ROIC-Abruf fehlgeschlagen oder Zeitlimit.')}}));
 let earnings:Row|null=null,earningsNote='Kein bestätigter künftiger Earnings-Termin verfügbar.';
 const event=rows(await calendar).find(r=>r.symbol===symbol&&typeof r.release_date==='string'&&r.release_date>=today&&r.release_date<=until&&r.is_reported!==true);
 if(event){earnings={date:event.release_date,hour:event.release_session};earningsNote='ROIC · '+(event.is_confirmed===true?'bestätigter Termin':'geschätzter Termin, kann sich ändern');}
 if(!earnings&&finnhubKey&&/^(NASDAQ|NYSE|AMEX):/.test(symbol))try{
 const bare=symbol.split(':').pop()!,v=await read('https://finnhub.io/api/v1/calendar/earnings?symbol='+encodeURIComponent(bare)+'&from='+today+'&to='+until,{'X-Finnhub-Token':finnhubKey},fetcher) as Row;
 const future=rows(v.earningsCalendar).filter(r=>r.symbol===bare&&typeof r.date==='string'&&r.date>=today&&r.date<=until).sort((a,b)=>String(a.date).localeCompare(String(b.date)));earnings=future[0]??null;earningsNote=earnings?'Finnhub · gemeldeter Kalendertermin, kann sich ändern.':earningsNote;
 }catch{earningsNote='Finnhub-Kalender nicht erreichbar oder nicht freigegeben.'}
 else if(!earnings) earningsNote=finnhubKey?'Kalender für diese ausländische Notierung nicht eindeutig verknüpft.':'FINNHUB_API_KEY fehlt für den Earnings-Kalender.';
 return {listing,raw,earnings,earningsNote,issues,retrievedAt:new Date().toISOString()};
}
