import time
import os
import threading
import paho.mqtt.client as mqtt
import numpy as np
from influxdb_client import InfluxDBClient, Point, WritePrecision
import json

# InfluxDB configuration
influxdb_url = os.getenv('INFLUXDB_URL')
influxdb_org = os.getenv('INFLUXDB_INIT_ORG')
influxdb_bucket = os.getenv('INFLUXDB_INIT_BUCKET')
influxdb_token = os.getenv('INFLUXDB_ADMIN_TOKEN')

# Explicit MQTT topic declarations
MQTT_BROKER = os.getenv('MQTT_BROKER')
MQTT_PORT = int(os.getenv('MQTT_PORT'))
MQTT_TOPIC_3AXIS = os.getenv('MQTT_TOPIC_3AXIS', 'sensors/accelerometer_3axis')
MQTT_TOPIC_1AXIS = os.getenv('MQTT_TOPIC_1AXIS', 'sensors/accelerometer_1axis')

# Create InfluxDB client
influx_client = InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)

# Accelerometer Simulation with 3-Axis at 5000 Hz
class Accelerometer3Axis:
    def __init__(self, normal_mean=0, normal_std=1, anomaly_probability=0.1):
        self.normal_mean = normal_mean
        self.normal_std = normal_std
        self.anomaly_probability = anomaly_probability

    def get_reading(self):
        if np.random.random() < self.anomaly_probability:
            return {
                "x": np.random.normal(self.normal_mean + 5, self.normal_std * 2),
                "y": np.random.normal(self.normal_mean + 5, self.normal_std * 2),
                "z": np.random.normal(self.normal_mean + 5, self.normal_std * 2)
            }
        else:
            return {
                "x": np.random.normal(self.normal_mean, self.normal_std),
                "y": np.random.normal(self.normal_mean, self.normal_std),
                "z": np.random.normal(self.normal_mean, self.normal_std)
            }

# Accelerometer Simulation with 1-Axis at 2000 Hz
class Accelerometer1Axis:
    def __init__(self, normal_mean=0, normal_std=1, anomaly_probability=0.1):
        self.normal_mean = normal_mean
        self.normal_std = normal_std
        self.anomaly_probability = anomaly_probability

    def get_reading(self):
        if np.random.random() < self.anomaly_probability:
            return np.random.normal(self.normal_mean + 5, self.normal_std * 2)
        else:
            return np.random.normal(self.normal_mean, self.normal_std)

# Instantiate sensors
sensor_3axis = Accelerometer3Axis()
sensor_1axis = Accelerometer1Axis()

# MQTT Publisher for 3-Axis Accelerometer
def mqtt_publisher_3axis():
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        return

    client.loop_start()  # Start MQTT loop in the background

    while True:
        reading = sensor_3axis.get_reading()
        client.publish(MQTT_TOPIC_3AXIS, json.dumps(reading))
        print(f"Published 3-axis data to MQTT: {reading}")
        time.sleep(0.2)  # 5 Hz

# MQTT Publisher for 1-Axis Accelerometer
def mqtt_publisher_1axis():
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        return

    client.loop_start()  # Start MQTT loop in the background

    while True:
        reading = sensor_1axis.get_reading()
        client.publish(MQTT_TOPIC_1AXIS, json.dumps({"value": reading}))
        print(f"Published 1-axis data to MQTT: {reading}")
        time.sleep(0.5)  # 2 Hz

# MQTT Subscriber to InfluxDB
def mqtt_subscriber():
    client = mqtt.Client()
    client.on_connect = lambda c, u, f, rc: [
        client.subscribe(MQTT_TOPIC_3AXIS),
        client.subscribe(MQTT_TOPIC_1AXIS)
    ]
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        return

    client.loop_start()  # Start the loop to process incoming messages

    while True:
        time.sleep(1)

# Process and Write to InfluxDB
def on_message(client, userdata, message):
    topic = message.topic
    payload = json.loads(message.payload.decode())

    if topic == MQTT_TOPIC_3AXIS:
        write_to_influxdb(payload, "vibration_3axis")
    elif topic == MQTT_TOPIC_1AXIS:
        write_to_influxdb(payload, "vibration_1axis")

def write_to_influxdb(data, measurement):
    try:
        if measurement == "vibration_3axis":
            data_point = Point(measurement) \
                .field("x", float(data["x"])) \
                .field("y", float(data["y"])) \
                .field("z", float(data["z"])) \
                .time(time.time_ns(), WritePrecision.NS)
        else:
            data_point = Point(measurement) \
                .field("value", float(data["value"])) \
                .time(time.time_ns(), WritePrecision.NS)

        write_api = influx_client.write_api()
        write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=data_point)
        print(f"Written to InfluxDB [{measurement}]: {data}")

    except ValueError as e:
        print(f"Error writing data to InfluxDB: {e}")

if __name__ == "__main__":
    # Create threads for publishers and subscriber
    publisher_3axis_thread = threading.Thread(target=mqtt_publisher_3axis)
    publisher_1axis_thread = threading.Thread(target=mqtt_publisher_1axis)
    subscriber_thread = threading.Thread(target=mqtt_subscriber)

    # Start the threads
    publisher_3axis_thread.start()
    publisher_1axis_thread.start()
    subscriber_thread.start()

    # Join threads to the main thread
    publisher_3axis_thread.join()
    publisher_1axis_thread.join()
    subscriber_thread.join()
