#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ModbusMaster.h>
#include <InfluxDbClient.h>

// Pin Definitions
#define MODBUS_DIR_PIN  4
#define MODBUS_RX_PIN 18
#define MODBUS_TX_PIN 19
#define MODBUS_SERIAL_BAUD 9600  // Increased baud rate for faster communication

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
const int SAMPLES_PER_BATCH = 50;  // 50 samples
const int SAMPLING_INTERVAL_MS = 20;  // 20ms = 50Hz sampling rate

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

float readSensor1() {
    uint8_t result = node.readInputRegisters(0x0003, 1);
    if (result == node.ku8MBSuccess) {
        float value = node.getResponseBuffer(0x00) / 10.0;
        return value;
    }
    return -999.0;
}

bool readSensor2(float &xAccel, float &yAccel, float &zAccel) {
    uint8_t result;
    
    result = node.readInputRegisters(0x000A, 3);  // Read all 3 axes at once
    if (result == node.ku8MBSuccess) {
        xAccel = node.getResponseBuffer(0) / 10.0;
        yAccel = node.getResponseBuffer(1) / 10.0;
        zAccel = node.getResponseBuffer(2) / 10.0;
        return true;
    }
    return false;
}

void sensorDataTask(void *pvParameters) {
    TickType_t xLastWakeTime;
    const TickType_t xFrequency = pdMS_TO_TICKS(SAMPLING_INTERVAL_MS);
    xLastWakeTime = xTaskGetTickCount();
    
    while (true) {
        // Get timestamp
        unsigned long timestamp = millis();
        
        // Read sensors
        float singleAxisAccel = readSensor1();
        float xAccel, yAccel, zAccel;
        bool sensor2Success = readSensor2(xAccel, yAccel, zAccel);
        
        // Print sensor data to serial monitor
        if (singleAxisAccel != -999.0) {
            Serial.print("Single-axis acceleration: ");
            Serial.println(singleAxisAccel);
        } else {
            Serial.println("Failed to read single-axis acceleration");
        }
        
        if (sensor2Success) {
            Serial.print("X-Axis: ");
            Serial.print(xAccel);
            Serial.print(" | Y-Axis: ");
            Serial.print(yAccel);
            Serial.print(" | Z-Axis: ");
            Serial.println(zAccel);
        } else {
            Serial.println("Failed to read 3-axis acceleration");
        }
        
        // Store data in buffer
        if (singleAxisAccel != -999.0 || sensor2Success) {
            sensorBuffer[currentSample].acceleration = singleAxisAccel;
            sensorBuffer[currentSample].x = xAccel;
            sensorBuffer[currentSample].y = yAccel;
            sensorBuffer[currentSample].z = zAccel;
            sensorBuffer[currentSample].timestamp = timestamp;
            
            currentSample++;
            Serial.print("Sample stored. Current sample count: ");
            Serial.println(currentSample);
        }
        
        // If buffer is full, publish data
        if (currentSample >= SAMPLES_PER_BATCH) {
            Serial.println("Buffer full. Preparing to publish data...");
            DynamicJsonDocument doc(4096);
            JsonArray samples = doc.createNestedArray("samples");
            
            for (int i = 0; i < SAMPLES_PER_BATCH; i++) {
                JsonObject sample = samples.createNestedObject();
                sample["timestamp"] = sensorBuffer[i].timestamp;
                sample["acceleration"] = sensorBuffer[i].acceleration;
                sample["x"] = sensorBuffer[i].x;
                sample["y"] = sensorBuffer[i].y;
                sample["z"] = sensorBuffer[i].z;
                
                // Write to InfluxDB
                sensor.clearFields();
                sensor.setTime(sensorBuffer[i].timestamp * 1000000LL);  // Convert to nanoseconds
                sensor.addField("acceleration", sensorBuffer[i].acceleration);
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
            
            // Print publication status
            Serial.println("Batch published to MQTT and InfluxDB.");
            
            // Reset buffer
            currentSample = 0;
            publishDebug("Batch published");
        }
        
        // Precise timing control
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
