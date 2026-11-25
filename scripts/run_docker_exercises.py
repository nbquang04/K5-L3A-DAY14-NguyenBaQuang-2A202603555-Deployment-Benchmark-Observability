"""Build Part 2 images, test Nginx and verify the Part 5 shared session."""
import json
from pathlib import Path
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence'
OUT.mkdir(exist_ok=True)


def run(args, name, cwd=ROOT, check=True):
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (OUT / name).write_text(result.stdout, encoding='utf-8')
    print(name, result.returncode, flush=True)
    if check and result.returncode:
        raise RuntimeError(result.stdout[-2000:])
    return result


def wait(url):
    for _ in range(120):
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                return r
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError('Not ready: ' + url)


def main():
    for kind, tag in [('develop', 'my-agent:develop'), ('production', 'my-agent:advanced')]:
        run(['docker', 'build', '-f', f'02-docker/{kind}/Dockerfile', '-t', tag, '.'], f'part2-build-{kind}.log')
    run(['docker', 'image', 'inspect', 'my-agent:develop', 'my-agent:advanced'], 'part2-images.json')
    name = 'k5-day14-basic-evidence'
    run(['docker', 'rm', '-f', name], 'part2-previous-container.log', check=False)
    run(['docker', 'run', '-d', '--name', name, '-p', '127.0.0.1::8000', 'my-agent:develop'], 'part2-run.log')
    try:
        port = subprocess.check_output(['docker', 'port', name, '8000/tcp'], text=True).strip().rsplit(':', 1)[1]
        wait(f'http://127.0.0.1:{port}/')
        r = httpx.post(f'http://127.0.0.1:{port}/ask', params={'question': 'What is Docker?'})
        (OUT / 'part2-develop-response.json').write_text(json.dumps({'status': r.status_code, 'body': r.json()}, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        run(['docker', 'rm', '-f', name], 'part2-stop.log')
    folder = ROOT / '02-docker/production'
    (folder / '.env.local').touch(exist_ok=True)
    compose = ['docker', 'compose', '-p', 'k5-day14-docker']
    try:
        run([*compose, 'up', '-d', '--build'], 'part2-stack-up.log', folder)
        wait('http://127.0.0.1/health')
        run(['curl', '-sS', '-i', 'http://127.0.0.1/health'], 'part2-nginx-health.txt')
        run(['curl', '-sS', '-i', '-X', 'POST', 'http://127.0.0.1/ask', '-H', 'Content-Type: application/json', '-d', '{"question":"Explain microservices"}'], 'part2-nginx-ask.txt')
    finally:
        run([*compose, 'down', '-v'], 'part2-stack-down.log', folder, check=False)
    folder = ROOT / '05-scaling-reliability/production'
    (folder / '.env.local').touch(exist_ok=True)
    compose = ['docker', 'compose', '-p', 'k5-day14-scaling']
    # Keep observability on another host port while this exercise uses 8080.
    try:
        run([*compose, 'up', '-d', '--build', '--scale', 'agent=3'], 'part5-stack-up.log', folder)
        wait('http://127.0.0.1:8080/health')
        run([sys.executable, 'test_stateless.py'], 'part5-stateless.txt', folder)
        run([*compose, 'logs', '--no-color', 'agent'], 'part5-agents.log', folder)
    finally:
        run([*compose, 'down', '-v'], 'part5-stack-down.log', folder, check=False)


if __name__ == '__main__':
    main()
