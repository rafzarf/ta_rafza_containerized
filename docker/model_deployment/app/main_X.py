import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import pandas as pd
import datetime
import joblib
from tensorflow.keras.models import load_model
import logging
from collections import deque
import matplotlib.pyplot as plt
from fastapi.responses import StreamingResponse
from io import BytesIO
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load Model and Scaler
try:
    autoencoder = load_model('/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/autoencoder_best_model.keras')
    scaler = joblib.load('/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/scaler_final.pkl')
    logger.info("Model and scaler loaded successfully.")
except Exception as e:
    logger.error(f"Error loading model or scaler: {e}")
    raise

# Data Buffers and Constants
BUFFER_SIZE = 24
DYNAMIC_THRESHOLD_WINDOW = 100
reconstruction_error_buffer = deque(maxlen=DYNAMIC_THRESHOLD_WINDOW)
data_buffer = {"x": [], "y": [], "z": [], "acceleration": []}

# Pydantic Models
class SensorData(BaseModel):
    x_accelerometer_data: float
    y_accelerometer_data: float
    z_accelerometer_data: float
    acceleration_accelerometer_data: float

class SensorBatch(BaseModel):
    data: list[SensorData]

# Helper: Feature Extraction
def create_features_from_batch(batch_data):
    acceleration = [d.acceleration_accelerometer_data for d in batch_data]
    x = [d.x_accelerometer_data for d in batch_data]
    y = [d.y_accelerometer_data for d in batch_data]
    z = [d.z_accelerometer_data for d in batch_data]

    def calc_stats(data):
        return [
            float(np.mean(data)),
            float(np.std(data)),
            float(data[-1] - np.mean(data)),
            float(pd.Series(data).skew()),
            float(pd.Series(data).kurt()),
        ]

    features = [acceleration[-1], x[-1], y[-1], z[-1]] + \
               calc_stats(x) + calc_stats(acceleration) + \
               calc_stats(y) + calc_stats(z)

    return np.array(features).reshape(1, -1)

# Helper: Generate Plot
def generate_plot(data_buffer, reconstruction_error, anomalies):
    fig, ax = plt.subplots(figsize=(10, 6))

    x_vals = [v for _, v in data_buffer["x"]]
    y_vals = [v for _, v in data_buffer["y"]]
    z_vals = [v for _, v in data_buffer["z"]]
    acceleration_vals = [v for _, v in data_buffer["acceleration"]]

    ax.plot(x_vals, label="X Acceleration", color="b", linestyle="-")
    ax.plot(y_vals, label="Y Acceleration", color="g", linestyle="-")
    ax.plot(z_vals, label="Z Acceleration", color="r", linestyle="-")
    ax.plot(acceleration_vals, label="Acceleration", color="purple", linestyle="-")

    for idx, anomaly in enumerate(anomalies):
        if anomaly:
            ax.scatter(idx, acceleration_vals[idx], color="red", label="Anomaly", zorder=5)

    ax.set_title(f"Sensor Data with Anomalies (Reconstruction Error: {reconstruction_error:.4f})")
    ax.set_xlabel("Time (samples)")
    ax.set_ylabel("Sensor Readings")
    ax.legend()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf

# Endpoint: Infer and Visualize
@app.post("/infer", response_class=StreamingResponse)
async def infer(batch: SensorBatch):
    if len(batch.data) != BUFFER_SIZE:
        raise HTTPException(status_code=400, detail="Batch size must be 24")

    # Extract and scale features
    features = create_features_from_batch(batch.data)
    scaled_features = scaler.transform(features).reshape(1, BUFFER_SIZE, 1)

    # Infer reconstruction error
    reconstruction = autoencoder.predict(scaled_features)
    reconstruction_error = np.mean(np.abs(reconstruction - scaled_features))

    # Update dynamic threshold
    reconstruction_error_buffer.append(reconstruction_error)
    threshold = np.percentile(reconstruction_error_buffer, 95)

    # Determine anomalies
    is_anomaly = reconstruction_error > threshold
    anomalies = [is_anomaly] * BUFFER_SIZE

    # Update buffers
    for idx, data in enumerate(batch.data):
        for key in data_buffer:
            data_buffer[key].append((datetime.datetime.now(), getattr(data, f"{key}_accelerometer_data")))
        if len(data_buffer[key]) > BUFFER_SIZE:
            data_buffer[key].pop(0)

    # Generate plot
    plot_buf = generate_plot(data_buffer, reconstruction_error, anomalies)

    # Return the plot
    return StreamingResponse(plot_buf, media_type="image/png")

# Background task to ensure backend is alive
def periodic_check():
    logger.info(f"Backend is running at {datetime.datetime.now()}")

# Schedule background task to run every minute
scheduler = BackgroundScheduler()
scheduler.add_job(periodic_check, 'interval', minutes=1)
scheduler.start()

# Run Uvicorn with FastAPI (handled by uvicorn)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
