"""Reconcile submission prose with the saved public verification evidence."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = json.loads((ROOT / 'evidence/public-check.json').read_text())
    assert len(result['checks']) == 4 and all(c['passed'] for c in result['checks'])
    url = result['base_url']
    ci = 'https://github.com/nbquang04/K5-L3A-DAY14-NguyenBaQuang-2A202603555-Deployment-Benchmark-Observability/actions/runs/45592822160'
    changes = {
        'Cloud chưa deploy; phần còn lại được chỉ rõ trong `DEPLOYMENT.md`.': f'Cloud đã deploy Railway: [{url}]({url}). Kết quả thật ở [public-check.json](evidence/public-check.json).',
        '**Chưa deploy; chưa có URL public hoặc ảnh cloud.** Code, Dockerfile và hai file cấu hình đã chuẩn bị. Thực hiện tiếp theo [DEPLOYMENT.md](DEPLOYMENT.md), sau đó điền URL và ảnh dashboard/running/test vào đây. Local `PASS 12/12` không thay thế bằng chứng cloud.': f'**Đã deploy Part 6 trên Railway**, project `zoological-tranquility`, environment `production`, cùng Redis private. Public URL: [{url}]({url}). Kiểm tra thật: GET `/health` 200, GET `/ready` 200, POST `/ask` thiếu key 401, có key 200. [JSON](evidence/public-check.json) · [Dashboard](screenshots/dashboard.png) · [Running](screenshots/running.png) · [Test](screenshots/test.png). API dùng mock LLM; `AGENT_API_KEY` xác thực ứng dụng. Xem [DEPLOYMENT.md](DEPLOYMENT.md).',
        'URL/ảnh cloud vẫn là việc còn lại.': 'URL và ảnh cloud được kiểm tra riêng ở Part 3.',
        'Cloud chưa được AI hay người học triển khai trong phiên này.': 'Người học thao tác deploy Railway, tạo Redis và cấu hình biến theo hướng dẫn AI; AI kiểm tra HTTP public, áp dụng thay đổi key còn staged và lưu minh chứng. Không đưa secret vào bài nộp.',
        'Job chưa được chạy trên GitHub trong phiên này; lệnh evaluator đã chạy local.': f'GitHub Actions đã chạy thành công: [eval run]({ci}); evaluator cũng đã chạy local.',
        'Cloud vẫn chưa deploy, xem `DEPLOYMENT.md`.': 'Cloud Part 6 đã deploy Railway và qua bốn kiểm tra HTTP; xem `DEPLOYMENT.md`.',
        'Chưa có deployment cloud; không dùng URL local làm URL public.': f'Public Railway: [{url}]({url}); health/ready và API authentication đã kiểm tra thành công.',
        '[Hướng dẫn deploy tiếp](DEPLOYMENT.md)': '[Deployment và kiểm tra public](DEPLOYMENT.md)',
    }
    for name in ('MISSION_ANSWERS.md', 'BENCHMARK_REPORT.md', 'README.md', 'scripts/build_submission.py'):
        path = ROOT / name
        text = path.read_text(encoding='utf-8')
        for old, new in changes.items():
            text = text.replace(old, new)
        path.write_text(text, encoding='utf-8')
    rows = ''.join(f'<tr><td>{c["method"]} {c["path"]}</td><td>{"Present" if c["authenticated"] else "Absent"}</td><td>{c["status"]}</td><td>{c["expected"]}</td><td>PASS</td></tr>' for c in result['checks'])
    page = '<!doctype html><meta charset="utf-8"><title>Public deployment verification</title><style>body{font:24px system-ui;padding:50px;color:#17212b}table{border-collapse:collapse;margin-top:35px;width:100%}td,th{padding:20px;border:1px solid #ccd5db;text-align:left}th{background:#edf7f1}code{font-size:18px}p{line-height:1.6}</style><h1>Railway public HTTP verification — PASS 4/4</h1><p>Actual HTTP requests from scripts/check_public.py<br>Evidence: evidence/public-check.json</p><code>' + html.escape(url) + '</code><table><tr><th>Request</th><th>API key</th><th>Actual</th><th>Expected</th><th>Result</th></tr>' + rows + '</table><p>Application key and Redis credentials are omitted.<br>This page renders recorded HTTP results; it is not a Railway dashboard.</p>'
    (ROOT / 'evidence/public-check.html').write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
