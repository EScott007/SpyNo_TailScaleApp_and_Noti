# imu_filter.py
import ahrs
import numpy as np
import statistics
import threading
import time
from serial_reader_2 import get_latest_sensor_data, stop_serial_reader
class IMUFilter:
    def __init__(self, sample_rate, beta_value=0.041, required_samples=15):
        self.dt = 1.0 / sample_rate
        self.madgwick_filter = ahrs.filters.Madgwick(gain=beta_value, per_fusion=False)
        self.quaternion = np.array([1.0, 0.0, 0.0, 0.0])
        self.roll_history = []
        self.pitch_history = []
        self.yaw_history = []
        self.required_samples = required_samples
        self.lock = threading.Lock()
        self.data_ready_event = threading.Event()
        self.thread = None
        self.is_running = False
    def remap_bno055_axes(self, acc, gyr, mag):
        new_acc = np.array([-acc, -acc, acc], dtype=float)
        new_gyr = np.array([-gyr, -gyr, gyr], dtype=float)
        new_mag = np.array([-mag, -mag, mag], dtype=float)
        return new_acc, new_gyr, new_mag
    def _sensor_reading_loop(self):
        print(f"Filter thread started. Collecting {self.required_samples} samples...")
        while len(self.yaw_history) < self.required_samples:
            start_time = time.time()
            sensor_data = get_latest_sensor_data()
            if sensor_data:
                gps_lat, gps_lng, gps_alt, gps_sats, gps_hdop = (float(sensor_data[0]), float(sensor_data[1]), float(sensor_data[2]), int(sensor_data[3]), float(sensor_data[4]))
                accel_x, accel_y, accel_z = map(float, sensor_data[5:8])
                gyro_x, gyro_y, gyro_z = map(float, sensor_data[8:11])
                mag_x, mag_y, mag_z = map(float, sensor_data[11:14])
                accel_cal, mag_cal, gyro_cal = map(int, sensor_data[14:17])
                add_data_to_file(gps_imu_file, f"GPS Lat: {gps_lat}, GPS Lng: {gps_lng}, GPS Alt: {gps_alt}, # of Sats: {gps_sats}, GPS HDOP: {gps_hdop}, IMU Accel X: {accel_x}, IMU Accel Y: {accel_y}, IMU Accel Z: {accel_z}, IMU Accel Cal: {accel_cal}, IMU Gyro X: {gyro_x}, IMU Gyro Y: {gyro_y}, IMU Gyro Z: {gyro_z}, IMU Gyro Cal: {gyro_cal}, IMU Mag X: {mag_x}, IMU Mag Y: {mag_y}, IMU Mag Z: {mag_z}, IMU Mag Cal: {mag_cal} " + time.strftime("%H:%M:%S"))
            accel_data = np.array([accel_x, accel_y, accel_z], dtype=float)
                    gyro_data = np.array([gyro_x, gyro_y, gyro_z], dtype=float)
                    mag_data = np.array([mag_x, mag_y, mag_z], dtype=float)
            with self.lock:
                mapped_acc, mapped_gyr, mapped_mag = self.remap_bno055_axes(raw_accel_data, raw_gyro_data, raw_mag_data)
                self.quaternion = self.madgwick_filter.update(q=self.quaternion, acc=mapped_acc, gyr=mapped_gyr, mag=mapped_mag, dt=self.dt)
                roll, pitch, yaw = ahrs.common.orientation.q2euler(self.quaternion, degrees=True)
                if yaw < 0: yaw += 360
                self.roll_history.append(roll)
                self.pitch_history.append(pitch)
                self.yaw_history.append(yaw)
                print(f"Sample {len(self.yaw_history)} collected.")
            elapsed_time = time.time() - start_time
            sleep_time = max(0, self.dt - elapsed_time)
            time.sleep(sleep_time)
        self.data_ready_event.set()
        self.is_running = False
        print("Filter thread finished data collection.")
    def start_collection_async(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._sensor_reading_loop)
            self.thread.start()
    def wait_for_completion_and_get_stable_angles(self, num_samples=5):
        print(f"Main thread waiting for filter data collection ({self.required_samples} samples)...")
        self.data_ready_event.wait()
        with self.lock:
            if len(self.yaw_history) >= num_samples:
                stable_roll = statistics.median(self.roll_history[-num_samples:])
                stable_pitch = statistics.median(self.pitch_history[-num_samples:])
                stable_yaw = statistics.median(self.yaw_history[-num_samples:])
                return {'roll': stable_roll, 'pitch': stable_pitch, 'yaw': stable_yaw}
            else:
                return None
