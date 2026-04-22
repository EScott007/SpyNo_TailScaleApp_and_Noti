import cv2
import numpy as np
import glob
import pickle
######################################################################################

# THIS CODE IS MAINLY PRODUCED BY AI as the Rectification Process has Been Done Before

######################################################################################
BOARD_WIDTH = 8
BOARD_HEIGHT = 7
SQUARE_SIZE = 10.5
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
objp = np.zeros((BOARD_HEIGHT * BOARD_WIDTH, 3), np.float32)
objp[:, :2] = np.mgrid[0:BOARD_WIDTH, 0:BOARD_HEIGHT].T.reshape(-1, 2) * SQUARE_SIZE
objpoints = [] 
imgpoints_left = []
imgpoints_right = []
left_images = sorted(glob.glob('calibration_images/left_*.png'))
right_images = sorted(glob.glob('calibration_images/right_*.png'))
if not left_images or not right_images:
    print("Error: No calibration images found in the 'calibration_images' folder.")
    exit()
print(f"Found {len(left_images)} image pairs for calibration.")
for left_img_path, right_img_path in zip(left_images, right_images):
    img_left = cv2.imread(left_img_path)
    img_right = cv2.imread(right_img_path)
    gray_left = cv2.cvtColor(img_left, cv2.COLOR_BGR2GRAY)
    gray_right = cv2.cvtColor(img_right, cv2.COLOR_BGR2GRAY)
    h, w = gray_left.shape[:2]
    ret_left, corners_left = cv2.findChessboardCorners(gray_left, (BOARD_WIDTH, BOARD_HEIGHT), None)
    ret_right, corners_right = cv2.findChessboardCorners(gray_right, (BOARD_WIDTH, BOARD_HEIGHT), None)
    if ret_left and ret_right:
        objpoints.append(objp)
        cv2.cornerSubPix(gray_left, corners_left, (11, 11), (-1, -1), criteria)
        imgpoints_left.append(corners_left)
        cv2.cornerSubPix(gray_right, corners_right, (11, 11), (-1, -1), criteria)
        imgpoints_right.append(corners_right)
        # cv2.drawChessboardCorners(img_left, (BOARD_WIDTH, BOARD_HEIGHT), corners_left, ret_left)
        # cv2.imshow('Left Corners', cv2.resize(img_left, (w//2, h//2)))
        # cv2.waitKey(10)
    else:
        print(f"Corners not found in one or both images: {left_img_path}, {right_img_path}")
# cv2.destroyAllWindows()
print("Starting individual camera calibration...")
ret_l, mtx_l, dist_l, rvecs_l, tvecs_l = cv2.calibrateCamera(
    objpoints, imgpoints_left, (w, h), None, None)
ret_r, mtx_r, dist_r, rvecs_r, tvecs_r = cv2.calibrateCamera(
    objpoints, imgpoints_right, (w, h), None, None)
print(f"Left camera error: {ret_l}, Right camera error: {ret_r}")
print("\nStarting stereo calibration...")
stereocalib_criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-5)
stereocalib_flags = cv2.CALIB_FIX_INTRINSIC 
ret_stereo, CM1, dist1, CM2, dist2, R, T, E, F = cv2.stereoCalibrate(
    objpoints, imgpoints_left, imgpoints_right, 
    mtx_l, dist_l, mtx_r, dist_r, (w, h), criteria=stereocalib_criteria, flags=stereocalib_flags)
print(f"Stereo calibration reprojection error: {ret_stereo}")
R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
    CM1, dist1, CM2, dist2, (w, h), R, T, alpha=1) # alpha=1 gives full image view
left_map_x, left_map_y = cv2.initUndistortRectifyMap(CM1, dist1, R1, P1, (w, h), cv2.CV_32FC1)
right_map_x, right_map_y = cv2.initUndistortRectifyMap(CM2, dist2, R2, P2, (w, h), cv2.CV_32FC1)
calibration_data = {
    "CM1": CM1, "dist1": dist1, "CM2": CM2, "dist2": dist2,
    "R": R, "T": T, "E": E, "F": F,
    "R1": R1, "R2": R2, "P1": P1, "P2": P2, "Q": Q,
    "left_map_x": left_map_x, "left_map_y": left_map_y,
    "right_map_x": right_map_x, "right_map_y": right_map_y,
    "roi1": roi1, "roi2": roi2}
with open("stereo_calibration.pkl", "wb") as f:
    pickle.dump(calibration_data, f)
print("\nCalibration successful and parameters saved to 'stereo_calibration.pkl'")
print("\n--- Key Extrinsic Results ---")
print("Rotation Matrix (R, left to right):\n", R)
print("Translation Vector (T, left to right, in your SQUARE_SIZE units):\n", T)
print("\n--- Key Rectification Results ---")
print("New Left Projection Matrix (P1):\n", P1)
print("New Right Projection Matrix (P2):\n", P2)
print("Disparity-to-Depth Mapping Matrix (Q):\n", Q)
