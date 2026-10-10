"""Bounded capability audit. Never infer a survivor-free universe from list access."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse

ENDPOINTS = {
    'current_members': 'sp500-constituent',
    'membership_changes': 'historical-sp500-constituent',
    'delisted_first_page': 'delisted-companies?page=0&limit=100',
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def probe(key):
    result = {}
    for name, path in ENDPOINTS.items():
        if not key:
            result[name] = {'status': 'missing_secret'}
            continue
        url = 'https://financialmodelingprep.com/stable/' + path
        url += ('&' if '?' in path else '?') + urllib.parse.urlencode({'apikey': key})
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ValueApp historical coverage audit'})
            with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
                raw = response.read(10_000_001)
                if len(raw) > 10_000_000:
                    result[name] = {'status': 'response_too_large'}
                    continue
                data = json.loads(raw)
            # Store only shape and count: never error bodies, URLs containing keys or raw provider data.
            valid = isinstance(data, list) and all(isinstance(r, dict) for r in data)
            result[name] = {'status': 'available' if valid and data else 'empty_or_unrecognized',
                            'rows': len(data) if valid else None,
                            'fields': sorted({str(k) for r in data[:3] for k in r if str(k) != key}) if valid else []}
        except urllib.error.HTTPError as exc:
            result[name] = {'status': 'access_denied' if exc.code in (401,402,403) else 'http_error', 'http': exc.code}
        except Exception:
            result[name] = {'status': 'network_or_parse_error'}
    return {'schema': 1, 'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'endpoints': result, 'complete_historical_universe_verified': False,
            'limitations': ['Capability check only; no historical membership or delisting returns verified.',
                            'Delisted list requests only first page. Index deletion is not security termination.']}

if __name__ == '__main__':
    out = Path('historical-universe-output'); out.mkdir(exist_ok=True)
    report = probe(os.environ.get('FMP_API_KEY', '').strip())
    (out/'source-status.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2))
