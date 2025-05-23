from flask import Flask, request, jsonify, Response, g
import requests
import logging
from logging.handlers import RotatingFileHandler
import os
from time import time, sleep
from datetime import datetime
from functools import wraps
import uuid
import json


# --- Logging setup function ---
def setup_logging():
    class RequestIDFilter(logging.Filter):
        def filter(self, record):
            try:
                from flask import g
                record.request_id = getattr(g, 'request_id', 'N/A')
            except Exception:
                record.request_id = 'N/A'
            return True

    file_handler = RotatingFileHandler("proxy.log", maxBytes=5 * 1024 * 1024, backupCount=3)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s]: %(message)s"))
    file_handler.addFilter(RequestIDFilter())

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s]: %(message)s"))
    stream_handler.addFilter(RequestIDFilter())

    class JsonLogFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "request_id": getattr(record, "request_id", "N/A"),
                "message": record.getMessage()
            }
            # Include any extra attributes in the log record
            for key, value in record.__dict__.items():
                if key not in ("levelname", "msg", "args", "levelno", "pathname", "filename", "module",
                               "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created",
                               "msecs", "relativeCreated", "thread", "threadName", "processName", "process",
                               "request_id"):
                    log_record[key] = value
            return json.dumps(log_record)

    json_handler = RotatingFileHandler("proxy.json.log", maxBytes=5 * 1024 * 1024, backupCount=3)
    json_handler.setLevel(logging.INFO)
    json_handler.setFormatter(JsonLogFormatter())
    json_handler.addFilter(RequestIDFilter())

    # Only reconfigure logging if not already configured by .env loading above
    if not logging.getLogger().handlers or len(logging.getLogger().handlers) == 1:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(request_id)s]: %(message)s",
            handlers=[
                file_handler,
                stream_handler,
                json_handler
            ]
        )


# --- Call logging setup after dotenv loading, before anything else ---
setup_logging()


app = Flask(__name__)

APPRISE_URL = "http://apprise-api:8000/notify/crossseed"

FUNCTION_META = {
    "run_start": {"emoji": "🏁", "color": 3447003},
    "run_end": {"emoji": "🏁", "color": 3447003},
    "upload": {"emoji": "📤", "color": 10197915},
    "check": {"emoji": "🔍", "color": 15844367},
    "default": {"emoji": "🎯", "color": 3066993},
    "cleanup_dirs": {"emoji": "🧹", "color": 3066993},
}

SUMMARY_LOOKUP = {
    "SUCCESS": "Injection completed successfully.",
    "FAILURE": "Manual action required to resolve injection failure.",
    "SAVED": "Torrent saved for manual review.",
    "UNKNOWN": "Event status unknown.",
}


def send_discord_notification(title: str, description: str, emoji: str, color: int, log_data: dict):
    title_with_emoji = f"{emoji} {title}"
    payload = {
        "title": title_with_emoji,
        "body": description
    }

    log_data["request_id"] = g.request_id
    logging.info(log_data)

    backoffs = [1, 2, 4]
    status_code = 500
    for attempt in range(3):
        try:
            resp = requests.post(APPRISE_URL, json=payload, timeout=5)
            status_code = resp.status_code
            if 200 <= status_code < 300:
                logging.info(f"Apprise response status code: {status_code} on attempt {attempt + 1}", extra={"request_id": g.request_id})
                break
            else:
                logging.warning(f"Apprise returned status code {status_code} on attempt {attempt + 1}", extra={"request_id": g.request_id})
        except requests.RequestException as e:
            logging.error(f"Failed to send notification on attempt {attempt + 1}: {e}", extra={"request_id": g.request_id})
        if attempt < 2:
            sleep(backoffs[attempt])
    else:
        logging.error(f"Failed to send notification after 3 attempts, final status code: {status_code}", extra={"request_id": g.request_id})

    return status_code

@app.before_request
def before_request():
    g.request_id = str(uuid.uuid4())
    g.start_time = time()

@app.after_request
def after_request(response):
    duration = time() - g.start_time
    logging.info(f"Request to {request.path} took {duration:.4f} seconds", extra={"request_id": g.request_id})
    # Add request_id header to response for traceability
    response.headers["X-Request-ID"] = g.request_id
    return response

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON", "request_id": g.request_id}), 400

    event_type = data.get("extra", {}).get("event", "UNKNOWN")

    # Allow TEST events to pass without needing full fields
    if event_type == "TEST":
        logging.info(
            f"Received TEST event at {datetime.utcnow().isoformat()}",
            extra={"request_id": g.request_id}
        )
        return jsonify({"status": "test received", "request_id": g.request_id}), 200

    extra = data.get("extra", {})
    result = extra.get("result", "UNKNOWN")

    title = "cross-seed match injected!"
    color_code = 3066993  # Default green

    if result == "FAILURE":
        title = "cross-seed injection failed!"
        color_code = 15158332  # Red
    elif result == "SAVED":
        title = "cross-seed torrent saved!"
        color_code = 10197915  # Blue
    elif result == "UNKNOWN":
        title = "cross-seed injection status unknown"
        color_code = 9807270  # Greyish

    summary = SUMMARY_LOOKUP.get(result, "No additional information available.")

    torrent_name = (
        extra.get("name")
        or extra.get("searchee", {}).get("path")
        or (extra.get("infoHashes", [None])[0])
        or "Unknown Torrent"
    )
    trackers = ", ".join(extra.get("trackers", [])) or "None"

    emoji = FUNCTION_META.get(event_type, FUNCTION_META['default'])['emoji']

    body = (
        f"**Torrent:** {torrent_name}\n"
        f"**Trackers:** {trackers}\n\n"
        f"**Status:** ✅ {result}"
    )

    log_data = {
        "event": "cross-seed_webhook",
        "result": result,
        "torrent": torrent_name,
        "trackers": trackers,
        "color": color_code,
        "emoji": emoji,
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": g.request_id
    }

    status_code = send_discord_notification(title, body, emoji, color_code, log_data)
    
    return jsonify({"status": "forwarded", "apprise_response": status_code, "request_id": g.request_id}), status_code

@app.route('/qbitmanage', methods=['POST'])
def handle_qbitmanage():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON", "request_id": g.request_id}), 400

    function = data.get('function', 'Unknown Task')
    result = data.get('result', 'Completed')
    summary = data.get('summary') or "No additional details."

    if function in ['run_start', 'run_end']:
        logging.info(
            f"Suppressed notification for function: {function} at {datetime.utcnow().isoformat()}",
            extra={"request_id": g.request_id}
        )
        return '', 204

    # Always use 🧹 emoji and green color for all qbitmanage notifications
    emoji = "🧹"
    color = 3066993

    title = f"qbitmanage: `{function}`"
    body = f"**Result:** ✅ {result}"

    log_data = {
        "event": "qbitmanage_webhook",
        "function": function,
        "result": result,
        "emoji": emoji,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": g.request_id
    }

    status_code = send_discord_notification(title, body, emoji, color, log_data)

    return jsonify({"status": "forwarded", "apprise_response": status_code, "request_id": g.request_id}), status_code


if __name__ == '__main__':
    logging.info(f"Container booted at {datetime.utcnow().isoformat()}Z", extra={"request_id": "N/A"})
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
