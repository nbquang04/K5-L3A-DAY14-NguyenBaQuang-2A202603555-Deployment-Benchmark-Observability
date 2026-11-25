"""HTTP integration checks for shared rate limits and strict budget reservation.

Uses a disposable Redis container and two Uvicorn workers, never the user's Redis.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time

import httpx
import redis

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence'


def run():
    name = 'k5-day14-test-' + secrets.token_hex(4)
    subprocess.run(['docker', 'run', '-d', '--rm', '--name', name,
                    '-p', '127.0.0.1::6379', 'redis:7-alpine'], check=True, stdout=subprocess.DEVNULL)
    port = subprocess.check_output(['docker', 'port', name, '6379/tcp'], text=True).strip().rsplit(':', 1)[1]
    store = redis.Redis.from_url(f'redis://127.0.0.1:{port}/0', decode_responses=True)
    results = {}
    proc = None
    try:
        for _ in range(50):
            try:
                store.ping()
                break
            except redis.RedisError:
                time.sleep(.1)
        for label, rate, budget in [('rate', 10, 10), ('budget', 1000, .0001)]:
            store.flushdb()  # This newly-created disposable test container only.
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                http_port = sock.getsockname()[1]
            key = secrets.token_urlsafe(32)
            env = {**os.environ, 'AGENT_API_KEY': key, 'REDIS_URL': f'redis://127.0.0.1:{port}/0',
                   'RATE_LIMIT_PER_MINUTE': str(rate), 'DAILY_BUDGET_USD': str(budget),
                   'MONTHLY_BUDGET_USD': str(budget)}
            with (OUT / f'concurrency-{label}.log').open('w') as log:
                proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
                                         '--port', str(http_port), '--workers', '2'],
                                        cwd=ROOT / '06-lab-complete', env=env, stdout=log, stderr=subprocess.STDOUT)
                url = f'http://127.0.0.1:{http_port}'
                with httpx.Client(timeout=15) as client:
                    for _ in range(100):
                        try:
                            client.get(url + '/ready').raise_for_status()
                            break
                        except httpx.HTTPError:
                            time.sleep(.1)
                    headers = {'X-API-Key': key}
                    if label == 'rate':
                        invalid = [client.post(url + '/ask', headers=headers, json=body).status_code
                                   for body in ({}, {'question': ''}, {'question': '   '}, {'question': 'x' * 2001})]
                        assert invalid == [422] * 4, invalid
                        results['invalid_input_statuses'] = invalid
                    def ask(_):
                        r = client.post(url + '/ask', headers=headers, json={'question': 'Docker'})
                        return r.status_code, r.json()
                    with ThreadPoolExecutor(max_workers=40) as pool:
                        responses = list(pool.map(ask, range(40)))
                    codes = [code for code, _ in responses]
                    assert set(codes) <= {200, 429 if label == 'rate' else 402}, codes
                    if label == 'rate':
                        assert codes.count(200) == 10 and codes.count(429) == 30, codes
                    else:
                        totals = {k: float(store.get(k)) for k in store.scan_iter('budget:*')}
                        spent = sum(body['usage']['cost_usd'] for code, body in responses if code == 200)
                        assert codes.count(402) > 0 and codes.count(200) > 0
                        assert all(value <= budget + 1e-12 and abs(value - spent) < 1e-12 for value in totals.values()), totals
                        results['budget_totals'] = totals
                        results['accepted_cost_usd'] = spent
                    results[label + '_codes'] = {str(code): codes.count(code) for code in set(codes)}
                proc.send_signal(signal.SIGTERM)
                proc.wait(15)
                assert proc.returncode == 0
                proc = None
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        store.close()
        subprocess.run(['docker', 'stop', name], check=True, stdout=subprocess.DEVNULL)
    (OUT / 'concurrency-check.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('PASS: input validation, atomic rate limit, atomic budget, two workers')


if __name__ == '__main__':
    run()
