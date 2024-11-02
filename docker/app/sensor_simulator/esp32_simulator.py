import threading
import time
import random
import json
import paho.mqtt.client as mqtt

# MQTT Configuration
mqtt_broker = "192.168.104.251"
mqtt_port = 1883
mqtt_topic = "sensors/accelerometer_data"
mqtt_status_topic = "sensors/status"
mqtt_rul_topic = "sensors/rul_prediction"
mqtt_anomaly_topic = "sensors/anomaly_score"

# System status variables
last_successful_read = 0
consecutive_failures = 0
system_healthy = True
initial_rul = 100  # Initial Remaining Useful Life in "cycles"

# MQTT client
mqtt_client = mqtt.Client()

# Function to simulate connecting to WiFi
def connect_wifi():
    print("Connecting to WiFi...")
    time.sleep(1)
    print("Connected to WiFi")

# Function to connect to MQTT broker
def connect_mqtt():
    mqtt_client.connect(mqtt_broker, mqtt_port, 60)
    print("Connected to MQTT broker")

# Publish message to MQTT topic
def publish_mqtt(topic, message):
    mqtt_client.publish(topic, message)
    print(f"Published to {topic}: {message}")

# Function to simulate reading data from sensors
def read_sensor_data():
    single_axis = round(random.uniform(-10.0, 10.0), 2)
    x_axis = round(random.uniform(-10.0, 10.0), 2)
    y_axis = round(random.uniform(-10.0, 10.0), 2)
    z_axis = round(random.uniform(-10.0, 10.0), 2)
    return single_axis, x_axis, y_axis, z_axis

# Simple anomaly detection function
def calculate_anomaly_score(data):
    threshold = 7.5  # Arbitrary threshold for anomaly detection
    score = max(0, abs(data) - threshold) / threshold
    return round(score, 2)

# RUL prediction function
def predict_rul(current_rul, anomaly_score):
    degradation_factor = 2.5  # Adjust this based on how quickly RUL should decrease with anomalies
    new_rul = max(0, current_rul - (anomaly_score * degradation_factor))
    return round(new_rul, 2)

# Function to check system health and publish status
def check_system_health():
    global system_healthy
    current_health = consecutive_failures < 5
    if current_health != system_healthy:
        system_healthy = current_health
        status = {"status": "healthy" if system_healthy else "error", "failures": consecutive_failures}
        publish_mqtt(mqtt_status_topic, json.dumps(status))

# Task to collect, process, and publish sensor data
def sensor_data_task():
    global last_successful_read, consecutive_failures, initial_rul
    sample_count = 0
    x_sum, y_sum, z_sum, single_axis_sum = 0, 0, 0, 0

    while True:
        single_axis, x_axis, y_axis, z_axis = read_sensor_data()
        single_axis_sum += single_axis
        x_sum += x_axis
        y_sum += y_axis
        z_sum += z_axis
        sample_count += 1

        if sample_count >= 10:
            avg_data = {
                "acceleration": single_axis_sum / sample_count,
                "x": x_sum / sample_count,
                "y": y_sum / sample_count,
                "z": z_sum / sample_count,
                "samples": sample_count,
                "timestamp": int(time.time() * 1000)
            }

            # Anomaly Detection
            anomaly_score = calculate_anomaly_score(avg_data["acceleration"])
            anomaly_message = {
                "timestamp": avg_data["timestamp"],
                "anomaly_score": anomaly_score
            }
            publish_mqtt(mqtt_anomaly_topic, json.dumps(anomaly_message))

            # RUL Prediction
            initial_rul = predict_rul(initial_rul, anomaly_score)
            rul_message = {
                "timestamp": avg_data["timestamp"],
                "predicted_rul": initial_rul
            }
            publish_mqtt(mqtt_rul_topic, json.dumps(rul_message))

            # Publish sensor data
            publish_mqtt(mqtt_topic, json.dumps(avg_data))

            # Reset the aggregation variables
            x_sum, y_sum, z_sum, single_axis_sum, sample_count = 0, 0, 0, 0, 0

        check_system_health()
        time.sleep(1)

# Main simulation function
def main():
    connect_wifi()
    connect_mqtt()

    # Start sensor data task on a separate thread
    sensor_thread = threading.Thread(target=sensor_data_task)
    sensor_thread.start()

    # Main loop for handling other tasks
    while True:
        # Reconnection logic if MQTT is disconnected
        if not mqtt_client.is_connected():
            print("MQTT disconnected. Reconnecting...")
            connect_mqtt()
        time.sleep(10)

if __name__ == "__main__":
    main()
