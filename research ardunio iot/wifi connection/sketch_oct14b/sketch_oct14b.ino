
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// Wi-Fi details
const char* WIFI_SSID = "SLT_FIBRE";
const char* WIFI_PASSWORD = "Abhishek";

// Laptop API URLs
const char* API_URL =
    "http://192.168.1.7:8000/readings";

const char* STATUS_URL =
    "http://192.168.1.7:8000/control/status";

// Sensor pins
const int SDA_PIN = 21;
const int SCL_PIN = 22;
const int VOLTAGE_PIN = 34;

#define ONE_WIRE_BUS 4
const byte MPU_ADDR = 0x68;

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature tempSensor(&oneWire);

bool mpuConnected = false;
bool wasCollecting = false;

unsigned long lastStatusCheck = 0;
const unsigned long STATUS_INTERVAL = 2000;

// Connect to Wi-Fi
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to Wi-Fi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWi-Fi connected!");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

// Check laptop's START / STOP command
bool isCollectionEnabled() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.setTimeout(3000);

  if (!http.begin(STATUS_URL)) {
    Serial.println("Cannot connect to control API.");
    return false;
  }

  int code = http.GET();
  bool enabled = false;

  if (code == HTTP_CODE_OK) {
    String response = http.getString();
    response.replace(" ", "");
    response.replace("\n", "");
    response.replace("\r", "");

    if (response.indexOf("\"enabled\":true") >= 0) {
      enabled = true;
    }
  } else {
    Serial.print("Status check failed: ");
    Serial.println(code);
  }

  http.end();
  return enabled;
}

// Read sensors and send data to API
void collectAndSendData() {
  int16_t ax = 0, ay = 0, az = 0;
  bool mpuOK = false;

  if (mpuConnected) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x3B);

    if (Wire.endTransmission(false) == 0 &&
        Wire.requestFrom(MPU_ADDR, (uint8_t)6) == 6) {

      ax = (int16_t)((Wire.read() << 8) | Wire.read());
      ay = (int16_t)((Wire.read() << 8) | Wire.read());
      az = (int16_t)((Wire.read() << 8) | Wire.read());

      mpuOK = true;
    }
  }

  tempSensor.requestTemperatures();
  float tempC = tempSensor.getTempCByIndex(0);

  bool tempOK =
      (tempC != DEVICE_DISCONNECTED_C && tempC > -100);

  int voltageADC = analogRead(VOLTAGE_PIN);
  float pinVoltage = voltageADC * (3.3f / 4095.0f);

  String json = "{";
  json += "\"vehicle_id\":\"TEST_CAR_001\",";

  json += "\"accel_x\":";
  json += mpuOK ? String(ax) : "null";

  json += ",\"accel_y\":";
  json += mpuOK ? String(ay) : "null";

  json += ",\"accel_z\":";
  json += mpuOK ? String(az) : "null";

  json += ",\"temperature_c\":";
  json += tempOK ? String(tempC, 2) : "null";

  json += ",\"voltage_adc\":";
  json += String(voltageADC);

  json += ",\"pin_voltage_v\":";
  json += String(pinVoltage, 3);
  json += "}";

  Serial.println("\nSending sensor data:");
  Serial.println(json);

  HTTPClient http;
  http.setTimeout(5000);

  if (http.begin(API_URL)) {
    http.addHeader("Content-Type", "application/json");

    int httpCode = http.POST(json);

    Serial.print("HTTP response code: ");
    Serial.println(httpCode);

    if (httpCode > 0) {
      Serial.println(http.getString());
    } else {
      Serial.println(http.errorToString(httpCode));
    }

    http.end();
  } else {
    Serial.println("Could not start HTTP connection.");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(SDA_PIN, SCL_PIN);

  Wire.beginTransmission(MPU_ADDR);
  if (Wire.endTransmission() == 0) {
    mpuConnected = true;

    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x6B);
    Wire.write(0x00);
    Wire.endTransmission();

    Serial.println("MPU6050 connected.");
  } else {
    Serial.println("MPU6050 not detected.");
  }

  tempSensor.begin();

  analogReadResolution(12);
  analogSetPinAttenuation(VOLTAGE_PIN, ADC_11db);

  connectWiFi();

  Serial.println("AutoSense control system ready.");
  Serial.println("Waiting for START command...");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected.");
    connectWiFi();
  }

  // Check the control command every 2 seconds
  if (millis() - lastStatusCheck >= STATUS_INTERVAL) {
    lastStatusCheck = millis();

    bool enabled = isCollectionEnabled();

    if (enabled && !wasCollecting) {
      Serial.println("START received: collection enabled.");
    }

    if (!enabled && wasCollecting) {
      Serial.println("STOP received: collection stopped.");
    }

    wasCollecting = enabled;

    if (enabled) {
      collectAndSendData();
    } else {
      Serial.println("Collection stopped. Waiting...");
    }
  }

  delay(10);
}
