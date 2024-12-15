import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import pandas as pd
import datetime
import joblib
from tensorflow.keras.models import load_model
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import Json  # Import Json adapter
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import time
from influxdb_client import InfluxDBClient, Point
import matplotlib.pyplot as plt
import numpy as np
import io
from fastapi.responses import StreamingResponse

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# Set up CORS middleware
origins = [
    "http://localhost",           # Allow local development
    "http://localhost:3000",      # If using a React or other frontend on port 3000
    "http://localhost:1880",      # If using a Vue frontend
    "http://172.19.0.3:1883",    # If using a Jupyter Notebook
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # Allows specific origins or '*' for all
    allow_credentials=True,
    allow_methods=["*"],            # Allows all methods like GET, POST, etc.
    allow_headers=["*"],            # Allows all headers
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load the model
try:
    autoencoder = load_model('/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/autoencoder_best_model_1213.keras')
    logger.info("Autoencoder model loaded successfully.")
except Exception as e:
    logger.error(f"Error loading autoencoder model: {e}")
    raise

# Load the scaler from the saved file
try:
    scaler = joblib.load('/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/scaler_final.pkl')
    logger.info("Scaler loaded successfully.")
except Exception as e:
    logger.error(f"Error loading scaler: {e}")
    raise

# Function to reset the data buffer
def reset_data_buffer():
    global data_buffer
    data_buffer = {
        'x': [],
        'y': [],
        'z': [],
        'acceleration': []
    }
    logger.info("Data buffer has been reset.")


# Initialize PostgreSQL connection pool
def init_db_pool():
    try:
        return psycopg2.pool.SimpleConnectionPool(
            1, 10,  # minconn, maxconn
            dbname="ta_rafza_db",
            user="rafzarf",
            password="Rf28012002@postgres",
            host="localhost"
        )
    except Exception as e:
        logger.error(f"Error initializing database connection pool: {e}")
        raise

# Initialize DB connection pool globally
try:
    db_pool = init_db_pool()
    logger.info("Database connection pool initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize database connection pool: {e}")
    raise

# InfluxDB configuration from environment variables
INFLUXDB_URL = "http://172.19.0.6:8086"
INFLUXDB_TOKEN = os.getenv("INFLUXDB_ADMIN_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_INIT_ORG")
INFLUXDB_BUCKET = "ta_rafza_db"

# Initialize InfluxDB client
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN)
write_api = client.write_api()

# Initialize InfluxDB client
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN)
write_api = client.write_api()

# Define a Pydantic response model
class InferenceResponse(BaseModel):
    timestamp: str
    reconstruction_error: float
    anomaly_status: bool

# FastAPI Endpoint to receive new data
class SensorData(BaseModel):
    x_accelerometer_data: float
    y_accelerometer_data: float
    z_accelerometer_data: float
    acceleration_accelerometer_data: float

class SensorBatch(BaseModel):
    data: list[SensorData]  # Ensure this is a list of 24 SensorData objects

# Buffer to store accumulated data (Global variable)
data_buffer = {
    'x': [],
    'y': [],
    'z': [],
    'acceleration': []
}

BUFFER_THRESHOLD = 100  # Define how many data points we want to accumulate before plotting

# Buffer to store reconstruction errors for dynamic threshold calculation
reconstruction_error_buffer = []

@app.post('/infer', response_model=InferenceResponse)
async def infer(batch: SensorBatch):
    try:
        if len(batch.data) != 24:
            raise HTTPException(status_code=400, detail="Batch size must be 24")
        
        logger.info(f"Received batch data: {batch.data}")

        # Create features from the batch of data
        features = create_features_from_batch(batch.data)

        # Normalize the features
        scaled_features = scaler.transform(features.reshape(1, -1))  # Reshaping for scaling

        # Reshape to match input shape expected by the autoencoder (1 sample, 24 features, 1 channel)
        scaled_features_reshaped = scaled_features.reshape(scaled_features.shape[0], 24, 1)

        # Get the reconstruction from the autoencoder
        reconstruction = autoencoder.predict(scaled_features_reshaped)

        # Calculate reconstruction error (mean absolute error)
        reconstruction_error = np.mean(np.abs(reconstruction - scaled_features_reshaped), axis=1)

        # Add reconstruction error to the buffer
        reconstruction_error_buffer.append(reconstruction_error[0])

        # Maintain a buffer of the last 100 reconstruction errors (or any suitable size)
        if len(reconstruction_error_buffer) > 100:
            reconstruction_error_buffer.pop(0)

        # Calculate the dynamic threshold (95th percentile)
        threshold = np.percentile(reconstruction_error_buffer, 99)

        # Check if the error is an anomaly
        is_anomaly = reconstruction_error[0] > threshold

        # Timestamp
        timestamp = datetime.datetime.now()

        # Accumulate data to the global buffer
        accumulate_data(batch.data, timestamp)  # Pass the timestamp

        # Check if accumulated data has reached the threshold for plotting
        if len(data_buffer['x']) >= BUFFER_THRESHOLD:
            # Generate and serve the plot image after threshold is reached
            plot_img = generate_plot(data_buffer, reconstruction_error[0], is_anomaly, timestamp)

            # Clear the buffer after plotting
            reset_data_buffer()

        # Store anomaly data in InfluxDB and PostgreSQL
        store_anomaly_in_influxdb(timestamp, float(reconstruction_error[0]), bool(is_anomaly))
        store_anomaly_in_postgres(timestamp, float(reconstruction_error[0]), bool(is_anomaly))

        # Return the response with the plot image URL and anomaly details
        return InferenceResponse(
            timestamp=timestamp.isoformat(),
            reconstruction_error=float(reconstruction_error[0]),
            anomaly_status=bool(is_anomaly),
        )

    except Exception as e:
        logger.error(f"Error during inference: {e}")
        raise HTTPException(status_code=500, detail=f"Error during inference: {str(e)}")



# Function to accumulate data across batches (with timestamp)
def accumulate_data(batch_data, timestamp):
    x_data = [data.x_accelerometer_data for data in batch_data]
    y_data = [data.y_accelerometer_data for data in batch_data]
    z_data = [data.z_accelerometer_data for data in batch_data]
    acceleration_data = [data.acceleration_accelerometer_data for data in batch_data]

    # Add timestamp to each data point
    for i in range(len(batch_data)):
        data_buffer['x'].append((timestamp, x_data[i]))
        data_buffer['y'].append((timestamp, y_data[i]))
        data_buffer['z'].append((timestamp, z_data[i]))
        data_buffer['acceleration'].append((timestamp, acceleration_data[i]))



def generate_plot(data_buffer, reconstruction_error, is_anomaly, timestamp):
    try:
        # Create the plot with accumulated data
        fig, ax = plt.subplots(figsize=(10, 6))

        # Extract just the acceleration values (remove timestamp)
        x_vals = [item[1] for item in data_buffer['x']]
        y_vals = [item[1] for item in data_buffer['y']]
        z_vals = [item[1] for item in data_buffer['z']]
        acceleration_vals = [item[1] for item in data_buffer['acceleration']]

        # Plot X, Y, Z accelerometer data
        ax.plot(x_vals, label="X Acceleration", color="b", marker="o")
        ax.plot(y_vals, label="Y Acceleration", color="g", marker="o")
        ax.plot(z_vals, label="Z Acceleration", color="r", marker="o")
        ax.plot(acceleration_vals, label="Total Acceleration", color="purple", marker="o")

        # Highlight anomalies if detected
        if is_anomaly:
            # Find the index of the anomaly (assuming you only have one anomaly per plot)
            anomaly_index = len(acceleration_vals) - 1  # Assume the last point is the anomaly
            ax.plot(anomaly_index, acceleration_vals[anomaly_index], 'ro', label="Anomaly Detected")
            ax.annotate(f"Anomaly at {timestamp.isoformat()}", 
                        xy=(anomaly_index, acceleration_vals[anomaly_index]), 
                        xytext=(anomaly_index + 5, acceleration_vals[anomaly_index] + 0.1),
                        arrowprops=dict(facecolor='red', shrink=0.05), 
                        fontsize=10)

        # Add reconstruction error information
        reconstruction_error_value = float(reconstruction_error)  # Convert to scalar value
        ax.text(0.5, 0.1, f"Reconstruction Error: {reconstruction_error_value:.3f}", ha='center', transform=ax.transAxes, fontsize=12, color='purple')

        # Add labels and title
        ax.set_xlabel("Time")
        ax.set_ylabel("Acceleration")
        ax.set_title(f"Accelerometer Data with Reconstruction Error {reconstruction_error_value:.3f}")
        ax.legend()

        # Save the plot as a PNG image to serve it
        plot_path = f"/tmp/reconstruction_error_long_plot_{timestamp.isoformat()}.png"
        plt.savefig(plot_path)

        # Return the image as a response
        with open(plot_path, 'rb') as f:
            img_data = f.read()

        return img_data

    except Exception as e:
        logger.error(f"Error generating long plot: {e}")
        raise


# Endpoint to serve the plot image
@app.get('/plot/{timestamp}')
async def serve_plot(timestamp: str):
    try:
        # Construct the path where the plot image is stored
        plot_path = f"/tmp/reconstruction_error_long_plot_{timestamp}.png"
        
        # Check if the plot image exists
        if not os.path.exists(plot_path):
            raise HTTPException(status_code=404, detail="Plot not found")

        # Serve the image
        return StreamingResponse(open(plot_path, "rb"), media_type="image/png")
    
    except Exception as e:
        logger.error(f"Error serving plot: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving plot: {str(e)}")


def store_anomaly_in_influxdb(timestamp, reconstruction_error, anomaly_status, measurement="predictions"):
    try:
        # Create a point for InfluxDB with the specified measurement
        point = Point(measurement) \
            .tag("sensor", "accelerometer") \
            .field("reconstruction_error", reconstruction_error) \
            .field("anomaly_status", anomaly_status) \
            .time(timestamp)

        # Write the point to InfluxDB
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        logger.info(f"Anomaly data stored to InfluxDB at {timestamp}")
    except Exception as e:
        logger.error(f"Error storing anomaly in InfluxDB: {e}")


def store_anomaly_in_postgres(timestamp, anomaly_score, is_anomaly):
    try:
        # Establish a database connection from the pool
        conn = db_pool.getconn()
        if conn is None:
            raise Exception("Database connection could not be established.")
        
        cursor = conn.cursor()

        # SQL query to insert anomaly score
        query = "INSERT INTO anomaly_scores (timestamp, anomaly_score, anomaly_status) VALUES (%s, %s, %s)"
        cursor.execute(query, (timestamp, anomaly_score, is_anomaly))
        conn.commit()

        # Clean up
        cursor.close()
        db_pool.putconn(conn)  # Return connection to pool
        logger.info(f"Anomaly score stored successfully in PostgreSQL at {timestamp}")

    except Exception as e:
        logger.error(f"Error storing anomaly in PostgreSQL: {e}")

# Function to create features from a batch of 24 data points
def create_features_from_batch(batch_data):
    # Extract data columns by accessing attributes directly (instead of using dictionary indexing)
    acceleration_data = [data.acceleration_accelerometer_data for data in batch_data]
    x_data = [data.x_accelerometer_data for data in batch_data]
    y_data = [data.y_accelerometer_data for data in batch_data]
    z_data = [data.z_accelerometer_data for data in batch_data]

    # Statistical features (mean, std, residual, skewness, kurtosis) for each axis
    def statistical_features(data):
        mean = float(np.mean(data))
        std = float(np.std(data))
        residual = float(data[-1] - mean)
        skewness = float(pd.Series(data).skew())
        kurtosis = float(pd.Series(data).kurt())
        return mean, std, residual, skewness, kurtosis

    # Initialize features list
    features = []

    # Raw features (latest values from each axis and acceleration)
    features.append(float(acceleration_data[-1]))  # last acceleration value
    features.append(float(x_data[-1]))              # last X value
    features.append(float(y_data[-1]))              # last Y value
    features.append(float(z_data[-1]))              # last Z value

    # Statistical features for each axis
    features.extend(statistical_features(x_data))          # X data
    features.extend(statistical_features(acceleration_data))# Acceleration data
    features.extend(statistical_features(y_data))          # Y data
    features.extend(statistical_features(z_data))          # Z data

    # Ensure the feature array has the correct length (24)
    if len(features) != 24:
        logger.warning(f"Feature length is {len(features)} instead of 24.")

    return np.array(features)

# Health check route
@app.get('/health')
async def health_check():
    return {"status": "ok"}

# Background task to ensure backend is alive
def periodic_check():
    logger.info(f"Backend is running at {datetime.datetime.now()}")

# Schedule background task to run every minute
scheduler = BackgroundScheduler()
scheduler.add_job(periodic_check, 'interval', minutes=1)
scheduler.start()

# Run Uvicorn with FastAPI (handled by uvicorn)
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
