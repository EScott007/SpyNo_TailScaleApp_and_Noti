import json
import math
import os
import random
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE_PATH = os.path.join(BASE_DIR, "ui_bridge.json")
BRIDGE_TMP_PATH = os.path.join(BASE_DIR, "ui_bridge.tmp.json")


def write_bridge_payload(payload):
    with open(BRIDGE_TMP_PATH, "w") as f:
        json.dump(payload, f)
    os.replace(BRIDGE_TMP_PATH, BRIDGE_PATH)


def heading_to_dir(heading):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int(((heading + 22.5) % 360) // 45)
    return dirs[idx]


def run_mock_loop():
    phase = 0.0
    while True:
        phase += 0.08
        heading = round((phase * 40.0) % 360.0, 1)
        payload = {
            "gps": {
                "lat": round(33.4545 + math.sin(phase) * 0.0008, 6),
                "lng": round(-88.7942 + math.cos(phase) * 0.0008, 6),
                "alt": round(145.0 + abs(math.sin(phase * 0.6)) * 10.0, 2)
            },
            "imu": {
                "heading": heading,
                "dir": heading_to_dir(heading)
            },
            "status": {
                "drone_detected": random.random() > 0.87
            },
            "fps": {
                "capture_cam0": round(9.0 + random.random() * 2.5, 2),
                "capture_cam1": round(9.0 + random.random() * 2.5, 2),
                "inference": round(7.0 + random.random() * 2.0, 2)
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "meta": {
                "producer": "mock"
            }
        }
        write_bridge_payload(payload)
        print(payload)
        time.sleep(0.5)


if __name__ == "__main__":
    run_mock_loop()
