
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

APPRISE_URL = "http://apprise-api:8000/notify/crossseed"
ICON_URL = "https://i.imgur.com/eDnBPLK.png"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()

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

    torrent_name = extra.get("searchee", {}).get("path", "Unknown Torrent")
    trackers = ", ".join(extra.get("trackers", []))

    body = f"**Torrent:** {torrent_name}\n**Trackers:** {trackers}\n\n{body}"

    payload = {
        "title": title,
        "body": body,
        "icon": ICON_URL
    }

    resp = requests.post(APPRISE_URL, json=payload)
    
    return jsonify({"status": "forwarded", "apprise_response": resp.status_code}), resp.status_code

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
