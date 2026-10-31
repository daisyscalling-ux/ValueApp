"""Reviewed holding liquidity, no inference from subsidiary or capital ratios."""
import datetime as dt,math,re
def liquidity_for(parent,archive,now):
 if archive.get('schema')!=1 or archive.get('method')!='reviewed-holding-lcr-v1':return None
 matches=[r for r in archive.get('records',[]) if r.get('rssdId')==parent.get('rssdId') and r.get('period')==parent.get('period')]
 if len(matches)!=1:return None
 r=matches[0]
 try:
  if r['scope']!='listed_consolidated_holding' or r['holdingName']!=parent['holdingName'] or r['averaging']!='quarter_average' or r['unit']!='fraction' or r['currency']!='USD':return None
  if not 0<=(now.date()-dt.date.fromisoformat(r['period'])).days<=180 or not dt.date.fromisoformat(r['period'])<=dt.date.fromisoformat(r['reviewedOn'])<=now.date()<=dt.date.fromisoformat(r['reviewExpires']):return None
  if not re.fullmatch(r'https://www\.sec\.gov/Archives/edgar/data/\d+/\d+/[A-Za-z0-9_.-]+\.htm',r['sourceUrl']):return None
  for k in ('hqla','netOutflows','reportedRatio','ratioRoundingTolerance'):
   if not isinstance(r[k],(int,float)) or isinstance(r[k],bool) or not math.isfinite(r[k]):return None
  if r['hqla']<0 or r['netOutflows']<=0 or not 0<=r['reportedRatio']<=10 or not 0<=r['ratioRoundingTolerance']<=.005:return None
  if abs(r['hqla']/r['netOutflows']-r['reportedRatio'])>r['ratioRoundingTolerance']:return None
 except (KeyError,ValueError,TypeError):return None
 return {**r,'state':'available','method':archive['method'],'scoreContribution':0}
