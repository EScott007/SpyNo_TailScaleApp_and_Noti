import cv2
import time
import os
import numpy as np
from picamera2 import Picamera2
######################################################################################

# THIS CODE IS MAINLY PRODUCED BY AI as the Rectification Process has Been Done Before

######################################################################################
BOARD_WIDTH = 8
BOARD_HEIGHT = 7
output_dir = "calibration_images"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
capture_width = 3840
capture_height = 2160
picam_left = Picamera2(0) 
picam_right = Picamera2(1) 
config_left = picam_left.create_preview_configuration(
    main={"size": (capture_width, capture_height), "format": "BGR888"},
    lores={"size": (640, 480), "format": "YUV420"})
picam_left.configure(config_left)
config_right = picam_right.create_preview_configuration(
    main={"size": (capture_width, capture_height), "format": "BGR888"},
    lores={"size": (640, 480), "format": "YUV420"})
picam_right.configure(config_right)
picam_left.start()
picam_right.start()
print("Cameras started. Press 'c' to capture image pair, 'q' to quit.")
img_count = 0
while True:
    frame_left = picam_left.capture_array("main")
    frame_right = picam_right.capture_array("main")
    display_left = cv2.resize(frame_left, (int(capture_width/2), int(capture_height/2)))
    display_right = cv2.resize(frame_right, (int(capture_width/2), int(capture_height/2)))
    combined_frame = cv2.hconcat([display_left, display_right])
    cv2.imshow("Stereo Feed (Resized for Display)", combined_frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('c'):
        left_path = os.path.join(output_dir, f"left_{img_count:02d}.png")
        right_path = os.path.join(output_dir, f"right_{img_count:02d}.png")
        cv2.imwrite(left_path, frame_left)
        cv2.imwrite(right_path, frame_right)
        print(f"Captured image pair {img_count} at {capture_width}x{capture_height}")
        img_count += 1
        time.sleep(0.5)
    elif key == ord('q'):
        break
picam_left.stop()
picam_right.stop()
cv2.destroyAllWindows()
