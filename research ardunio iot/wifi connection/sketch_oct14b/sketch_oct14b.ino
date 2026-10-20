
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// Wi-Fi details (iPhone hotspot, "Maximize Compatibility" on for 2.4 GHz)
const char* WIFI_SSID = "Tharuka’s iphone";
const char* WIFI_PASSWORD = "12345678";

// AutoSense backend on the laptop (run "ipconfig" if the hotspot gives a new IP)
const char* API_URL =
    "http://172.20.10.9:3000/api/v1/readings";

// Device key from the website: Vehicles -> vehicle -> add device (shown only once)
const char* DEVICE_KEY = "f9485bc13b54eaf0303d5e7369fbb27b9c5f8839a378dacf";

// Sensor pins
const int SDA_PIN = 21;
const int SCL_PIN = 22;
const int VOLTAGE_PIN = 34;

#define ONE_WIRE_BUS 4
const byte MPU_ADDR = 0x68;

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature tempSensor(&oneWire);

bool mpuConnected = false;

unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 2000;

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

// Read sensors and send one reading to the backend
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

  // Backend format: {"readings":[{...}]}. Missing sensors are left out (null is rejected).
  String json = "{\"readings\":[{";
  json += "\"pin_voltage_v\":";
  json += String(pinVoltage, 3);

  if (mpuOK) {
    json += ",\"accel_x\":";
    json += String(ax);
    json += ",\"accel_y\":";
    json += String(ay);
    json += ",\"accel_z\":";
    json += String(az);
  }

  if (tempOK) {
    json += ",\"temperature_c\":";
    json += String(tempC, 2);
  }

  json += "}]}";

  Serial.println("\nSending sensor data:");
  Serial.println(json);

  HTTPClient http;
  http.setTimeout(5000);

  if (http.begin(API_URL)) {
    http.addHeader("Content-Type", "application/json");
    http.addHeader("x-device-key", DEVICE_KEY);

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

  Serial.println("AutoSense ready. Sending readings every 2 seconds.");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected.");
    connectWiFi();
  }

  if (millis() - lastSend >= SEND_INTERVAL) {
    lastSend = millis();
    collectAndSendData();
  }

  delay(10);
}
