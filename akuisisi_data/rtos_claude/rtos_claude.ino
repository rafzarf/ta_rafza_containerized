#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ModbusMaster.h>
#include <InfluxDbClient.h>

// Pin Definitions
#define MODBUS_DIR_PIN  4
#define MODBUS_RX_PIN 18
#define MODBUS_TX_PIN 19
#define MODBUS_SERIAL_BAUD 9600

// WiFi and MQTT Configuration
const char* ssid = "DINGINLESTARI";
const char* password = "ray12345678";
const char* mqtt_broker = "172.16.66.238";
const int mqtt_port = 1883;
const char* mqtt_topic_sensor1 = "sensors/accelerometer1/raw";
const char* mqtt_topic_sensor2 = "sensors/accelerometer2/raw";

// InfluxDB Configuration
#define INFLUXDB_URL "http://172.16.66.238:8086"
#define INFLUXDB_TOKEN "49Zx_X5c9z0f8daAYwjUXBa4Z9e86E1mdOaFLNWDEYZrl_mYI8o6xqQDBuf68_kAIS3Op858rZspGjA=="
#define INFLUXDB_ORG "polman_bdg"
#define INFLUXDB_BUCKET_COMBINED "bucket_combined"

// Queue handles and global instances
QueueHandle_t sensor1Queue, sensor2Queue;
ModbusMaster node;
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
InfluxDBClient influxClient(INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET_COMBINED, INFLUXDB_TOKEN);
SemaphoreHandle_t modbusLock;

struct Sensor1Data {
    unsigned long timestamp;
    float acceleration;
    bool valid;
};

struct Sensor2Data {
    unsigned long timestamp;
    float x;
    float y;
    float z;
    bool valid;
};

// Function to connect to WiFi
bool connectWiFi() {
    WiFi.begin(ssid, password);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 10) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("Connected to WiFi");
        return true;
    } else {
        Serial.println("Failed to connect to WiFi");
        return false;
    }
}

// Function to connect to MQTT broker
bool connectMQTT() {
    mqttClient.setServer(mqtt_broker, mqtt_port);
    while (!mqttClient.connected()) {
        Serial.print("Attempting MQTT connection...");
        if (mqttClient.connect("ESP32Client")) {
            Serial.println("Connected to MQTT broker");
            return true;
        } else {
            Serial.printf("Failed, rc=%d; retrying in 5 seconds\n", mqttClient.state());
            delay(5000);
        }
    }
    return mqttClient.connected();
}

// Function to publish MQTT message
void publishMQTT(const char* topic, const char* payload) {
    if (!mqttClient.connected()) {
        connectMQTT();
    }
    mqttClient.publish(topic, payload);
}

// Function to read sensor data using Modbus
bool readModbusData(uint8_t sensorId, Sensor1Data* sensor1Data, Sensor2Data* sensor2Data) {
    bool success = false;
    if (xSemaphoreTake(modbusLock, pdMS_TO_TICKS(50)) == pdTRUE) {
        node.begin(sensorId, Serial2);
        delay(1);  // Ensure proper timing for Modbus communication

        if (sensorId == 1 && sensor1Data != nullptr) {
            uint8_t result = node.readInputRegisters(0x0003, 1);
            if (result == node.ku8MBSuccess) {
                sensor1Data->acceleration = node.getResponseBuffer(0x00) / 10.0;
                sensor1Data->valid = true;
                success = true;
            } else {
                sensor1Data->valid = false;
            }
        } else if (sensorId == 2 && sensor2Data != nullptr) {
            success = true;
            uint8_t result = node.readInputRegisters(0x000A, 1);
            sensor2Data->x = (result == node.ku8MBSuccess) ? node.getResponseBuffer(0x00) / 10.0 : 0;
            result = node.readInputRegisters(0x000B, 1);
            sensor2Data->y = (result == node.ku8MBSuccess) ? node.getResponseBuffer(0x00) / 10.0 : 0;
            result = node.readInputRegisters(0x000C, 1);
            sensor2Data->z = (result == node.ku8MBSuccess) ? node.getResponseBuffer(0x00) / 10.0 : 0;
            sensor2Data->valid = (sensor2Data->x != 0 || sensor2Data->y != 0 || sensor2Data->z != 0);
        }
        xSemaphoreGive(modbusLock);
    }
    return success;
}

// Task to read sensor data at higher sampling rates
void sensorReadTask(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(5); // 5ms for ~200 Hz sampling

    while (true) {
        Sensor1Data data1 = {millis(), 0.0f, false};
        Sensor2Data data2 = {millis(), 0.0f, 0.0f, 0.0f, false};

        if (readModbusData(1, &data1, nullptr)) {
            xQueueSend(sensor1Queue, &data1, 0);
        }
        if (readModbusData(2, nullptr, &data2)) {
            xQueueSend(sensor2Queue, &data2, 0);
        }

        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}

// Task to send and process data
void communicationTask(void *pvParameters) {
    while (true) {
        Sensor1Data data1;
        Sensor2Data data2;

        // Send Sensor 1 data to MQTT
        if (xQueueReceive(sensor1Queue, &data1, pdMS_TO_TICKS(10)) == pdTRUE) {
            if (data1.valid) {
                DynamicJsonDocument doc(128);
                doc["timestamp"] = data1.timestamp;
                doc["acceleration"] = data1.acceleration;
                char jsonBuffer[128];
                serializeJson(doc, jsonBuffer);
                publishMQTT(mqtt_topic_sensor1, jsonBuffer);

                // Write to InfluxDB
                Point sensorPoint("accelerometer1");
                sensorPoint.setTime(data1.timestamp * 1000000LL);
                sensorPoint.addField("acceleration", data1.acceleration);
                influxClient.writePoint(sensorPoint);
            }
        }

        // Send Sensor 2 data to MQTT
        if (xQueueReceive(sensor2Queue, &data2, pdMS_TO_TICKS(10)) == pdTRUE) {
            if (data2.valid) {
                DynamicJsonDocument doc(256);
                doc["timestamp"] = data2.timestamp;
                doc["x"] = data2.x;
                doc["y"] = data2.y;
                doc["z"] = data2.z;
                char jsonBuffer[256];
                serializeJson(doc, jsonBuffer);
                publishMQTT(mqtt_topic_sensor2, jsonBuffer);

                // Write to InfluxDB
                Point sensorPoint("accelerometer2");
                sensorPoint.setTime(data2.timestamp * 1000000LL);
                sensorPoint.addField("x", data2.x);
                sensorPoint.addField("y", data2.y);
                sensorPoint.addField("z", data2.z);
                influxClient.writePoint(sensorPoint);
            }
        }

        vTaskDelay(pdMS_TO_TICKS(50)); // Allow other tasks to run
    }
}

void setup() {
    Serial.begin(115200);
    Serial.println("Setup started");

    pinMode(MODBUS_DIR_PIN, OUTPUT);
    digitalWrite(MODBUS_DIR_PIN, LOW);
    Serial2.begin(MODBUS_SERIAL_BAUD, SERIAL_8N1, MODBUS_RX_PIN, MODBUS_TX_PIN);
    modbusLock = xSemaphoreCreateMutex();
    sensor1Queue = xQueueCreate(500, sizeof(Sensor1Data)); // Increased queue size for higher sampling rate
    sensor2Queue = xQueueCreate(500, sizeof(Sensor2Data)); // Increased queue size for higher sampling rate

    if (!connectWiFi() || !connectMQTT()) {
        Serial.println("Failed to connect, restarting...");
        ESP.restart();
    }

    // Start tasks with optimized stack sizes
    xTaskCreatePinnedToCore(sensorReadTask, "SensorRead", 20000, NULL, 2, NULL, 1);
    xTaskCreatePinnedToCore(communicationTask, "Communication", 16000, NULL, 1, NULL, 0);

    Serial.println("Setup completed");
}

void loop() {
    if (WiFi.status() != WL_CONNECTED) {
        connectWiFi();
    }
    mqttClient.loop();
    delay(100);
}
