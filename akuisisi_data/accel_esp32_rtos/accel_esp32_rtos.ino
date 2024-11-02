#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ModbusMaster.h>
#include <InfluxDbClient.h>
#include "freertos/queue.h"
#include <kiss_fft.h>
#include <kiss_fftr.h> // For real-to-complex FFT

// Pin Definitions
#define MODBUS_DIR_PIN  4
#define MODBUS_RX_PIN 18
#define MODBUS_TX_PIN 19
#define MODBUS_SERIALs_BAUD 9600

// Register definitions
const uint16_t data_register_x_axis_1 = 0x0003;  // Sensor 1 (1-axis)
const uint16_t data_register_x_axis_2 = 0x000A;  // Sensor 2 (X-axis)
const uint16_t data_register_y_axis_2 = 0x000B;  // Sensor 2 (Y-axis)
const uint16_t data_register_z_axis_2 = 0x000C;  // Sensor 2 (Z-axis)

// WiFi and MQTT Configuration
const char* ssid = "DINGINLESTARI";
const char* password = "ray12345678";
const char* mqtt_broker = "172.16.66.238";
const int mqtt_port = 1883;
const char* mqtt_topic_sensor1 = "sensors/accelerometer1/raw";
const char* mqtt_topic_sensor2 = "sensors/accelerometer2/raw";

// InfluxDB Configuration
#define INFLUXDB_URL "http://172.16.66.238:8086"
#define INFLUXDB_TOKEN "49Zx_X5c9z0f8daAYwjUXBa4Z9e86E1mdOaFLNWDEYZrl_mYI8o6Q0laCn6xqQDBuf68_kAIS3Op858rZspGjA=="
#define INFLUXDB_ORG "polman_bdg"
#define INFLUXDB_BUCKET_COMBINED "bucket_combined"


// Queue handles and global instances
QueueHandle_t sensor1Queue, sensor2Queue;
ModbusMaster node;
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
InfluxDBClient influxClient(INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET_COMBINED, INFLUXDB_TOKEN);
SemaphoreHandle_t modbusLock;

// FFT settings
#define SAMPLES 128 // Must be a power of 2
kiss_fft_scalar vReal[SAMPLES]; // Input data array
kiss_fft_cpx vComplex[SAMPLES / 2 + 1]; // Output array for KissFFT (complex numbers)
kiss_fftr_cfg cfg; // FFT configuration

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

// High-pass filter to remove low-frequency noise
float highPassFilter(float input, float previousInput, float previousOutput, float alpha = 0.1) {
    return alpha * (previousOutput + input - previousInput);
}

// Envelope detection for extracting fault characteristics
float envelopeDetection(float data) {
    return abs(data); // Simple rectification as a placeholder
}

// Function to connect to WiFi
bool connectWiFi() {
    WiFi.begin(ssid, password);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 10) {
        delay(1000);
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
        } else {
            Serial.printf("Failed, rc=%d; retrying in 5 seconds\n", mqttClient.state());
            delay(5000);
        }
    }
    return mqttClient.connected();
}

// Function to publish MQTT message with reconnection logic
void publishMQTT(const char* topic, const char* payload) {
    if (!mqttClient.connected()) {
        connectMQTT();
    }
    if (mqttClient.publish(topic, payload)) {
        Serial.printf("Published to topic: %s - Payload: %s\n", topic, payload);
    } else {
        Serial.printf("Failed to publish to topic: %s\n", topic);
    }
}

// Memory monitoring function
void monitorMemory(const char* taskName) {
    UBaseType_t highWaterMark = uxTaskGetStackHighWaterMark(NULL);
    Serial.printf("[%s] Task high water mark (min free stack): %u\n", taskName, highWaterMark);
    Serial.printf("[%s] Free heap: %d\n", taskName, ESP.getFreeHeap());
}

// Function to read data from Modbus and update sensor structures
bool readModbusData(uint8_t sensorId, Sensor1Data* sensor1Data, Sensor2Data* sensor2Data) {
    bool success = false;

    if (xSemaphoreTake(modbusLock, pdMS_TO_TICKS(50)) == pdTRUE) {
        node.begin(sensorId, Serial2);
        delay(1);

        if (sensorId == 1) {
            uint8_t result = node.readInputRegisters(data_register_x_axis_1, 1);
            if (result == node.ku8MBSuccess) {
                float rawAcc = node.getResponseBuffer(0x00) / 10.0;
                sensor1Data->acceleration = envelopeDetection(highPassFilter(rawAcc, 0, 0));
                sensor1Data->valid = true;
                success = true;
            } else {
                Serial.println("Modbus read failed for Sensor 1");
            }
        } else if (sensorId == 2) {
            uint8_t result;
            result = node.readInputRegisters(data_register_x_axis_2, 1);
            sensor2Data->x = (result == node.ku8MBSuccess) ? envelopeDetection(node.getResponseBuffer(0x00) / 10.0) : 0;
            result = node.readInputRegisters(data_register_y_axis_2, 1);
            sensor2Data->y = (result == node.ku8MBSuccess) ? envelopeDetection(node.getResponseBuffer(0x00) / 10.0) : 0;
            result = node.readInputRegisters(data_register_z_axis_2, 1);
            sensor2Data->z = (result == node.ku8MBSuccess) ? envelopeDetection(node.getResponseBuffer(0x00) / 10.0) : 0;

            if (sensor2Data->x && sensor2Data->y && sensor2Data->z) {
                sensor2Data->valid = true;
                success = true;
            } else {
                Serial.println("Modbus read failed for Sensor 2");
            }
        }

        xSemaphoreGive(modbusLock);
    }
    return success;
}

// Task to read sensor data
void sensorReadTask(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(10); // 10ms delay for ~100Hz sampling

    while (true) {
        Sensor1Data data1 = {millis(), 0.0f, false};
        Sensor2Data data2 = {millis(), 0.0f, 0.0f, 0.0f, false};

        if (readModbusData(1, &data1, nullptr)) {
            xQueueSend(sensor1Queue, &data1, 0);
        }
        if (readModbusData(2, nullptr, &data2)) {
            xQueueSend(sensor2Queue, &data2, 0);
        }

        monitorMemory("SensorReadTask");
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}

// Task to process and send data
void communicationTask(void *pvParameters) {
    const int BATCH_SIZE = 100;
    Sensor1Data sensor1Batch[BATCH_SIZE];
    Sensor2Data sensor2Batch[BATCH_SIZE];
    int sensor1BatchIndex = 0;
    int sensor2BatchIndex = 0;

    while (true) {
        Sensor1Data data1;
        Sensor2Data data2;

        if (xQueueReceive(sensor1Queue, &data1, 0) == pdTRUE) {
            DynamicJsonDocument doc(128);
            doc["timestamp"] = data1.timestamp;
            doc["acceleration"] = data1.acceleration;
            char jsonBuffer[128];
            serializeJson(doc, jsonBuffer);
            publishMQTT(mqtt_topic_sensor1, jsonBuffer);

            sensor1Batch[sensor1BatchIndex++] = data1;
            if (sensor1BatchIndex >= BATCH_SIZE) {
                sendBatchToInfluxDB("accelerometer1", sensor1Batch, sensor1BatchIndex);
                sensor1BatchIndex = 0;
            }
        }

        if (xQueueReceive(sensor2Queue, &data2, 0) == pdTRUE) {
            DynamicJsonDocument doc(256);
            doc["timestamp"] = data2.timestamp;
            doc["x"] = data2.x;
            doc["y"] = data2.y;
            doc["z"] = data2.z;
            char jsonBuffer[256];
            serializeJson(doc, jsonBuffer);
            publishMQTT(mqtt_topic_sensor2, jsonBuffer);

            sensor2Batch[sensor2BatchIndex++] = data2;
            if (sensor2BatchIndex >= BATCH_SIZE) {
                sendBatchToInfluxDB("accelerometer2", sensor2Batch, sensor2BatchIndex);
                sensor2BatchIndex = 0;
            }
        }

        monitorMemory("CommunicationTask");
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

template <typename T>
void sendBatchToInfluxDB(const char* measurement, T* batch, int batchSize) {
    for (int i = 0; i < batchSize; i++) {
        Point point(measurement);
        point.clearFields();
        point.setTime(batch[i].timestamp * 1000000LL);

        // Check the type and add appropriate fields
        if constexpr (std::is_same<T, Sensor1Data>::value) {
            point.addField("acceleration", batch[i].acceleration);
        } else if constexpr (std::is_same<T, Sensor2Data>::value) {
            point.addField("x", batch[i].x);
            point.addField("y", batch[i].y);
            point.addField("z", batch[i].z);
        }

        if (!influxClient.writePoint(point)) {
            Serial.printf("Failed to write %s data to InfluxDB\n", measurement);
        }
    }
}


void setup() {
    Serial.begin(115200);
    Serial.println("Setup started");
    
    pinMode(MODBUS_DIR_PIN, OUTPUT);
    digitalWrite(MODBUS_DIR_PIN, LOW);
    Serial2.begin(MODBUS_SERIALs_BAUD, SERIAL_8N1, MODBUS_RX_PIN, MODBUS_TX_PIN);
    modbusLock = xSemaphoreCreateMutex();
    sensor1Queue = xQueueCreate(1000, sizeof(Sensor1Data));
    sensor2Queue = xQueueCreate(1000, sizeof(Sensor2Data));

    cfg = kiss_fftr_alloc(SAMPLES, 0, NULL, NULL);
    if (!cfg) {
        Serial.println("Failed to allocate memory for FFT configuration.");
        ESP.restart();
    }

    if (!connectWiFi() || !connectMQTT()) {
        Serial.println("Failed to connect, restarting...");
        ESP.restart();
    }

    xTaskCreatePinnedToCore(sensorReadTask, "SensorRead", 20000, NULL, 2, NULL, 0);
    xTaskCreatePinnedToCore(communicationTask, "Communication", 12000, NULL, 1, NULL, 1);
    Serial.println("Setup completed");
}

void loop() {
    if (WiFi.status() != WL_CONNECTED) {
        connectWiFi();
    }
    if (!mqttClient.connected()) {
        connectMQTT();
    }
    mqttClient.loop();
    delay(1000);
}

void cleanup() {
    free(cfg);
}