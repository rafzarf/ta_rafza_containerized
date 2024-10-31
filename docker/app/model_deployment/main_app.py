import os
from flask import Flask, jsonify
from influxdb_client import InfluxDBClient
import psycopg2

app = Flask(__name__)

# InfluxDB connection
influx_client = InfluxDBClient(
    url=os.getenv('INFLUXDB_URL'),
    token=os.getenv('INFLUXDB_ADMIN_TOKEN'),
    org=os.getenv('INFLUXDB_INIT_ORG')
)

# PostgreSQL connection
def get_db_connection():
    return psycopg2.connect(
        host="postgres",
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD')
    )

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('FLASK_MAIN_PORT', 5000)))
