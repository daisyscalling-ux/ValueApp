export function validYahooBenchmark(h:any,proxy:string|null,now=Date.now()):boolean{
 const age=now-Date.parse(h?.retrievedAt);
 return !!proxy&&h?.proxy===proxy&&h.symbol==='YAHOO:'+proxy&&h.provider==='Yahoo Finance / yfinance'&&h.adjustment==='total_return'&&h.currency==='USD'&&h.instrumentType==='ETF'&&['PCX','NYQ','NMS','NGM','NCM','ASE','BATS','BTS'].includes(h.exchange)&&Number.isFinite(age)&&age>=0&&age<86400000&&Array.isArray(h.bars);
}
