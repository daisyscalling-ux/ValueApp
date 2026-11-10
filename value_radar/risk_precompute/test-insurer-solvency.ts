import assert from 'node:assert/strict';
import registry from './reviewed-insurer-solvency.json';
import {withRegulatoryContext} from './regulatory-context';
import {verifiedInsurer} from './insurer-solvency';
const now=Date.parse('2026-11-10T12:00:00Z');
const e=registry.entries[0],row=e.inputIdentity;
const record={...e,state:'available',reviewedOn:registry.reviewedOn,reviewExpires:registry.reviewExpires};
const archive={schema:1,source:registry.source,generatedAt:'2026-11-10T10:00:00Z',stocks:{[row.listing_symbol]:record}};
const base={profile:'insurer',state:'context_only',sectorRequirements:['eligible_own_funds','solvency_requirement','jurisdiction_and_regulatory_scope']};
const merge=(a:any=archive,identity=true)=>withRegulatoryContext(base,row,{insurers:a},identity,now);
assert.equal(merge().insurerSolvency.primary.ratio,2.25);
assert.equal(merge().sectorRequirements.length,0);
assert.equal(merge().sectorAssessment.state,'open');
assert.equal(merge().sectorAssessment.scoreContribution,0);
assert.equal(merge().insurerSolvency.observations[1].amountsVerified,false);
assert.equal(merge(undefined,false).insurerSolvency,null);
for(const patch of [{generatedAt:'2026-11-05'},{generatedAt:'2026-11-11'},{source:'other'},{stocks:{[row.listing_symbol]:{...record,inputIdentity:{...row,isin:'other'}}}}])assert.equal(merge({...archive,...patch}).insurerSolvency,null);
for(const patch of [{scope:'subsidiary'},{reviewExpires:'2026-11-09'},{reviewedOn:'2026-11-11'},{observations:[{...record.observations[0],ratio:2.18}]},{observations:[record.observations[0],record.observations[0]]},{framework:'SST'},{regulator:'FINMA'}])assert.equal(verifiedInsurer({...record,...patch},now),null);
assert.equal(verifiedInsurer({...record,primary:{ratio:99}},now)?.primary.ratio,2.25);
// Reine Quote: zaehlt als Quote, belegt aber keine Betraege.
const ratioOnly=verifiedInsurer({...record,observations:[record.observations[1]]},now);assert.equal(ratioOnly?.primary.ratio,2.18);assert.equal(ratioOnly?.primary.amountsVerified,false);
const ro=withRegulatoryContext(base,row,{insurers:{...archive,stocks:{[row.listing_symbol]:{...record,observations:[record.observations[1]]}}}},true,now);
assert.deepEqual(ro.sectorAssessment.fulfilledRequirements,['jurisdiction_and_regulatory_scope']);assert.deepEqual(ro.sectorRequirements,['eligible_own_funds','solvency_requirement']);
// Weitere Aufsichtssysteme aus dem Register: Solvency UK (GBP) und Norwegen (NOK).
for(const s of ['LSE:AV.','OSL:GJF','HEL:SAMPO']){const x=registry.entries.find((y:any)=>y.inputIdentity.listing_symbol===s)!;assert.ok(verifiedInsurer({...x,state:'available',reviewedOn:registry.reviewedOn,reviewExpires:registry.reviewExpires},now)?.primary.amountsVerified,s)}
assert.equal(verifiedInsurer({...record,observations:[{...record.observations[0],currency:'JPY'}]},now),null);
console.log('Insurer scope, identity, basis, freshness and amount validation passed');
