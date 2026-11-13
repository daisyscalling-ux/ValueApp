// Scanner-Werte aus dem App-Rechenweg (evaluateStock). Eingabe: JSON {universe:[Zeilen], funds:{ticker: fund}},
// Ausgabe: JSON {ticker: Felder|{error}}. Peers wie in der App: selectPeers ueber das (identitaetsgepruefte) Universum.
// Aufruf aus export_cf.py ueber ts_bewertung.py; gebaut im Workflow precompute-3tage mit esbuild.
import {scannerFields} from './src/lib/scanner-evaluation';
import {selectPeers} from './src/lib/peer-selection';
import {safeUniverse} from './src/lib/listing-identity';
import fs from 'node:fs';
const [input,output]=process.argv.slice(2);
const data=JSON.parse(fs.readFileSync(input,'utf8')) as {universe?:Record<string,unknown>[];funds:Record<string,any>};
const universe=safeUniverse(Array.isArray(data.universe)?data.universe:[]),byTicker=new Map(universe.map(r=>[String(r.ticker),r]));
const out:Record<string,unknown>={};
for(const [ticker,fund] of Object.entries(data.funds??{})){
 try{
  const row=byTicker.get(ticker);
  const peers=row?selectPeers({...row,...Object.fromEntries(['sector','industry','currency','isin','sub_industry'].filter(k=>fund[k]).map(k=>[k,fund[k]]))},universe):null;
  out[ticker]=scannerFields(fund,peers);
 }catch(e){out[ticker]={error:String(e).slice(0,200)}}
}
fs.writeFileSync(output,JSON.stringify(out));
