# Slack Notification

> Đọc và làm theo đúng thứ tự — bỏ qua bước nào sẽ bị lỗi.

---

## Yêu cầu

- Có tài khoản GitHub và repo đã tạo
- Có quyền Admin trên repo
- Có workspace Slack

---

## Bước 1 — Tạo Slack App

**1.1** Vào https://api.slack.com/apps → **Create New App** → **From scratch**

**1.2** Điền thông tin:
```
App Name:   API Dev Bot
Workspace:  chọn workspace của team
```

**1.3** Vào **OAuth & Permissions** → kéo xuống **Bot Token Scopes** → **Add an OAuth Scope**, thêm 2 scope:
```
chat:write
chat:write.public
```

**1.4** Kéo lên đầu trang → **Install to Workspace** → **Allow**

**1.5** Copy **Bot User OAuth Token** — dạng:
```
xoxb-XXXXXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXX
```

> ⚠️ Không share token này lên chat, email, hay bất kỳ chỗ nào công khai.

---

## Bước 2 — Lấy Channel ID

**2.1** Mở Slack → vào channel `#api-dev-log`

**2.2** Click tên channel ở trên cùng → **View channel details**

**2.3** Kéo xuống dưới cùng → copy **Channel ID** — dạng:
```
C0XXXXXXXXX
```

---

## Bước 3 — Invite Bot vào Channel

Trong Slack, vào channel `#api-dev-log` và gõ:
```
/invite @API Dev Bot
```

---

## Bước 4 — Add Secrets vào GitHub

**4.1** Vào GitHub repo → **Settings** → **Secrets and variables** → **Actions**

**4.2** Chọn tab **Secrets** → phần **Repository secrets** → **New repository secret**

Tạo 2 secrets:

| Name               | Value                           |
| ------------------ | ------------------------------- |
| `SLACK_BOT_TOKEN`  | `xoxb-...` vừa copy ở Bước 1    |
| `SLACK_CHANNEL_ID` | `C0XXXXXXXXX` vừa copy ở Bước 2 |

> ⚠️ Phải add vào **Repository secrets**, không phải Environment secrets.

---

## Bước 5 — Merge Workflow vào `main` Trước Khi Code

> Đây là bước hay bị bỏ qua nhất — GitHub chỉ đọc secrets khi workflow file tồn tại trên nhánh default (`main`).

```bash
# Đảm bảo file .github/workflows/validate.yaml đã có
git checkout main
git merge feature/your-branch
git push origin main
```

Kiểm tra workflow đã lên `main` chưa:
```bash
git show main:.github/workflows/validate.yaml | head -5
```

---

## Bước 6 — Kiểm tra Token Hợp Lệ

Chạy lệnh này trong terminal trước khi push code:

```bash
curl -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer xoxb-token-của-bạn"
```

Kết quả hợp lệ:
```json
{"ok": true, "team": "CI/CD", "user": "api_dev_bot", ...}
```

Nếu `"ok": false` → token sai, lấy lại ở Bước 1.

---

## Bước 7 — Test Toàn Bộ

```bash
# Tạo feature branch
git checkout -b feat/schema-test

# Sửa nhẹ 1 file trong components/schemas/
echo "# test" >> components/schemas/_shared/StandardError.yaml

# Commit và push
git add .
git commit -m "test(ci): trigger slack notification"
git push origin feat/schema-test
```

Vào **GitHub → Actions** xem CI có chạy không, và kiểm tra `#api-dev-log` trên Slack có nhận được message không.

---

## Thứ Tự Setup Tóm Tắt

```
1. Tạo Slack App                     → lấy xoxb- token
2. Lấy Channel ID                    → dạng C0XXXXXXXXX
3. Invite bot vào #api-dev-log       → /invite @API Dev Bot
4. Add 2 secrets vào GitHub          → SLACK_BOT_TOKEN, SLACK_CHANNEL_ID
5. Merge workflow vào main           → bắt buộc trước khi code
6. Test token bằng curl              → đảm bảo "ok": true
7. Push code và kiểm tra Slack       → CI chạy → Slack nhận message
```

---

## Lỗi Thường Gặp

| Lỗi                 | Nguyên nhân                     | Fix                                       |
| ------------------- | ------------------------------- | ----------------------------------------- |
| `not_authed`        | Token sai hoặc trống            | Kiểm tra lại secret SLACK_BOT_TOKEN       |
| `Token length: 0`   | Secret chưa được set            | Add lại secret trên GitHub                |
| CI không trigger    | Workflow chưa có trên `main`    | Merge workflow vào main trước             |
| `invalid_auth`      | Token bị revoke hoặc sai format | Lấy token mới từ Slack App                |
| `channel_not_found` | Bot chưa được invite            | Chạy `/invite @API Dev Bot` trong channel |

---

> Sau khi setup xong, mỗi lần push code có thay đổi trong `components/schemas/` thì Slack sẽ tự động nhận thông báo — không cần làm gì thêm.
