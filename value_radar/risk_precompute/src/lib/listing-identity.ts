const VENUES:Record<string,string[]>={"DE": ["XETR"], "F": ["FRA"], "L": ["LSE"], "IL": ["LSE"], "PA": ["EPA", "EURONEXT"], "AS": ["AMS", "EURONEXT"], "BR": ["EBR", "EURONEXT"], "IR": ["ISE", "DUB", "EURONEXT"], "LS": ["ELI", "EURONEXT"], "MI": ["MIL"], "MC": ["BME"], "WA": ["GPW"], "AT": ["ATHEX"], "SW": ["SIX"], "VX": ["SIX"], "ST": ["STO"], "HE": ["HEL"], "OL": ["OSL"], "CO": ["CPH"], "VI": ["VIE"], "T": ["TSE", "TYO", "JPX"], "HK": ["HKEX", "HKG"], "TO": ["TSX"], "AX": ["ASX"], "BK": ["SET"], "KL": ["MYX"], "MU": ["MUN"], "BE": ["BER"], "SG": ["STU"], "DU": ["DUS"], "HM": ["HAM"], "HA": ["HAN"]};
export function listingMatches(ticker:unknown,listing:unknown):boolean {
 let q=String(ticker??'').trim().toUpperCase();const s=String(listing??'').trim().toUpperCase();
 if(!q||!s.includes(':'))return false;
 if(q.includes(':'))return q===s;
 const split=s.indexOf(':'),ex=s.slice(0,split),base=s.slice(split+1);
 if(q==='BRK.A'||q==='BRK.B')q=q.replace('.','-');
 if(q.includes('.')){
  const at=q.lastIndexOf('.'),wanted=q.slice(0,at);
  if(!VENUES[q.slice(at+1)]?.includes(ex))return false;
  // Marktspezifische Schreibweise wie in der Pipeline (value_radar/listing_identity.py): Gattungsbuchstabe bleibt erhalten.
  if(['STO','CPH','HEL'].includes(ex)){const classKey=(v:string)=>v.replace(/[._ -]([A-Z])$/,'-$1');return classKey(base)===classKey(wanted);}
  if(ex==='LSE')return base.replace(/\.+$/,'')===wanted.replace(/\.+$/,'');
  return base===wanted;
 }
 return ['NASDAQ','NYSE','NYSEAMERICAN','AMEX','OTC'].includes(ex)&&base.replaceAll('.','-')===q;
}
export function safeUniverse<T extends Record<string,unknown>>(rows:T[]):T[]{
 return rows.filter(r=>!r.listing_symbol||!r.ticker||listingMatches(r.ticker,r.listing_symbol));
}
