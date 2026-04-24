import os
import json
import time
import math
import random
import base64
import threading
from flask import Flask, jsonify, render_template_string, send_from_directory, Response

app = Flask(__name__)

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE_PATH = os.path.join(BASE_DIR, "ui_bridge.json")
BRIDGE_TMP_PATH = os.path.join(BASE_DIR, "ui_bridge.tmp.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")
LATEST_IMAGE_PATH = os.path.join(STATIC_DIR, "latest_detection.jpg")
TAILSCALE_HOST = os.getenv("APP_HOST", "100.72.170.79")
APP_PORT = int(os.getenv("APP_PORT", "5000"))
MOCK_MODE = os.getenv("MOCK_MODE", "0") == "1"
BRIDGE_STALE_SECONDS = float(os.getenv("BRIDGE_STALE_SECONDS", "3.0"))

# Tiny valid JPEG for fallback and mock mode bootstrapping.
FALLBACK_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAQDAwQDAwQEAwQFBAQFBgoHBgYGBgoICQoKCgkICQkK"
    "DA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQUGBggICgkKCg8ODg8QDxAQEBAQEBAQ"
    "EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAABAAEDASIAAhEB"
    "AxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAA"
    "AAAAAAAAAAAAAAABAgP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwA//Z"
)

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

def get_pi_temp():
    """Reads Pi 5 CPU temperature directly from system files."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except:
        return "0.0"


def deep_merge(base, incoming):
    for key, value in incoming.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def mjpeg_generator():
    while True:
        if os.path.exists(LATEST_IMAGE_PATH):
            try:
                with open(LATEST_IMAGE_PATH, "rb") as f:
                    frame = f.read()
                if frame:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                    )
            except Exception:
                pass
        time.sleep(0.1)


def ensure_latest_image_exists():
    if os.path.exists(LATEST_IMAGE_PATH):
        return
    try:
        with open(LATEST_IMAGE_PATH, "wb") as f:
            f.write(base64.b64decode(FALLBACK_JPEG_BASE64))
    except Exception:
        pass


def write_bridge_payload(payload):
    try:
        with open(BRIDGE_TMP_PATH, "w") as f:
            json.dump(payload, f)
        os.replace(BRIDGE_TMP_PATH, BRIDGE_PATH)
    except Exception:
        pass


def load_bridge_data():
    if not os.path.exists(BRIDGE_PATH):
        return None, None
    try:
        with open(BRIDGE_PATH, "r") as f:
            bridge = json.load(f)
        if not isinstance(bridge, dict):
            return None, None
        mtime = os.path.getmtime(BRIDGE_PATH)
        return bridge, mtime
    except Exception:
        return None, None


def compute_bridge_health(bridge_mtime):
    if bridge_mtime is None:
        return {"state": "offline", "age_sec": None}
    age_sec = max(0.0, time.time() - bridge_mtime)
    if age_sec > BRIDGE_STALE_SECONDS:
        return {"state": "stale", "age_sec": round(age_sec, 2)}
    return {"state": "live", "age_sec": round(age_sec, 2)}


def get_bridge_producer(bridge):
    if not isinstance(bridge, dict):
        return "unknown"
    meta = bridge.get("meta")
    if isinstance(meta, dict):
        producer = meta.get("producer")
        if isinstance(producer, str) and producer.strip():
            return producer.strip().lower()
    return "unknown"


def evaluate_bridge_acceptance(bridge, health):
    if bridge is None:
        return False, "no_bridge"
    if health["state"] != "live":
        return False, health["state"]
    producer = get_bridge_producer(bridge)
    if MOCK_MODE:
        return True, ""
    if producer == "mock":
        return False, "mock_payload_in_prod_mode"
    if producer in ("real", "main"):
        return True, ""
    return False, "unknown_producer"


def run_mock_bridge_publisher():
    phase = 0.0
    while True:
        phase += 0.12
        heading = round((phase * 40.0) % 360.0, 1)
        heading_idx = int(((heading + 22.5) % 360) // 45)
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        payload = {
            "gps": {
                "lat": round(33.4545 + math.sin(phase) * 0.0006, 6),
                "lng": round(-88.7942 + math.cos(phase) * 0.0006, 6),
                "alt": round(145.0 + abs(math.sin(phase * 0.7)) * 8.0, 2)
            },
            "imu": {
                "heading": heading,
                "dir": dirs[heading_idx]
            },
            "status": {
                "drone_detected": random.random() > 0.85
            },
            "fps": {
                "capture_cam0": round(9.5 + random.random() * 2.0, 2),
                "capture_cam1": round(9.5 + random.random() * 2.0, 2),
                "inference": round(7.5 + random.random() * 1.8, 2)
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "meta": {
                "producer": "mock"
            }
        }
        write_bridge_payload(payload)
        ensure_latest_image_exists()
        time.sleep(0.5)

# --- HUD INTERFACE ---
HUD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>SpyNo-SAARUS | NODE 01</title>
    <style>
        body { background: #050505; color: #00f2ff; font-family: 'Courier New', monospace; padding: 10px; text-transform: uppercase; overflow: hidden; }
        .header { border-bottom: 1px solid #00f2ff; padding-bottom: 5px; margin-bottom: 10px; font-size: 14px; display: flex; justify-content: space-between; }
        .main-layout { display: flex; gap: 15px; }
        .video-sector { flex: 2; border: 1px solid #333; background: #000; position: relative; }
        .video-sector img { width: 100%; height: auto; display: block; border: 1px solid #00f2ff; }
        .data-sector { flex: 1; display: flex; flex-direction: column; gap: 10px; }
        .card { border: 1px solid #00f2ff; padding: 10px; background: rgba(0, 242, 255, 0.05); }
        .label { color: #555; font-size: 10px; display: block; margin-bottom: 2px; }
        .value { font-size: 22px; color: #fff; font-weight: bold; }
        #status-alert { border: 2px solid #00f2ff; padding: 15px; text-align: center; font-size: 20px; font-weight: bold; transition: 0.3s; }
        #integration-status { border: 1px solid #00f2ff; padding: 8px 10px; font-size: 12px; margin-bottom: 8px; }
        .danger { border-color: #ff3e3e !important; color: #ff3e3e !important; background: rgba(255, 62, 62, 0.2) !important; }
        .warn { border-color: #ffb347 !important; color: #ffb347 !important; background: rgba(255, 179, 71, 0.2) !important; }
    </style>
</head>
<body>
    <div class="header">
        <span>SpyNo-SAARUS // NODE_01 // ACTIVE_SCAN</span>
        <span id="clock">00:00:00</span>
    </div>
    
    <div class="main-layout">
        <div class="video-sector">
            <img id="stream" src="/video_feed" onerror="this.src='/static/latest_detection.jpg'">
        </div>
        
        <div class="data-sector">
            <div id="integration-status">SOURCE: BOOT | FEED: WAITING</div>
            <div id="status-alert">INITIALIZING</div>
            <div class="card"><span class="label">CORE_TEMP</span><span id="temp" class="value">--</span><span class="value">°C</span></div>
            <div class="card"><span class="label">GPS_POSITION</span><span id="gps" class="value">0.0, 0.0</span></div>
            <div class="card"><span class="label">HEADING_IMU</span><span id="heading" class="value">0° N</span></div>
            <div class="card"><span class="label">CAPTURE_FPS_CAM0</span><span id="fps-cam0" class="value">0.0</span></div>
            <div class="card"><span class="label">CAPTURE_FPS_CAM1</span><span id="fps-cam1" class="value">0.0</span></div>
            <div class="card"><span class="label">INFERENCE_FPS</span><span id="fps-infer" class="value">0.0</span></div>
        </div>
    </div>

    <script>
        async function fetchUpdates() {
            try {
                const r = await fetch('/api/data');
                const d = await r.json();
                document.getElementById('temp').innerText = d.cpu_temp;
                document.getElementById('gps').innerText = d.gps.lat + ", " + d.gps.lng;
                document.getElementById('heading').innerText = d.imu.heading + "° " + d.imu.dir;
                document.getElementById('fps-cam0').innerText = d.fps.capture_cam0;
                document.getElementById('fps-cam1').innerText = d.fps.capture_cam1;
                document.getElementById('fps-infer').innerText = d.fps.inference;

                const integration = document.getElementById('integration-status');
                integration.classList.remove('danger');
                integration.classList.remove('warn');
                const mode = d.meta.mock_mode ? 'MOCK' : 'PROD';
                const producer = (d.meta.producer || 'unknown').toUpperCase();
                const age = d.meta.bridge_age_sec === null ? '--' : d.meta.bridge_age_sec + 's';
                integration.innerText = `MODE: ${mode} | SRC: ${producer} | FEED: ${d.meta.bridge_state.toUpperCase()} | AGE: ${age}`;
                if (d.meta.bridge_state === 'offline') {
                    integration.classList.add('danger');
                } else if (d.meta.bridge_state === 'stale') {
                    integration.classList.add('warn');
                } else if (!d.meta.bridge_accepted) {
                    integration.classList.add('warn');
                }
                
                const alert = document.getElementById('status-alert');
                if(d.status.drone_detected) {
                    alert.innerText = "🚨 TARGET ACQUIRED";
                    alert.classList.add('danger');
                } else {
                    alert.innerText = "AIRSPACE CLEAR";
                    alert.classList.remove('danger');
                }
            } catch(e) {}
        }
        
        setInterval(fetchUpdates, 1000);
        setInterval(() => { document.getElementById('clock').innerText = new Date().toLocaleTimeString(); }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HUD_HTML)

@app.route('/api/data')
def api_data():
    payload = {
        "gps": {"lat": 0.0, "lng": 0.0, "alt": 0.0},
        "imu": {"heading": 0.0, "dir": "N"},
        "status": {"drone_detected": False},
        "fps": {"capture_cam0": 0.0, "capture_cam1": 0.0, "inference": 0.0},
        "timestamp": "",
        "cpu_temp": get_pi_temp(),
        "meta": {
            "mock_mode": MOCK_MODE,
            "bridge_state": "offline",
            "bridge_age_sec": None,
            "bridge_stale_seconds": BRIDGE_STALE_SECONDS,
            "producer": "unknown",
            "bridge_accepted": False,
            "reject_reason": ""
        }
    }

    bridge, bridge_mtime = load_bridge_data()
    health = compute_bridge_health(bridge_mtime)
    producer = get_bridge_producer(bridge)
    accepted, reject_reason = evaluate_bridge_acceptance(bridge, health)

    if accepted:
        bridge_data = dict(bridge)
        bridge_data.pop("meta", None)
        deep_merge(payload, bridge_data)

    payload["meta"]["bridge_state"] = health["state"]
    payload["meta"]["bridge_age_sec"] = health["age_sec"]
    payload["meta"]["producer"] = producer
    payload["meta"]["bridge_accepted"] = accepted
    payload["meta"]["reject_reason"] = reject_reason

    payload["cpu_temp"] = get_pi_temp()
    return jsonify(payload)


@app.route('/api/health')
def api_health():
    bridge, bridge_mtime = load_bridge_data()
    health = compute_bridge_health(bridge_mtime)
    producer = get_bridge_producer(bridge)
    accepted, reject_reason = evaluate_bridge_acceptance(bridge, health)
    return jsonify({
        "ok": accepted,
        "bridge_state": health["state"],
        "bridge_age_sec": health["age_sec"],
        "bridge_stale_seconds": BRIDGE_STALE_SECONDS,
        "mock_mode": MOCK_MODE,
        "producer": producer,
        "bridge_accepted": accepted,
        "reject_reason": reject_reason,
        "host": TAILSCALE_HOST,
        "port": APP_PORT,
        "bridge_path": BRIDGE_PATH,
        "has_payload": isinstance(bridge, dict)
    })

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.route('/video_feed')
def video_feed():
    return Response(mjpeg_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    ensure_latest_image_exists()
    if MOCK_MODE:
        mock_thread = threading.Thread(target=run_mock_bridge_publisher, daemon=True)
        mock_thread.start()
        print("MOCK_MODE enabled: generating synthetic telemetry in ui_bridge.json")

    try:
        print(f"Starting dashboard on http://{TAILSCALE_HOST}:{APP_PORT}")
        app.run(host=TAILSCALE_HOST, port=APP_PORT)
    except OSError as e:
        print(f"Failed to bind to {TAILSCALE_HOST}:{APP_PORT} ({e}). Falling back to 0.0.0.0:{APP_PORT}.")
        app.run(host='0.0.0.0', port=APP_PORT)
