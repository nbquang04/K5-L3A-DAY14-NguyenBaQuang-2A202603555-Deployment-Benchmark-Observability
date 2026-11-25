"""Record only non-sensitive machine/runtime facts used to interpret benchmarks."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import psutil

root = Path(__file__).resolve().parents[1]
info = json.loads(subprocess.check_output(['docker', 'info', '--format', '{{json .}}'], text=True))
result = {
    'platform': platform.platform(),
    'python': sys.version.split()[0],
    'os_name': os.name,
    'logical_cpus_wsl': os.cpu_count(),
    'wsl_memory_total_bytes': psutil.virtual_memory().total,
    'docker_server_version': info['ServerVersion'],
    'docker_cpus': info['NCPU'],
    'docker_memory_total_bytes': info['MemTotal'],
    'agent_cpu_limit_each': 0.5,
    'agent_memory_limit_each_bytes': 256 * 1024 * 1024,
}
(root / 'evidence/environment.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
