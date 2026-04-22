# serial_reader_2.py

######################################################

# Author: Jordan Carver

######################################################
import serial
import sys
import threading
import time
serial_port = '/dev/ttyUSB0'
baud_rate = 115200
ser = None
data_raw = None
data_lock = threading.Lock()
stop_thread = threading.Event()
reader_thread = None
def _serial_reader_thread():
    global ser
    global data_raw
    try:
        ser = serial.Serial(serial_port, baud_rate, timeout=1)
        print(f"Serial reader thread connected to ESP32 on {serial_port}")
        while not stop_thread.is_set():
            line = ser.readline().decode('utf-8').strip()
            if line.startswith('<') and line.endswith('>'):
                data_string = line[1:-1]
                data_values = data_string.split(',')
                if len(data_values) == 23:
                    with data_lock:
                        data_raw = data_values
    except serial.SerialException as e:
        print(f"Serial reader thread error: {e}", file=sys.stderr)
        ser = None
    finally:
        if ser and ser.is_open:
            ser.close()
        print("Serial reader thread finished.")
def get_latest_sensor_data():
    with data_lock:
        if data_raw:
            return data_raw.copy()
        return None
def stop_serial_reader():
    stop_thread.set()
    if reader_thread and reader_thread.is_alive():
        reader_thread.join()
reader_thread = threading.Thread(target=_serial_reader_thread, daemon=True)
reader_thread.start()
