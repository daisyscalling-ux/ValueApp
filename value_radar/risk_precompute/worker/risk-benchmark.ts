import {riskHistory} from './risk-data';
export const marketProxy=(country:string)=>({US:'SPY',USA:'SPY','UNITED STATES':'SPY',DE:'EWG',GERMANY:'EWG',JP:'EWJ',JAPAN:'EWJ',GB:'EWU','UNITED KINGDOM':'EWU',FR:'EWQ',FRANCE:'EWQ',HK:'EWH','HONG KONG':'EWH',IN:'INDA',INDIA:'INDA',CN:'MCHI',CHINA:'MCHI',KR:'EWY','SOUTH KOREA':'EWY',TW:'EWT',TAIWAN:'EWT'} as Record<string,string>)[country.trim().toUpperCase()]||null;
export async function benchmarkHistory(country:string,key:string,fetcher:typeof fetch=fetch){
 const ticker=marketProxy(country);if(!ticker)throw Error('Für dieses Land ist noch kein Marktvergleich zugeordnet.');if(!key)throw Error('ROIC_API_KEY fehlt.');
 const r=await fetcher('https://api.roic.ai/v3.0.0/tickers/search?query='+ticker,{headers:{Authorization:'Bearer '+key},signal:AbortSignal.timeout(8000),redirect:'error'});if(!r.ok)throw Error('Marktvergleich: ROIC HTTP '+r.status);const raw=await r.json() as any;
 const rows=Array.isArray(raw)?raw:raw.data;const matches=(Array.isArray(rows)?rows:[]).filter((x:any)=>String(x.symbol).split(':').pop()===ticker&&x.is_primary===true&&x.listing_country_code==='US'&&['etf','fund'].includes(String(x.type).toLowerCase()));
 if(matches.length!==1)throw Error('Markt-ETF nicht eindeutig im ROIC-Katalog gefunden.');
 const result=await riskHistory(matches[0].symbol,key,fetcher);return {...result,proxy:ticker,region:country,note:'US-gehandelter Länder-/Markt-ETF in '+result.currency+'. Bei ausländischen Märkten einschließlich Wechselkurseinfluss; keine reine lokale Indexrendite.'};
}
