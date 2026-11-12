import {riskHistory} from './risk-data';
import registry from '../market-proxies.json';
export const MARKET_COUNTRIES=registry.map(r=>r.country);
const countryProxies=new Map(registry.flatMap(r=>[r.country,...r.aliases].map(a=>[a,r.proxy] as const)));
export const marketProxy=(country:string)=>countryProxies.get(country.trim().toUpperCase())||null;
// Ersatz-ETF (z. B. Eurozone für Portugal): gekennzeichnet über substituteFor, Hinweistext aus dem Register.
const substitutes=new Map(registry.filter((r:any)=>r.substituteFor).flatMap((r:any)=>[r.country,...r.aliases].map((a:string)=>[a,String(r.note||'Ersatz-ETF')] as const)));
export const marketSubstituteNote=(country:string)=>substitutes.get(country.trim().toUpperCase())||null;
export async function benchmarkHistory(country:string,key:string,fetcher:typeof fetch=fetch){
 const ticker=marketProxy(country);if(!ticker)throw Error('Für dieses Land ist noch kein Marktvergleich zugeordnet.');if(!key)throw Error('ROIC_API_KEY fehlt.');
 const r=await fetcher('https://api.roic.ai/v3.0.0/tickers/search?query='+ticker,{headers:{Authorization:'Bearer '+key},signal:AbortSignal.timeout(8000),redirect:'error'});if(!r.ok)throw Error('Marktvergleich: ROIC HTTP '+r.status);const raw=await r.json() as any;
 const rows=Array.isArray(raw)?raw:raw.data;const matches=(Array.isArray(rows)?rows:[]).filter((x:any)=>String(x.symbol).split(':').pop()===ticker&&x.listing_country_code==='US'&&['etf','fund'].includes(String(x.type).toLowerCase()));
 if(matches.length!==1)throw Error('Markt-ETF nicht eindeutig im ROIC-Katalog gefunden.');
 const result=await riskHistory(matches[0].symbol,key,fetcher);const substitute=marketSubstituteNote(country);return {...result,proxy:ticker,region:country,...(substitute?{substitute:true}:{}),note:(substitute?substitute+' ':'')+'US-gehandelter Länder-/Markt-ETF in '+result.currency+'. Bei ausländischen Märkten einschließlich Wechselkurseinfluss; keine reine lokale Indexrendite.'};
}
