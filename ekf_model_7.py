# ekf_model_7.py

######################################################################

# THIS CODE IS MAINLY PRODUCED BY AI as the EKF Algorithm is Complex

######################################################################
# Standard Library Imports
import numpy as np
from filterpy.kalman import ExtendedKalmanFilter
from scipy.spatial.transform import Rotation as R
from math import radians, cos

#########################################################
# Helper Functions for Coordinate Conversion
class CoordinateConverter:
    def __init__(self, lat0, lon0, alt0):
        self.lat0 = radians(lat0)
        self.lon0 = radians(lon0)
        self.alt0 = alt0
        self.R_earth = 6378137.0

    def lla_to_ned(self, lat, lon, alt):
        lat_rad = radians(lat)
        lon_rad = radians(lon)
        
        d_lat = lat_rad - self.lat0
        d_lon = lon_rad - self.lon0
        
        N = self.R_earth * d_lat
        E = self.R_earth * d_lon * cos(self.lat0)
        D = -(alt - self.alt0)
        
        return np.array([N, E, D])

#########################################################
# EKF Class for IMU-GPS Fusion
class IMUGPS_EKF:
    def __init__(self, initial_state, initial_covariance, reference_lla):
        # State vector size: [px, py, pz, vx, vy, vz, qw, qx, qy, qz, bax, bay, baz, bgx, bgy, bgz, bmx, bmy, bmz]
        self.ekf = ExtendedKalmanFilter(dim_x=19, dim_z=3)
        self.ekf.x = np.array(initial_state)
        self.ekf.P = initial_covariance
        
        self.ekf.Q = np.diag([
            1e-3, 1e-3, 1e-3,  # Position
            1e-3, 1e-3, 1e-3,  # Velocity
            1e-3, 1e-3, 1e-3, 1e-3,  # Orientation (quat)
            1e-4, 1e-4, 1e-4,  # Accel bias
            1e-5, 1e-5, 1e-5,  # Gyro bias
            1e-4, 1e-4, 1e-4,  # Mag bias
        ])
        
        self.ekf.R = np.diag([1.0, 1.0, 1.0])
        
        self.gravity = np.array([0.0, 0.0, 9.81])
        self.coord_converter = CoordinateConverter(*reference_lla)
        
    def predict(self, dt, accel, gyro):
        """Propagate state forward using IMU readings (manual for older filterpy)."""
        
        # Unpack state for easier reading
        pos = self.ekf.x[0:3]
        vel = self.ekf.x[3:6]
        quat = R.from_quat(self.ekf.x[6:10])
        accel_bias = self.ekf.x[10:13]
        gyro_bias = self.ekf.x[13:16]
        biases = self.ekf.x[10:19]
        
        accel_comp = accel - accel_bias
        gyro_comp = gyro - gyro_bias
        
        # Rotate accel from body to NED frame using SciPy
        accel_ned = quat.apply(accel_comp)
        accel_ned -= self.gravity
        
        # Manually compute the predicted state (f(x, u, dt))
        new_pos = pos + vel * dt + 0.5 * accel_ned * dt**2
        new_vel = vel + accel_ned * dt
        
        # Update orientation using SciPy's composition
        rotation_vector = gyro_comp * dt
        new_quat = (R.from_rotvec(rotation_vector) * quat).as_quat()
        
        # Assign the new state to the ekf object
        self.ekf.x = np.concatenate((new_pos, new_vel, new_quat, biases))
        
        # Manually compute the Jacobian of the state transition (F)
        F = np.eye(19)
        F[0:3, 3:6] = np.eye(3) * dt
        
        # Update the covariance matrix (P)
        self.ekf.P = F @ self.ekf.P @ F.T + self.ekf.Q
        
    def update_gps(self, lat, lon, alt, sats, hdop):
        """Update state using GPS measurements."""
        z = self.coord_converter.lla_to_ned(lat, lon, alt)
        
        # Define hx and Hx functions for the update call
        def h_gps(x):
            return x[0:3]
        
        def H_gps_jacobian(x):
            H = np.zeros((3, 19))
            H[0:3, 0:3] = np.eye(3)
            return H
            
        hdop_scale = max(1.0, hdop)
        num_sat_scale = 1.0 if sats >= 4 else 10.0
        tuned_R = self.ekf.R * hdop_scale * num_sat_scale
        
        # Corrected 1.4.5 update call using positional arguments
        self.ekf.update(z, H_gps_jacobian, h_gps, R=tuned_R)
        
    def update_magnetometer(self, mag, mag_cal_status):
        """Update state using Magnetometer measurements."""
        def h_mag(x):
            quat = R.from_quat(x[6:10])
            mag_bias = x[16:19]
            mag_field_ned = np.array([0.23, 0.0, -0.42])
            
            mag_pred_body = quat.inv().apply(mag_field_ned)
            return mag_pred_body + mag_bias
        
        def H_mag_jacobian(x):
            H = np.zeros((3, 19))
            return H
            
        cal_scale = 1.0 / (mag_cal_status + 1)
        tuned_R = self.ekf.R * cal_scale
        
        # Corrected 1.4.5 update call using positional arguments
        self.ekf.update(mag, H_mag_jacobian, h_mag, R=tuned_R)
        
    def update_accelerometer(self, accel, accel_cal_status):
        def h_accel(x):
            quat = R.from_quat(x[6:10])
            accel_bias = x[10:13]
            return quat.inv().apply(self.gravity) + accel_bias
        
        def H_accel_jacobian(x):
            H = np.zeros((3,19))
            return H
        
        cal_scale = 1.0 /(accel_cal_status + 1)
        tuned_R = self.ekf.R * cal_scale
        
        self.ekf.update(accel, H_accel_jacobian, h_accel, R=tuned_R)
        
    def get_euler_angles(self):
            quat = R.from_quat(self.ekf.x[6:10])
            return quat.as_euler('zyx', degrees=False)

#########################################################
