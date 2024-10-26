import time
import os
from vibration_sensor import VibrationSensor
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

def run_esp32_simulator():
    # InfluxDB connection details
    url = os.environ.get('INFLUXDB_URL')
    token = os.environ.get('INFLUXDB_ADMIN_TOKEN')
    org = os.environ.get('INFLUXDB_INIT_ORG')
    bucket = os.environ.get('INFLUXDB_INIT_BUCKET')

    client = InfluxDBClient(url=url, token=token, org=org)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    sensor = VibrationSensor()

    while True:
        vibration = sensor.get_reading()
        point = Point("vibration").field("value", vibration)
        write_api.write(bucket=bucket, org=org, record=point)
        print(f"Sent vibration data: {vibration}")
        time.sleep(1)

if __name__ == "__main__":
    run_esp32_simulator()
