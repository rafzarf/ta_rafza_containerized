import os
import threading
import time
from flask import Flask, jsonify
from influxdb_client import InfluxDBClient
import psycopg2
import paho.mqtt.client as mqtt
from vibration_sensor import VibrationSensor
from prediction_api import app as prediction_app

app = Flask(__name__)

# InfluxDB connection
influx_client = InfluxDBClient(
    url=os.environ.get('INFLUXDB_URL'),
    token=os.environ.get('INFLUXDB_ADMIN_TOKEN'),
    org=os.environ.get('INFLUXDB_INIT_ORG')
)

# PostgreSQL connection
def get_db_connection():
    conn = psycopg2.connect(
        host="postgres",
        database=os.environ.get('POSTGRES_DB'),
        user=os.environ.get('POSTGRES_USER'),
        password=os.environ.get('POSTGRES_PASSWORD')
    )
    return conn

@app.route('/')
def home():
    return jsonify(message="Hello from Flask mock app!")

@app.route('/db-check')
def db_check():
    influx_health = influx_client.health()
    
    pg_conn = get_db_connection()
    pg_cursor = pg_conn.cursor()
    pg_cursor.execute('SELECT version();')
    pg_version = pg_cursor.fetchone()[0]
    pg_cursor.close()
    pg_conn.close()

    return jsonify({
        "influxdb_status": influx_health.status,
        "postgres_version": pg_version
    })

def run_esp32_simulator():
    max_retries = 5
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            client = mqtt.Client()
            client.connect("mosquitto", 1883, 60)
            
            sensor = VibrationSensor()

            while True:
                vibration = sensor.get_reading()
                client.publish("vibration/data", str(vibration))
                print(f"Published vibration data: {vibration}")
                time.sleep(1)
        except Exception as e:
            print(f"Error in ESP32 simulator: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Max retries reached. Exiting ESP32 simulator.")
                break

if __name__ == '__main__':
    # Start ESP32 simulator in a separate thread
    simulator_thread = threading.Thread(target=run_esp32_simulator)
    simulator_thread.start()

    # Run both Flask apps
    main_port = int(os.environ.get('FLASK_MAIN_PORT', 5000))
    prediction_port = int(os.environ.get('FLASK_PREDICTION_PORT', 5001))

    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=main_port, debug=False, use_reloader=False)).start()
    prediction_app.run(host='0.0.0.0', port=prediction_port, debug=False, use_reloader=False)
