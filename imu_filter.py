# imu_filter.py
import ahrs
import numpy as np
import statistics
class IMUFilter:
	def __init__(self, sample_rate, beta_value=0.041):
		self.dt = 1.0 / sample_rate
		self.madgwick_filter = ahrs.Madgwick(gain=beta_value, per_fusion=False)
		self.quaternion = np.array([1.0, 0.0, 0.0, 0.0])
		self.roll_history = []
		self.pitch_history = []
		self.yaw_history = []
		self.current_angles = {'roll': None, 'pitch': None, 'yaw': None}
	def remap_bno055_axes(self, acc, gyr, mag):
		new_acc = np.array([-acc, -acc, acc], dtype=float)
		new_gyr = np.array([-gyr, -gyr, gyr], dtype=float)
		new_mag = np.array([-mag, -mag, mag], dtype=float)
		return new_acc, new_gyr, new_mag
	def update(self, raw_acc, raw_gyr, raw_mag):
		mapped_acc, mapped_gyr, mapped_mag = self.remap_bno055_axes(raw_acc, raw_gyr, raw_mag)
		self.quaternion = self.madgwick_filter.update(q=self.quaternion, acc=mapped_acc, gyr=mapped_gyr, mag=mapped_mag, dt=self.dt)
		roll, pitch, yaw = ahrs.common.orientation.q2euler(self.quaternion, degrees=True)
		if yaw < 0:
			yaw += 360
		self.current_angles = {'roll': roll, 'pitch': pitch, 'yaw': yaw}
		self.roll_history.append(roll)
		self.pitch_history.append(pitch)
		self.yaw_history.append(yaw)
		return self.current_angles
	def get_stable_angles(self, num_samples=5):
		if len(self.yaw_history) < num_samples:
			return None
		stable_roll = statistics.median(self.roll_history[-num_samples:])
		stable_pitch = statistics.median(self.pitch_history[-num_samples:])
		stable_yaw = statistics.median(self.yaw_history[-num_samples:])
		return {'roll': stable_roll, 'pitch': stable_pitch, 'yaw': stable_yaw}
