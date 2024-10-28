import os
from flask import Flask, jsonify
from influxdb_client import InfluxDBClient
import psycopg2

app = Flask(__name__)

# InfluxDB configuration
influx_client = InfluxDBClient(
    url=os.environ.get('INFLUXDB_URL'),
    token=os.environ.get('INFLUXDB_ADMIN_TOKEN'),
    org=os.environ.get('INFLUXDB_INIT_ORG')
)

# PostgreSQL connection function
def get_db_connection():
    """Establishes a PostgreSQL database connection."""
    return psycopg2.connect(
        host="postgres",
        database=os.environ.get('POSTGRES_DB'),
        user=os.environ.get('POSTGRES_USER'),
        password=os.environ.get('POSTGRES_PASSWORD')
    )

# Health check endpoint
@app.route('/')
def home():
    """Simple health check endpoint."""
    return jsonify(message="Vibration monitoring API is running!")

@app.route('/db-check')
def db_check():
    """
    Checks the status of both InfluxDB and PostgreSQL databases.
    Ensures the application can connect to and interact with both databases.
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

# Initialize and run the application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('FLASK_MAIN_PORT', 5000)))
