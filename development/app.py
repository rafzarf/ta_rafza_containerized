import os
from flask import Flask, jsonify
from influxdb_client import InfluxDBClient
import psycopg2

# Initialize the Flask application
app = Flask(__name__)

# InfluxDB connection
influx_client = InfluxDBClient(
    url="http://influxdb:8086",
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

# Define a simple route
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

# If this file is executed directly, run the Flask application
if __name__ == '__main__':
    # Use host 0.0.0.0 to ensure it's accessible outside the container
    app.run(host='0.0.0.0', port=int(os.environ.get('FLASK_PORT', 5000)))
