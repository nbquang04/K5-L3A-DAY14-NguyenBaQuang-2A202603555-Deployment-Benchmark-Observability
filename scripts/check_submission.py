"""Check evidence consistency and protected files; cloud remains a separate step."""
import ast
import csv
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def main():
    protected = ['06-lab-complete/check_production_ready.py',
                 '06-lab-complete/benchmark-observability/develop/eval/golden_dataset.jsonl']
    result = subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', *protected], cwd=ROOT, capture_output=True)
    assert result.returncode == 0, 'Protected grader or dataset changed'
    for p in [*(ROOT / 'scripts').glob('*.py'), *(ROOT / '06-lab-complete/app').glob('*.py')]:
        ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p))
    names = [f'load_v2_c{c}' for c in (1, 10, 50, 100)]
    names += [f'load_v2_slow_{r}' for r in ('0', '0.03', '0.1')]
    for name in names:
        report = load(f'reports/{name}.json')
        assert report['total_requests'] == 300
        assert sum(report['status_codes'].values()) == 300
        errors = sum(v for k, v in report['status_codes'].items() if k != '200')
        assert abs(report['error_rate'] - errors / 300) < .00006
        slo = report['slo']
        assert slo['passed'] == (report['latency_ms']['p95'] <= slo['p95_ms'] and report['error_rate'] <= slo['error_rate'])
    for name in ('eval_v1', 'eval_v2', 'eval_v2_fixed'):
        report = load(f'reports/{name}.json')
        assert report['total'] == len(report['results']) == 23
    fixed = load('reports/eval_v2_fixed.json')
    assert fixed['passed'] == 23 and fixed['accuracy'] == 1 and fixed['quality_gate']['passed']
    assert not fixed['quality_gate']['regressions']
    for scale in (1, 3):
        path = Path(f'benchmark-results/scale_{scale}_stats.csv')
        nested = Path('06-lab-complete/benchmark-observability/production') / path
        assert (ROOT / path).read_bytes() == (ROOT / nested).read_bytes()
        with (ROOT / path).open() as f:
            row = next(r for r in csv.DictReader(f) if r['Name'] == '/ask')
        assert int(row['Request Count']) > 0 and float(row['Requests/s']) > 0
    for name in ('grafana-dashboard', 'jaeger-slow-trace', 'jaeger-error-trace', 'prometheus-alert-firing', 'dashboard', 'running', 'test'):
        png = (ROOT / f'screenshots/{name}.png').read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', png[16:24])[0] >= 1000
    alerts = load('evidence/prometheus-alerts-firing.json')['data']['alerts']
    firing = {a['labels']['alertname'] for a in alerts if a['state'] == 'firing'}
    assert {'AgentHighErrorRate', 'AgentHighLatencyP95'} <= firing
    correlation = load('evidence/trace-log-correlation.json')
    for kind in ('slow', 'error'):
        trace = load(f'evidence/jaeger-{kind}-trace.json')
        assert len(trace['spans']) >= 4
        assert any(event['trace_id'] == trace['traceID'] for event in correlation[kind])
    error = load('evidence/jaeger-error-trace.json')
    assert any(field.get('value') == 'exception'
               for span in error['spans'] for log in span['logs'] for field in log['fields'])
    for name in ('MISSION_ANSWERS.md', 'BENCHMARK_REPORT.md'):
        body = (ROOT / name).read_text(encoding='utf-8')
        for match in re.finditer(r'\]\(([^)]+)\)', body):
            link = match.group(1)
            if '://' not in link and not link.startswith('#'):
                assert (ROOT / link.split('#')[0]).exists(), f'Broken link: {link}'
    assert 'PASS 12/12' in (ROOT / 'production-check.log').read_text(encoding='utf-8')
    print('PASS: protected files, Python syntax, 10 JSON reports, Locust CSV, four screenshots, two firing alerts, trace/log correlation, document links')
    public = load('evidence/public-check.json')
    assert public['base_url'].startswith('https://')
    assert [(c['method'], c['path'], c['authenticated'], c['status']) for c in public['checks']] == [
        ('GET', '/health', False, 200), ('GET', '/ready', False, 200),
        ('POST', '/ask', False, 401), ('POST', '/ask', True, 200)]
    assert all(c['passed'] and c['status'] == c['expected'] for c in public['checks'])
    print('PASS: public HTTP 4/4 and three cloud screenshots; LMS submission remains manual')


if __name__ == '__main__':
    main()
