# Deployment — phần bạn thực hiện trên tài khoản cloud

**Trạng thái: chưa deploy. Chưa có URL public hoặc ảnh cloud.** Code Part 6 đã chuẩn bị trong `06-lab-complete/`; không deploy thư mục app mẫu Part 3 hoặc app benchmark Part 7.

## Cách 1: Railway

1. Kiểm tra thay đổi, commit và push bài lên repo GitHub cá nhân. Repo phải Public để Lab Coach mở được. Không đưa `.env` hoặc token vào commit.
2. Đăng nhập Railway, tạo project mới và chọn **Deploy from GitHub repo**, chọn repo bài này.
3. Trong service agent, đặt **Root Directory** là `/06-lab-complete`. File Dockerfile và `railway.toml` đều ở đây. Nếu dùng trường Config File Path tính từ gốc repo, chọn `/06-lab-complete/railway.toml`. Không để service build Dockerfile ở gốc repo.
4. Trong cùng project, thêm database **Redis**. Đợi Redis sẵn sàng.
5. Trong Variables của service agent, thêm:

   | Biến | Giá trị |
   |---|---|
   | `AGENT_API_KEY` | Chuỗi ngẫu nhiên tự tạo, giữ riêng |
   | `REDIS_URL` | Reference tới `REDIS_URL` của service Redis, thường là `${{Redis.REDIS_URL}}`; tên phải khớp service thực tế |
   | `ENVIRONMENT` | `production` |
   | `RATE_LIMIT_PER_MINUTE` | `10` |
   | `DAILY_BUDGET_USD` | `1` |
   | `MONTHLY_BUDGET_USD` | `10` |
   | `LOG_LEVEL` | `INFO` |

   Để nền tảng cấp `PORT`; Dockerfile tự đọc biến này. Không đặt `REDIS_URL=localhost` vì Redis chạy ở service khác.
6. Deploy/redeploy agent. Logs phải có JSON `startup`; healthcheck `/health` thành công.
7. Vào Networking → Generate Domain để lấy URL HTTPS. Chạy kiểm tra ở mục bên dưới.

Cách tạo key trong terminal của bạn: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Chỉ dán vào Variables; không chụp key trong screenshot.

Root directory và Docker build dựa trên [Railway monorepo docs](https://docs.railway.com/deployments/monorepo) và [Dockerfile docs](https://docs.railway.com/builds/dockerfiles).

## Cách 2: Render

1. Trên Render, tạo **Key Value** tương thích Redis, cùng region với web service. Lấy **Internal URL**, giữ riêng.
2. New → Blueprint → kết nối repo. Blueprint Path: `06-lab-complete/render.yaml`.
3. Blueprint đã đặt `rootDir: 06-lab-complete`, `dockerfilePath: ./Dockerfile`, `dockerContext: .` và healthcheck `/health`. Đây là đường dẫn tương đối với root directory của service.
4. Điền `REDIS_URL` bằng Internal URL vừa lấy. `AGENT_API_KEY` dùng `generateValue: true`; xem giá trị trên trang Environment khi cần test và giữ riêng.
5. Kiểm tra gói dịch vụ hiển thị trên tài khoản trước khi tạo. Nếu hệ thống yêu cầu thanh toán ngoài ý muốn, dừng và hỏi Lab Coach.
6. Deploy, lấy URL `https://...onrender.com`, kiểm tra `/ready` chứ không chỉ `/health`.

Key Value được tạo riêng có chủ đích; Blueprint không tự tạo datastore. Cấu hình tham chiếu [Render monorepo](https://render.com/docs/monorepo-support) và [Blueprint specification](https://render.com/docs/blueprint-spec). Gói Key Value miễn phí có thể bị restart và mất dữ liệu, theo [Render free services](https://render.com/docs/free); đây là giới hạn môi trường demo.

## Kiểm tra sau deploy

Từ **gốc repo**, chạy bằng Python (script chỉ dùng thư viện chuẩn):

```bash
python scripts/check_public.py https://DOMAIN-CUA-BAN
```

Script hỏi key bằng ô nhập ẩn nếu chưa có biến `AGENT_API_KEY`, không in key và lưu `evidence/public-check.json`. Kết quả đúng:

```text
GET /health key=False: 200 (expected 200)
GET /ready key=False: 200 (expected 200)
POST /ask key=False: 401 (expected 401)
POST /ask key=True: 200 (expected 200)
```

Nếu `/ready` trả 503: xem Redis có đang chạy, kiểm tra reference `REDIS_URL`, region và private network. Nếu `/ask` có key trả 401: nhập lại đúng key ở service agent. Nếu 429: chờ 60 giây rồi chạy lại.

Có thể chạy thêm script chấm trên WSL trong `06-lab-complete/`:

```bash
export AGENT_API_KEY='KEY-CHI-GIU-TRONG-TERMINAL'
python check_production_ready.py --public-url https://DOMAIN-CUA-BAN
```

## Điền thông tin để nộp

- **Public URL:** chưa có — điền sau khi deploy thật.
- **Platform:** chọn Railway hoặc Render sau khi tạo service.
- **Environment:** ghi tên các biến đã đặt, không ghi giá trị secret.
- [ ] `screenshots/dashboard.png`: trang project/deployment, che secret.
- [ ] `screenshots/running.png`: service live và healthcheck thành công.
- [ ] `screenshots/test.png`: bốn mã HTTP ở trên.
- [ ] Điền URL và link ảnh vào Part 3 trong `MISSION_ANSWERS.md`.
- [ ] Kiểm tra repo Public, push commit cuối và nộp link repo trên LMS.

Ảnh Grafana/Jaeger/Prometheus là bằng chứng local Part 7; không thay thế ba ảnh cloud này.
