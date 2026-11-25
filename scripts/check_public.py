"""Verify a deployed Part 6 service without printing the API key."""
import getpass
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else input('Public HTTPS URL: ')).rstrip('/')
    if not base.startswith('https://'):
        raise SystemExit('Use the public https:// URL')
    key = os.getenv('AGENT_API_KEY') or getpass.getpass('AGENT_API_KEY (hidden): ')
    checks = []
    for path, method, authenticated, expected in [
        ('/health', 'GET', False, 200), ('/ready', 'GET', False, 200),
        ('/ask', 'POST', False, 401), ('/ask', 'POST', True, 200),
    ]:
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['X-API-Key'] = key
        data = json.dumps({'question': 'Hello'}).encode() if method == 'POST' else None
        request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        checks.append({'method': method, 'path': path, 'authenticated': authenticated,
                       'status': status, 'expected': expected, 'passed': status == expected})
        print(f'{method} {path} key={authenticated}: {status} (expected {expected})')
    out = Path(__file__).resolve().parents[1] / 'evidence/public-check.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({'base_url': base, 'checks': checks}, indent=2), encoding='utf-8')
    raise SystemExit(0 if all(c['passed'] for c in checks) else 1)


if __name__ == '__main__':
    main()
