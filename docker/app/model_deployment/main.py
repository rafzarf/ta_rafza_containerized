import os
import sys
import threading
from flask import Flask, jsonify
from influxdb_client import InfluxDBClient
import psycopg2
from prediction_api import app as prediction_app

# Add the sensor_simulator directory to the Python path
sys.path.append('/sensor_simulator')

from vibration_sensor import VibrationSensor

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

if __name__ == '__main__':
    main_port = int(os.environ.get('FLASK_MAIN_PORT', 5000))
    prediction_port = int(os.environ.get('FLASK_PREDICTION_PORT', 5001))

    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=main_port, debug=False, use_reloader=False)).start()
    prediction_app.run(host='0.0.0.0', port=prediction_port, debug=False, use_reloader=False)
