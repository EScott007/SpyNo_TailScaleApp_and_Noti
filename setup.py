# setup.py

###################################################################

# Author: Jordan Carver

###################################################################
import time
from picamera2 import Picamera2
from ultralytics import YOLO
from libcamera import Transform
import torch

import hailo
from hailo_platform import HEF

def setup_all_systems():
    picam2_cam1, picam2_cam0 = None, None
    # ~ if torch.backends.vulkan.is_available():
        # ~ device = 'vulkan'
        # ~ print("Vulkan GPU Detected. Attempting to Load Model on Vulkan")
    # ~ elif torch.has_mps or toch.has_cuda:
        # ~ device = 'gpu'
        # ~ print(f"No Compatible GPU Detected. Attempting to Load Model on {device}.")
    # ~ else:
        # ~ device = 'cpu'
        # ~ print("No Compatible GPU Detected. Loading Model on CPU.")
    while True:
        try:
            picam2_cam1 = Picamera2(camera_num=1)
            picam2_cam0 = Picamera2(camera_num=0)
            still_config = picam2_cam1.create_still_configuration(main={"size": (3840, 2160), "format": "BGR888"}, transform=Transform(hflip = True, vflip=True), buffer_count = 2)
            picam2_cam1.configure(still_config)
            picam2_cam0.configure(still_config)
            # ~ picam2_cam1.set_controls({"ExposureTime": 10000, "AnalogueGain": 4.0, "FrameRate": 14.8})
            # ~ picam2_cam0.set_controls({"ExposureTime": 10000, "AnalogueGain": 4.0, "FrameRate": 14.8})
            picam2_cam1.start()
            picam2_cam0.start()
            time.sleep(2)
            print("Cameras initialized and started successfully.")
            #yolo_model = YOLO(model_path)
            #model.to(device)
                        
            #model_path = 'best.pt'
            #yolo_model = YOLO(model_path)
            #yolo_model.to('vulkan')
            # ~ print(f"YOLOv8 model '{model_path}' loaded successfully.")
            break
        except Exception as e:
            print(f"Setup failed due to error: {e}")
            print("Retrying setup in 5 seconds...")
            if picam2_cam1 and picam2_cam1.is_open:
                picam2_cam1.stop()
            if picam2_cam0 and picam2_cam0.is_open:
                picam2_cam0.stop()
            time.sleep(5)
            continue
    return picam2_cam1, picam2_cam0

