# 🧩 cross-seed-proxy (Ultra Minimal Apprise Webhook Proxy)

This is a super lightweight Flask-based webhook forwarder for qbitmanage and cross-seed notifications.
No `.env`, no API keys, no metrics — just clean, Apprise-compatible alerts.

---

## ✅ How to Use

1. Make sure [Apprise](https://github.com/caronc/apprise) is running:
   ```
   http://apprise-api:8000/notify/crossseed
   ```

2. Start the container:

```bash
docker-compose up -d
```

---

## 🔧 Webhook Routes

- **POST /qbitmanage** — Handles qbitmanage hooks
- **POST /webhook** — Handles cross-seed events

---

## 🧪 Test Locally

### qbitmanage:

```bash
curl -X POST http://localhost:5000/qbitmanage \
  -H "Content-Type: application/json" \
  -d '{
    "function": "cleanup_dirs",
    "result": "Success",
    "summary": "Removed 3 empty folders."
  }'
```

### cross-seed:

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "extra": {
      "event": "download",
      "result": "SUCCESS",
      "name": "Test.Show.S01E01.1080p.WEB",
      "trackers": ["tracker.example.org"]
    }
  }'
```

---

## 🎯 Features

- 🧹 qbitmanage gets 1 emoji (`🧹`)
- 🎯 cross-seed gets 1 emoji (`🎯`)
- No auth, no .env, no config
- Minimal dependencies, logs to console + rotating files
- Works with anything Apprise supports

---

MIT License | Built for clarity and speed.
