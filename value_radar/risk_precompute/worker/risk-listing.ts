// Risk-specific listing resolution: a traded ADR need not be the issuer's primary listing.
type Row=Record<string,any>;
const venues:Record<string,[string,string[]]>={WA:['PL',['GPW']],IR:['IE',['EURONEXTDUB','ISE']],AT:['GR',['ATHEX']],LS:['PT',['EURONEXTLIS','LIS']],DE:['DE',['XETR','ETR','GER']],F:['DE',['FRA']],SW:['CH',['SIX','SWX']],T:['JP',['TSE','JPX','TYO']],L:['GB',['LSE']],PA:['FR',['EURONEXTPAR','PAR','EURONEXT']],AS:['NL',['EURONEXTAMS','AMS','EURONEXT']],MI:['IT',['MIL']],MC:['ES',['BME']],HK:['HK',['HKEX']],ST:['SE',['OMXSTO']],CO:['DK',['OMXCOP']],HE:['FI',['OMXHEX']],OL:['NO',['OSL']],BR:['BE',['EURONEXTBRU','EURONEXT']],VI:['AT',['VIE']],NS:['IN',['NSE']],BO:['IN',['BSE']]};
export function chooseRiskListing(input:string,rows:Row[]){
 const raw=input.toUpperCase().trim(),qualified=raw.includes(':'),suffix=!qualified?raw.match(/\.([A-Z]{1,2})$/)?.[1]:undefined;
 const venue=suffix?venues[suffix]:undefined,query=venue?raw.slice(0,-suffix!.length-1):raw;
 const norm=(s:string)=>s.replace(/[-._]/g,'').replace(/^0+(?=\d)/,'');
 const usable=rows.filter(r=>['stock','dr'].includes(r.type)&&r.status!=='delisted'&&typeof r.symbol==='string');
 let matches=usable.filter(r=>qualified?r.symbol.toUpperCase()===raw:norm(r.symbol.split(':').pop()!.toUpperCase())===norm(query)&&(!venue||r.listing_country_code===venue[0]));
 if(!qualified&&venue){const exact=matches.filter(r=>venue[1].includes(String(r.exchange||r.symbol.split(':')[0])));if(exact.length)matches=exact;else if(matches.length>1){const primary=matches.filter(r=>r.is_primary===true);if(primary.length===1)matches=primary}}
 if(!qualified&&!venue){const us=matches.filter(r=>r.listing_country_code==='US');if(us.length)matches=us}
 if(matches.length!==1)throw Error('Notierung nicht eindeutig: '+raw);return matches[0];
}
export async function resolveRiskListing(input:string,key:string,fetcher:typeof fetch=fetch){
 if(!key)throw Error('ROIC_API_KEY fehlt.');const raw=input.toUpperCase().trim();if(!/^[A-Z0-9._:-]{1,100}$/.test(raw))throw Error('Ungültiges Symbol.');
 const suffix=raw.match(/\.([A-Z]{1,2})$/)?.[1],query=raw.includes(':')?raw:suffix&&venues[suffix]?raw.slice(0,-suffix.length-1):raw;
 const r=await fetcher('https://api.roic.ai/v3.0.0/tickers/search?query='+encodeURIComponent(query),{headers:{Authorization:'Bearer '+key},signal:AbortSignal.timeout(12000),redirect:'error'});
 if(!r.ok)throw Error('ROIC-Symbolsuche HTTP '+r.status);const d=await r.json() as any;return chooseRiskListing(raw,Array.isArray(d)?d:d.data||[]);
}
