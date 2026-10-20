// Copy this file to secrets.h (same folder) and fill it in.
// secrets.h is git-ignored: never commit the Wi-Fi password or the device key.
#pragma once

// Wi-Fi (iPhone hotspot: turn on "Maximize Compatibility" for 2.4 GHz)
#define WIFI_SSID "your-hotspot-name"
#define WIFI_PASSWORD "your-hotspot-password"

// AutoSense backend on the laptop: http://<laptop IP from ipconfig>:3000/api/v1
#define API_BASE "http://172.20.10.9:3000/api/v1"

// Website: Vehicles -> vehicle -> "Register ESP32 device" (shown only once)
#define DEVICE_KEY "paste-device-key-here"

// ELM327 Bluetooth name as shown when pairing (often "OBDII" or "OBD2"), and its PIN
#define OBD_DEVICE_NAME "OBDII"
#define OBD_PIN "1234"
