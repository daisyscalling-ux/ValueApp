"""Fetch priority only. Never a liquidity, quality or risk classification."""
import datetime as dt
import json
from pathlib import Path
RULES=json.loads(Path(__file__).with_name('market-priority.json').read_text(encoding='utf8'))
def market_tier(symbol):
 venue=str(symbol or '').split(':')[0].upper()
 return 0 if venue in RULES['primary'] else 1 if venue in RULES['europe'] else 2
def fetch_priority(symbol,last_attempt,now):
 try:
  date=dt.datetime.fromisoformat(str(last_attempt).replace('Z','+00:00'))
  if date.tzinfo is None or date>now:raise ValueError()
 except (TypeError,ValueError):date=None
 # Old failures re-enter ahead of new work after a week; retained, not deleted.
 rotation=bool(date and now-date>=dt.timedelta(days=RULES['rotationDays']))
 return (0 if rotation else 1, market_tier(symbol), date.timestamp() if date else 0, str(symbol))
