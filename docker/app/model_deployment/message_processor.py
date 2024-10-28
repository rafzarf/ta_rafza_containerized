import os
import time
import numpy as np
from paho.mqtt.client import Client
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import psycopg2

class MessageProcessor:
    def __init__(self):
        # Initialize MQTT client
        self.client = Client()
        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", 1883))
        self.mqtt_topic = os.getenv("MQTT_TOPIC", "vibration/data")

        # Initialize InfluxDB client
        self.influx_client = InfluxDBClient(
            url=os.getenv("INFLUXDB_URL"),
            token=os.getenv("INFLUXDB_ADMIN_TOKEN"),
            org=os.getenv("INFLUXDB_INIT_ORG")
        )
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)

        # Initialize PostgreSQL connection parameters
        self.pg_host = "postgres"
        self.pg_database = os.getenv("POSTGRES_DB")
        self.pg_user = os.getenv("POSTGRES_USER")
        self.pg_password = os.getenv("POSTGRES_PASSWORD")

    def connect_to_mqtt(self):
        """Connects to the MQTT broker and subscribes to the topic."""
        self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.client.subscribe(self.mqtt_topic)
        self.client.on_message = self.on_message
        print("Connected to MQTT broker and subscribed to topic.")

    def get_db_connection(self):
        """Establish a connection to PostgreSQL."""
        return psycopg2.connect(
            host=self.pg_host,
            database=self.pg_database,
            user=self.pg_user,
            password=self.pg_password
        )

    def store_anomaly_score(self, score):
        """Stores anomaly score in PostgreSQL."""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("INSERT INTO anomaly_scores (score) VALUES (%s)", (score,))
                    conn.commit()
                    print(f"Anomaly score {score} stored in PostgreSQL.")
        except Exception as e:
            print(f"Failed to store anomaly score: {e}")

    def write_to_influxdb(self, vibration_data):
        """Writes vibration data to InfluxDB."""
        try:
            point = Point("vibration").field("value", vibration_data)
            self.write_api.write(bucket=os.getenv("INFLUXDB_INIT_BUCKET"), record=point)
            print(f"Vibration data {vibration_data} written to InfluxDB.")
        except Exception as e:
            print(f"Failed to write to InfluxDB: {e}")

    def on_message(self, client, userdata, message):
        """Process incoming MQTT messages."""
        try:
            vibration_data = float(message.payload.decode())
            self.write_to_influxdb(vibration_data)
            
            # Generate anomaly score and route to PostgreSQL if necessary
            anomaly_score = np.random.random()  # Replace with real anomaly detection logic
            if anomaly_score > 0.8:  # Example threshold
                self.store_anomaly_score(anomaly_score)
                print(f"High anomaly detected: {anomaly_score}")

        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    def run(self):
        """Start processing messages."""
        self.connect_to_mqtt()
        self.client.loop_forever()
