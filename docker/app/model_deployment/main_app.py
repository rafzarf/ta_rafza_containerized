import os
import json
import numpy as np
import psycopg2
import time
from flask import Flask, render_template, request, jsonify
from influxdb_client import InfluxDBClient
import paho.mqtt.client as mqtt
from apscheduler.schedulers.background import BackgroundScheduler
from sklearn.externals import joblib  # Use for loading models if they are in scikit-learn format

# Create the Flask app
app = Flask(__name__, template_folder='templates')

# Environment variables for database connections
INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://localhost:8086')
INFLUXDB_ADMIN_TOKEN = os.getenv('INFLUXDB_ADMIN_TOKEN', 'my-token')
INFLUXDB_INIT_ORG = os.getenv('INFLUXDB_INIT_ORG', 'my-org')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'mydb')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'user')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')  # Use 'localhost' or 'postgres' for Docker setup

MQTT_BROKER = os.getenv('MQTT_BROKER', '172.16.66.238')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC = "sensors/accelerometer_data"

# Initialize InfluxDB client
influx_client = InfluxDBClient(
    url=INFLUXDB_URL,
    token=INFLUXDB_ADMIN_TOKEN,
    org=INFLUXDB_INIT_ORG
)

# Load pre-trained models
anomaly_model_path = 'path/to/anomaly_model.pkl'
rul_model_path = 'path/to/rul_model.pkl'

try:
    anomaly_model = joblib.load(anomaly_model_path)
    rul_model = joblib.load(rul_model_path)
    print("Models loaded successfully.")
except Exception as e:
    print(f"Error loading models: {e}")

# Global variable to store the latest sensor data and RUL prediction
latest_sensor_data = {}
latest_rul = {}

# Function to handle incoming MQTT messages
def on_message(client, userdata, msg):
    global latest_sensor_data
    try:
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        latest_sensor_data = data  # Store the data for real-time access
        print(f"Received data: {data}")
    except Exception as e:
        print(f"Error processing MQTT message: {e}")

# Set up MQTT client
mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message

# Connect to the MQTT broker and subscribe to the topic
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.subscribe(MQTT_TOPIC)
    mqtt_client.loop_start()
    print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT} and subscribed to {MQTT_TOPIC}")
except Exception as e:
    print(f"Failed to connect to MQTT broker: {e}")

# Background scheduler for periodic RUL calculation
scheduler = BackgroundScheduler()

def calculate_rul():
    global latest_sensor_data, latest_rul
    if latest_sensor_data:
        try:
            # Replace simulated RUL logic with model prediction
            input_data = np.array([latest_sensor_data['feature1'], latest_sensor_data['feature2']])  # Adjust keys
            input_data = input_data.reshape(1, -1)  # Ensure input shape is correct for the model
            rul_prediction = int(rul_model.predict(input_data)[0])
            
            # Update the latest RUL prediction
            latest_rul = {
                "timestamp": int(time.time() * 1000),
                "rul_prediction": rul_prediction
            }
            print(f"Updated RUL prediction: {latest_rul}")
        except Exception as e:
            print(f"Error during RUL prediction: {e}")

# Schedule the RUL calculation to run every hour
scheduler.add_job(func=calculate_rul, trigger="interval", hours=1)
scheduler.start()

# Flask route to get the latest RUL data
@app.route('/get-rul-data', methods=['GET'])
def get_rul_data():
    global latest_rul
    if 'rul_prediction' in latest_rul:
        return jsonify(latest_rul)
    else:
        print("RUL not calculated yet")
        return jsonify({"error": "RUL not calculated yet"}), 400

# Flask route to get the latest sensor data and perform anomaly detection
@app.route('/get-anomaly-data', methods=['GET'])
def get_anomaly_data():
    global latest_sensor_data
    if latest_sensor_data:
        try:
            # Assuming latest_sensor_data is a dictionary with appropriate keys for the model
            input_data = np.array([latest_sensor_data['feature1'], latest_sensor_data['feature2']])  # Adjust keys
            input_data = input_data.reshape(1, -1)  # Ensure input shape is correct for the model
            anomaly_score = anomaly_model.predict_proba(input_data)[0][1]  # Example: get the probability of anomaly
            
            return jsonify({
                "timestamp": int(time.time() * 1000),
                "anomaly_score": round(anomaly_score, 2),
                "sensor_data": latest_sensor_data
            })
        except Exception as e:
            print(f"Error during anomaly detection: {e}")
            return jsonify({"error": "Error during anomaly detection"}), 500
    else:
        print("No data received yet for /get-anomaly-data")
        return jsonify({"error": "No data received yet"}), 400

# Root route to check if the app is running
@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')  # Updated to return index.html

# Run the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('FLASK_MAIN_PORT', 5000)))
