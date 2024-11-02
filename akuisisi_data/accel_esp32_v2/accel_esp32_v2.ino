#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ModbusMaster.h>

// Pin Definitions
#define MODBUS_DIR_PIN  4  // DE/RE pin for the shared MAX485 transceiver
#define MODBUS_RX_PIN 18   // RX pin for MAX485 (Serial2)
#define MODBUS_TX_PIN 19   // TX pin for MAX485 (Serial2)
#define MODBUS_SERIAL_BAUD 9600  // Baud rate for communication

// WiFi Configuration
const char* ssid = "DINGINLESTARI";
const char* password = "ray12345678";

// MQTT Configuration
const char* mqtt_broker = "172.16.66.238";
const int mqtt_port = 1883;
const char* mqtt_topic = "sensors/accelerometer_data";
const char* mqtt_status_topic = "sensors/status";  // New topic for status messages

// Register data for reading accelerometer data
const uint16_t data_register_x_axis_1 = 0x0003;  // Sensor 1 (1-axis)
const uint16_t data_register_x_axis_2 = 0x000A;  // Sensor 2 (X-axis)
const uint16_t data_register_y_axis_2 = 0x000B;  // Sensor 2 (Y-axis)
const uint16_t data_register_z_axis_2 = 0x000C;  // Sensor 2 (Z-axis)

// System status variables
unsigned long lastSuccessfulRead = 0;
int consecutiveFailures = 0;
bool systemHealthy = true;

// ModbusMaster instance for both sensors (slaves)
ModbusMaster node;

// WiFi and MQTT client instances
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// Function to control MAX485 direction (shared DE/RE pin)
void modbusPreTransmission() {
  digitalWrite(MODBUS_DIR_PIN, HIGH);  // Set MAX485 to transmit mode
  delayMicroseconds(50);  // Short delay for stability
}

void modbusPostTransmission() {
  delayMicroseconds(50);  // Short delay for stability
  digitalWrite(MODBUS_DIR_PIN, LOW);   // Set MAX485 to receive mode
}

// Function to connect to WiFi with timeout
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
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    return true;
  } else {
    Serial.println("\nFailed to connect to WiFi");
    return false;
  }
}

// Function to connect to MQTT broker with timeout
bool connectMQTT() {
  mqttClient.setServer(mqtt_broker, mqtt_port);
  
  Serial.print("Connecting to MQTT...");
  int attempts = 0;
  
  while (!mqttClient.connected() && attempts < 3) {
    Serial.print(".");
    String clientId = "ESP32Client-" + String(random(0xffff), HEX);
    
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("\nConnected to MQTT broker");
      // Publish connection status
      mqttClient.publish(mqtt_status_topic, "{\"status\":\"connected\",\"device\":\"ESP32\"}");
      return true;
    }
    
    attempts++;
    delay(2000);
  }
  
  Serial.println("\nFailed to connect to MQTT broker");
  return false;
}

// Function to setup Modbus communication
void setup_modbus() {
  // Configure direction control pin
  pinMode(MODBUS_DIR_PIN, OUTPUT);
  digitalWrite(MODBUS_DIR_PIN, LOW);  // Default to receive mode

  // Begin serial communication with proper configuration
  Serial2.begin(MODBUS_SERIAL_BAUD, SERIAL_8N1, MODBUS_RX_PIN, MODBUS_TX_PIN);
  
  // Clear any pending data in serial buffer
  while(Serial2.available()) {
    Serial2.read();
  }
  
  // Set pre/post transmission callbacks
  node.preTransmission(modbusPreTransmission);
  node.postTransmission(modbusPostTransmission);

  // Add delay for MAX485 to stabilize
  delay(100);

  Serial.println("Modbus setup complete.");
}

// Function to read data from Sensor 1 (Slave ID 1) with reduced delays
float readSensor1() {
  uint8_t result;
  uint16_t raw_data_acceleration_1;

  node.clearResponseBuffer();
  node.begin(1, Serial2);

  result = node.readInputRegisters(data_register_x_axis_1, 1);
  if (result == node.ku8MBSuccess) {
    raw_data_acceleration_1 = node.getResponseBuffer(0x00);
    float acceleration_1 = raw_data_acceleration_1 / 10.0;
    lastSuccessfulRead = millis();
    consecutiveFailures = 0;
    return acceleration_1;
  } else {
    consecutiveFailures++;
    return -999.0;
  }
}

// Function to read data from Sensor 2 (Slave ID 2) with reduced delays
bool readSensor2(float &xAccel, float &yAccel, float &zAccel) {
  uint8_t result;

  node.clearResponseBuffer();
  node.begin(2, Serial2);

  result = node.readInputRegisters(data_register_x_axis_2, 1);
  if (result == node.ku8MBSuccess) {
    xAccel = node.getResponseBuffer(0x00) / 10.0;
  } else {
    return false;
  }

  result = node.readInputRegisters(data_register_y_axis_2, 1);
  if (result == node.ku8MBSuccess) {
    yAccel = node.getResponseBuffer(0x00) / 10.0;
  } else {
    return false;
  }

  result = node.readInputRegisters(data_register_z_axis_2, 1);
  if (result == node.ku8MBSuccess) {
    zAccel = node.getResponseBuffer(0x00) / 10.0;
  } else {
    return false;
  }

  return true;
}

// Function to publish data to MQTT with health check
void publishMQTT(const char* topic, const char* message) {
  if (!mqttClient.connected()) {
    if (!connectMQTT()) {
      Serial.println("Failed to reconnect to MQTT");
      return;
    }
  }
  
  if (mqttClient.publish(topic, message)) {
    Serial.println("Data published successfully");
  } else {
    Serial.println("Failed to publish data");
  }
}

// Function to check system health and publish status
void checkSystemHealth() {
  bool currentHealth = (consecutiveFailures < 5) && 
                      (millis() - lastSuccessfulRead < 30000) &&
                      (WiFi.status() == WL_CONNECTED) &&
                      mqttClient.connected();
                      
  if (currentHealth != systemHealthy) {
    systemHealthy = currentHealth;
    DynamicJsonDocument statusDoc(128);
    statusDoc["status"] = systemHealthy ? "healthy" : "error";
    statusDoc["failures"] = consecutiveFailures;
    statusDoc["lastRead"] = millis() - lastSuccessfulRead;
    
    char statusBuffer[128];
    serializeJson(statusDoc, statusBuffer);
    publishMQTT(mqtt_status_topic, statusBuffer);
  }
}

// Task to collect sensor data (runs on Core 1)
// Modified task to read sensor data at 100 Hz
void sensorDataTask(void *pvParameters) {
  static float xSum = 0, ySum = 0, zSum = 0, singleAxisSum = 0;
  static int sampleCount = 0;
  
  unsigned long lastTime = micros();  // Use micros() for more precise timing
  
  while (true) {
    unsigned long currentTime = micros();
    if (currentTime - lastTime >= 10000) {  // 10000 microseconds = 10 ms (100 Hz)
      lastTime = currentTime;

      // Read from Sensor 1
      float singleAxisAccel = readSensor1();
      if (singleAxisAccel != -999.0) {
        singleAxisSum += singleAxisAccel;
        sampleCount++;
      }

      // Read from Sensor 2
      float xAccel, yAccel, zAccel;
      if (readSensor2(xAccel, yAccel, zAccel)) {
        xSum += xAccel;
        ySum += yAccel;
        zSum += zAccel;
      }

      // Publish data every 10 samples
      if (sampleCount >= 10) {
        DynamicJsonDocument doc(256);
        doc["acceleration"] = singleAxisSum / sampleCount;
        doc["x"] = xSum / sampleCount;
        doc["y"] = ySum / sampleCount;
        doc["z"] = zSum / sampleCount;
        doc["samples"] = sampleCount;
        doc["timestamp"] = millis();
        
        char jsonBuffer[256];
        serializeJson(doc, jsonBuffer);
        publishMQTT(mqtt_topic, jsonBuffer);

        // Reset aggregation variables
        xSum = ySum = zSum = singleAxisSum = 0;
        sampleCount = 0;
      }
    }

    // Minimal delay to allow task switching
    delayMicroseconds(50);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("\nStarting system...");

  if (!connectWiFi()) {
    ESP.restart();  // Restart if WiFi connection fails
  }

  if (!connectMQTT()) {
    ESP.restart();  // Restart if MQTT connection fails
  }

  setup_modbus();

  // Create task for sensor data collection on Core 1
  xTaskCreatePinnedToCore(
    sensorDataTask,    // Task function
    "SensorDataTask",  // Task name
    10000,            // Stack size (bytes)
    NULL,             // Task parameters
    1,                // Priority
    NULL,             // Task handle
    1                 // Core ID
  );

  Serial.println("Setup complete.");
}

void loop() {
  // Main loop runs on Core 0
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection lost. Reconnecting...");
    connectWiFi();
  }
  
  mqttClient.loop();  // Handle MQTT messages
  delay(10);
}