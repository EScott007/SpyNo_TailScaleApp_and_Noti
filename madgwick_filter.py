import ahrs
import numpy as np
import time
import math
import statistics
sample_rate = 1.0
dt = 1.0 / sample_rate
beta_value = 0.041
madgwick_filter = ahrs.filters.Madgwick(gain=beta_value, per_fusion=False)
quaternion = np.array([1.0, 0.0, 0.0, 0.0])
headings = []
def remap_bno055_axes(acc, gyr, mag):
	new_acc = np.array([-acc[1], -acc[0], acc[2]])
	new_gyr = np.array([-gyr[1], -gyr[0], gyr[2]])
	new_mag = np.array([-mag[1], -mag[0], mag[2]])
	return new_acc, new_gyr, new_mag
def process_sensor_data(raw_acc, raw_gyr, raw_mag):
	global quaternion
	mapped_acc, mapped_gyr, mapped_mag = remap_bno055_axes(raw_acc, raw_gyr, raw_mag)
	quaternion = madgwick_filter.update(q=quaternion, acc=mapped_acc, gyr=mapped_gyr, mag=mapped_mag, dt=dt)
	euler_angles = ahrs.common.orientation.q2euler(quaternion, degrees=True)
	yaw = euler_angles[2]
	if yaw < 0:
		yaw += 360
	headings.append(yaw)
	print(f"Current System Headings: {yaw:.2f} degrees")
	return yaw
