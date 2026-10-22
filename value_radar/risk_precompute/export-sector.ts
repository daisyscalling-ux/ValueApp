import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {buildSectorComparisons} from './sector-comparison';
const read=(p:string)=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return null}};
export function exportSector(folder='value_radar/daten',cachePath='.risk-sector-series.json',now=Date.now()){
 const universe=read(path.join(folder,'cf_universum.json'));if(!Array.isArray(universe?.kandidaten)||!universe.kandidaten.length)throw Error('Universum fehlt');
 const result=buildSectorComparisons(universe,read(path.join(folder,'cf_peer_groups.json')),read(cachePath),now);
 const out=path.join(folder,'cf_sector_context.json');fs.writeFileSync(out+'.tmp',JSON.stringify(result));fs.renameSync(out+'.tmp',out);
 console.log(JSON.stringify(result.summary));return result;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)exportSector(process.argv[2]||'value_radar/daten',process.env.RISK_SECTOR_STATE||'.risk-sector-series.json');
