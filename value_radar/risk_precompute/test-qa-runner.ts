// Tests des QA-Runners (Gruppen, Regionen). Bau: npx esbuild test-qa-runner.ts --bundle --platform=node --format=esm
import assert from 'node:assert/strict';
import {region,nachGruppe} from './qa-runner';
assert.deepEqual(['US','JP','GB','DE','AU',null].map(region),['USA','Japan','Grossbritannien','Europa ohne GB','sonstige','sonstige']);
const b=(s:any)=>[{id:'E1',status:s,titel:'',detail:''}];
const g=nachGruppe([{gruppe:'USA',befunde:b('ok')},{gruppe:'USA',befunde:b('fehler')},{gruppe:'Japan',befunde:b('offen')}]);
assert.deepEqual(g.USA.E1,{ok:1,offen:0,auffaellig:0,fehler:1});assert.deepEqual(g.Japan.E1,{ok:0,offen:1,auffaellig:0,fehler:0});
console.log('qa-runner ok');
