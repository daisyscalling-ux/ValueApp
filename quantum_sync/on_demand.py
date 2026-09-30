"""Process only requested stock supplements; never alters the universe checkpoint."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ENDPOINT = 'https://quantum-equity-research.daisyscalling.workers.dev/api/supplement-sync'


def post(payload):
    token = os.environ.get('QUANTUM_SYNC_TOKEN', '')
    if len(token) < 32:
        raise RuntimeError('QUANTUM_SYNC_TOKEN missing')
    request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
        'User-Agent': 'QuantumSupplement/1.0'}, method='POST')
    # Do not forward the sync credential on redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
        return json.load(response)


def main():
    deadline = time.monotonic() + 240
    processed = 0
    while time.monotonic() < deadline - 150:
        jobs = post({'action': 'claim'}).get('jobs', [])
        if not jobs:
            break
        for job in jobs:
            try:
                child = subprocess.run([sys.executable, str(Path(__file__).with_name('yahoo_supplement.py'))],
                    input=json.dumps(job['stock']), text=True, encoding='utf-8', capture_output=True,
                    timeout=40, check=True)
                extra = json.loads(child.stdout)
            except (subprocess.SubprocessError, ValueError):
                extra = {'error': 'Yahoo supplement unavailable'}
            result = post({'action': 'complete', 'id': job['id'], 'lease': job['lease'], 'extra': extra})
            processed += 1
            print('Supplement completed:', processed, 'accepted:', result.get('accepted', False), flush=True)
    print('Requested stocks processed:', processed, flush=True)


if __name__ == '__main__':
    main()
