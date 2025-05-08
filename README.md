# cross-seed-proxy

A lightweight Flask-based webhook proxy for use with qbitmanage and cross-seed. Sends simple, readable notifications via Apprise.

## 🚀 Quick Start

### With Docker Compose

```bash
docker-compose up -d
```

### With Docker

```bash
docker run -d -p 5000:5000 --name cross-seed-proxy thisisgm/cross-seed-proxy:latest
```

## ✅ Test Webhook (qbitmanage)

```bash
curl -X POST http://localhost:5000/qbitmanage \
  -H "Content-Type: application/json" \
  -d '{
    "function": "cleanup_dirs",
    "result": "Success",
    "summary": "Removed 3 empty folders."
  }'
```

## 📡 Routes

- `/qbitmanage`: Handles qbitmanage webhooks
- `/webhook`: Handles cross-seed webhooks
- `/metrics`: JSON stats
- `/metrics/prometheus`: Prometheus-formatted metrics
- `/health`, `/ready`, `/startup`: Docker/Kubernetes health endpoints
- `/debug`: App status, startup time, and recent activity

## 🔧 Configuration

No `.env` file or API key needed — this is plug-and-play.

Make sure [Apprise](https://github.com/caronc/apprise) is running at:
```
http://apprise-api:8000/notify/crossseed
```

## 📦 Build (optional)

```bash
docker build -t thisisgm/cross-seed-proxy:latest .
```

## 📜 License

MIT
