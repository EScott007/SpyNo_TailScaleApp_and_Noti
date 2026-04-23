# threaded_capture.py

#########################################################

# Author: Jordan Carver

#########################################################
import threading
import queue
import time
import sys
from picamera2 import Picamera2

image_queue_1 = queue.Queue(maxsize=1)
image_queue_0 = queue.Queue(maxsize=1)
stop_capture = threading.Event()
cam1_thread, cam0_thread = None, None
_fps_lock = threading.Lock()
_capture_fps = {0: 0.0, 1: 0.0}


class CaptureThread(threading.Thread):
    def __init__(self, picam2_object, custom_id):
        super().__init__()
        self.picam2 = picam2_object
        self.custom_id = custom_id
        self.daemon = True

    def run(self):
        try:
            print(f"Capture thread is running for camera {self.picam2}.")
            self.picam2.start()
            time.sleep(2)
            frames = 0
            window_start = time.time()
            while not stop_capture.is_set():
                image = self.picam2.capture_array()
                if self.custom_id == 1 and image_queue_1.full():
                    image_queue_1.get()
                if self.custom_id == 1:
                    image_queue_1.put(image)
                if self.custom_id == 0 and image_queue_0.full():
                    image_queue_0.get()
                if self.custom_id == 0:
                    image_queue_0.put(image)

                frames += 1
                now = time.time()
                elapsed = now - window_start
                if elapsed >= 1.0:
                    fps_value = frames / elapsed
                    with _fps_lock:
                        _capture_fps[self.custom_id] = fps_value
                    frames = 0
                    window_start = now

                time.sleep(0.1)
        except Exception as e:
            print(f"Error in capture thread for camera {self.picam2}: {e}", file=sys.stderr)
        finally:
            if self.picam2:
                self.picam2.stop()
            print(f"Capture thread for camera {self.picam2} has stopped.")


def start_capture_threads(picam2_cam1, picam2_cam0):
    global cam1_thread, cam0_thread
    cam1_thread = CaptureThread(picam2_cam1, custom_id=1)
    cam0_thread = CaptureThread(picam2_cam0, custom_id=0)
    cam1_thread.start()
    cam0_thread.start()


def get_latest_images():
    try:
        image1 = image_queue_1.get_nowait()
        image2 = image_queue_0.get_nowait()
        return image1, image2
        print("helo")
    except queue.Empty:
        return None, None
        print("Empty")


def get_capture_fps():
    with _fps_lock:
        return {
            "cam0": round(_capture_fps.get(0, 0.0), 2),
            "cam1": round(_capture_fps.get(1, 0.0), 2)
        }


def stop_capture_threads():
    global cam1_thread, cam0_thread
    stop_capture.set()
    if cam1_thread:
        cam1_thread.join(timeout=2)
    if cam0_thread:
        cam0_thread.join(timeout=2)
