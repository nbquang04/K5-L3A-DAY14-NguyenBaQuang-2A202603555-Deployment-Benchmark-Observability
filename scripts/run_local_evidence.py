"""Run real HTTP exercises and Part 7 benchmarks. Use the WSL lab venv.

Initial run: python scripts/run_local_evidence.py
After correcting the KB: python scripts/run_local_evidence.py --fixed
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
EVIDENCE = ROOT / 'evidence'
REPORTS.mkdir(exist_ok=True)
EVIDENCE.mkdir(exist_ok=True)
PYTHON = sys.executable


class Server:
    def __init__(self, folder, port, **env):
        self.folder, self.port, self.env = folder, port, env

    def __enter__(self):
        self.log = (EVIDENCE / f'{self.port}-server.log').open('a', encoding='utf-8')
        command = [PYTHON, '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1',
                   '--port', str(self.port)]
        # This teaching example installs signal handlers at import time: run its
        # documented entrypoint so Uvicorn installs its handlers afterwards.
        if self.folder == '05-scaling-reliability/develop':
            command = [PYTHON, 'app.py']
        self.proc = subprocess.Popen(
            command, cwd=ROOT / self.folder,
            env={**os.environ, **self.env, 'PORT': str(self.port)},
            stdout=self.log, stderr=subprocess.STDOUT)
        self.url = f'http://127.0.0.1:{self.port}'
        for _ in range(100):
            if self.proc.poll() is not None:
                raise RuntimeError(f'Server {self.folder} exited; see evidence log')
            try:
                httpx.get(self.url + '/openapi.json', timeout=1).raise_for_status()
                return self
            except httpx.HTTPError:
                time.sleep(.1)
        raise RuntimeError('Server startup timed out')

    def __exit__(self, *args):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.log.close()


def save(name, data):
    (EVIDENCE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def response(r):
    return {'status': r.status_code, 'headers': dict(r.headers), 'body': r.json()}


def curl_capture(path, url, *args):
    result = subprocess.run(['curl', '-sS', '-i', *args, url], text=True, capture_output=True, check=True)
    (EVIDENCE / path).write_text(result.stdout, encoding='utf-8')


def exercises():
    data = {}
    with Server('01-localhost-vs-production/develop', 8101) as s:
        data['part1_develop'] = response(httpx.post(s.url + '/ask', params={'question': 'Hello'}))
    with Server('01-localhost-vs-production/production', 8102) as s:
        data['part1_production'] = response(httpx.get(s.url + '/health'))
    with Server('04-api-gateway/develop', 8104, AGENT_API_KEY='local-evidence-key') as s:
        body = json.dumps({'question': 'Hello'})
        curl_capture('api-key-401.txt', s.url + '/ask', '-X', 'POST', '-H', 'Content-Type: application/json', '-d', body)
        curl_capture('api-key-200.txt', s.url + '/ask', '-X', 'POST', '-H', 'Content-Type: application/json', '-H', 'X-API-Key: local-evidence-key', '-d', body)
    with Server('04-api-gateway/production', 8105, JWT_SECRET=os.urandom(32).hex()) as s:
        r = httpx.post(s.url + '/auth/token', json={'username': 'student', 'password': 'demo123'})
        r.raise_for_status()
        token = r.json()['access_token']
        headers = {'Authorization': 'Bearer ' + token}
        codes = []
        with httpx.Client() as client:
            for i in range(20):
                r = client.post(s.url + '/ask', headers=headers, json={'question': f'Test {i}'})
                codes.append(r.status_code)
        data['jwt_rate_limit_codes'] = codes
        curl_capture('jwt-429.txt', s.url + '/ask', '-X', 'POST', '-H', 'Content-Type: application/json', '-H', 'Authorization: Bearer ' + token, '-d', '{"question":"Test"}')
    with Server('05-scaling-reliability/develop', 8106) as s:
        data['part5_health'] = response(httpx.get(s.url + '/health'))
        data['part5_ready'] = response(httpx.get(s.url + '/ready'))
        holder = {}
        def ask():
            holder['result'] = response(httpx.post(s.url + '/ask', params={'question': 'Hello'}, timeout=10))
        thread = threading.Thread(target=ask)
        thread.start()
        time.sleep(.05)
        s.proc.send_signal(signal.SIGTERM)
        thread.join(15)
        s.proc.wait(15)
        data['part5_sigterm'] = {**holder, 'exit_code': s.proc.returncode}
    save('local-exercises.json', data)


def command(args, name):
    with (EVIDENCE / name).open('w', encoding='utf-8') as log:
        result = subprocess.run([PYTHON, *args], cwd=ROOT / '06-lab-complete/benchmark-observability/develop', stdout=log, stderr=subprocess.STDOUT)
    print(name, 'exit', result.returncode, flush=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(name)


def benchmark(fixed, load_only=False):
    folder = '06-lab-complete/benchmark-observability/develop'
    if fixed:
        with Server(folder, 8002, AGENT_VERSION='v2', MOCK_ERROR_RATE='0') as s:
            command(['eval/run_eval.py', '--url', s.url, '--min-accuracy', '1.0', '--baseline', str(REPORTS / 'eval_v2.json'), '--out', str(REPORTS / 'eval_v2_fixed.json')], 'eval_v2_fixed.log')
        return
    if not load_only:
        with Server(folder, 8001, AGENT_VERSION='v1', MOCK_ERROR_RATE='0') as s:
            command(['eval/run_eval.py', '--url', s.url, '--out', str(REPORTS / 'eval_v1.json')], 'eval_v1.log')
        with Server(folder, 8002, AGENT_VERSION='v2', MOCK_ERROR_RATE='0') as s:
            command(['eval/run_eval.py', '--url', s.url, '--baseline', str(REPORTS / 'eval_v1.json'), '--out', str(REPORTS / 'eval_v2.json')], 'eval_v2.log')
    with Server(folder, 8002, AGENT_VERSION='v2') as s:
        for c in (1, 10, 50, 100):
            command(['load_test.py', '--url', s.url, '--requests', '300', '--concurrency', str(c), '--out', str(REPORTS / f'load_v2_c{c}.json')], f'load_v2_c{c}.log')
        metrics = httpx.get(s.url + '/metrics').text
        (EVIDENCE / 'develop-metrics.txt').write_text(metrics, encoding='utf-8')
    for slow in ('0', '0.03', '0.1'):
        with Server(folder, 8002, AGENT_VERSION='v2', MOCK_SLOW_RATE=slow) as s:
            command(['load_test.py', '--url', s.url, '--requests', '300', '--concurrency', '20', '--out', str(REPORTS / f'load_v2_slow_{slow}.json')], f'load_v2_slow_{slow}.log')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixed', action='store_true')
    parser.add_argument('--load-only', action='store_true')
    parser.add_argument('--overwrite-baselines', action='store_true',
                        help='Explicitly replace the recorded v1/v2 baseline reports')
    args = parser.parse_args()
    if not args.fixed and not args.load_only and (REPORTS / 'eval_v2.json').exists() and not args.overwrite_baselines:
        parser.error('Baseline already exists. Use --fixed or --load-only; --overwrite-baselines deliberately replaces historical evidence.')
    if not args.fixed and not args.load_only:
        exercises()
    benchmark(args.fixed, args.load_only)
