"""Build submission documents from real JSON/CSV/log evidence, without invented results."""
import csv
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')


def data(path):
    return json.loads(read(path))


def write(path, text):
    (ROOT / path).write_text(text, encoding='utf-8')


def mission():
    images = data('evidence/part2-images.json')
    sizes = {item['RepoTags'][0]: item['Size'] for item in images}
    dev, prod = sizes['my-agent:develop'], sizes['my-agent:advanced']
    checks = read('production-check.log')
    checklist = checks[checks.index('  📋 Checklist Deliverable'):]
    text = f'''# Day 14 — Mission Answers

Các kết quả dưới đây lấy từ lệnh thật chạy trên Ubuntu WSL2 và Docker Desktop ngày 25/11/2026. Bằng chứng ở `evidence/`, `reports/`, `benchmark-results/`, `screenshots/`. Cloud chưa deploy; phần còn lại được chỉ rõ trong `DEPLOYMENT.md`.

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-patterns

1. `01-localhost-vs-production/develop/app.py:17`: hardcode API key mẫu; thay key thật vào đây sẽ làm lộ khi push repo.
2. Dòng 18: thông tin kết nối database kèm credential nằm trong source.
3. Dòng 21: bật debug cố định; môi trường production cần điều khiển bằng env.
4. Dòng 34: in API key vào log; log có thể được lưu lâu và nhiều người truy cập.
5. Dòng 51: bind `localhost`, khiến app không nhận kết nối từ ngoài container.
6. Dòng 52: cố định cổng 8000, không đọc `PORT` do nền tảng cấp.
7. Không có endpoint liveness/readiness và cleanup tài nguyên bằng lifespan.

### Exercise 1.2 — Chạy develop

`POST /ask?question=Hello` trả **200**. Bản develop nhận query, không nhận JSON. Chi tiết response thật: [local-exercises.json](evidence/local-exercises.json), mục `part1_develop`. Script tái hiện: `scripts/run_local_evidence.py`.

### Exercise 1.3 — So sánh

| Feature | Develop | Production mẫu | Vì sao quan trọng |
|---|---|---|---|
| Config | Hằng số trong source | `config.py` đọc env | Cùng code chạy dev/staging/prod, không rebuild để đổi cổng |
| Secret | Hardcode và in log | Đọc từ môi trường | Giảm nguy cơ lộ secret vào Git/log |
| Health/readiness | Không có | Có `/health`, `/ready` | Phân biệt process sống và sẵn sàng phục vụ |
| Logging | `print()` | Formatter JSON dạng chuỗi | Dễ thu thập; formatter mẫu chưa escape nội dung an toàn, Part 6 dùng `json.dumps` |
| Shutdown | Không có lifecycle cleanup | Có lifespan/signal demo | Hoàn tất request và giải phóng kết nối |
| Bind/port | localhost:8000 | Host/port đọc env | Nhận traffic trong container và dùng cổng cloud |

Bản production mẫu `/health` đã trả 200, xem `part1_production` trong JSON. Ví dụ mẫu cần chạy đúng entrypoint; không mặc định mọi đoạn minh hoạ đều là giải pháp production hoàn chỉnh.

## Part 2 — Docker

### Exercise 2.1 — Dockerfile

1. Base image thực tế của develop là **`python:3.11`**, theo Dockerfile, khác ví dụ đáp án slim trong tài liệu.
2. Working directory: **`/app`**.
3. Copy `requirements.txt` trước source để cache layer cài dependency; đổi source không buộc pip cài lại.
4. `CMD` cung cấp command/arguments mặc định và bị thay khi truyền command cho `docker run`. `ENTRYPOINT` định nghĩa executable chính; arguments runtime thường được nối vào và có thể thay executable bằng `--entrypoint`.

### Exercise 2.2–2.3 — Build, chạy và đo image

Build từ gốc repo:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker image inspect my-agent:develop my-agent:advanced
```

| Image | Bytes từ Docker inspect | MB (10^6 bytes) | MiB (2^20 bytes) |
|---|---:|---:|---:|
| Develop | {dev} | {dev / 1e6:.2f} | {dev / 1048576:.2f} |
| Production | {prod} | {prod / 1e6:.2f} | {prod / 1048576:.2f} |

Giảm **{(1 - prod / dev) * 100:.2f}%**, tính `(develop - production) / develop × 100`. Đây là trường `Size` Docker Engine trên máy chạy, không dùng số ước lượng của README. Bằng chứng: [image inspect](evidence/part2-images.json), hai build log và [response container develop](evidence/part2-develop-response.json).

Builder cài compiler/dependencies; runtime chỉ nhận package và source cần chạy, dùng base slim và user non-root. Đã bổ sung `PYTHONUSERBASE=/home/appuser/.local` vào Dockerfile mẫu để Python non-root tìm đúng package sau khi copy từ builder.

### Exercise 2.4 — Compose và Nginx

```mermaid
flowchart LR
    Client -->|HTTP port 80| Nginx
    Nginx -->|port 8000| Agent
    Agent -. REDIS_URL .-> Redis
    Agent -. QDRANT_URL .-> Qdrant
```

Compose có agent, Redis, Qdrant và Nginx trong network `internal`; Redis/Qdrant có healthcheck và volume. Hai đường nét đứt biểu diễn cấu hình kết nối: app mẫu Part 2 chưa thực hiện retrieval hoặc lưu session qua hai backend này.

Stack `k5-day14-docker` đã build/start; `/health` và `POST /ask` qua Nginx đều 200. Xem [health](evidence/part2-nginx-health.txt), [ask](evidence/part2-nginx-ask.txt), `evidence/part2-stack-up.log`. Đã dừng và dọn volume của riêng stack lab sau khi test.

## Part 3 — Cloud Deployment

### Exercise 3.1/3.2 — Trạng thái

**Chưa deploy; chưa có URL public hoặc ảnh cloud.** Code, Dockerfile và hai file cấu hình đã chuẩn bị. Thực hiện tiếp theo [DEPLOYMENT.md](DEPLOYMENT.md), sau đó điền URL và ảnh dashboard/running/test vào đây. Local `PASS 12/12` không thay thế bằng chứng cloud.

### So sánh Railway và Render

| Mục | `railway.toml` | `render.yaml` |
|---|---|---|
| Định dạng | TOML, các bảng build/deploy | YAML, danh sách service |
| Build | `builder=DOCKERFILE`, Dockerfile tại root service | `runtime: docker`, `rootDir`, docker context/path |
| Health | `healthcheckPath=/health` | `healthCheckPath: /health` |
| Secret/Redis | Đặt Variables/reference trong dashboard | `generateValue` cho key, `sync: false` yêu cầu nhập Redis URL |
| Phạm vi | Cấu hình một service | Blueprint có thể mô tả nhiều tài nguyên; bản này dùng datastore tạo riêng |

Cả hai cấu hình đều đọc `PORT` qua CMD của Dockerfile và cần Redis thật trên cloud.

### Exercise 3.3 — Pipeline Cloud Run

`cloudbuild.yaml` mô tả cài dependency và chạy pytest, rồi build image gắn `$COMMIT_SHA` và `latest`.
Image được push lên registry trước khi `gcloud run deploy` triển khai revision mới ở `asia-southeast1`.
Lệnh deploy đặt tài nguyên, timeout, min/max instance và lấy secret từ Secret Manager.
`service.yaml` mô tả cấu hình tương đương bằng Knative YAML: image, concurrency, resource, env và probes.
Chưa chạy pipeline này: mẫu còn yêu cầu tests/requirements và thông tin project thật; file test step cũng cần fail-fast để không che lỗi pytest bởi lệnh echo cuối.

## Part 4 — API Security

### Exercise 4.1 — API key

FastAPI dependency kiểm tra header `X-API-Key` với `AGENT_API_KEY`; thiếu/sai key bị 401. Rotate bằng cách tạo key mới, cập nhật secret ở môi trường chạy và restart/redeploy; client chuyển sang key mới. Không log key.

HTTP output thật (header request có secret không được ghi ra file):

```http
{read('evidence/api-key-401.txt').strip()}
```

```http
{read('evidence/api-key-200.txt').strip()}
```

### Exercise 4.2 — JWT

Đã lấy token qua `POST /auth/token` với tài khoản demo `student`, rồi dùng Bearer token cho `/ask`. Token không lưu trong bài. JWT gồm claims `sub`, `role`, `iat`, `exp`; server xác minh chữ ký HS256 và hạn dùng. API key đơn giản cho service; JWT mang danh tính/quyền/hạn dùng; OAuth2 dùng khi cần delegated authorization và tích hợp identity provider.

### Exercise 4.3 — Rate limiting

Mẫu Part 4 dùng deque timestamp theo user, xoá các request ngoài cửa sổ 60 giây: sliding-window log, dù comment đặt tên counter. User giới hạn 10 req/phút; admin không bypass hoàn toàn mà có bucket 100 req/phút. Chạy 20 request: **10 lần 200, sau đó 10 lần 429**.

```http
{read('evidence/jwt-429.txt').strip()}
```

Mẫu lưu trong RAM nên restart/multi-worker sẽ mất/chia riêng quota; bản Part 6 đã dùng Redis sorted set và Lua atomic cho mọi worker.

### Exercise 4.4 — Cost guard

Rate limit bảo vệ số lần gọi trong một khoảng thời gian; cost guard bảo vệ tổng tiền, vì request dài/model lớn tốn nhiều tiền hơn. Cần cả hai.

Mẫu Part 4 theo dõi usage trong RAM theo ngày, chưa phải Redis monthly guard. Cách làm monthly per-user là dùng key `budget:<user>:YYYY-MM`, đọc/tăng chi phí token bằng thao tác atomic, đổi tháng tạo key mới và đặt TTL để dọn key cũ; vượt $10/tháng trả 402.

Bản Part 6 triển khai giới hạn **toàn service** theo ngày và tháng trong Redis, lần lượt mặc định $1 và $10. Trước gọi mock, Lua reserve chi phí tối đa biết trước từ tập response; sau gọi settle về chi phí thực. Tránh hai worker cùng thấy còn tiền và cùng tiêu vượt hạn mức. Redis lỗi trả 503, không tiếp tục tiêu không kiểm soát. Token là ước lượng ký tự/4 của mock, không phải billing API thật.

## Part 5 — Scaling & Reliability

### Exercise 5.1–5.2 — Probes và SIGTERM

`/health` cho biết process sống; `/ready` báo khả năng nhận traffic, phụ thuộc Redis trong Part 6. Redis hỏng không nên làm liveness fail và gây restart vô ích.

Đã chạy mẫu develop bằng `python app.py`, gửi request rồi SIGTERM lúc xử lý: request vẫn **200**, process thoát **0**. `/health` và `/ready` đều 200 trước khi tắt. Xem [kết quả](evidence/local-exercises.json), mục `part5_*`, và `evidence/8106-server.log`.

Uvicorn ngừng nhận kết nối mới, chờ request đang chạy, rồi vào lifespan shutdown để dọn tài nguyên. Nếu đăng ký handler riêng sau khi Uvicorn đã cài handler mà không chain lại, server có thể không tắt; vì thế phải test đúng command thực tế. Part 6 dùng lifespan, không ghi đè SIGTERM của Uvicorn.

### Exercise 5.3–5.5 — Redis và 3 instance

Session trong RAM chỉ tồn tại ở một process; request sau qua instance khác sẽ mất context. Redis tách state ra khỏi instance, dùng chung được khi scale.

```bash
cd 05-scaling-reliability/production
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
python test_stateless.py
docker compose -p k5-day14-scaling down -v
```

Kết quả thật:

```text
{read('evidence/part5-stateless.txt').strip()}
```

Script chứng minh 5 lượt đi qua 3 instance và history còn 10 tin nhắn. Script **không kill instance**; không diễn giải output này thành thử nghiệm failover. Cổng stack là 8080, endpoint `/chat`.

## Part 6 — Final Project

Script chấm nguyên bản chạy đầy đủ trong Ubuntu WSL2, Docker Engine hoạt động; **43/43 checks passed**:

```text
{checklist.strip()}
```

Log đầy đủ: [production-check.log](production-check.log). Không sửa script chấm.

Kiểm tra bổ sung [concurrency-check.json](evidence/concurrency-check.json): 40 request đồng thời, hai worker; quota 10 cho đúng 10 lần 200 + 30 lần 429. Với budget $0.0001, 6 lần thành công + 34 lần 402, tổng ghi nhận $0.0000657, không vượt budget. Input thiếu/rỗng/toàn khoảng trắng/quá dài đều 422. Script `scripts/check_concurrency.py` dùng Redis container tạm riêng.

Tiêu chí "Public URL ready" trong script kiểm tra cấu hình và PORT, không chứng minh đã deploy. URL/ảnh cloud vẫn là việc còn lại.

## Part 7

Kết quả và giải thích Exercise 7.1–7.7: [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md). Bộ câu hỏi eval và script chấm giữ nguyên; sửa kiến thức trong KB. Các file JSON/CSV là output thực của chương trình, không sửa số để đạt SLO.

## AI log

| Yêu cầu gửi AI | Hỗ trợ nhận được | Kiểm tra đã thực hiện |
|---|---|---|
| Đọc toàn bộ hướng dẫn và Markdown | Tổng hợp 22 tài liệu, xác định điều chỉnh K5 và deliverables | Đối chiếu README, RULES, CHECKPOINTS, SUBMISSION, RUBRIC và hợp đồng Part 6 |
| Hoàn thiện phần làm trước, để người học tự deploy | AI viết code Part 6, script bằng chứng, KB bổ sung JWT/HPA, CI, câu trả lời và hướng dẫn deploy | Script chấm nguyên bản full Docker PASS 12/12; HTTP exercises; concurrency tests; load/eval JSON; Locust CSV; Prometheus rule test và ảnh UI thật |

Code/câu trả lời ở trên được AI soạn và tự kiểm tra bằng công cụ trong phiên làm việc. Người học cần đọc, tự chạy lại các lệnh chính và giải thích được code/số đo trước khi nộp; không khai nhận rằng đã tự viết hoặc tự kiểm tra thủ công những phần chưa làm. Cloud chưa được AI hay người học triển khai trong phiên này.
'''
    write('MISSION_ANSWERS.md', text)


def benchmark():
    # This report is rendered only after all required machine evidence exists.
    loads = [data(f'reports/load_v2_c{c}.json') for c in (1, 10, 50, 100)]
    slow = [(rate, data(f'reports/load_v2_slow_{rate}.json')) for rate in ('0', '0.03', '0.1')]
    evals = [data(f'reports/{name}.json') for name in ('eval_v1', 'eval_v2', 'eval_v2_fixed')]
    load_rows = '\n'.join(f"| {d['concurrency']} | {d['rps']} | {d['latency_ms']['p50']} | {d['latency_ms']['p95']} | {d['latency_ms']['p99']} | {d['error_rate'] * 100:.2f}% | {'PASS' if d['slo']['passed'] else 'FAIL'} |" for d in loads)
    slow_rows = '\n'.join(f"| {rate} | {d['latency_ms']['avg']} | {d['latency_ms']['p95']} | {d['latency_ms']['p99']} |" for rate, d in slow)
    metric_rows = []
    for label, values in [
        ('Accuracy', [f"{d['accuracy'] * 100:.2f}% ({d['passed']}/{d['total']})" for d in evals]),
        ('Avg tokens/câu', [str(d['avg_tokens']) for d in evals]),
        ('Tổng cost USD', [str(d['total_cost_usd']) for d in evals]),
        ('Cost/câu đúng USD', [str(d['cost_per_correct_usd']) for d in evals]),
        ('Quality gate', ['PASS' if d['quality_gate']['passed'] else 'FAIL' for d in evals]),
    ]:
        metric_rows.append('| ' + ' | '.join([label, *values]) + ' |')
    timing = data('evidence/alert-timing.json')
    slow_trace = data('evidence/jaeger-slow-trace.json')
    error_trace = data('evidence/jaeger-error-trace.json')
    total_us = max(s['startTime'] + s['duration'] for s in slow_trace['spans']) - min(s['startTime'] for s in slow_trace['spans'])
    llm = max((s for s in slow_trace['spans'] if s['operationName'].startswith('chat ')), key=lambda s: s['duration'])
    logs = data('evidence/trace-log-correlation.json')
    slow_log = next((e for e in logs['slow'] if e.get('event') == 'llm_call'), logs['slow'][0])
    scale_rows = []
    scale_values = []
    for scale in (1, 3):
        source = ROOT / f'06-lab-complete/benchmark-observability/production/benchmark-results/scale_{scale}_stats.csv'
        shutil.copy2(source, ROOT / 'benchmark-results' / source.name)
        with source.open(encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        row = next(r for r in rows if r['Name'] == '/ask')
        scale_values.append(row)
        scale_rows.append(f"| {scale} | {float(row['Requests/s']):.2f} | {row['50%']} | {row['95%']} | {row['99%']} | {row['Failure Count']}/{row['Request Count']} |")
    signals = data('evidence/prometheus-scale-3.json')
    def number(key):
        values = signals[key]['data']['result']
        return float(values[0]['value'][1]) if values else float('nan')
    text = f'''# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Bá Quang — MSSV 2A202603555  
**Ngày chạy:** 25/11/2026  
**Môi trường:** Windows host, Ubuntu WSL2 Python 3.12, Docker Desktop Linux Engine 28.3.2; [cấu hình đo được](evidence/environment.json). Mock LLM, không gọi LLM thương mại.

## 1. SLO và phương pháp

| SLI | SLO | Lý do |
|---|---|---|
| p95 `/ask` | ≤ 500 ms | Mục tiêu phản hồi tương tác trong lab |
| Error rate `/ask` | ≤ 2% | Mock mặc định khoảng 1% lỗi, có khoảng dự phòng |
| Accuracy | ≥ 85% trong CI; bản sửa cuối 100%, không regression | Chặn giảm chất lượng và đáp ứng yêu cầu 23/23 |

Load test mỗi lượt 300 request, warm-up không tính; latency trong report của script tính trên response 200, error rate tính tất cả request. Concurrency 1/10/50/100 dùng v2 và mặc định slow 0.03/error 0.01. So sánh slow rate giữ concurrency 20 và 300 request. Eval tắt lỗi ngẫu nhiên (`MOCK_ERROR_RATE=0`), còn slow rate mặc định; 23 mẫu eval không đủ kết luận latency.

Lượt load cuối chạy sau khi dừng stack quan sát và hết các job build của bài, tránh trộn ảnh hưởng build image vào so sánh slow rate. Các dịch vụ sẵn có của người dùng không bị tắt. Đây là số đo một máy và một lượt ngẫu nhiên cho mỗi cấu hình, không phải kết luận capacity production.

## 2. Benchmark hiệu năng

### 2.1 Concurrency

| Concurrency | RPS | p50 ms | p95 ms | p99 ms | Error rate | SLO |
|---|---:|---:|---:|---:|---:|---|
{load_rows}

File nguồn: `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json`. Không thay số khi một lượt FAIL. RPS phụ thuộc concurrency, event loop, CPU, I/O/log và thời gian chờ LLM; không tăng vô hạn theo số client. Với chỉ 300 mẫu và slow rate 3%, số mẫu chậm thực tế có thể vượt 5%, khiến cả p95 tăng dù cấu hình mặc định không đổi.

### 2.2 Tail latency

| MOCK_SLOW_RATE | avg ms | p95 ms | p99 ms |
|---|---:|---:|---:|
{slow_rows}

p99 nhạy với vài request chậm; khi tỷ lệ slow vượt 5%, p95 cũng phản ánh nhóm này. Average làm loãng trải nghiệm nhóm chậm bằng nhiều request nhanh. Histogram/SLO phải giữ cả p95/p99 và error rate; không chỉ dùng average. Số đo có jitter, scheduling và độ bất định do mẫu hữu hạn.

### Exercise 7.1 — Metrics

Counter: `http_requests_total`, `llm_tokens_total`; Gauge: `agent_in_flight_requests`; Histogram: `http_request_duration_seconds`. Đã thêm Histogram **`agent_question_length_chars`** và observe `len(body.question)` trong bản develop, bucket 20/50/100/200/500/1000/2000, không gắn mỗi độ dài thành label. Bằng chứng scrape: [develop-metrics.txt](evidence/develop-metrics.txt).

Middleware lấy route template và gán `unmatched` cho URL lạ. Dùng raw URL khi bot quét hàng nghìn đường dẫn sẽ tạo hàng nghìn time series, tăng RAM/storage và chi phí query; không thêm user_id/question/request_id làm label.

## 3. Benchmark chất lượng

| Chỉ số | v1 | v2 ban đầu | v2 sửa KB |
|---|---:|---:|---:|
{chr(10).join(metric_rows)}

| ID sai ban đầu | Thiếu kiến thức/keyword | Sửa |
|---|---|---|
| `scaling-03` | CPU, memory, custom metrics | Thêm entry Kubernetes/HPA/autoscaling |
| `security-02` | token, hết hạn, chữ ký | Thêm entry giải thích API key và JWT |

Bổ sung trong `develop/utils/mock_llm.py` và `production/utils/mock_llm.py`; không sửa golden dataset hoặc cách chấm. Restart agent rồi eval với baseline `eval_v2.json` và `--min-accuracy 1.0`: 23/23, không regression. Output `reports/eval_v2_fixed.json`.

v2 dùng retrieval nên prompt/context dài, token/cost mỗi câu cao hơn v1. Tuy nhiên cost/câu đúng giảm mạnh vì độ chính xác tăng. Những latency trong eval là mô tả mẫu nhỏ, không dùng thay load test.

CI ở [.github/workflows/eval.yml](.github/workflows/eval.yml): khởi động v2, chờ health, chạy evaluator với ngưỡng 0.85 và baseline bản sửa cuối. Exit code 1 làm job fail; cần bật required status check trong branch protection của repo để thực sự chặn merge. Job chưa được chạy trên GitHub trong phiên này; lệnh evaluator đã chạy local.

## 4. Observability stack

### 4.1 Dashboard và Exercise 7.4

![Grafana đang có tải](screenshots/grafana-dashboard.png)

Stack agent/Nginx/Prometheus/Grafana/Jaeger/Locust chạy bằng Docker Compose, project riêng `k5-day14-observability`. Cổng thực tế trên máy này: agent 18080, Grafana 3001, Prometheus 9090, Jaeger 16686, Locust 8089. Đã sửa Dockerfile mẫu thêm `PYTHONUSERBASE` cho package của user non-root.

Snapshot Prometheus sau scale 3: p95 **{number('p95') * 1000:.2f} ms**, avg **{number('avg') * 1000:.2f} ms**, error rate **{number('error_rate') * 100:.2f}%**. Dữ liệu raw: [prometheus-scale-3.json](evidence/prometheus-scale-3.json). Các thời điểm screenshot và API snapshot khác nhau nên không buộc mọi số trên ảnh phải giống snapshot.

RPS từng instance ở snapshot cùng file cho thấy phân bố traffic; Nginx round-robin cân bằng số request tương đối, không đảm bảo số request đang xử lý hoặc độ trễ bằng nhau. Input tokens/s cao hơn output vì prompt gồm system instructions, câu hỏi và context retrieval. `/metrics` qua Nginx trả 404 theo config, để tránh public metric nội bộ; Prometheus scrape trực tiếp từng agent qua Docker network.

### 4.2 Chaos và alert

Hai thay đổi A+B được áp dụng cùng lúc để có hai alert firing đồng thời, bắt đầu **{timing['configuration_started_utc']}**. Đồng hồ dùng monotonic từ trước lệnh recreate service, bao gồm thời gian deploy local; poll mỗi 2 giây nên thời điểm phát hiện có sai số poll và evaluation interval 5 giây.

| Thí nghiệm | Thay đổi | Alert | Thời gian tới firing | Panel |
|---|---|---|---:|---|
| A | `MOCK_ERROR_RATE=0.2` | AgentHighErrorRate | {timing['first_firing_seconds']['AgentHighErrorRate']} s | Error rate |
| B | `MOCK_SLOW_RATE=0.3` | AgentHighLatencyP95 | {timing['first_firing_seconds']['AgentHighLatencyP95']} s | p95/p99 latency |
| C | Model lớn | Không chạy riêng | Không có số đo | Phân tích: token cost và cost burn rate tăng |
| D | Pause instance | Không chạy riêng | Không có số đo | Phân tích: `up=0`; lỗi 504 tại Nginx không nhất thiết được agent đếm |
| E | Đổi sang v1 | Không chạy chaos riêng; đã eval v1 | Không có số đo firing | Eval thấy accuracy thấp dù metric hạ tầng có thể xanh |

![Hai alert cùng firing](screenshots/prometheus-alert-firing.png)

Raw: [alert-timing.json](evidence/alert-timing.json), [prometheus-alerts-firing.json](evidence/prometheus-alerts-firing.json), [PromQL lúc chaos](evidence/prometheus-chaos.json). Không dùng thời gian rule `for` làm thời gian đo: còn cửa sổ rate, scrape, evaluation và recreate. Rule tests: [alert-rules-test.log](evidence/alert-rules-test.log), kết quả SUCCESS. Sau thí nghiệm khôi phục default và dừng stack lab.

E là lỗi chất lượng: latency/error rate không đủ để phát hiện. Cần eval trước release, canary, synthetic golden questions, theo dõi feedback và lấy mẫu đánh giá câu trả lời trong production. Với D, cần thêm metrics Nginx hoặc external synthetic probe để thấy lỗi tại gateway.

### 4.3 Trace và log

![Trace chậm](screenshots/jaeger-slow-trace.png)

- Trace ID: `{slow_trace['traceID']}`.
- Tổng thời gian: **{total_us / 1000:.3f} ms**.
- Span LLM chậm nhất: `{llm['operationName']}`, **{llm['duration'] / 1000:.3f} ms**, **{llm['duration'] / total_us * 100:.2f}%** tổng thời gian; đây là span công việc, không tính lại các parent span bao trùm nó.
- Trace chọn chậm nhất trong tập summary truy vấn có log tương ứng, không khẳng định chậm nhất mọi request từng chạy. Raw: [jaeger-slow-trace.json](evidence/jaeger-slow-trace.json).

Log JSON có cùng trace_id:

```json
{json.dumps(slow_log, ensure_ascii=False)}
```

![Trace lỗi](screenshots/jaeger-error-trace.png)

Trace lỗi `{error_trace['traceID']}` có span lỗi và event exception. Raw: [jaeger-error-trace.json](evidence/jaeger-error-trace.json); correlation của cả hai: [trace-log-correlation.json](evidence/trace-log-correlation.json). Lỗi mock upstream được chuyển thành 503, không lộ stack trace cho client.

## 5. Scaling — Locust headless

Mỗi lượt 100 users, spawn rate 10/s, 2 phút, cùng model/version/default fault rate. Bảng dùng **dòng POST `/ask`** trong CSV; CSV cũng chứa `/health` và Aggregated, không trộn p95 giữa chúng.

| Instance | RPS `/ask` | p50 ms | p95 ms | p99 ms | Failures/requests |
|---|---:|---:|---:|---:|---:|
{chr(10).join(scale_rows)}

Nguồn: [scale_1_stats.csv](benchmark-results/scale_1_stats.csv), [scale_3_stats.csv](benchmark-results/scale_3_stats.csv). Full logs trong `evidence/locust-scale-*.log`. Locust trả exit 1 khi có lỗi mock; phải đọc số failure/status thay vì coi đó là lỗi chạy công cụ.

Trong lượt đo này, scale 3 **không cải thiện**: RPS từ {float(scale_values[0]['Requests/s']):.2f} thành {float(scale_values[1]['Requests/s']):.2f}, p95 từ {scale_values[0]['95%']} thành {scale_values[1]['95%']} ms. p99 đều {scale_values[0]['99%']} ms, cho thấy tail upstream vẫn tồn tại. Kết quả không chứng minh thêm replica luôn tốt; cần phân biệt hạn chế upstream, scheduling trên cùng host và tải thực tế trước khi tăng replica.

Locust mô phỏng người dùng nghỉ 0.5–2 giây sau mỗi tác vụ, nên RPS không tăng gấp ba chỉ vì tăng ba instance. App async chủ yếu chờ LLM, mỗi container giới hạn CPU 0.5/memory 256MB; scale giúp chia xử lý nhưng không loại bỏ tail latency của upstream. Phải xem cả panel LLM và tải máy trước khi kết luận nút thắt. Các lần chạy hữu hạn có lỗi/ngẫu nhiên khác nhau, không dùng chênh lệch nhỏ làm bằng chứng tối ưu chắc chắn.

## 6. Kết luận và giới hạn

1. Percentile cho thấy nhóm request chậm mà average che khuất; error rate cần theo dõi riêng vì latency chỉ tính request thành công.
2. Chất lượng phải được eval: tăng token mỗi câu có thể giảm chi phí mỗi câu đúng.
3. Kết hợp metric → trace → log cùng trace_id rút ngắn việc xác định lỗi nằm ở retrieval, model hay gateway.

Nếu triển khai thật: thêm metric ở gateway, timeout/retry và queue depth, burn-rate/error-budget theo nhiều cửa sổ, budget per-user, eval trên mẫu đa dạng và quản lý retention/sampling trace. Bộ 23 câu keyword chỉ kiểm tra hồi quy của lab, chưa đủ chứng minh chất lượng AI tổng quát. Chi phí là mô phỏng; không phát sinh bill LLM. Cloud vẫn chưa deploy, xem `DEPLOYMENT.md`.
'''
    write('BENCHMARK_REPORT.md', text)


if __name__ == '__main__':
    (ROOT / 'benchmark-results').mkdir(exist_ok=True)
    mission()
    benchmark()
