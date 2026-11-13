// Scanner-Werte aus dem App-Rechenweg (evaluateStock). Eingabe: JSON {ticker: fund}, Ausgabe: JSON {ticker: Felder|{error}}.
// Aufruf aus export_cf.py ueber ts_bewertung.py; gebaut im Workflow precompute-3tage mit esbuild.
import {scannerFields} from './src/lib/scanner-evaluation';
import fs from 'node:fs';
const [input,output]=process.argv.slice(2);
const rows=JSON.parse(fs.readFileSync(input,'utf8')) as Record<string,any>,out:Record<string,unknown>={};
for(const [ticker,fund] of Object.entries(rows)){
 try{out[ticker]=scannerFields(fund)}catch(e){out[ticker]={error:String(e).slice(0,200)}}
}
fs.writeFileSync(output,JSON.stringify(out));
