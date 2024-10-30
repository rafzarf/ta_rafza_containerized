#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <InfluxDbClient.h> 
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
const char* mqtt_broker = "192.168.221.251";
const int mqtt_port = 1883;
const char* mqtt_topic = "sensors/accelerometer_data";

// InfluxDB Configuration
#define INFLUXDB_URL "http://192.168.131.251:8086"
#define INFLUXDB_TOKEN "49Zx_X5c9z0f8daAYwjUXBa4Z9e86E1mdOaFLNWDEYZrl_mYI8o6Q0laCn6xqQDBuf68_kAIS3Op858rZspGjA=="
#define INFLUXDB_ORG "polman_bdg"
#define INFLUXDB_BUCKET "ta_rafza"

// Register data for reading accelerometer data
uint16_t data_register_x_axis_1 = 0x0003;  // Sensor 1 (1-axis)
uint16_t data_register_x_axis_2 = 0x000A;  // Sensor 2 (X-axis)
uint16_t data_register_y_axis_2 = 0x000B;  // Sensor 2 (Y-axis)
uint16_t data_register_z_axis_2 = 0x000C;  // Sensor 2 (Z-axis)

// ModbusMaster instance for both sensors (slaves)
ModbusMaster node;

// InfluxDB Client and data points
InfluxDBClient influxClient(INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET, INFLUXDB_TOKEN);
Point sensor1AxisPoint("sensor1");
Point sensor3AxisPoint("sensor3");


// WiFi and MQTT client instances
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// Function to control MAX485 direction (shared DE/RE pin)
void modbusPreTransmission() {
  digitalWrite(MODBUS_DIR_PIN, HIGH);  // Set MAX485 to transmit mode
}

void modbusPostTransmission() {
  digitalWrite(MODBUS_DIR_PIN, LOW);   // Set MAX485 to receive mode
}

// Function to connect to WiFi
void connectWiFi() {
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");
}

// Function to connect to MQTT broker
void connectMQTT() {
  mqttClient.setServer(mqtt_broker, mqtt_port);
  while (!mqttClient.connected()) {
    Serial.print("Connecting to MQTT...");
    if (mqttClient.connect("ESP32Client")) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

// Function to setup Modbus communication
void setup_modbus() {
  pinMode(MODBUS_DIR_PIN, OUTPUT);
  digitalWrite(MODBUS_DIR_PIN, LOW);  // Default to receive mode

  Serial2.begin(MODBUS_SERIAL_BAUD, SERIAL_8N1, MODBUS_RX_PIN, MODBUS_TX_PIN);
  
  // Set pre/post transmission callbacks
  node.preTransmission(modbusPreTransmission);
  node.postTransmission(modbusPostTransmission);

  Serial.println("Modbus setup complete.");
}

// Function to read data from Sensor 1 (Slave ID 1)
float readSensor1() {
  uint8_t result;
  uint16_t raw_data_acceleration_1;

  node.begin(1, Serial2);
  result = node.readInputRegisters(data_register_x_axis_1, 1);

  if (result == node.ku8MBSuccess) {
    raw_data_acceleration_1 = node.getResponseBuffer(0x00);
    float acceleration_1 = raw_data_acceleration_1 / 10.0;
    return acceleration_1;
  } else {
    Serial.println("Error reading from Sensor 1");
    return -1;
  }
}

// Function to read data from Sensor 2 (Slave ID 2)
bool readSensor2(float &xAccel, float &yAccel, float &zAccel) {
  uint8_t result;
  
  node.begin(2, Serial2);

  // Read X-axis from Sensor 2
  result = node.readInputRegisters(data_register_x_axis_2, 1);
  if (result == node.ku8MBSuccess) {
    xAccel = node.getResponseBuffer(0x00) / 10.0;
  } else {
    Serial.println("Error reading X-Axis from Sensor 2");
    return false;
  }

  delay(100);  // Small delay to prevent data collision

  // Read Y-axis from Sensor 2
  result = node.readInputRegisters(data_register_y_axis_2, 1);
  if (result == node.ku8MBSuccess) {
    yAccel = node.getResponseBuffer(0x00) / 10.0;
  } else {
    Serial.println("Error reading Y-Axis from Sensor 2");
    return false;
  }

  delay(100);  // Small delay to prevent data collision

  // Read Z-axis from Sensor 2
  result = node.readInputRegisters(data_register_z_axis_2, 1);
  if (result == node.ku8MBSuccess) {
    zAccel = node.getResponseBuffer(0x00) / 10.0;
  } else {
    Serial.println("Error reading Z-Axis from Sensor 2");
    return false;
  }

  return true;
}

// Function to publish data to MQTT
void publishMQTT(const char* topic, const char* message) {
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.publish(topic, message);
}

// Function to directly write data to InfluxDB (without batching)
void writeDirectToInfluxDB(float singleAxisAccel, float xAccel, float yAccel, float zAccel) {
  // Write single-axis data directly to InfluxDB
  sensor1AxisPoint.clearFields();
  sensor1AxisPoint.addField("acceleration", singleAxisAccel);
  if (influxClient.writePoint(sensor1AxisPoint)) {
    Serial.println("Single-axis data written to InfluxDB successfully.");
  } else {
    Serial.print("Failed to write single-axis data to InfluxDB: ");
    Serial.println(influxClient.getLastErrorMessage());
  }

  // Write three-axis data directly to InfluxDB
  sensor3AxisPoint.clearFields();
  sensor3AxisPoint.addField("x", xAccel);
  sensor3AxisPoint.addField("y", yAccel);
  sensor3AxisPoint.addField("z", zAccel);
  if (influxClient.writePoint(sensor3AxisPoint)) {
    Serial.println("Three-axis data written to InfluxDB successfully.");
  } else {
    Serial.print("Failed to write three-axis data to InfluxDB: ");
    Serial.println(influxClient.getLastErrorMessage());
  }
}

void setup() {
  Serial.begin(115200);
  connectWiFi();
  connectMQTT();
  setup_modbus();

  // Set up InfluxDB tags
  sensor1AxisPoint.addTag("device", "ESP32");
  sensor3AxisPoint.addTag("device", "ESP32");

  Serial.println("Setup complete.");
}

void loop() {
  // Read from Sensor 1
  float singleAxisAccel = readSensor1();
  if (singleAxisAccel != -1) {
    Serial.print("Sensor 1 Acceleration: ");
    Serial.println(singleAxisAccel);

    // Publish to MQTT
    DynamicJsonDocument doc1(64);
    doc1["acceleration"] = singleAxisAccel;
    char jsonBuffer[64];
    serializeJson(doc1, jsonBuffer);
    publishMQTT(mqtt_topic, jsonBuffer);
  }

  delay(500); // Small delay to prevent data collision

  // Read from Sensor 2
  float xAccel, yAccel, zAccel;
  if (readSensor2(xAccel, yAccel, zAccel)) {
    Serial.print("Sensor 2 X: "); Serial.print(xAccel);
    Serial.print(" Y: "); Serial.print(yAccel);
    Serial.print(" Z: "); Serial.println(zAccel);

    // Publish to MQTT
    DynamicJsonDocument doc2(128);
    doc2["x"] = xAccel;
    doc2["y"] = yAccel;
    doc2["z"] = zAccel;
    char jsonBuffer[128];
    serializeJson(doc2, jsonBuffer);
    publishMQTT(mqtt_topic, jsonBuffer);

    // Write data to InfluxDB directly after reading
    writeDirectToInfluxDB(singleAxisAccel, xAccel, yAccel, zAccel);
  }

  delay(1000); // Main loop delay to stabilize
}