# Railway deployment — Part 6

**Đã deploy và kiểm tra public ngày 25/11/2026.**

- **Public URL:** https://k5-l3a-day14-nguyenbaquang-2a202603555-deploymen-production.up.railway.app
- **Platform:** Railway; project `zoological-tranquility`, environment `production`.
- **Source:** branch `main`, app trong `06-lab-complete/`, commit code `ceab8258f2c18595fe4a399a1fd2e28ac69b02a1`.
- [Dashboard](screenshots/dashboard.png) · [Running](screenshots/running.png) · [Test](screenshots/test.png).
- [JSON kết quả HTTP thật](evidence/public-check.json). Ảnh test hiển thị JSON này, không phải giao diện Railway.

## Cấu hình đã dùng

Root Directory `/06-lab-complete`, builder Dockerfile, Dockerfile path `/06-lab-complete/Dockerfile`, healthcheck `/health`, public domain target port `8000`. Dùng CMD trong Dockerfile, không cần Custom Start Command. Railway UI thông báo Config as Code deprecated và service mới không thể opt in; đã cấu hình qua dashboard. `railway.toml` vẫn giữ cho bài lab.

Redis nằm **cùng project và environment** với app, dùng private network, không cần expose Redis public.

| Biến service app | Giá trị |
|---|---|
| `AGENT_API_KEY` | Secret xác thực ứng dụng, không ghi vào repo |
| `REDIS_URL` | Reference `${{Redis.REDIS_URL}}` |
| `PORT` | `8000` |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1` |
| `MONTHLY_BUDGET_USD` | `10` |
| `LOG_LEVEL` | `INFO` |

`AGENT_API_KEY` tự tạo, gửi qua header `X-API-Key`. Không phải key OpenAI/Gemini. App dùng mock LLM cho benchmark, không gọi model trả phí. Không lưu giá trị key hay Redis URL vào báo cáo.

## Kiểm tra thực tế

| Request | Key | HTTP | Kết quả |
|---|---|---|---|
| GET `/health` | Không | 200 | PASS |
| GET `/ready` | Không | 200 | PASS |
| POST `/ask` | Không | 401 | PASS |
| POST `/ask` | Đúng | 200 | PASS |

Chạy lại từ gốc repo:

```bash
python scripts/check_public.py https://k5-l3a-day14-nguyenbaquang-2a202603555-deploymen-production.up.railway.app
```

Script hỏi key bằng ô nhập ẩn hoặc đọc biến môi trường `AGENT_API_KEY`; không in key. `/docs` có Authorize; body mẫu POST `/ask`: `{"question":"Docker là gì?"}`. Không có endpoint `/v1/ask`.

## Các lỗi đã xử lý

- Redis ban đầu ở project khác: tạo Redis trong project chứa app, thêm reference.
- Redis URL scheme invalid: ô giá trị chỉ chứa reference, không thêm `REDIS_URL=` hoặc dấu ngoặc kép.
- API 401 sau đổi key: thay đổi còn staged chưa Apply. Đã Apply, deployment Active và gọi có key trả 200.

## Bàn giao

Ba ảnh cloud và bốn ảnh observability local có trong `screenshots/`. Local grader nguyên bản PASS 12/12 (43/43 checks); kiểm tra public là bằng chứng riêng. GitHub Actions eval đã [chạy thành công](https://github.com/nbquang04/K5-L3A-DAY14-NguyenBaQuang-2A202603555-Deployment-Benchmark-Observability/actions/runs/45592822160).

Repo cần giữ Public và nộp link lên LMS. Chưa thao tác nộp LMS. URL phụ thuộc vòng đời dịch vụ Railway trial.
