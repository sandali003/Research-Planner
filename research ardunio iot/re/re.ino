#include <Wire.h>

const int SDA_PIN = 21;
const int SCL_PIN = 22;

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);
  delay(1000);

  Serial.println("Checking MPU6050...");

  Wire.beginTransmission(0x68);
  byte error = Wire.endTransmission();

  if (error == 0) {
    Serial.println("MPU6050 connected successfully!");
  } else {
    Serial.println("MPU6050 NOT detected!");
  }
}

void loop() {
  delay(2000);
}