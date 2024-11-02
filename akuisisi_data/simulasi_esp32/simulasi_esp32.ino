#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <InfluxDbClient.h>
#include <random>

// WiFi Configuration
const char* ssid = "DINGINLESTARI";
const char* password = "ray12345678";

// MQTT Configuration
const char* mqtt_broker = "172.16.67.121";
const int mqtt_port = 1883;
const char* topic_3axis = "sensors/accelerometer_3axis";
const char* topic_1axis = "sensors/accelerometer_1axis";

// InfluxDB Configuration
#define INFLUXDB_URL "http://172.16.67.121:8086"
#define INFLUXDB_TOKEN "49Zx_X5c9z0f8daAYwjUXBa4Z9e86E1mdOaFLNWDEYZrl_mYI8o6Q0laCn6xqQDBuf68_kAIS3Op858rZspGjA=="
#define INFLUXDB_ORG "polman_bdg"
#define INFLUXDB_BUCKET "ta_rafza"

InfluxDBClient influxClient(INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET, INFLUXDB_TOKEN);
Point sensor("accelerometer");

// MQTT client setup
WiFiClient espClient;
PubSubClient client(espClient);

// Pseudo random generator for simulation
std::default_random_engine generator;
std::normal_distribution<float> distribution(0.0, 1.0);

// Accelerometer Simulation
struct Accelerometer3Axis {
  float getX() { return distribution(generator); }
  float getY() { return distribution(generator); }
  float getZ() { return distribution(generator); }
};

struct Accelerometer1Axis {
  float getValue() { return distribution(generator); }
};

// Instantiate sensors
Accelerometer3Axis sensor3Axis;
Accelerometer1Axis sensor1Axis;

// Connect to WiFi
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected");
}

// Connect to MQTT broker
void setup_mqtt() {
  client.setServer(mqtt_broker, mqtt_port);
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    if (client.connect("ESP32Client")) {
      Serial.println("connected");
    } else {
      Serial.print("failed with state ");
      Serial.print(client.state());
      delay(2000);
    }
  }
}

// Publish sensor data
void publish_data() {
  // 3-axis data
  float x = sensor3Axis.getX();
  float y = sensor3Axis.getY();
  float z = sensor3Axis.getZ();

  // Create JSON object
  DynamicJsonDocument doc(128);
  doc["x"] = x;
  doc["y"] = y;
  doc["z"] = z;

  // Serialize and publish
  char jsonBuffer[128];
  serializeJson(doc, jsonBuffer);
  if (client.publish(topic_3axis, jsonBuffer)) {
    Serial.print("Published 3-axis data: ");
    Serial.println(jsonBuffer);
  } else {
    Serial.println("Failed to publish 3-axis data");
  }

  // Send data to InfluxDB
  sensor.clearFields();
  sensor.addField("x", x);
  sensor.addField("y", y);
  sensor.addField("z", z);
  influxClient.writePoint(sensor);

  // 1-axis data
  float value = sensor1Axis.getValue();
  DynamicJsonDocument doc1(64);
  doc1["value"] = value;

  // Serialize and publish
  serializeJson(doc1, jsonBuffer);
  if (client.publish(topic_1axis, jsonBuffer)) {
    Serial.print("Published 1-axis data: ");
    Serial.println(jsonBuffer);
  } else {
    Serial.println("Failed to publish 1-axis data");
  }

  // Send 1-axis data to InfluxDB
  sensor.clearFields();
  sensor.addField("value", value);
  influxClient.writePoint(sensor);
}

void setup() {
  Serial.begin(115200);
  setup_wifi();
  setup_mqtt();

  // Setup InfluxDB client
  if (influxClient.validateConnection()) {
    Serial.print("Connected to InfluxDB: ");
    Serial.println(influxClient.getServerUrl());
  } else {
    Serial.print("InfluxDB connection failed: ");
    Serial.println(influxClient.getLastErrorMessage());
  }
}

void loop() {
  if (!client.connected()) {
    setup_mqtt();
  }
  client.loop();

  static unsigned long last_3axis_publish = 0;
  static unsigned long last_1axis_publish = 0;

  unsigned long now = millis();
  if (now - last_3axis_publish >= 200) { // 5 Hz publishing
    publish_data();
    last_3axis_publish = now;
  }

  if (now - last_1axis_publish >= 500) { // 2 Hz publishing
    publish_data();
    last_1axis_publish = now;
  }
}