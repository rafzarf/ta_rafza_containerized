import os
import numpy as np
from paho.mqtt.client import Client
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import psycopg2

class MQTTProcessor:
    def __init__(self):
        self.client = Client()
        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", 1883))
        self.mqtt_topic = os.getenv("MQTT_TOPIC", "vibration/data")

        # InfluxDB setup
        self.influx_client = InfluxDBClient(
            url=os.getenv("INFLUXDB_URL"),
            token=os.getenv("INFLUXDB_ADMIN_TOKEN"),
            org=os.getenv("INFLUXDB_INIT_ORG")
        )
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)

    def connect_to_mqtt(self):
        self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.client.subscribe(self.mqtt_topic)
        self.client.on_message = self.on_message

    def write_to_influxdb(self, vibration_data):
        try:
            point = Point("vibration").field("value", vibration_data)
            self.write_api.write(bucket=os.getenv("INFLUXDB_INIT_BUCKET"), record=point)
        except Exception as e:
            print(f"Failed to write to InfluxDB: {e}")

    def on_message(self, client, userdata, message):
        try:
            vibration_data = float(message.payload.decode())
            self.write_to_influxdb(vibration_data)

            # Generate an anomaly score (placeholder logic)
            anomaly_score = np.random.random()
            if anomaly_score > 0.8:
                print(f"High anomaly detected: {anomaly_score}")
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    def run(self):
        self.connect_to_mqtt()
        self.client.loop_forever()

if __name__ == '__main__':
    processor = MQTTProcessor()
    processor.run()
