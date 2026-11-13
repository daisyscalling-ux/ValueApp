import INDUSTRY_GROUPS from './peer-industry-groups.json';
import {listingMatches} from './listing-identity';
type Row=Record<string,unknown>;
const text=(x:unknown)=>String(x??'').trim();
export const peerSymbol=(x:unknown)=>text(x).toUpperCase().split(':').pop()!;
const company=(x:unknown)=>text(x).toLowerCase().replace(/&/g,'and').replace(/\b(incorporated|inc|corporation|corp|plc|limited|ltd|company|co|publ|class [a-z])\b/g,'').replace(/[^\p{L}\p{N}]/gu,'');
// Explicit business families; sector alone never establishes comparability.
const families:[string,RegExp][]=[
 ['Universalbanken',/citigroup|jpmorgan|bank of america|wells fargo|hsbc|bnp paribas|banco santander|barclays|deutsche bank|unicredit|mitsubishi ufj|sumitomo mitsui|mizuho/],
 ['Regionalbanken',/pnc financial|us bancorp|u\.?s\.? bancorp|truist|fifth third|regions financial|huntington bancshares|keycorp/],
 ['Investmentbanken',/goldman sachs|morgan stanley|jefferies/],
 ['Vermögensverwalter',/blackrock|schroders|man group|t\.? rowe price|franklin resources|amundi/],
 ['Versicherer',/allianz|axa|unipol|zurich insurance|chubb|travelers|progressive|munich re|swiss re/],
 ['Beteiligungsgesellschaften',/investor ab|industriv|berkshire hathaway|exor/],
 ['Zahlungsnetzwerke',/^(visa|mastercard)\b/],
 ['Unternehmenssoftware',/microsoft|oracle|salesforce|sap se|servicenow|adobe|workday/],
 ['Chipdesigner',/nvidia|advanced micro devices|broadcom|qualcomm|marvell/],
 ['Chipfertiger',/taiwan semiconductor|united microelectronics|globalfoundries/],
 ['Speicherchips',/micron|sk hynix/],
 ['Halbleiterausrüstung',/asml|applied materials|lam research|kla corporation/],
 ['Internetwerbung',/alphabet|meta platforms/],
 ['Telekommunikation',/deutsche telekom|verizon|at&t|vodafone|telefonica|orange sa|t-mobile/],
 ['Automobilhersteller',/toyota|volkswagen|mercedes|bmw|ford motor|general motors|honda motor|suzuki motor|tesla|stellantis/],
 ['Getränkehersteller',/coca.cola|pepsico|keurig dr pepper/]
];
// Gepruefte Branchengruppen (peer-industry-groups.json): Angleichung abweichender Bezeichnungen und Gruppen eng verwandter Branchen.
const crosswalk=INDUSTRY_GROUPS.crosswalk as Record<string,string>;
const groupOf=new Map<string,string>(Object.entries(INDUSTRY_GROUPS.groups as Record<string,string[]>).flatMap(([g,list])=>list.map(i=>[i,g] as [string,string])));
export const PEER_MINIMUM=3,GROUP_FILL=5;
function normalizedIndustry(r:Row){const raw=text(r.industry).toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();return crosswalk[raw]||raw}
// Branche fuer die Ergaenzung (ohne Sammelbegriffe wie "finance" oder "technology").
export function peerIndustry(r:Row):string{const i=normalizedIndustry(r);return i&&!/^(finance|financial services|technology|industrials|other|unknown)$/.test(i)?i:''}
// Gruppe verwandter Branchen; nur fuer reine Branchenfamilien (kuratierte Familien und Unterbranchen nie).
export function industryGroup(r:Row):string{return peerFamily(r).startsWith('Branche: ')?groupOf.get(normalizedIndustry(r))||'':''}
export function peerFamily(r:Row):string{
 const sub=text(r.sub_industry).toLowerCase().trim();if(sub&&!/^(unknown|other|n\/a)$/.test(sub))return 'Unterbranche: '+sub.replace(/[^\p{L}\p{N}]+/gu,' ');
 const n=text(r.name_full||r.name).toLowerCase();for(const [family,re] of families)if(re.test(n))return family;
 const industry=normalizedIndustry(r);
 if(/^(major banks|banks diversified|diversified banks|money center banks)$/.test(industry))return 'Universalbanken';
 if(/^(regional banks|banks regional)$/.test(industry))return 'Regionalbanken';
 return industry&&!/^(finance|financial services|technology|industrials|other|unknown)$/.test(industry)?'Branche: '+industry:'';
}
const cik=(x:unknown)=>/^0*[1-9][0-9]*$/.test(text(x))?text(x).replace(/^0+/,''):'';
export function sameCompany(a:Row,b:Row){return (text(a.ticker).toUpperCase()===text(b.ticker).toUpperCase()|| (!!a.listing_symbol&&a.listing_symbol===b.listing_symbol))||!!(a.isin&&a.isin===b.isin)||!!(cik(a.cik)&&cik(a.cik)===cik(b.cik))||!!(a.lei&&a.lei===b.lei)||!!(company(a.name_full||a.name)&&company(a.name_full||a.name)===company(b.name_full||b.name))}
// Boersenendung (z. B. SAN.PA fuer EURONEXT:SAN) ist keine Vorzugsaktien-Kennung: nur entfernen, wenn die Notierungspruefung sie bestaetigt.
const bareSymbol=(r:Row)=>{const t=peerSymbol(r.ticker);return t.includes('.')&&listingMatches(r.ticker,r.listing_symbol)?t.slice(0,t.lastIndexOf('.')):t};
const preferred=(r:Row)=>/preferred|preference|warrant|fund|etf|bond/i.test(text(r.security_type))||/[-.]P(?:R)?[A-Z]+$|\^|\/P[A-Z]/.test(bareSymbol(r))||/preferred|depositary shares|preference shares|warrant/i.test(text(r.name));
const bankUS=new Set(['C','JPM','BAC','WFC']);
export function selectPeers(target:Row,rows:Row[],limit=8):Row[]{
 const group=peerFamily(target);if(!group)return [];
 const usable=(r:Row)=>!!text(r.ticker)&&!preferred(r)&&!sameCompany(target,r);
 const cap=(r:Row)=>{const x=Number(r.market_cap);return Number.isFinite(x)&&x>0?x:null};
 const order=(a:Row,b:Row)=>{
  if(group==='Universalbanken'&&bankUS.has(peerSymbol(target.ticker))){const diff=Number(bankUS.has(peerSymbol(b.ticker)))-Number(bankUS.has(peerSymbol(a.ticker)));if(diff)return diff}
  const primaryDiff=Number(b.is_primary===true)-Number(a.is_primary===true);if(primaryDiff)return primaryDiff;
  const base=cap(target),ac=cap(a),bc=cap(b);if(base&&ac&&bc&&target.currency&&a.currency===target.currency&&b.currency===target.currency)return Math.abs(Math.log(ac/base))-Math.abs(Math.log(bc/base));
  // Prefer short primary symbols to OTC/secondary listings; never rank by investment score.
  return peerSymbol(a.ticker).length-peerSymbol(b.ticker).length||text(a.name).localeCompare(text(b.name));
 };
 const selected:Row[]=[];
 for(const r of rows.filter(r=>usable(r)&&peerFamily(r)===group).sort(order)){if(!selected.some(p=>sameCompany(p,r)))selected.push({...r,peer_reason:group});if(selected.length===limit)break}
 // Weniger als drei Peers der Familie: zuerst dieselbe Branche aus anderen Familien (z. B. Micron neben Chipdesignern,
 // Monster neben Coca-Cola; nicht fuer Unterbranchen), dann bei reinen Branchenfamilien Firmen eng verwandter Branchen
 // (gepruefte Gruppe), jeweils bis GROUP_FILL.
 const cap2=Math.min(limit,GROUP_FILL),industry=group.startsWith('Unterbranche: ')?'':peerIndustry(target),related=industryGroup(target);
 const fill=(candidates:Row[],reason:(r:Row)=>string)=>{for(const r of candidates.sort(order)){if(selected.length>=cap2)break;if(!selected.some(p=>sameCompany(p,r)))selected.push({...r,peer_reason:reason(r)})}};
 if(selected.length<PEER_MINIMUM&&industry)fill(rows.filter(r=>usable(r)&&peerFamily(r)!==group&&peerIndustry(r)===industry),()=>'Branche: '+text(target.industry));
 if(selected.length<PEER_MINIMUM&&related)fill(rows.filter(r=>usable(r)&&peerFamily(r)!==group&&peerIndustry(r)!==industry&&industryGroup(r)===related),r=>'Branchengruppe: '+related+' ('+text(r.industry)+')');
 return selected;
}
