# main.py

##########################################################################################

# Author: Jordan Carver

##########################################################################################
import time
import threading
import numpy as np
import cv2
import math
from picamera2 import Picamera2
import hailo
import json
import os
from collections import deque

import hailo_platform as hpf

# ~ from hailo_platform import HEF, Device, VDevice, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, HailoStreamInterface

#from quaternion import as_float_array, as_quat_array  # Incompatible within other library version ranges
from scipy.spatial.transform import Rotation as R
import requests
from serial_reader_2 import get_latest_sensor_data, stop_serial_reader
from threaded_capture import start_capture_threads, stop_capture_threads, get_latest_images, get_capture_fps
from setup import setup_all_systems
from drawing_utils import draw_detections
from resize_image import resize_image
#from ekf_model_7 import IMUGPS_EKF, CoordinateConverter
from imu_filter import IMUFilter
from add_data_to_file import add_data_to_file
gps_imu_file = "gps_imu_data.txt"
camera_det_file = "cam_det_data.txt"
gps_data_raw = "gps_data_raw.txt"
imu_data_raw = "imu_data_raw.txt"
camera_data_raw = "camera_data_raw.txt"

# --- UI & NTFY CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
BRIDGE_PATH = os.path.join(BASE_DIR, "ui_bridge.json")
BRIDGE_TMP_PATH = os.path.join(BASE_DIR, "ui_bridge.tmp.json")
SAVE_PATH = os.path.join(STATIC_DIR, "latest_detection.jpg")
TMP_PATH = os.path.join(STATIC_DIR, "latest_detection_tmp.jpg")

NTFY_TOPIC = "SpyNo-SAARUS-Notifications-for-Senior-Design-MSU"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

last_detection_state = False

def get_cardinal_dir(degree):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[round(degree / 45) % 8]

def send_ntfy_alert(image_path, heading, coords):
    try:
        # Removed raw emoji and .encode() to prevent HTTP header crashes
        title = "SpyNo-SAARUS: TARGET ACQUIRED"
        message = f"Detection at {coords}. Heading: {heading}."
        
        with open(image_path, "rb") as f:
            response = requests.post(
                NTFY_URL,
                data=f,
                headers={
                    "Title": title,
                    "X-Message": message, # Use X-Message when attaching a file
                    "Priority": "5",
                    "Tags": "warning,drone,target_locked,rotating_light", # rotating_light adds the 🚨
                    "Filename": "drone_capture.jpg"
                },
                timeout=10
            )
            # Actually print the server's response so we know it worked
            print(f"\n>>> NTFY STATUS: {response.status_code} - {response.text}\n")
            
    except Exception as e:
        # Added borders so this doesn't get lost in the GPS/IMU terminal spam
        print(f"\n{'='*40}\n🚨 NOTIFICATION FAILED: {e}\n{'='*40}\n")


def extract_candidate_detections(raw_detections):
    arr = np.squeeze(raw_detections)
    if arr.ndim == 1:
        return [arr]
    if arr.ndim == 2:
        if arr.shape[1] >= 5:
            return arr
        if arr.shape[0] >= 5:
            return arr.T
    return []


def write_bridge_json(gps_lat, gps_lng, gps_alt, sys_direction, sys_dir_letter, drone_found, capture_fps, inference_fps):
    bridge_data = {
        "gps": {
            "lat": gps_lat if gps_lat is not None else 0.0,
            "lng": gps_lng if gps_lng is not None else 0.0,
            "alt": gps_alt if gps_alt is not None else 0.0
        },
        "imu": {
            "heading": round(sys_direction, 1) if sys_direction is not None else 0.0,
            "dir": sys_dir_letter if sys_dir_letter else "N"
        },
        "status": {
            "drone_detected": bool(drone_found)
        },
        "fps": {
            "capture_cam0": capture_fps.get("cam0", 0.0),
            "capture_cam1": capture_fps.get("cam1", 0.0),
            "inference": round(inference_fps, 2)
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "meta": {
            "producer": "real"
        }
    }
    with open(BRIDGE_TMP_PATH, "w") as f:
        json.dump(bridge_data, f)
    os.replace(BRIDGE_TMP_PATH, BRIDGE_PATH)

if __name__ == "__main__":
    picam2_cam1, picam2_cam0 = None, None
    setup_successful = False
    print("Attempting to initialize systems...")
    while not setup_successful:
        picam2_cam1, picam2_cam0 = setup_all_systems()
        if picam2_cam1 and picam2_cam0:
            setup_successful = True
            print("All systems initialized successfully.")
        else:
            print("System setup failed. Retrying in 5 seconds...")
            time.sleep(5)
    start_capture_threads(picam2_cam1, picam2_cam0)
    i = 0
    
    try:
        last_process_time = time.time()
        inference_fps_samples = deque(maxlen=30)
        image_cam1, image_cam0 = None, None
        sys_dir_letter, sys_direction = None, None
        gps_lat, gps_lng, gps_alt = None, None, None
        gps_data_set_size, imu_data_set_size, cam_data_set_size = 0, 0, 0
        SAMPLE_RATE = 1.0 # Madgwick Filter Rate
        # ~ imu_processor = IMUFilter(sample_rate=SAMPLE_RATE, be`ta_value=0.041)
        # ~ print("Initializing IMU Filter and Collecting Data...")
        hef = hpf.HEF('yolov8n.hef')

        network_group_params = None

        with hpf.VDevice() as target:
            configure_params = hpf.ConfigureParams.create_from_hef(hef, interface=hpf.HailoStreamInterface.PCIe)
            network_group = target.configure(hef, configure_params)[0]
            network_group_params = network_group.create_params()
            
            input_vstream_info = hef.get_input_vstream_infos()[0]
            output_vstream_info = hef.get_output_vstream_infos()[0]
            
            input_vstreams_params = hpf.InputVStreamParams.make_from_network_group(network_group, quantized=False, format_type=hpf.FormatType.UINT8)
            output_vstreams_params = hpf.OutputVStreamParams.make_from_network_group(network_group, quantized=False, format_type=hpf.FormatType.FLOAT32)
            
            input_shape = input_vstream_info.shape
            output_shape = output_vstream_info.shape
            
            print(f"Input shape: {input_shape}, Output shape: {output_shape}")
            with network_group.activate(network_group_params):
                with hpf.InferVStreams(network_group, input_vstreams_params, output_vstreams_params) as infer_pipeline:
                    
                    while True:
                        current_time = time.time()
                        drone_found = False # Flag for UI and NTFY

                        if current_time - last_process_time >= 1:
                            sensor_data = get_latest_sensor_data()
                            sensor_collection_time = time.time()
                            if sensor_data:
                                gps_lat, gps_lng, gps_alt, gps_sats, gps_hdop = (float(sensor_data[0]), float(sensor_data[1]), float(sensor_data[2]), int(sensor_data[3]), float(sensor_data[4]))
                                accel_x, accel_y, accel_z = map(float, sensor_data[5:8])
                                gyro_x, gyro_y, gyro_z = map(float, sensor_data[8:11])
                                mag_x, mag_y, mag_z = map(float, sensor_data[11:14])
                                euler_x, euler_y, euler_z = map(float, sensor_data[14:17])
                                accel_cal, mag_cal, gyro_cal = map(int, sensor_data[17:20])
                                #add_data_to_file(gps_data_readable, f"GPS Lat: {gps_lat}, GPS Lng: {gps_lng}, GPS Alt: {gps_alt}, # of Sats: {gps_sats}, GPS HDOP: {gps_hdop} " + time.strftime("%H:%M:%S"))
                                #add_data_to_file(imu_data_readable, f"IMU Accel X: {accel_x}, IMU Accel Y: {accel_y}, IMU Accel Z: {accel_z}, IMU Accel Cal: {accel_cal}, IMU Gyro X: {gyro_x}, IMU Gyro Y: {gyro_y}, IMU Gyro Z: {gyro_z}, IMU Gyro Cal: {gyro_cal}, IMU Mag X: {mag_x}, IMU Mag Y: {mag_y}, IMU Mag Z: {mag_z}, IMU Mag Cal: {mag_cal} " + time.strftime("%H:%M:%S"))
                                if gps_sats >= 4:
                                    add_data_to_file(gps_data_raw, f"{gps_lat} {gps_lng} {gps_alt} {gps_sats} {gps_hdop} " + time.strftime("%H:%M:%S"))
                                    gps_data_set_size += 1
                                    print(f"GPS Data Points Collected: {gps_data_set_size}")  # Uncomment after demo
                                if accel_cal == 3 and gyro_cal == 3 and mag_cal == 3:
                                    add_data_to_file(imu_data_raw, f"{euler_x} {euler_y} {euler_z} " + time.strftime("%H:%M:%S"))
                                    imu_data_set_size += 1
                                    print(f"Calibrated IMU Data Points Collected: {imu_data_set_size}")  # Uncomment after demo
                                accel_data = np.array([accel_x, accel_y, accel_z], dtype=float)
                                gyro_data = np.array([gyro_x, gyro_y, gyro_z], dtype=float)
                                mag_data = np.array([mag_x, mag_y, mag_z], dtype=float)
                                # ~ current_angles = imu_processor.update(accel_data, gyro_data, mag_data)
                                sys_direction = (euler_x - 90.0) % 360
                                if sys_direction >= 337.5 or sys_direction < 22.5:
                                    sys_dir_letter = "N"
                                elif sys_direction >= 22.5 and sys_direction < 67.5:
                                    sys_dir_letter = "NE"
                                elif sys_direction >= 67.5 and sys_direction < 112.5:
                                    sys_dir_letter = "E"
                                elif sys_direction >= 112.5 and sys_direction < 157.5:
                                    sys_dir_letter = "SE"
                                elif sys_direction >= 157.5 and sys_direction < 202.5:
                                    sys_dir_letter = "S"
                                elif sys_direction >= 202.5 and sys_direction < 247.5:
                                    sys_dir_letter = "SW"
                                elif sys_direction >= 247.5 and sys_direction < 292.5:
                                    sys_dir_letter = "W"
                                elif sys_direction >= 292.5 and sys_direction < 337.5:
                                    sys_dir_letter = "NW"
                                else:
                                    sys_dir_letter = "Unknown"
                                print(f"Accelerometer Calibration: {accel_cal} ")
                                print(f"Accelerometer Readings: [{accel_x}, {accel_y}, {accel_z}]")
                                print(" ")
                                print(f"Magnetometer Calibration:  {mag_cal} ")
                                print(f"Magnetometer Readings: [{mag_x}, {mag_y}, {mag_z}]")
                                print(" ")
                                print(f"Gyroscope Calibration:     {gyro_cal} ")
                                print(f"Gyroscope Readings: [{gyro_x}, {gyro_y}, {gyro_z}]")
                                print(" ")
                                print(f"Heading: {sys_direction} Direction: {sys_dir_letter}")
                                print(" ")
                                print(f"GPS # of Satellites:       {gps_sats} ")
                                print(f"GPS HDOP value:            {gps_hdop} ")
                                print(f"Latitude:                  {gps_lat}  ")
                                print(f"Longitude:                 {gps_lng}  ")
                                print(f"Altitude:                  {gps_alt}  ")
                                print(" ")
                                time_now = time.strftime("%H:%M:%S")
                                print(f"Timestamp: {time_now}")
                                print(" ")
                            else:
                                print("ruh roh raggy")
                            last_process_time = time.time()
                        image_cam1_rgb, image_cam0_rgb = get_latest_images()
                        if image_cam1_rgb is not None and image_cam0_rgb is not None:
                            infer_start = time.time()
                            
                            resized_frame_1 = cv2.resize(image_cam1_rgb, (640, 640))
                            
                            input_data_1 = {list(input_vstreams_params.keys())[0]: (np.expand_dims(resized_frame_1, axis=0).astype(np.uint8))}
                            
                            val = input_data_1[list(input_data_1.keys())[0]]
                            print(f"Data range: {val.min()} to {val.max()} | Type: {val.dtype}")
                            
                            results = infer_pipeline.infer(input_data_1)
                            
                            output_name = list(results.keys())[0]
                            detections = results[output_name][0]
                            candidates = extract_candidate_detections(detections)
                            print(f"Detections parsed: {len(candidates)}")
                            
                            img_w = 640
                            img_h = 640
                            
                            for i, det in enumerate(candidates):
                                if len(det) < 5:
                                    continue
                                ymin, xmin, ymax, xmax, confidence = det[:5]
                                try:
                                    confidence = float(confidence)
                                except (TypeError, ValueError):
                                    continue
                                print(f"Confidence of object detected: {confidence}")
                                if confidence > 0.5:
                                    drone_found = True # Target acquired
                                    print(f"Object {i} found with confidence: {confidence:.2f}")
                                    left = int(float(xmin) * img_w)
                                    top = int(float(ymin) * img_h)
                                    right = int(float(xmax) * img_w)
                                    bottom = int(float(ymax) * img_h)
                                    
                                    print("Detection Made")
                                    
                                    cv2.rectangle(resized_frame_1, (left, top), (right, bottom), (0, 0, 255), 2)
                                    
                                    label = f"{confidence:.2f}"
                                    cv2.putText(resized_frame_1, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                            infer_duration = time.time() - infer_start
                            if infer_duration > 0:
                                inference_fps_samples.append(1.0 / infer_duration)
                            inference_fps = sum(inference_fps_samples) / len(inference_fps_samples) if inference_fps_samples else 0.0
                            
                            display_frame = cv2.cvtColor(resized_frame_1, cv2.COLOR_RGB2BGR)
                            
                            # --- UI BRIDGE UPDATE ---
                            write_bridge_json(
                                gps_lat,
                                gps_lng,
                                gps_alt,
                                sys_direction,
                                sys_dir_letter,
                                drone_found,
                                get_capture_fps(),
                                inference_fps
                            )
                            
                            # --- WEB HUD UPDATE ---
                            cv2.imwrite(TMP_PATH, display_frame)
                            os.replace(TMP_PATH, SAVE_PATH)

                            # --- NOTIFICATION TRIGGER --- #

                            if drone_found and not last_detection_state:
                                # Protect against a crash if a drone is found before the first IMU reading
                                safe_heading = round(sys_direction, 1) if sys_direction is not None else "Calculating..."
                                safe_letter = sys_dir_letter if sys_dir_letter is not None else "N/A"
                                
                                send_ntfy_alert(SAVE_PATH, f"{safe_heading} {safe_letter}", f"{gps_lat}, {gps_lng}")
                            last_detection_state = drone_found

                            cv2.imshow("Hailo-8L Inference", display_frame)
                            cv2.waitKey(1)
                            # ~ Demo code
                            # ~ image_cam1_bgr = cv2.cvtColor(image_cam1_rgb, cv2.COLOR_RGB2BGR)
                            # ~ image_cam0_bgr = cv2.cvtColor(image_cam0_rgb, cv2.COLOR_RGB2BGR)
                            # ~ image_cam1_bgr_down_scaled = resize_image(image_cam1_bgr)
                            # ~ image_cam0_bgr_down_scaled = resize_image(image_cam0_bgr)
                            # ~ mod_pred_time_before = time.time()
                            # ~ #### RUN YOLOV8 MODEL PREDICTIONS ON HIGH RESOLUTION IMAGES ####
                            # ~ results_cam1 = yolo_model.predict(image_cam1_rgb, verbose=False)
                            # ~ results_cam0 = yolo_model.predict(image_cam0_rgb, verbose=False)
                            # ~ mod_pred_time_after = time.time()
                            # ~ time_elapsed_od_pred = mod_pred_time_after - mod_pred_time_before
                            # ~ add_data_to_file(camera_det_file, f"Time of Recent Detection: {time_elapsed_od_pred} s " + time.strftime("%H:%M:%S"))                
                            # ~ print(f"Time Elapsed for Dual Prediction: {time_elapsed_od_pred:.2f} sec")
                            # ~ if len(results_cam0[0].boxes) > 0 and len(results_cam1[0].boxes) > 0:
                                # ~ annotated_image_cam1_bgr_down_scaled = draw_detections(image_cam1_bgr_down_scaled, results_cam1[0])
                                # ~ annotated_image_cam0_bgr_down_scaled = draw_detections(image_cam0_bgr_down_scaled, results_cam0[0])
                                # ~ combined_image = np.hstack((annotated_image_cam1_bgr_down_scaled, annotated_image_cam0_bgr_down_scaled))
                                # ~ font = cv2.FONT_HERSHEY_SIMPLEX
                                # ~ font_scale = 1
                                # ~ color = (0, 0, 0)
                                # ~ thickness = 2
                                # ~ direction_str = str(sys_dir_letter) + " " + str(sys_direction)
                                # ~ dont_ask = "Lat: "
                                # ~ gps_str = str(dont_ask) + str(gps_lat) + " Long: " + str(gps_lng) + " Alt: " + str(gps_alt)
                                # ~ time_now = time.time()
                                # ~ time_elapsed = time_now - current_time
                                # ~ fps = 1.0 / time_elapsed
                                # ~ time_str = str(fps) + " FPS"
                                # ~ (text_width, text_height), baseline = cv2.getTextSize(direction_str, font, font_scale, thickness)
                                # ~ (text_width_gps, text_height_gps), baseline_gps = cv2.getTextSize(gps_str, font, font_scale, thickness)
                                # ~ (text_width_time, text_height_time), baseline_time = cv2.getTextSize(time_str, font, font_scale, thickness)
                                # ~ image_center_x = 1280
                                # ~ org_x = image_center_x - (text_width // 2)
                                # ~ org_y = 100
                                # ~ org = (org_x, org_y)
                                # ~ org_x_gps = image_center_x - (text_width_gps // 2)
                                # ~ org_y_gps = 50
                                # ~ org_gps = (org_x_gps, org_y_gps)
                                # ~ org_x_time = image_center_x - (text_width_time // 2)
                                # ~ org_y_time = 150
                                # ~ org_time = (org_x_time, org_y_time)
                                # ~ cv2.putText(combined_image, gps_str, org_gps, font, font_scale, color, thickness, cv2.LINE_AA)
                                # ~ cv2.putText(combined_image, direction_str, org, font, font_scale, color, thickness, cv2.LINE_AA)
                                # ~ cv2.putText(combined_image, time_str, org_time, font, font_scale, color, thickness, cv2.LINE_AA)                    
                                # ~ cv2.imshow("Stereo Cameras with YOLO", combined_image)
                                # ~ end_time = time.time()
                                # ~ full_proc_time = current_time - end_time
                                # ~ print(f"Full Processing Time = {full_proc_time:.2f}")
                            # ~ else:
                                # ~ print("NO ANNOTATED PICS FOR YOU BIC BOI")
                                # ~ combined_image = np.hstack((image_cam1_bgr_down_scaled, image_cam0_bgr_down_scaled))                    
                                # ~ font = cv2.FONT_HERSHEY_SIMPLEX
                                # ~ font_scale = 1
                                # ~ color = (0, 0, 0)
                                # ~ thickness = 2
                                # ~ direction_str = str(sys_dir_letter) + " " + str(sys_direction)
                                # ~ dont_ask = "Lat: "
                                # ~ gps_str = str(dont_ask) + str(gps_lat) + " Long: " + str(gps_lng) + " Alt: " + str(gps_alt)
                                # ~ time_now = time.time()
                                # ~ time_elapsed = time_now - current_time
                                # ~ fps = 1.0 / time_elapsed
                                # ~ time_str = str(fps) + " FPS"
                                # ~ (text_width, text_height), baseline = cv2.getTextSize(direction_str, font, font_scale, thickness)
                                # ~ (text_width_gps, text_height_gps), baseline_gps = cv2.getTextSize(gps_str, font, font_scale, thickness)
                                # ~ (text_width_time, text_height_time), baseline_time = cv2.getTextSize(time_str, font, font_scale, thickness)
                                # ~ image_center_x = 1280
                                # ~ org_x = image_center_x - (text_width // 2)
                                # ~ org_y = 100
                                # ~ org = (org_x, org_y)
                                # ~ org_x_gps = image_center_x - (text_width_gps // 2)
                                # ~ org_y_gps = 50
                                # ~ org_gps = (org_x_gps, org_y_gps)
                                # ~ org_x_time = image_center_x - (text_width_time // 2)
                                # ~ org_y_time = 150
                                # ~ org_time = (org_x_time, org_y_time)
                                # ~ cv2.putText(combined_image, gps_str, org_gps, font, font_scale, color, thickness, cv2.LINE_AA)
                                # ~ cv2.putText(combined_image, direction_str, org, font, font_scale, color, thickness, cv2.LINE_AA)
                                # ~ cv2.putText(combined_image, time_str, org_time, font, font_scale, color, thickness, cv2.LINE_AA)                    
                                # ~ cv2.imshow("Stereo Cameras with YOLO", combined_image)
                                # ~ end_time = time.time()
                                # ~ full_proc_time = end_time - current_time
                                # ~ print(f"Full Processing Time = {full_proc_time:.2f}")
                            # ~ image_output_time = time.time()
                            # ~ true_output_time = image_output_time - current_time
                            # ~ image_output_str = str(true_output_time)
                            # ~ output_fps = 1.0 / true_output_time
                            # ~ image_output_str = f"FPS: {output_fps:.2f}"
                            # ~ add_data_to_file(camera_data_raw, f"{output_fps} " + time.strftime("%H:%M:%S"))
                            # ~ font = cv2.FONT_HERSHEY_SIMPLEX
                            # ~ font_scale = 1
                            # ~ color = (0, 0, 0)
                            # ~ thickness = 2
                            # ~ (text_width, text_height), baseline = cv2.getTextSize(image_output_str, font, font_scale, thickness)
                            # ~ imu_output_str = f"Direction: {sys_direction} {sys_dir_letter}"
                            # ~ gps_output_str = f"GPS Position: {gps_lat} N {gps_lng} W"
                            # ~ (imu_text_width, imu_text_height), baseline_imu = cv2.getTextSize(imu_output_str, font, font_scale, thickness)
                            # ~ (gps_text_width, gps_text_height), baseline_gps = cv2.getTextSize(gps_output_str, font, font_scale, thickness)
                            # ~ image_center = 1280
                            # ~ org_x = image_center - (text_width // 2)
                            # ~ org_y = 50
                            # ~ org = (org_x, org_y)
                            # ~ imu_org_x = image_center - (imu_text_width // 2)
                            # ~ imu_org_y = 80
                            # ~ imu_org = (imu_org_x, imu_org_y)
                            # ~ gps_org_x = image_center - (gps_text_width // 2)
                            # ~ gps_org_y = 110
                            # ~ gps_org = (gps_org_x, gps_org_y)
                            # ~ combined_image = np.hstack((image_cam1_bgr_down_scaled, image_cam0_bgr_down_scaled))
                            # ~ cv2.putText(combined_image, image_output_str, org, font, font_scale, color, thickness, cv2.LINE_AA)
                            # ~ cv2.putText(combined_image, imu_output_str, imu_org, font, font_scale, color, thickness, cv2.LINE_AA)
                            # ~ cv2.putText(combined_image, gps_output_str, gps_org, font, font_scale, color, thickness, cv2.LINE_AA)
                            # ~ cv2.imshow("Stereo Cameras with YOLO", combined_image)
                            # ~ cam_data_set_size += 1
                            #print(f"Cam FPS Data Points Collected: {cam_data_set_size}")  # Uncomment after demo
                        else:
                            print("NO PICS LOADED FOR YOU BIC BOI")
                        if cv2.waitKey(1) & 0xFF ==ord('q'):
                            break
                        time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping program.")
    finally:
        picam2_cam1.stop()
        picam2_cam0.stop()
        stop_capture_threads()
        stop_serial_reader()
        print(f"Total GPS Data Points Collected: {gps_data_set_size}")
        print(f"Total IMU Data Points Collected: {imu_data_set_size}")
        print(f"Total Cam Data Points Colelcted: {cam_data_set_size}")
        print("Program finished.")
