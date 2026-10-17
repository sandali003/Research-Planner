
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ===== MPU6050 SETTINGS =====
const int SDA_PIN = 21;
const int SCL_PIN = 22;
const byte MPU_ADDR = 0x68;

// ===== DS18B20 SETTINGS =====
#define ONE_WIRE_BUS 4
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature tempSensor(&oneWire);

// ===== VOLTAGE SENSOR SETTINGS =====
const int VOLTAGE_PIN = 34;

// ===== SENSOR STATUS =====
bool mpuConnected = false;

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Initialize I2C
  Wire.begin(SDA_PIN, SCL_PIN);

  // Check MPU6050 connection
  Wire.beginTransmission(MPU_ADDR);
  byte error = Wire.endTransmission();

  if (error == 0) {
    mpuConnected = true;

    // Wake up MPU6050
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x6B);
    Wire.write(0x00);
    Wire.endTransmission();
  }

  // Initialize DS18B20
  tempSensor.begin();

  // Configure ADC
  analogReadResolution(12);
  analogSetPinAttenuation(VOLTAGE_PIN, ADC_11db);

  // CSV header
  Serial.println("Time_ms,MPU_Status,Accel_X_Raw,Accel_Y_Raw,Accel_Z_Raw,Temperature_C,Voltage_ADC,ESP32_Pin_V");
}

void loop() {
  // ===== 1. READ MPU6050 =====
  int16_t ax = 0;
  int16_t ay = 0;
  int16_t az = 0;
  bool mpuReadOK = false;

  if (mpuConnected) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x3B);

    if (Wire.endTransmission(false) == 0 &&
        Wire.requestFrom(MPU_ADDR, (uint8_t)6) == 6) {

      ax = (int16_t)((Wire.read() << 8) | Wire.read());
      ay = (int16_t)((Wire.read() << 8) | Wire.read());
      az = (int16_t)((Wire.read() << 8) | Wire.read());

      mpuReadOK = true;
    }
  }

  // ===== 2. READ TEMPERATURE =====
  tempSensor.requestTemperatures();
  float temperature = tempSensor.getTempCByIndex(0);

  bool tempOK = (temperature != DEVICE_DISCONNECTED_C);

  // ===== 3. READ VOLTAGE ADC =====
  int rawADC = analogRead(VOLTAGE_PIN);
  float pinVoltage = rawADC * (3.3 / 4095.0);

  // ===== 4. PRINT CSV ROW =====
  Serial.print(millis());
  Serial.print(",");

  Serial.print(mpuReadOK ? "OK" : "ERROR");
  Serial.print(",");

  if (mpuReadOK) {
    Serial.print(ax);
    Serial.print(",");
    Serial.print(ay);
    Serial.print(",");
    Serial.print(az);
  } else {
    Serial.print("NA,NA,NA");
  }
  Serial.print(",");

  if (tempOK) {
    Serial.print(temperature, 2);
  } else {
    Serial.print("NA");
  }
  Serial.print(",");

  Serial.print(rawADC);
  Serial.print(",");

  Serial.println(pinVoltage, 3);

  delay(2000);
}
