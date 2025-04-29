
# cross-seed-proxy

🎯 A lightweight Python webhook middleware that prettifies [cross-seed](https://github.com/cross-seed/cross-seed) notifications and sends them to [Apprise](https://github.com/caronc/apprise) for delivery to Discord or other platforms.

This proxy formats raw `cross-seed` webhook data into clean, branded markdown alerts — including emojis, torrent name, tracker info, and result status.

---

## 📦 Features

- ✅ Auto-formats success (`INJECTED`), save (`SAVED`), and failure (`FAILURE`) results
- 🎯 Consistent lowercase `cross-seed` branding
- 🖼️ Custom logo support via direct image URL
- 💬 Sends clean Discord-friendly markdown
- 🐳 Dockerized, lightweight, and self-contained
- 🧪 Includes test scripts to simulate events manually

---

## 🔧 How It Works

```
cross-seed ➜ cross-seed-proxy ➜ Apprise ➜ Discord
```

1. `cross-seed` sends a webhook to this proxy  
2. Proxy formats a human-readable message  
3. Proxy forwards it to your Apprise server  
4. Apprise delivers it to your Discord webhook (or any other notifier)

---

## 🐳 Docker Deployment

### 1. Requirements

- Docker & Docker Compose installed  
- `crossseed_network` (or another shared network) must exist  
- Apprise container must be running and reachable via Docker internal hostname (e.g. `apprise-api`)

---

### 2. Deployment

Extract the repo to your Unraid or Linux host:

```bash
docker-compose up -d
```

This will:
- Build and launch `cross-seed-proxy`
- Expose it on port `5000`
- Set timezone and permissions
- Connect it to your `crossseed_network`

---

## ⚙️ Docker Compose Example

```yaml
services:
  cross-seed-proxy:
    build: .
    container_name: cross-seed-proxy
    ports:
      - "5000:5000"
    environment:
      - PUID=1000
      - PGID=1000
      - UMASK=002
      - TZ=Etc/UTC
    restart: unless-stopped
    networks:
      - crossseed_network

networks:
  crossseed_network:
    external: true
```

---

## 🧩 cross-seed Configuration

In your `config.js`, set the `notificationWebhookUrls` like this:

```js
notificationWebhookUrls: [
  "http://cross-seed-proxy:5000/webhook"
],
```

Then restart the cross-seed container.

---

## 🧪 Test It Manually

Run these scripts to simulate messages:

```bash
./test-success.sh     # ✅ Simulates a successful injection
./test-failure.sh     # ❌ Simulates a failure notification
```

These scripts send mock payloads directly to your proxy.

---

## 🖼️ Customization

To change the icon/logo, update this line in `webhook_proxy.py`:

```python
ICON_URL = "https://i.imgur.com/eDnBPLK.png"
```

You can host your own logo or use Imgur/CDN for a direct PNG/JPG.

---

## 🙌 Credits

- [cross-seed](https://github.com/cross-seed/cross-seed)
- [Apprise](https://github.com/caronc/apprise)
- [Flask](https://flask.palletsprojects.com/)
- Inspired by real-world deployment needs

---

## 🪪 License

This project is licensed under the MIT License — see [LICENSE](./LICENSE) for details.
