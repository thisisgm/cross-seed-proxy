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
def get_client_ip():
    """Returns the real client IP address, handling X-Forwarded-For if present."""
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        # X-Forwarded-For may be a comma-separated list of IPs; the first is the real client
        real_ip = xff.split(',')[0].strip()
        proxy_ip = request.remote_addr
        return real_ip, proxy_ip
    return request.remote_addr, None

# --- Optional .env loading via python-dotenv ---
_dotenv_loaded = False
try:
    from dotenv import load_dotenv
    _dotenv_loaded = load_dotenv()
    if _dotenv_loaded:
        logging.basicConfig(level=logging.INFO)
        logging.info("Loaded environment variables from .env file.", extra={"request_id": "N/A"})
    else:
        logging.basicConfig(level=logging.INFO)
        logging.info("No .env file found or already loaded, skipping dotenv.", extra={"request_id": "N/A"})
except ImportError:
    # python-dotenv not installed; skip loading .env
    pass



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

# --- Optional OpenTelemetry distributed tracing support ---
# If OTEL environment variables are set, attempt to instrument Flask app
_otel_enabled = (
    os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    or os.getenv("OTEL_TRACES_EXPORTER")
    or os.getenv("OTEL_SERVICE_NAME")
)
if _otel_enabled:
    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        # Users are expected to configure exporters via OTEL env vars.
        trace.set_tracer_provider(TracerProvider())
        app = Flask(__name__)
        FlaskInstrumentor().instrument_app(app)
        logging.info("OpenTelemetry tracing enabled for Flask app.", extra={"request_id": "N/A"})
    except ImportError:
        app = Flask(__name__)
        logging.warning("OpenTelemetry tracing requested via environment, but opentelemetry packages not installed.", extra={"request_id": "N/A"})
else:
    app = Flask(__name__)

APPRISE_URL = os.getenv("APPRISE_URL", "http://apprise-api:8000/notify/crossseed")
ICON_URL = os.getenv("ICON_URL", "https://raw.githubusercontent.com/cross-seed/cross-seed.org/master/static/img/cross-seed.png")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

startup_time = time()

FUNCTION_META = {
    "run_start": {"emoji": "🏁", "color": 3447003},
    "run_end": {"emoji": "🏁", "color": 3447003},
    "download": {"emoji": "📥", "color": 3066993},
    "upload": {"emoji": "📤", "color": 10197915},
    "check": {"emoji": "🔍", "color": 15844367},
    "default": {"emoji": "📦", "color": 3066993},
}

SUMMARY_LOOKUP = {
    "SUCCESS": "Injection completed successfully.",
    "FAILURE": "Manual action required to resolve injection failure.",
    "SAVED": "Torrent saved for manual review.",
    "UNKNOWN": "Event status unknown.",
}

last_request_time = 0

metrics = {
    "total_requests": 0,
    "successful_sends": 0,
    "failed_sends": 0,
    "last_event": {
        "webhook": None,
        "qbitmanage": None
    },
    "last_request_duration": 0.0
}

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if AUTH_TOKEN is None:
            return f(*args, **kwargs)
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Forbidden", "request_id": g.request_id}), 403
        token = auth_header[len('Bearer '):].strip()
        if token != AUTH_TOKEN:
            return jsonify({"error": "Forbidden", "request_id": g.request_id}), 403
        return f(*args, **kwargs)
    return decorated

def send_slack_fallback(message: str):
    if not SLACK_WEBHOOK_URL:
        logging.warning("Slack fallback webhook URL not configured.", extra={"request_id": g.request_id})
        return False
    payload = {"text": message}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        if 200 <= resp.status_code < 300:
            logging.info("Slack fallback notification sent successfully.", extra={"request_id": g.request_id})
            return True
        else:
            logging.error(f"Slack fallback returned status code {resp.status_code}", extra={"request_id": g.request_id})
            return False
    except requests.RequestException as e:
        logging.error(f"Failed to send Slack fallback notification: {e}", extra={"request_id": g.request_id})
        return False

def send_telegram_fallback(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram fallback bot token or chat ID not configured.", extra={"request_id": g.request_id})
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if 200 <= resp.status_code < 300:
            logging.info("Telegram fallback notification sent successfully.", extra={"request_id": g.request_id})
            return True
        else:
            logging.error(f"Telegram fallback returned status code {resp.status_code}", extra={"request_id": g.request_id})
            return False
    except requests.RequestException as e:
        logging.error(f"Failed to send Telegram fallback notification: {e}", extra={"request_id": g.request_id})
        return False

def send_discord_notification(title: str, description: str, emoji: str, color: int, log_data: dict):
    title_with_emoji = f"{emoji} {title}"
    embed = {
        "author": {
            "name": title_with_emoji,
            "icon_url": ICON_URL
        },
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat()
    }
    payload = {
        "embeds": [embed]
    }

    # Check for optional dynamic channel routing header
    thread_id = request.headers.get('X-Discord-Thread-ID')
    if thread_id:
        # Apprise may not natively support thread_id, but we include it in payload for custom handling
        payload['thread_id'] = thread_id

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
                metrics["successful_sends"] += 1
                break
            else:
                logging.warning(f"Apprise returned status code {status_code} on attempt {attempt + 1}", extra={"request_id": g.request_id})
        except requests.RequestException as e:
            logging.error(f"Failed to send notification on attempt {attempt + 1}: {e}", extra={"request_id": g.request_id})
        if attempt < 2:
            sleep(backoffs[attempt])
    else:
        logging.error(f"Failed to send notification after 3 attempts, final status code: {status_code}", extra={"request_id": g.request_id})
        metrics["failed_sends"] += 1
        fallback_message = f"{title_with_emoji}\n{description}"
        send_slack_fallback(fallback_message)
        send_telegram_fallback(fallback_message)

    return status_code

@app.before_request
def limit_remote_addr():
    global last_request_time
    g.request_id = str(uuid.uuid4())
    g.start_time = time()
    now = g.start_time
    if now - last_request_time < 0.2:
        return jsonify({"error": "Too many requests", "request_id": g.request_id}), 429
    last_request_time = now

@app.after_request
def after_request(response):
    duration = time() - g.start_time
    metrics["last_request_duration"] = duration
    logging.info(f"Request to {request.path} took {duration:.4f} seconds", extra={"request_id": g.request_id})
    # Add request_id header to response for traceability
    response.headers["X-Request-ID"] = g.request_id
    return response

@app.route('/webhook', methods=['POST'])
def webhook():
    metrics["total_requests"] += 1
    metrics["last_event"]["webhook"] = datetime.utcnow().isoformat()

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON", "request_id": g.request_id}), 400

    event_type = data.get("extra", {}).get("event", "UNKNOWN")
    real_ip, proxy_ip = get_client_ip()

    # Allow TEST events to pass without needing full fields
    if event_type == "TEST":
        logging.info(
            f"Received TEST event from real_ip={real_ip}"
            + (f", proxy_ip={proxy_ip}" if proxy_ip else "")
            + f" at {datetime.utcnow().isoformat()}",
            extra={"request_id": g.request_id}
        )
        return jsonify({"status": "test received", "request_id": g.request_id}), 200

    extra = data.get("extra", {})
    result = extra.get("result", "UNKNOWN")

    title = "🎯 cross-seed match injected!"
    color_code = 3066993  # Default green

    if result == "FAILURE":
        title = "❌ cross-seed injection failed!"
        color_code = 15158332  # Red
    elif result == "SAVED":
        title = "💾 cross-seed torrent saved!"
        color_code = 10197915  # Blue
    elif result == "UNKNOWN":
        title = "❓ cross-seed injection status unknown"
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
        f"**Status:** {result}\n"
        f"**Summary:** {summary}"
    )

    log_data = {
        "event": "cross-seed_webhook",
        "result": result,
        "torrent": torrent_name,
        "trackers": trackers,
        "color": color_code,
        "emoji": emoji,
        "remote_ip": real_ip,
        "proxy_ip": proxy_ip,
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": g.request_id
    }

    status_code = send_discord_notification(title, body, emoji, color_code, log_data)
    
    return jsonify({"status": "forwarded", "apprise_response": status_code, "request_id": g.request_id}), status_code

@app.route('/qbitmanage', methods=['POST'])
def handle_qbitmanage():
    metrics["total_requests"] += 1
    metrics["last_event"]["qbitmanage"] = datetime.utcnow().isoformat()

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON", "request_id": g.request_id}), 400

    function = data.get('function', 'Unknown Task')
    result = data.get('result', 'Completed')
    summary = data.get('summary') or "No additional details."
    real_ip, proxy_ip = get_client_ip()

    if function in ['run_start', 'run_end']:
        logging.info(
            f"Suppressed notification for function: {function} from real_ip={real_ip}"
            + (f", proxy_ip={proxy_ip}" if proxy_ip else "")
            + f" at {datetime.utcnow().isoformat()}",
            extra={"request_id": g.request_id}
        )
        return '', 204

    meta = FUNCTION_META.get(function, FUNCTION_META['default'])
    emoji = meta['emoji']
    color = meta['color']

    title = f"qbitmanage: `{function}`"
    body = f"**Result:** `{result}`\n\n{summary}"

    log_data = {
        "event": "qbitmanage_webhook",
        "function": function,
        "result": result,
        "summary": summary,
        "emoji": emoji,
        "color": color,
        "remote_ip": real_ip,
        "proxy_ip": proxy_ip,
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": g.request_id
    }

    status_code = send_discord_notification(title, body, emoji, color, log_data)

    return jsonify({"status": "forwarded", "apprise_response": status_code, "request_id": g.request_id}), status_code


# --- Health, readiness, and startup endpoints for Docker/Kubernetes probes ---
@app.route('/health', methods=['GET'])
def health():
    # Legacy health endpoint, returns OK if app is running
    return jsonify({"status": "ok", "request_id": g.request_id}), 200

@app.route('/ready', methods=['GET'])
def ready():
    # Readiness probe: always ready if server is up
    return jsonify({"status": "ready", "request_id": g.request_id}), 200

@app.route('/startup', methods=['GET'])
def startup_probe():
    # Startup probe: returns 200 if server has booted and startup_time is set
    return jsonify({
        "status": "started",
        "startup_time": datetime.utcfromtimestamp(startup_time).isoformat() + "Z",
        "request_id": g.request_id
    }), 200

@app.route('/metrics', methods=['GET'])
@auth_required
def metrics_endpoint():
    response = metrics.copy()
    response["request_id"] = g.request_id
    return jsonify(response), 200

@app.route('/metrics/prometheus', methods=['GET'])
@auth_required
def metrics_prometheus():
    def iso_to_unix(timestamp):
        if timestamp is None:
            return 0
        try:
            dt = datetime.fromisoformat(timestamp)
            return int(dt.timestamp())
        except Exception:
            return 0

    failed_send_alert = 1 if metrics["failed_sends"] > 5 else 0
    slow_request_alert = 1 if metrics["last_request_duration"] > 2.0 else 0

    prometheus_metrics = [
        f'proxy_total_requests {metrics["total_requests"]}',
        f'proxy_successful_sends {metrics["successful_sends"]}',
        f'proxy_failed_sends {metrics["failed_sends"]}',
        f'proxy_last_event_timestamp_seconds{{event="webhook"}} {iso_to_unix(metrics["last_event"]["webhook"])}',
        f'proxy_last_event_timestamp_seconds{{event="qbitmanage"}} {iso_to_unix(metrics["last_event"]["qbitmanage"])}',
        f'proxy_last_request_duration_seconds {metrics["last_request_duration"]:.6f}',
        f'proxy_failed_send_alert{{threshold="5"}} {failed_send_alert}',
        f'proxy_slow_request_alert{{threshold="2.0"}} {slow_request_alert}'
    ]
    resp = Response("\n".join(prometheus_metrics) + "\n", mimetype="text/plain; version=0.0.4")
    resp.headers["X-Request-ID"] = g.request_id
    return resp

def mask_url(url):
    # Simple masking: show scheme and host, mask path/query
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        masked_path = "/***masked***"
        masked_url = f"{parsed.scheme}://{parsed.netloc}{masked_path}"
        return masked_url
    except Exception:
        return "***masked***"

@app.route('/debug', methods=['GET'])
@auth_required
def debug():
    current_time = time()
    uptime_seconds = current_time - startup_time
    sanitized_config = {
        "APPRISE_URL": mask_url(APPRISE_URL),
        "ICON_URL": ICON_URL
    }
    debug_info = {
        "uptime_seconds": uptime_seconds,
        "startup_time_iso": datetime.utcfromtimestamp(startup_time).isoformat() + "Z",
        "current_time_iso": datetime.utcnow().isoformat(),
        "active_config": sanitized_config,
        "metrics": metrics,
        "request_id": g.request_id
    }
    return jsonify(debug_info), 200

if __name__ == '__main__':
    logging.info(f"Container booted at {datetime.utcfromtimestamp(startup_time).isoformat()}Z", extra={"request_id": "N/A"})
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
