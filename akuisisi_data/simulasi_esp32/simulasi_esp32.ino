#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ModbusMaster.h>
#include <InfluxDbClient.h>
#include <SD.h>
#include <SPI.h>

// Pin Definitions
#define MODBUS_DIR_PIN  4
#define MODBUS_RX_PIN 18
#define MODBUS_TX_PIN 19
#define MODBUS_SERIAL_BAUD 9600

// SD Card Configuration
#define SD_CS_PIN 5

// WiFi Configuration
const char* ssid = "DINGINLESTARI";
const char* password = "ray12345678";

// MQTT Configuration
const char* mqtt_broker = "172.16.66.238";
const int mqtt_port = 1883;
const char* mqtt_topic = "sensors/accelerometer_data";
const char* mqtt_status_topic = "sensors/status";
const char* mqtt_debug_topic = "sensors/debug";

// InfluxDB Configuration
#define INFLUXDB_URL "http://172.16.66.238:8086"
#define INFLUXDB_TOKEN "49Zx_X5c9z0f8daAYwjUXBa4Z9e86E1mdOaFLNWDEYZrl_mYI8o6Q0laCn6xqQDBuf68_kAIS3Op858rZspGjA=="
#define INFLUXDB_ORG "polman_bdg"
#define INFLUXDB_BUCKET_COMBINED "bucket_combined"

InfluxDBClient influxClientCombined(INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET_COMBINED, INFLUXDB_TOKEN);
Point sensor("accelerometer");

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
ModbusMaster node;

// System status variables
unsigned long lastSuccessfulRead = 0;
int consecutiveFailures = 0;
bool systemHealthy = true;

// Buffer for storing samples
const int SAMPLES_PER_BATCH = 50;  // 50 samples for MQTT
const int SAMPLING_INTERVAL_MS = 20;  // 20ms = 50Hz sampling rate for MQTT
const int HIGH_FREQ_SAMPLING_MS = 1;  // 1ms = 1000Hz for saving to SD

struct SensorData {
    float acceleration;
    float x;
    float y;
    float z;
    unsigned long timestamp;
};

SensorData sensorBuffer[SAMPLES_PER_BATCH];
int currentSample = 0;

// Forward declarations
bool connectWiFi();
bool connectMQTT();
void setup_modbus();

void publishDebug(const char* message) {
    Serial.println(message);
    mqttClient.publish(mqtt_debug_topic, message);
}

void publishDebug(String message) {
    Serial.println(message);
    mqttClient.publish(mqtt_debug_topic, message.c_str());
}

float simulateSensorValue() {
    return random(-100, 100) / 10.0;  // Simulated value between -10.0 and 10.0
}

bool simulateSensorData(float &xAccel, float &yAccel, float &zAccel) {
    xAccel = simulateSensorValue();
    yAccel = simulateSensorValue();
    zAccel = simulateSensorValue();
    return true;
}

void sensorDataTask(void *pvParameters) {
    TickType_t xLastWakeTime;
    const TickType_t xFrequency = pdMS_TO_TICKS(SAMPLING_INTERVAL_MS);
    xLastWakeTime = xTaskGetTickCount();
    
    while (true) {
        unsigned long timestamp = millis();
        float xAccel, yAccel, zAccel;
        bool sensor2Success = simulateSensorData(xAccel, yAccel, zAccel);
        
        if (sensor2Success) {
            Serial.print("X-Axis: ");
            Serial.print(xAccel);
            Serial.print(" | Y-Axis: ");
            Serial.print(yAccel);
            Serial.print(" | Z-Axis: ");
            Serial.println(zAccel);
        } else {
            Serial.println("Failed to read simulated sensor data");
        }
        
        // Store data in buffer for MQTT/InfluxDB
        sensorBuffer[currentSample].x = xAccel;
        sensorBuffer[currentSample].y = yAccel;
        sensorBuffer[currentSample].z = zAccel;
        sensorBuffer[currentSample].timestamp = timestamp;
        
        currentSample++;
        Serial.print("Sample stored. Current sample count: ");
        Serial.println(currentSample);
        
        // Save high-frequency data to SD card
        File dataFile = SD.open("/sensor_data.csv", FILE_APPEND);
        if (dataFile) {
            dataFile.printf("%lu,%.2f,%.2f,%.2f\n", timestamp, xAccel, yAccel, zAccel);
            dataFile.close();
        } else {
            Serial.println("Error writing to SD card");
        }
        
        // If buffer is full, publish data
        if (currentSample >= SAMPLES_PER_BATCH) {
            Serial.println("Buffer full. Preparing to publish data...");
            DynamicJsonDocument doc(4096);
            JsonArray samples = doc.createNestedArray("samples");
            
            for (int i = 0; i < SAMPLES_PER_BATCH; i++) {
                JsonObject sample = samples.createNestedObject();
                sample["timestamp"] = sensorBuffer[i].timestamp;
                sample["x"] = sensorBuffer[i].x;
                sample["y"] = sensorBuffer[i].y;
                sample["z"] = sensorBuffer[i].z;
                
                // Write to InfluxDB
                sensor.clearFields();
                sensor.setTime(sensorBuffer[i].timestamp * 1000000LL);
                sensor.addField("x", sensorBuffer[i].x);
                sensor.addField("y", sensorBuffer[i].y);
                sensor.addField("z", sensorBuffer[i].z);
                
                if (!influxClientCombined.writePoint(sensor)) {
                    Serial.print("Failed to write point to InfluxDB: ");
                    Serial.println(influxClientCombined.getLastErrorMessage());
                } else {
                    Serial.println("Point written successfully to InfluxDB.");
                }
            }
            
            // Publish to MQTT
            String jsonString;
            serializeJson(doc, jsonString);
            mqttClient.publish(mqtt_topic, jsonString.c_str());
            
            Serial.println("Batch published to MQTT and InfluxDB.");
            currentSample = 0;
            publishDebug("Batch published");
        }
        
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}

bool connectWiFi() {
    Serial.print("Connecting to WiFi...");
    WiFi.begin(ssid, password);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nConnected to WiFi");
        return true;
    } else {
        Serial.println("\nFailed to connect to WiFi");
        return false;
    }
}

bool connectMQTT() {
    mqttClient.setServer(mqtt_broker, mqtt_port);
    Serial.print("Connecting to MQTT...");
    while (!mqttClient.connected()) {
        String clientId = "ESP32Client-" + String(random(0xffff), HEX);
        if (mqttClient.connect(clientId.c_str())) {
            Serial.println("\nConnected to MQTT broker");
            mqttClient.publish(mqtt_status_topic, "{\"status\":\"connected\",\"device\":\"ESP32\"}");
            return true;
        }
        Serial.print(".");
        delay(1000);
    }
    Serial.println("\nFailed to connect to MQTT broker");
    return false;
}

void setup_modbus() {
    pinMode(MODBUS_DIR_PIN, OUTPUT);
    digitalWrite(MODBUS_DIR_PIN, LOW);
    Serial2.begin(MODBUS_SERIAL_BAUD, SERIAL_8N1, MODBUS_RX_PIN, MODBUS_TX_PIN);
    node.begin(1, Serial2);
    node.preTransmission([]() { digitalWrite(MODBUS_DIR_PIN, HIGH); });
    node.postTransmission([]() { digitalWrite(MODBUS_DIR_PIN, LOW); });
    delay(100);
    Serial.println("Modbus setup complete.");
}

void setup() {
    Serial.begin(115200);
    Serial.println("\nStarting system...");

    if (!SD.begin(SD_CS_PIN)) {
        Serial.println("SD card initialization failed!");
        return;
    }
    Serial.println("SD card initialized.");

    if (!connectWiFi()) {
        ESP.restart();
    }

    if (!connectMQTT()) {
        ESP.restart();
    }

    setup_modbus();

    if (!influxClientCombined.validateConnection()) {
        Serial.print("Failed to connect to InfluxDB Combined Bucket: ");
        Serial.println(influxClientCombined.getLastErrorMessage());
    } else {
        Serial.print("Connected to InfluxDB Combined Bucket: ");
        Serial.println(influxClientCombined.getServerUrl());
    }

    xTaskCreatePinnedToCore(sensorDataTask, "SensorDataTask", 20000, NULL, 1, NULL, 1);
    Serial.println("Setup complete.");
}

void loop() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi disconnected. Reconnecting...");
        connectWiFi();
    }
    
    if (!mqttClient.connected()) {
        Serial.println("MQTT disconnected. Reconnecting...");
        connectMQTT();
    }
    
    mqttClient.loop();
    delay(10);
}
