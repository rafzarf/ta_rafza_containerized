import os
import json
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient

# InfluxDB configuration
influxdb_url = os.getenv('INFLUXDB_URL', 'http://influxdb:8086')
influxdb_org = os.getenv('INFLUXDB_INIT_ORG', 'polman_bdg')
influxdb_bucket = os.getenv('INFLUXDB_INIT_BUCKET', 'ta_rafza')
influxdb_token = os.getenv('INFLUXDB_ADMIN_TOKEN')

# Create InfluxDB client
client = InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with result code " + str(rc))
    client.subscribe(os.getenv('MQTT_TOPIC', 'vibration/data'))

def on_message(client, userdata, msg):
    # Parse the message
    data = msg.payload.decode()
    print(f"Received message: {data}")

    # Prepare data for InfluxDB
    json_body = [
        {
            "measurement": "vibration",
            "fields": {
                "value": float(data)  # Assuming the data is a float
            }
        }
    ]

    # Write data to InfluxDB
    client.write_points(json_body, bucket=influxdb_bucket)

def run_mqtt_to_influxdb():
    mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
    mqtt_port = int(os.getenv('MQTT_PORT', 1883))

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect(mqtt_broker, mqtt_port, 60)
    mqtt_client.loop_forever()

if __name__ == "__main__":
    run_mqtt_to_influxdb()
