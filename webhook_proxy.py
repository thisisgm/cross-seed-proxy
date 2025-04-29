from flask import Flask, request, jsonify
import requests
import logging
import os
from time import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("proxy.log"),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

APPRISE_URL = os.getenv("APPRISE_URL", "http://apprise-api:8000/notify/crossseed")
ICON_URL = os.getenv("ICON_URL", "https://raw.githubusercontent.com/cross-seed/cross-seed.org/master/static/img/cross-seed.png")

last_request_time = 0

@app.before_request
def limit_remote_addr():
    global last_request_time
    now = time()
    if now - last_request_time < 0.2:
        return jsonify({"error": "Too many requests"}), 429
    last_request_time = now

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON"}), 400
    logging.info(f"Received webhook: {data}")

    # Default fallback values
    title = "🎯 cross-seed match injected!"
    body = "**Status:** ✅ injection successful"
    
    # Check if extra.result exists
    extra = data.get("extra", {})
    result = extra.get("result", "SUCCESS")

    if result == "FAILURE":
        title = "❌ cross-seed injection failed!"
        body = "**Status:** ❌ injection failed\n🔴 **action needed:** manual check recommended."
    elif result == "SAVED":
        title = "💾 cross-seed torrent saved!"
        body = "**Status:** 💾 torrent saved for manual review."

    torrent_name = (
        extra.get("name")
        or extra.get("searchee", {}).get("path")
        or (extra.get("infoHashes", [None])[0])
        or "Unknown Torrent"
    )
    trackers = ", ".join(extra.get("trackers", []))

    body = f"**Torrent:** {torrent_name}\n**Trackers:** {trackers}\n\n{body}"

    color_code = 3066993  # Default green
    if result == "FAILURE":
        color_code = 15158332  # Red
    elif result == "SAVED":
        color_code = 10197915  # Blue

    payload = {
        "embeds": [
            {
                "title": title,
                "description": body,
                "color": color_code,
                "thumbnail": {
                    "url": ICON_URL
                }
            }
        ]
    }

    try:
        resp = requests.post(APPRISE_URL, json=payload, timeout=5)
        status_code = resp.status_code
    except requests.RequestException as e:
        logging.error(f"Failed to send notification: {e}")
        status_code = 500
    
    return jsonify({"status": "forwarded", "apprise_response": status_code}), status_code

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
