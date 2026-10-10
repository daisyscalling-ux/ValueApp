// Uses exactly the existing price-only risk study, no duplicated scoring formula.
import fs from 'node:fs';
import {validateHistory} from '../risk_precompute/src/lib/risk-validation';
const source=JSON.parse(fs.readFileSync('sec-study-output/histories.json','utf8'));
const observations=Object.fromEntries(Object.entries(source.histories).map(([symbol,h]:[string,any])=>[symbol,validateHistory(h,Date.parse(h.retrievedAt))]));
fs.writeFileSync('sec-study-output/price-observations.json',JSON.stringify(observations));
