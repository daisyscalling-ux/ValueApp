"""Peer metadata from already loaded profiles. No network requests."""
import datetime as dt
FIELDS=('industry','sub_industry','isin','cik','lei','exchange','listing_symbol','is_primary','primary_listing','security_type','country','currency','market_cap','metadata_source','metadata_asof','name_full')
def metadata(profile, listing=None):
 p=profile or {}; l=listing or {}
 def get(*keys):
  return next((p[k] for k in keys if p.get(k) not in (None,'')),None)
 primary=l.get('is_primary')
 if primary not in (True,False): primary=None
 return dict(industry=get('industry'),sub_industry=get('sub_industry','subIndustry'),
  isin=get('isin') or l.get('isin'),cik=get('cik'),lei=get('lei'),
  exchange=l.get('exchange') or get('exchange'),listing_symbol=l.get('symbol') or get('symbol'),
  is_primary=primary,primary_listing=l.get('symbol') if primary is True else get('primary_listing','primaryListing'),
  security_type=get('security_type','securityType') or l.get('type'),
  country=get('country_code','country') or l.get('country'),metadata_source='ROIC profile/listing',
  metadata_asof=dt.datetime.now(dt.timezone.utc).isoformat())
def export_metadata(f):
 return {**{k:f.get(k) for k in FIELDS},'name_full':f.get('name_full') or f.get('name')}
def coverage(rows):
 return {key:sum(r.get(key) not in (None,'','Unknown') for r in rows) for key in ('industry','sub_industry','isin','cik','primary_listing','market_cap')}
