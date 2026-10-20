/*
  AutoSense ESP32 firmware: external sensors + OBD-II (ELM327 Bluetooth Classic).

  Every SEND_INTERVAL_MS:
    - Vibration burst: BURST_SAMPLES accelerometer samples at ~BURST_RATE_HZ,
      sent as one batch. The backend removes gravity and computes the RMS per
      axis over the window, so it gets real engine vibration (a single sample
      every few seconds cannot measure it).
    - DS18B20 temperature and battery pin voltage go with the first sample.
  OBD-II (rpm, load, coolant, speed) is polled without blocking; each full
  set is sent to /api/v1/readings/obd. Without an adapter the sensors keep
  streaming and the adapter is retried every OBD_RETRY_MS.

  Board: "ESP32 Dev Module" (original ESP32; S3/C3 have no Bluetooth Classic).
  Tools -> Partition Scheme -> "Huge APP (3MB No OTA)" (WiFi + Bluetooth is large).
  Libraries: ELMduino, OneWire, DallasTemperature.
  Settings: copy secrets.example.h to secrets.h and fill it in.
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <BluetoothSerial.h>
#include <ELMduino.h>

#include "secrets.h"

// Sensor pins
const int SDA_PIN = 21;
const int SCL_PIN = 22;
const int VOLTAGE_PIN = 34;
#define ONE_WIRE_BUS 4
const byte MPU_ADDR = 0x68;

// Vibration burst
const int BURST_SAMPLES = 256;
const int BURST_RATE_HZ = 500;
const unsigned long SEND_INTERVAL_MS = 5000;

// OBD-II
const unsigned long OBD_RETRY_MS = 30000;

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature tempSensor(&oneWire);
BluetoothSerial SerialBT;
ELM327 elm;

bool mpuConnected = false;
bool obdConnected = false;
unsigned long lastSend = 0;
unsigned long lastObdTry = 0;

int16_t burstX[BURST_SAMPLES], burstY[BURST_SAMPLES], burstZ[BURST_SAMPLES];

// OBD-II polling: one PID at a time (ELMduino is non-blocking)
enum ObdPid { PID_RPM, PID_LOAD, PID_COOLANT, PID_SPEED, PID_COUNT };
ObdPid currentPid = PID_RPM;
float obdValues[PID_COUNT];

// ---------------------------------------------------------------
// Wi-Fi + HTTP
// ---------------------------------------------------------------
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.print("\nWi-Fi connected. ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

void postJson(const String& url, const String& json, const char* label) {
  HTTPClient http;
  http.setTimeout(5000);
  if (!http.begin(url)) {
    Serial.println("Could not start HTTP connection.");
    return;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("x-device-key", DEVICE_KEY);
  int code = http.POST(json);
  Serial.printf("%s -> HTTP %d ", label, code);
  Serial.println(code > 0 ? http.getString() : http.errorToString(code));
  http.end();
}

// ---------------------------------------------------------------
// External sensors
// ---------------------------------------------------------------
void setupMpu() {
  Wire.beginTransmission(MPU_ADDR);
  if (Wire.endTransmission() != 0) {
    Serial.println("MPU6050 not detected.");
    return;
  }
  mpuConnected = true;

  Wire.beginTransmission(MPU_ADDR);  // wake up
  Wire.write(0x6B);
  Wire.write(0x00);
  Wire.endTransmission();

  Wire.beginTransmission(MPU_ADDR);  // low-pass filter ~184 Hz (anti-aliasing for 500 Hz sampling)
  Wire.write(0x1A);
  Wire.write(0x01);
  Wire.endTransmission();

  Serial.println("MPU6050 connected.");
}

bool readAccel(int16_t& ax, int16_t& ay, int16_t& az) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom(MPU_ADDR, (uint8_t)6) != 6) {
    return false;
  }
  ax = (int16_t)((Wire.read() << 8) | Wire.read());
  ay = (int16_t)((Wire.read() << 8) | Wire.read());
  az = (int16_t)((Wire.read() << 8) | Wire.read());
  return true;
}

// Fills the burst buffers; returns how many samples were read
int sampleBurst() {
  if (!mpuConnected) return 0;
  const unsigned long periodUs = 1000000UL / BURST_RATE_HZ;
  int n = 0;
  unsigned long next = micros();
  for (int i = 0; i < BURST_SAMPLES; i++) {
    while ((long)(micros() - next) < 0) {}
    next += periodUs;
    if (readAccel(burstX[n], burstY[n], burstZ[n])) n++;
  }
  return n;
}

void sendSensorBatch() {
  int n = sampleBurst();

  tempSensor.requestTemperatures();
  float tempC = tempSensor.getTempCByIndex(0);
  bool tempOK = (tempC != DEVICE_DISCONNECTED_C && tempC > -100);
  float pinVoltage = analogRead(VOLTAGE_PIN) * (3.3f / 4095.0f);

  // {"readings":[{first sample + temperature + voltage}, {sample}, ...]}
  String json;
  json.reserve(64 + n * 48);
  json = "{\"readings\":[{\"pin_voltage_v\":" + String(pinVoltage, 3);
  if (tempOK) json += ",\"temperature_c\":" + String(tempC, 2);
  for (int i = 0; i < n; i++) {
    if (i > 0) json += ",{";
    else json += ",";
    json += "\"accel_x\":" + String(burstX[i]) +
            ",\"accel_y\":" + String(burstY[i]) +
            ",\"accel_z\":" + String(burstZ[i]) + "}";
  }
  if (n == 0) json += "}";
  json += "]}";

  Serial.printf("\nSensors: %d vibration samples, %.2f C, pin %.3f V\n", n, tempOK ? tempC : NAN, pinVoltage);
  postJson(String(API_BASE) + "/readings", json, "sensor batch");
}

// ---------------------------------------------------------------
// OBD-II
// ---------------------------------------------------------------
void connectObd() {
  lastObdTry = millis();
  Serial.printf("Connecting to OBD-II adapter \"%s\"...\n", OBD_DEVICE_NAME);
  if (!SerialBT.connect(OBD_DEVICE_NAME)) {
    Serial.println("OBD-II adapter not found. Sending sensor data only.");
    return;
  }
  if (!elm.begin(SerialBT, false, 2000)) {
    Serial.println("ELM327 did not respond.");
    SerialBT.disconnect();
    return;
  }
  obdConnected = true;
  currentPid = PID_RPM;
  Serial.println("OBD-II connected.");
}

float queryPid(ObdPid pid) {
  switch (pid) {
    case PID_RPM: return elm.rpm();
    case PID_LOAD: return elm.engineLoad();
    case PID_COOLANT: return elm.engineCoolantTemp();
    default: return elm.kph();
  }
}

void sendObdReading() {
  String json = "{\"readings\":[{\"rpm\":" + String(obdValues[PID_RPM], 0) +
                ",\"engine_load\":" + String(obdValues[PID_LOAD], 1) +
                ",\"coolant_temp\":" + String(obdValues[PID_COOLANT], 1) +
                ",\"speed\":" + String(obdValues[PID_SPEED], 0) + "}]}";
  Serial.println(json);
  postJson(String(API_BASE) + "/readings/obd", json, "obd");
}

void pollObd() {
  float value = queryPid(currentPid);
  if (elm.nb_rx_state == ELM_GETTING_MSG) return;  // still waiting for this PID

  if (elm.nb_rx_state != ELM_SUCCESS) {
    elm.printError();
    if (!SerialBT.connected()) {
      Serial.println("OBD-II connection lost.");
      obdConnected = false;
      return;
    }
    currentPid = PID_RPM;  // start the set again
    return;
  }

  obdValues[currentPid] = value;
  currentPid = (ObdPid)(currentPid + 1);
  if (currentPid == PID_COUNT) {
    sendObdReading();
    currentPid = PID_RPM;
  }
}

// ---------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);
  setupMpu();

  tempSensor.begin();
  analogReadResolution(12);
  analogSetPinAttenuation(VOLTAGE_PIN, ADC_11db);

  connectWiFi();

  SerialBT.begin("AutoSense", true);  // master mode
  // ESP32 core 3.x signature; on core 2.x use SerialBT.setPin(OBD_PIN);
  SerialBT.setPin(OBD_PIN, strlen(OBD_PIN));
  connectObd();

  Serial.println("AutoSense ready.");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected.");
    connectWiFi();
  }

  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    sendSensorBatch();
  }

  if (obdConnected) {
    pollObd();
  } else if (millis() - lastObdTry >= OBD_RETRY_MS) {
    connectObd();
  }
}
