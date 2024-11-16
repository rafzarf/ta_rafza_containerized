import time
import json
import random
import paho.mqtt.client as mqtt
from datetime import datetime

# MQTT Configuration
MQTT_BROKER = "192.168.66.251"  # Replace with your broker's IP
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
degradation_rate = 0.00001  # Rate at which vibration increases over time

# Counter for spike simulation
spike_counter = 0
SPIKE_INTERVAL = int(3 * 60 * 60 / DATA_PUBLISH_INTERVAL)  # Calculate iterations for 3 hours

def simulate_sensor_data():
    global base_x, base_y, base_z, base_acceleration, degradation_rate, spike_counter
    
    # Gradually increase base values to simulate degradation
    base_x += degradation_rate
    base_y += degradation_rate
    base_z += degradation_rate
    base_acceleration += degradation_rate

    # Add random noise to simulate real-world sensor fluctuations
    x = round(random.uniform(base_x - 0.5, base_x + 0.5), 2)
    y = round(random.uniform(base_y - 0.5, base_y + 0.5), 2)
    z = round(random.uniform(base_z - 0.5, base_z + 0.5), 2)
    acceleration = round(random.uniform(base_acceleration - 0.5, base_acceleration + 0.5), 2)
    
    # Introduce a spike every SPIKE_INTERVAL iterations (approximately every 3 hours)
    spike_counter += 1
    if spike_counter >= SPIKE_INTERVAL:
        spike_counter = 0  # Reset counter after a spike
        spike_magnitude = random.uniform(2.0, 5.0)  # Larger spike
        x += spike_magnitude
        y += spike_magnitude
        z += spike_magnitude
        acceleration += spike_magnitude

    # Ensure values remain within realistic Class I range and don't exceed limits
    x = min(x, 7.0)
    y = min(y, 7.0)
    z = min(z, 7.0)
    acceleration = min(acceleration, 7.0)

    return {"x": round(x, 2), "y": round(y, 2), "z": round(z, 2), "acceleration": round(acceleration, 2)}

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
        classification = classify_data(sensor_data["acceleration"])
        sensor_data["classification"] = classification  # Add classification to each data point
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
