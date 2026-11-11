"""Reviewed holding liquidity, no inference from subsidiary or capital ratios. Spiegel von holding-liquidity.ts."""
import datetime as dt,math,re
SEC=r'https://www\.sec\.gov/Archives/edgar/data/\d+/\d+/[A-Za-z0-9_.-]+\.htm'

def _num(v):
 return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

def _anchored(r,parent,now):
 try:
  if r.get('method')!='reviewed-holding-lcr-v1' or r['scope']!='listed_consolidated_holding' or r['holdingName']!=parent['holdingName']:return False
  if not 0<=(now.date()-dt.date.fromisoformat(r['period'])).days<=180 or not dt.date.fromisoformat(r['period'])<=dt.date.fromisoformat(r['reviewedOn'])<=now.date()<=dt.date.fromisoformat(r['reviewExpires']):return False
  return bool(re.fullmatch(SEC,r['sourceUrl'])) and isinstance(r.get('sourceSection'),str) and bool(r['sourceSection'].strip())
 except (KeyError,ValueError,TypeError):return False

def liquidity_for(parent,archive,now):
 if archive.get('schema')!=1 or archive.get('method')!='reviewed-holding-lcr-v1':return None
 matches=[r for r in archive.get('records',[]) if r.get('rssdId')==parent.get('rssdId') and r.get('period')==parent.get('period')]
 if len(matches)!=1:return None
 r={'method':archive['method'],**matches[0]}
 try:
  if not _anchored(r,parent,now) or r['averaging']!='quarter_average' or r['unit']!='fraction' or r['currency']!='USD':return None
  if not _num(r['reportedRatio']) or not 0<r['reportedRatio']<=10:return None
  basis=r.get('basis','amounts')
  if basis=='amounts':
   for k in ('hqla','netOutflows','ratioRoundingTolerance'):
    if not _num(r[k]):return None
   if r['hqla']<0 or r['netOutflows']<=0 or not 0<=r['ratioRoundingTolerance']<=.005:return None
   if abs(r['hqla']/r['netOutflows']-r['reportedRatio'])>r['ratioRoundingTolerance']:return None
  elif basis=='ratio_only':
   if r.get('netOutflows') is not None or not (r.get('hqla') is None or (_num(r['hqla']) and r['hqla']>=0)):return None
  else:return None
 except (KeyError,ValueError,TypeError):return None
 return {**r,'state':'available','method':archive['method'],'scoreContribution':0}

def exemption_for(parent,archive,now):
 """Gepruefte Ausnahme ohne LCR-Pflicht (US-Kategorie IV), gleicher Stichtag wie das Kapital."""
 if archive.get('schema')!=1 or archive.get('method')!='reviewed-holding-lcr-v1':return None
 matches=[r for r in archive.get('exemptions',[]) if r.get('rssdId')==parent.get('rssdId') and r.get('period')==parent.get('period')]
 if len(matches)!=1:return None
 r={'method':archive['method'],**matches[0],'state':'not_applicable'}
 if not _anchored(r,parent,now) or r.get('reason')!='us_category_iv_lcr_not_applicable' or not (isinstance(r.get('quote'),str) and len(r['quote'].strip())>=20):return None
 return {**r,'scoreContribution':0}
