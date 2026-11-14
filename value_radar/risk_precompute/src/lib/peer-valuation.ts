/**
 * peer-valuation.ts - Peers fuer Composite-Perzentile und EV/EBITDA-Multiple (seit 13.11.2026).
 * Peers = selectPeers (dieselbe Auswahl wie Peer-Vergleich und Risikoscore) aus cf_universum.json.
 * Eine Kennzahl wird nur gegen Peers bewertet, wenn mindestens PEER_PERCENTILE_MIN Peers einen gueltigen
 * Wert haben (Entscheidung des Nutzers); sonst gilt die feste Ersatzskala, gekennzeichnet.
 * Identische Kopie unter ValueApp/value_radar/risk_precompute/src/lib.
 */
import type {Fund} from './valuation';
export const PEER_PERCENTILE_MIN=5;
type Row=Record<string,unknown>;
const n=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?v:null;
const pct=(v:unknown)=>{const x=n(v);return x===null?null:x/100};
/** Universumszeile -> Kennzahlen in Fund-Skala. Prozentfelder des Exports (roe, gross_margin, revenue_growth) werden zu Anteilen. */
export function peerFundFromRow(r:Row):Fund&Row{
 // Forward-KGV der Peers nur aus geprüftem Konsens (eps_forward_method, seit 14.11.2026); ältere Zeilen bleiben offen.
 const price=n(r.price),epsF=r.eps_forward_method==='consensus_ntm_blend_v1'?n(r.eps_forward):null;
 return {ticker:String(r.listing_symbol??r.ticker??''),ev_ebitda:n(r.ev_ebitda),pb:n(r.pb),
  pe_forward:price&&price>0&&epsF&&epsF>0?price/epsF:null,roe:pct(r.roe),gross_margin:pct(r.gross_margin),
  revenue_growth:pct(r.revenue_growth),net_debt_ebitda:n(r.net_debt_ebitda)};
}
export function peerFundsFromRows(rows:Row[]|null|undefined):(Fund&Row)[]{return Array.isArray(rows)?rows.filter(r=>r&&typeof r==='object').map(peerFundFromRow):[]}
