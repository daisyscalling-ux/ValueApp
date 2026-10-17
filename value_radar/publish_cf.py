"""Publish a validated export from an isolated checkout; never hide push failures."""
import datetime as dt
import json
import pathlib
import subprocess
import sys

TARGET = 'value_radar/daten/cf_universum.json'


def git(repo, *args, check=True):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, timeout=90)
    if check and result.returncode:
        raise RuntimeError('Git operation failed: ' + args[0])
    return result


def validate(path, now=None):
    data = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    end = dt.datetime.strptime(data['stand'], '%Y-%m-%d %H:%M UTC').replace(tzinfo=dt.timezone.utc)
    now = now or dt.datetime.now(dt.timezone.utc)
    if not 0 <= (now-end).total_seconds() <= 86400:
        raise ValueError('Export is stale or future dated')
    rows = data['kandidaten']
    if not isinstance(rows, list) or not rows or data['anzahl'] != len(rows):
        raise ValueError('Export is empty or row count is inconsistent')
    return data, end


def publish(repo, source, now=None):
    repo, source = pathlib.Path(repo), pathlib.Path(source)
    data, end = validate(source, now)
    if git(repo, 'status', '--porcelain').stdout.strip():
        raise RuntimeError('Publication requires a clean isolated checkout')
    git(repo, 'fetch', 'origin', 'main')
    git(repo, 'merge', '--ff-only', 'origin/main')
    target = repo / TARGET
    if target.exists():
        old = json.loads(target.read_text(encoding='utf-8'))
        old_end = dt.datetime.strptime(old['stand'], '%Y-%m-%d %H:%M UTC').replace(tzinfo=dt.timezone.utc)
        if old_end > end:
            raise RuntimeError('A newer export is already published; refusing replacement')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    git(repo, 'add', '--', TARGET)
    if git(repo, 'diff', '--cached', '--quiet', check=False).returncode == 0:
        return 'unchanged'
    git(repo, 'commit', '-m', 'Cloudflare-Universum aktualisiert [skip ci]')
    for attempt in range(3):
        if git(repo, 'push', 'origin', 'HEAD:main', check=False).returncode == 0:
            return 'published'
        if attempt < 2:
            git(repo, 'fetch', 'origin', 'main')
            # Preserve unrelated concurrent updates. Conflicting changes to the
            # export itself stop publication rather than choosing either side.
            if git(repo, 'rebase', 'origin/main', check=False).returncode:
                git(repo, 'rebase', '--abort', check=False)
                raise RuntimeError('Concurrent export conflict; saved artifact requires review')
    raise RuntimeError('Publication failed after three attempts; export remains in artifact')


if __name__ == '__main__':
    print(publish(sys.argv[1], sys.argv[2]))

