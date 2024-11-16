import time
import json
import random
import paho.mqtt.client as mqtt
from datetime import datetime

# MQTT Configuration
MQTT_BROKER = "172.16.66.128"  # Replace with your broker's IP
MQTT_PORT = 1883
MQTT_TOPIC_DATA = "sensors/accelerometer_data_simulated"
MQTT_TOPIC_STATUS = "sensors/status"

# Simulation Parameters
HEALTH_CHECK_INTERVAL = 5  # seconds
DATA_PUBLISH_INTERVAL = 0.5  # seconds
BATCH_SIZE = 30  # Number of samples required by the model

# Buffer for batching data points
data_batch = []
last_health_check_time = 0
system_healthy = True

# MQTT Setup
client = mqtt.Client("PythonSimulator")

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.publish(MQTT_TOPIC_STATUS, json.dumps({"status": "connected", "device": "PythonSimulator"}))

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnection.")

client.on_connect = on_connect
client.on_disconnect = on_disconnect

# Connect to MQTT broker
print("Connecting to MQTT broker...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()


# Initialize global variables for simulating gradual degradation
base_x, base_y, base_z, base_acceleration = 1.0, 1.0, 1.0, 1.0
degradation_rate = 0.01  # Rate at which vibration increases over time

# Kalman filter parameters
process_variance = 0.05  # Process noise
measurement_variance = 0.1  # Measurement noise
estimated_error = 1.0  # Initial error estimate
kalman_gain = 0.0

# Kalman state initialization
kalman_x, kalman_y, kalman_z, kalman_acceleration = base_x, base_y, base_z, base_acceleration

def kalman_filter(value, estimated, error):
    global kalman_gain
    # Prediction update
    kalman_gain = error / (error + measurement_variance)
    estimated = estimated + kalman_gain * (value - estimated)
    error = (1 - kalman_gain) * error + process_variance
    return estimated, error

def simulate_sensor_data():
    global base_x, base_y, base_z, base_acceleration, degradation_rate
    global kalman_x, kalman_y, kalman_z, kalman_acceleration, estimated_error
    
    # Gradually increase base values to simulate degradation
    base_x += degradation_rate
    base_y += degradation_rate
    base_z += degradation_rate
    base_acceleration += degradation_rate

    # Generate raw sensor data with random noise
    x = round(random.uniform(base_x - 0.5, base_x + 0.5), 2)
    y = round(random.uniform(base_y - 0.5, base_y + 0.5), 2)
    z = round(random.uniform(base_z - 0.5, base_z + 0.5), 2)
    acceleration = round(random.uniform(base_acceleration - 0.5, base_acceleration + 0.5), 2)
    
    # Occasionally introduce a sudden spike to simulate an impact or anomaly
    if random.random() < 0.05:  # 5% chance of a spike
        spike_magnitude = random.uniform(2.0, 5.0)  # Larger spike
        x += spike_magnitude
        y += spike_magnitude
        z += spike_magnitude
        acceleration += spike_magnitude

    # Apply Kalman filter to each axis
    kalman_x, estimated_error = kalman_filter(x, kalman_x, estimated_error)
    kalman_y, estimated_error = kalman_filter(y, kalman_y, estimated_error)
    kalman_z, estimated_error = kalman_filter(z, kalman_z, estimated_error)
    kalman_acceleration, estimated_error = kalman_filter(acceleration, kalman_acceleration, estimated_error)

    # Ensure values remain within realistic Class I range and don't exceed limits
    x = min(x, 7.0)
    y = min(y, 7.0)
    z = min(z, 7.0)
    acceleration = min(acceleration, 7.0)

    # Return both raw and filtered data
    return {
        "raw": {"x": round(x, 2), "y": round(y, 2), "z": round(z, 2), "acceleration": round(acceleration, 2)},
        "filtered": {
            "x": round(kalman_x, 2),
            "y": round(kalman_y, 2),
            "z": round(kalman_z, 2),
            "acceleration": round(kalman_acceleration, 2)
        }
    }

# Function to classify data based on Class I criteria
def classify_data(acceleration):
    if acceleration <= 0.71:
        return "A (Good)"
    elif acceleration <= 1.12:
        return "B (Acceptable)"
    elif acceleration <= 1.8:
        return "C (Alert)"
    else:
        return "D (Not Allowed)"

# Function to check system health and publish status
def publish_health_status():
    global system_healthy
    health_status = {
        "status": "healthy" if system_healthy else "error",
        "timestamp": int(time.time())
    }
    client.publish(MQTT_TOPIC_STATUS, json.dumps(health_status))
    print("Published health status:", health_status)

# Main loop for data batching and publication
try:
    while True:
        current_time = time.time()

        # Simulate reading data from sensors
        sensor_data = simulate_sensor_data()
        raw_classification = classify_data(sensor_data["raw"]["acceleration"])
        filtered_classification = classify_data(sensor_data["filtered"]["acceleration"])
        sensor_data["raw"]["classification"] = raw_classification
        sensor_data["filtered"]["classification"] = filtered_classification
        print("Simulated sensor data:", sensor_data)

        # Append each classified data point to the batch
        data_batch.append(sensor_data)

        # Check if the batch size is reached
        if len(data_batch) >= BATCH_SIZE:
            # Publish the batch to MQTT as a JSON array
            client.publish(MQTT_TOPIC_DATA, json.dumps(data_batch))
            print("Published batch data:", data_batch)

            # Clear the batch for the next round
            data_batch = []

        # Periodically publish health status
        if current_time - last_health_check_time >= HEALTH_CHECK_INTERVAL:
            publish_health_status()
            last_health_check_time = current_time

        # Sleep for a short interval to simulate a periodic task
        time.sleep(DATA_PUBLISH_INTERVAL)

except KeyboardInterrupt:
    print("Simulation stopped by user.")
finally:
    client.loop_stop()
    client.disconnect()
