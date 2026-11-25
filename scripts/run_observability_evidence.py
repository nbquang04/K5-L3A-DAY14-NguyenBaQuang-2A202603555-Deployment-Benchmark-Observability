"""Collect Locust CSV, Prometheus samples, traces, logs and real alert timings."""
import json
import os
from pathlib import Path
import subprocess
import time
import argparse
from datetime import datetime, timezone

import httpx

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / '06-lab-complete/benchmark-observability/production'
OUT = ROOT / 'evidence'
OUT.mkdir(exist_ok=True)
ENV = {**os.environ, 'GRAFANA_PORT': '3001', 'OBSERVABILITY_PORT': '18080'}
COMPOSE = ['docker', 'compose', '-p', 'k5-day14-observability']


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def run(args, name, env=ENV, allowed=(0,)):
    with (OUT / name).open('w', encoding='utf-8') as log:
        result = subprocess.run([*COMPOSE, *args], cwd=FOLDER, env=env,
                                stdout=log, stderr=subprocess.STDOUT)
    print(name, 'exit', result.returncode, flush=True)
    if result.returncode not in allowed:
        raise RuntimeError(name)


def query(expression):
    r = httpx.get('http://localhost:9090/api/v1/query', params={'query': expression}, timeout=15)
    r.raise_for_status()
    return r.json()


def samples(name):
    expressions = {
        'p95': 'histogram_quantile(0.95,sum by(le)(rate(http_request_duration_seconds_bucket{job="agent",route="/ask"}[1m])))',
        'avg': 'sum(rate(http_request_duration_seconds_sum{job="agent",route="/ask"}[1m])) / sum(rate(http_request_duration_seconds_count{job="agent",route="/ask"}[1m]))',
        'rps_by_instance': 'sum by(instance)(rate(http_requests_total{job="agent",route="/ask"}[1m]))',
        'tokens': 'sum by(type)(rate(llm_tokens_total{job="agent"}[1m]))',
        'error_rate': 'sum(rate(http_requests_total{job="agent",route="/ask",status=~"5.."}[1m])) / sum(rate(http_requests_total{job="agent",route="/ask"}[1m]))',
    }
    save(name, {key: query(expr) for key, expr in expressions.items()})


def collect_traces():
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    summaries = httpx.get('http://localhost:16686/api/v3/trace-summaries', params={
        'query.serviceName': 'observable-agent',
        'query.startTimeMin': (now - timedelta(hours=2)).isoformat(),
        'query.startTimeMax': now.isoformat(), 'query.searchDepth': 1000,
    }, timeout=30)
    summaries.raise_for_status()
    save('jaeger-trace-summaries.json', summaries.json())
    candidates = sorted(summaries.json()['summaries'],
                        key=lambda t: int(t['maxEndTimeUnixNano']) - int(t['minStartTimeUnixNano']), reverse=True)
    run(['logs', '--no-color', 'agent'], 'observability-agents.log')
    log_events = []
    for line in (OUT / 'observability-agents.log').read_text(encoding='utf-8').splitlines():
        try:
            event = json.loads(line[line.index('{'):])
            if event.get('trace_id'):
                log_events.append(event)
        except (ValueError, json.JSONDecodeError):
            pass
    ids_with_logs = {e['trace_id'] for e in log_events}
    slow_id = next(t['traceId'] for t in candidates if t['traceId'] in ids_with_logs)
    slow = httpx.get('http://localhost:16686/api/traces/' + slow_id, timeout=20).json()['data'][0]
    # Wait for complete batches: a trace can initially contain only its retrieval
    # span while the later LLM error is still buffered by the exporter.
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=10)
    errors = [e for e in log_events if e.get('event') == 'llm_error'
              and datetime.fromisoformat(e['ts']) < cutoff]
    error = None
    for event in reversed(errors):
        result = httpx.get('http://localhost:16686/api/traces/' + event['trace_id'], timeout=20)
        if result.status_code == 200 and result.json().get('data'):
            error = result.json()['data'][0]
            break
    if not error:
        raise RuntimeError('No retained error trace found')
    save('jaeger-slow-trace.json', slow)
    save('jaeger-error-trace.json', error)
    save('trace-log-correlation.json', {kind: [e for e in log_events if e['trace_id'] == t['traceID']]
         for kind, t in [('slow', slow), ('error', error)]})
    save('screenshot-targets.json', {'grafana': 'http://localhost:3001',
         'prometheus': 'http://localhost:9090/alerts',
         'slow': 'http://localhost:16686/trace/' + slow['traceID'],
         'error': 'http://localhost:16686/trace/' + error['traceID']})


def main(chaos_only=False):
    run(['up', '-d', '--build', '--scale', 'agent=1'], 'obs-build.log')
    for attempt in range(90):
        try:
            httpx.get('http://localhost:18080/health', timeout=2).raise_for_status()
            break
        except httpx.HTTPError:
            time.sleep(1)
    else:
        raise RuntimeError('Observable agent failed health check')
    time.sleep(15)
    for scale in (() if chaos_only else (1, 3)):
        if scale == 3:
            run(['up', '-d', '--scale', 'agent=3'], 'obs-scale3-up.log')
            time.sleep(15)
        run(['run', '--rm', 'locust', '-f', '/mnt/locust/locustfile.py', '--host', 'http://nginx',
             '--headless', '-u', '100', '-r', '10', '-t', '2m', '--csv', f'/mnt/results/scale_{scale}'],
            f'locust-scale-{scale}.log', allowed=(0, 1))
        samples(f'prometheus-scale-{scale}.json')
    # A+B combined intentionally: obtain two simultaneously firing alerts.
    chaos_env = {**ENV, 'MOCK_ERROR_RATE': '0.2', 'MOCK_SLOW_RATE': '0.3'}
    started = time.monotonic()
    start_utc = datetime.now(timezone.utc).isoformat()
    run(['up', '-d', '--scale', 'agent=3'], 'obs-chaos-up.log', chaos_env)
    log = (OUT / 'locust-chaos.log').open('w', encoding='utf-8')
    load = subprocess.Popen([*COMPOSE, 'run', '--rm', 'locust', '-f', '/mnt/locust/locustfile.py',
                             '--host', 'http://nginx', '--headless', '-u', '30', '-r', '5', '-t', '10m',
                             '--csv', '/mnt/results/chaos'], cwd=FOLDER, env=chaos_env,
                            stdout=log, stderr=subprocess.STDOUT)
    timing = {'configuration_started_utc': start_utc,
              'faults': {'MOCK_ERROR_RATE': 0.2, 'MOCK_SLOW_RATE': 0.3},
              'first_firing_seconds': {}}
    try:
        while time.monotonic() - started < 330:
            alerts = httpx.get('http://localhost:9090/api/v1/alerts', timeout=10).json()
            for alert in alerts['data']['alerts']:
                name = alert['labels']['alertname']
                if name in ('AgentHighErrorRate', 'AgentHighLatencyP95') and alert['state'] == 'firing' and name not in timing['first_firing_seconds']:
                    timing['first_firing_seconds'][name] = round(time.monotonic() - started, 2)
                    print('FIRING', name, timing['first_firing_seconds'][name], flush=True)
            save('alert-timing.json', timing)
            if {'AgentHighErrorRate', 'AgentHighLatencyP95'} <= timing['first_firing_seconds'].keys():
                save('prometheus-alerts-firing.json', alerts)
                break
            time.sleep(2)
        else:
            raise RuntimeError('Two alerts did not fire within 330 seconds')
        samples('prometheus-chaos.json')
        collect_traces()
        print('READY FOR SCREENSHOTS', flush=True)
        for _ in range(300):
            if (OUT / 'screenshots-captured').exists():
                break
            time.sleep(2)
    finally:
        load.terminate()
        try:
            load.wait(10)
        except subprocess.TimeoutExpired:
            load.kill()
        log.close()
        # Restore the normal config. Root agent collects screenshots before down.
        run(['up', '-d', '--scale', 'agent=3'], 'obs-restore.log')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--chaos-only', action='store_true')
    parser.add_argument('--traces-only', action='store_true')
    args = parser.parse_args()
    if args.traces_only:
        collect_traces()
    else:
        main(args.chaos_only)
