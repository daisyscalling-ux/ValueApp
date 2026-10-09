type Bar={date:string;close:number};
export async function riskHistory(symbol:string,key:string,fetcher:typeof fetch=fetch,now=Date.now()){
 if(!key)throw Error('ROIC_API_KEY fehlt.');
 if(!/^[A-Z0-9_-]+:[A-Z0-9._-]+$/i.test(symbol))throw Error('Eindeutige Börsennotierung fehlt.');
 const host='https://api.roic.ai',today=new Date(now).toISOString().slice(0,10),from=new Date(now-6*365.25*86400000).toISOString().slice(0,10);
 let next=host+'/v3.0.0/stock-prices/'+encodeURIComponent(symbol)+'?adjustment=total_return&order=desc&limit=1000&date.gte='+from+'&date.lt='+today;
 let currency='',pages=0;const bars:Bar[]=[],seen=new Set<string>(),deadline=AbortSignal.timeout(28000);
 while(next&&pages<3){const u=new URL(next,host);if(u.origin!==host||u.pathname!=='/v3.0.0/stock-prices/'+encodeURIComponent(symbol)&&decodeURIComponent(u.pathname)!=='/v3.0.0/stock-prices/'+symbol||u.searchParams.get('adjustment')!=='total_return'||seen.has(u.href))throw Error('Ungültige ROIC-Paginierung.');seen.add(u.href);
 const r=await fetcher(u.href,{headers:{Authorization:'Bearer '+key},signal:AbortSignal.any([deadline,AbortSignal.timeout(12000)]),redirect:'error'});if(!r.ok)throw Error('ROIC-Kurshistorie HTTP '+r.status);
 const d=await r.json() as any;if(d.symbol!==symbol||!d.currency||currency&&d.currency!==currency||!Array.isArray(d.data))throw Error('Kurshistorie: Notierung oder Währung stimmt nicht.');currency=d.currency;
 for(const row of d.data)bars.push({date:String(row.date),close:row.close});pages++;next=d.next_page_url||'';
 }
 if(next)throw Error('Kurshistorie unvollständig: zu viele Seiten.');
 return {symbol,currency,adjustment:'total_return',bars,requestedFrom:from,retrievedAt:new Date(now).toISOString()};
}
