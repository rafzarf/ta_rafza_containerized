import time
import os
import paho.mqtt.client as mqtt
from vibration_sensor import VibrationSensor

def run_esp32_simulator():
    mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
    mqtt_port = int(os.getenv('MQTT_PORT', 1883))
    topic = os.getenv('MQTT_TOPIC', 'vibration/data')

    client = mqtt.Client()
    client.connect(mqtt_broker, mqtt_port, 60)

    sensor = VibrationSensor()

    while True:
        vibration = sensor.get_reading()
        client.publish(topic, vibration)
        print(f"Published vibration data to MQTT: {vibration}")
        time.sleep(1)

if __name__ == "__main__":
    run_esp32_simulator()
