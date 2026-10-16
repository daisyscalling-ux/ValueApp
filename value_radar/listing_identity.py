"""Exact ticker/venue identity. Search ranking is never identity evidence."""
SUFFIXES={
 'DE':('XETR',),'F':('FRA',),'L':('LSE',),'IL':('LSE',),
 'PA':('EPA','EURONEXT'),'AS':('AMS','EURONEXT'),'BR':('EBR','EURONEXT'),
 'IR':('ISE','DUB','EURONEXT'),'LS':('ELI','EURONEXT'),'MI':('MIL',),'MC':('BME',),
 'WA':('GPW',),'AT':('ATHEX',),'SW':('SIX',),'VX':('SIX',),'ST':('STO',),
 'HE':('HEL',),'OL':('OSL',),'CO':('CPH',),'VI':('VIE',),'T':('TSE','TYO','JPX'),
 'HK':('HKEX','HKG'),'TO':('TSX',),'AX':('ASX',),'BK':('SET',),'KL':('MYX',),
 'MU':('MUN',),'BE':('BER',),'SG':('STU',),'DU':('DUS',),'HM':('HAM',),'HA':('HAN',)}
def listing_matches(ticker,listing):
 q=str(ticker or '').strip().upper();s=str(listing or '').strip().upper()
 if not q or ':' not in s:return False
 if ':' in q:return q==s
 ex,base=s.split(':',1)
 if q in ('BRK.A','BRK.B'):q=q.replace('.','-')
 if '.' in q:
  wanted,suffix=q.rsplit('.',1)
  return ex in SUFFIXES.get(suffix,()) and base==wanted
 return ex in ('NASDAQ','NYSE','NYSEAMERICAN','AMEX','OTC') and base.replace('.','-')==q
def select_listing(ticker,hits):
 eligible=[r for r in hits if listing_matches(ticker,r.get('symbol'))]
 if not eligible:return None
 eligible.sort(key=lambda r:(r.get('symbol','').startswith('OTC:'),r.get('is_primary') is not True))
 best=eligible[0]
 if any(r.get('symbol')==best.get('symbol') and r.get('isin') and best.get('isin') and r['isin']!=best['isin'] for r in eligible):return None
 return best

