import asyncio
from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import load_model
from collections import deque
import psycopg2
from psycopg2 import sql
import datetime
import time
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import joblib

# Flask setup
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load the model
autoencoder = load_model('/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/autoencoder_best_model.keras')

# Load the scaler from the saved file
scaler = joblib.load('/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/scaler_final.pkl')

# Initialize buffers
buffer_size = 24
buffer_X = deque(maxlen=buffer_size)
buffer_Y = deque(maxlen=buffer_size)
buffer_Z = deque(maxlen=buffer_size)
buffer_acceleration = deque(maxlen=buffer_size)

# Function to create features from buffer
def create_features_from_buffer(buffer_X, buffer_Y, buffer_Z, buffer_acceleration):
    raw_features = np.array([
        buffer_acceleration[-1],
        buffer_X[-1],
        buffer_Y[-1],
        buffer_Z[-1],
    ])
    
    # Rolling mean and standard deviation features
    rolling_mean_X = np.mean(buffer_X)
    rolling_std_X = np.std(buffer_X)
    rolling_mean_acceleration = np.mean(buffer_acceleration)
    rolling_std_acceleration = np.std(buffer_acceleration)
    rolling_mean_Y = np.mean(buffer_Y)
    rolling_std_Y = np.std(buffer_Y)
    rolling_mean_Z = np.mean(buffer_Z)
    rolling_std_Z = np.std(buffer_Z)
    
    # Statistical features
    mean_X = np.mean(buffer_X)
    std_X = np.std(buffer_X)
    residual_X = buffer_X[-1] - mean_X
    skewness_X = pd.Series(buffer_X).skew()
    kurtosis_X = pd.Series(buffer_X).kurt()

    mean_acceleration = np.mean(buffer_acceleration)
    std_acceleration = np.std(buffer_acceleration)
    residual_acceleration = buffer_acceleration[-1] - mean_acceleration
    skewness_acceleration = pd.Series(buffer_acceleration).skew()
    kurtosis_acceleration = pd.Series(buffer_acceleration).kurt()

    mean_Y = np.mean(buffer_Y)
    std_Y = np.std(buffer_Y)
    residual_Y = buffer_Y[-1] - mean_Y
    skewness_Y = pd.Series(buffer_Y).skew()
    kurtosis_Y = pd.Series(buffer_Y).kurt()

    mean_Z = np.mean(buffer_Z)
    std_Z = np.std(buffer_Z)
    residual_Z = buffer_Z[-1] - mean_Z
    skewness_Z = pd.Series(buffer_Z).skew()
    kurtosis_Z = pd.Series(buffer_Z).kurt()

    all_features = np.array([
        raw_features[0], raw_features[1], raw_features[2], raw_features[3],
        rolling_mean_X, rolling_std_X, residual_X, skewness_X, kurtosis_X,
        rolling_mean_acceleration, rolling_std_acceleration, residual_acceleration, skewness_acceleration, kurtosis_acceleration,
        rolling_mean_Y, rolling_std_Y, residual_Y, skewness_Y, kurtosis_Y,
        rolling_mean_Z, rolling_std_Z, residual_Z, skewness_Z, kurtosis_Z
    ])

    return all_features

# Initialize PostgreSQL connection with retry logic
def get_db_connection():
    max_retries = 5
    retries = 0
    while retries < max_retries:
        try:
            conn = psycopg2.connect(
                dbname="ta_rafza_db",
                user="rafzarf",
                password="Rf28012002@postgres",
                host="localhost"
            )
            return conn
        except psycopg2.OperationalError as e:
            retries += 1
            logger.error(f"Database connection attempt {retries} failed: {e}")
            time.sleep(5)  # wait for 5 seconds before retrying
            if retries == max_retries:
                logger.critical("Failed to connect to the database after multiple retries.")
                raise Exception("Failed to connect to the database after multiple retries.")
    return None

# Store anomaly data in PostgreSQL with error handling
def store_anomaly(timestamp, sensor_values, anomaly_status):
    try:
        conn = get_db_connection()
        if conn is None:
            raise Exception("Database connection could not be established.")
        cursor = conn.cursor()
        query = sql.SQL("INSERT INTO anomalies (timestamp, sensor_values, anomaly_status) VALUES (%s, %s, %s)")
        cursor.execute(query, (timestamp, str(sensor_values), anomaly_status))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Anomaly data stored successfully at {timestamp}")
    except Exception as e:
        logger.error(f"Error storing anomaly: {e}")

# Async function to wait for data
async def wait_for_data():
    while len(buffer_X) < buffer_size:
        logger.info(f"Waiting for more data, current buffer size: {len(buffer_X)}")
        await asyncio.sleep(5)  # Wait for 5 seconds before checking again
    return True

# Endpoint to receive new data
@app.route('/infer', methods=['POST'])
async def infer():
    try:
        data = request.json  # Assuming input is a JSON
        if not data:
            return jsonify({'error': 'No data received'}), 400

        logger.info(f"Received data: {data}")

        # Check for required fields
        if 'x accelerometer_data' not in data or 'y accelerometer_data' not in data or \
           'z accelerometer_data' not in data or 'acceleration accelerometer_data' not in data:
            return jsonify({'error': 'Missing required accelerometer data'}), 400

        # Populate the buffer with incoming data
        buffer_X.append(data['x accelerometer_data'])
        buffer_Y.append(data['y accelerometer_data'])
        buffer_Z.append(data['z accelerometer_data'])
        buffer_acceleration.append(data['acceleration accelerometer_data'])

        # Wait for the buffer to fill asynchronously (if not enough data yet)
        await wait_for_data()

        # Feature extraction
        features = create_features_from_buffer(buffer_X, buffer_Y, buffer_Z, buffer_acceleration)

        # Normalize the features
        scaled_features = scaler.transform(features.reshape(1, -1))  # Reshaping for scaling

        # Reshape to match input shape expected by the autoencoder (24 features, 1 channel)
        scaled_features_reshaped = scaled_features.reshape(scaled_features.shape[0], 24, 1)

        # Get the reconstruction from the autoencoder
        reconstruction = autoencoder.predict(scaled_features_reshaped)

        # Calculate reconstruction error (mean absolute error)
        reconstruction_error = np.mean(np.abs(reconstruction - scaled_features_reshaped), axis=1)

        # Define anomaly threshold
        threshold = 0.941  # You can adjust the threshold based on experimentation

        # Check if the error is an anomaly
        is_anomaly = reconstruction_error[0] > threshold
        anomaly_status = "True" if is_anomaly else "False"

        # Store anomaly data in PostgreSQL
        timestamp = datetime.datetime.now()
        store_anomaly(timestamp, data, anomaly_status)

        # Return the result to the user
        return jsonify({
            'anomaly_detected': is_anomaly,
            'reconstruction_error': reconstruction_error[0],
            'timestamp': timestamp
        })

    except Exception as e:
        logger.error(f"Error during inference: {e}")
        return jsonify({'error': str(e)}), 500


# Health check route
@app.route('/health', methods=['GET'])
def health_check():
    try:
        # You can implement more detailed checks (e.g., DB or model status)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'error': str(e)}), 500

# Background task to ensure backend is alive
def periodic_check():
    logger.info(f"Backend is running at {datetime.datetime.now()}")

# Schedule background task to run every minute
scheduler = BackgroundScheduler()
scheduler.add_job(periodic_check, 'interval', minutes=1)
scheduler.start()

if __name__ == '__main__':
    # Run Flask app
    app.run(debug=True, host="0.0.0.0", port=5000)
