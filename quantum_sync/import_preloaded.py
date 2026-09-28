"""Upload the precomputed file without fetching any stock/provider data."""
import json
import os
from pathlib import Path
import urllib.request


def main():
    payload = Path('value_radar/daten/cf_universum.json').read_bytes()
    document = json.loads(payload)
    if not document.get('kandidaten'):
        raise RuntimeError('Empty export; previous screener retained')
    token = os.environ.get('QUANTUM_SYNC_TOKEN', '').strip()
    if len(token) < 32:
        raise RuntimeError('QUANTUM_SYNC_TOKEN missing')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    request = urllib.request.Request(
        'https://quantum-equity-research.daisyscalling.workers.dev/api/preloaded-sync',
        data=payload, method='POST', headers={'Authorization': 'Bearer '+token,
            'Content-Type': 'application/json', 'User-Agent': 'QuantumPreloaded/1.0'})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
        result = json.load(response)
    print('Screener import:', result.get('accepted'), 'stocks; data date:', result.get('stand'))


if __name__ == '__main__':
    main()

