void setup() {
  Serial.begin(115200);
}

void loop() {
  int raw = analogRead(34);
  float volts = raw * (3.3 / 4095.0);

  Serial.print("ADC: ");
  Serial.print(raw);
  Serial.print(" | Input voltage: ");
  Serial.println(volts, 3);

  delay(1000);
}