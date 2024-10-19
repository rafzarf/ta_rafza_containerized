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

def get_db_connection():
    """
    Establishes a connection to the PostgreSQL database.
    
    Purpose: To provide a reusable function for connecting to the database,
    ensuring consistent connection parameters across the application.
    """
    conn = psycopg2.connect(
        host="postgres",
        database=os.environ.get('POSTGRES_DB'),
        user=os.environ.get('POSTGRES_USER'),
        password=os.environ.get('POSTGRES_PASSWORD')
    )
    return conn

@app.route('/')
def home():
    """
    Defines the root endpoint of the Flask application.
    
    Purpose: To provide a simple health check and confirm that the Flask app is running.
    """
    return jsonify(message="Hello from Flask mock app!")

@app.route('/db-check')
def db_check():
    """
    Checks the status of both InfluxDB and PostgreSQL databases.
    
    Purpose: To ensure that the application can connect to and interact with both 
    databases, providing a quick way to verify database connectivity.
    """
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
    """
    Simulates an ESP32 device publishing vibration data to an MQTT broker.
    
    Purpose: To generate mock vibration data for testing and development purposes
    when a physical ESP32 device is not available. It implements retry logic to
    handle potential connection issues with the MQTT broker.
    """
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
    """
    Main entry point of the application.
    
    Purpose: To start the ESP32 simulator in a separate thread and run both Flask 
    applications (main and prediction) concurrently. This allows the system to 
    simulate data generation, process incoming requests, and make predictions 
    simultaneously.
    """
    # Start ESP32 simulator in a separate thread
    simulator_thread = threading.Thread(target=run_esp32_simulator)
    simulator_thread.start()

    # Run both Flask apps
    main_port = int(os.environ.get('FLASK_MAIN_PORT', 5000))
    prediction_port = int(os.environ.get('FLASK_PREDICTION_PORT', 5001))

    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=main_port, debug=False, use_reloader=False)).start()
    prediction_app.run(host='0.0.0.0', port=prediction_port, debug=False, use_reloader=False)
