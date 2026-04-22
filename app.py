import os
import json
from flask import Flask, jsonify, render_template_string, send_from_directory

app = Flask(__name__)

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE_PATH = os.path.join(BASE_DIR, "ui_bridge.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

def get_pi_temp():
    """Reads Pi 5 CPU temperature directly from system files."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except:
        return "0.0"

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
        .danger { border-color: #ff3e3e !important; color: #ff3e3e !important; background: rgba(255, 62, 62, 0.2) !important; }
    </style>
</head>
<body>
    <div class="header">
        <span>SpyNo-SAARUS // NODE_01 // ACTIVE_SCAN</span>
        <span id="clock">00:00:00</span>
    </div>
    
    <div class="main-layout">
        <div class="video-sector">
            <img id="stream" src="/static/latest_detection.jpg" onerror="this.src='https://placehold.co/640x360/000/333?text=WAITING+FOR+MAIN.PY'">
        </div>
        
        <div class="data-sector">
            <div id="status-alert">INITIALIZING</div>
            <div class="card"><span class="label">CORE_TEMP</span><span id="temp" class="value">--</span><span class="value">°C</span></div>
            <div class="card"><span class="label">GPS_POSITION</span><span id="gps" class="value">0.0, 0.0</span></div>
            <div class="card"><span class="label">HEADING_IMU</span><span id="heading" class="value">0° N</span></div>
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

        setInterval(() => {
            document.getElementById('stream').src = "/static/latest_detection.jpg?t=" + Date.now();
        }, 100);
        
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
        "gps": {"lat": "0.0000", "lng": "0.0000"},
        "imu": {"heading": "0", "dir": "N"},
        "status": {"drone_detected": False},
        "cpu_temp": get_pi_temp()
    }
    
    if os.path.exists(BRIDGE_PATH):
        try:
            with open(BRIDGE_PATH, "r") as f:
                payload.update(json.load(f))
        except:
            pass

    payload["cpu_temp"] = get_pi_temp()
    return jsonify(payload)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)