import numpy as np
import time

class VibrationSensor:
    def __init__(self, normal_mean=0, normal_std=1, anomaly_probability=0.1):
        self.normal_mean = normal_mean
        self.normal_std = normal_std
        self.anomaly_probability = anomaly_probability

    def get_reading(self):
        if np.random.random() < self.anomaly_probability:
            # Simulate an anomaly
            return np.random.normal(self.normal_mean + 5, self.normal_std * 2)
        else:
            # Normal reading
            return np.random.normal(self.normal_mean, self.normal_std)

if __name__ == "__main__":
    sensor = VibrationSensor()
    while True:
        print(f"Vibration reading: {sensor.get_reading()}")
        time.sleep(1)

