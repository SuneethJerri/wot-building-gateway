// room1-plug  -  smart plug (relay) exposed as an HTTP server.
//
// Level-3 distributed firmware, assigned to ESP8266 #2 (CC:50:E3:56:7F:8E).
// Embedded twin of devices/http_plug.py, fulfils tds/plug.json:
//   GET  http://<host>:8081/status -> {"on": bool, "power": W}
//   POST http://<host>:8081/on                      -> relay on,  returns status
//   POST http://<host>:8081/off                     -> relay off, returns status
// The node-wot gateway consumes this TD unchanged; the app never learns the IP.
//
// Reachable as room1-plug.local via mDNS so the TD survives DHCP changes.
// No relay wired yet is fine: the GPIO just toggles a pin; state is still tracked.

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
#include "secrets.h"

// ---- config ----------------------------------------------------------------
static const uint8_t RELAY_PIN = 5;        // D1 / GPIO5 - safe, not a boot-strap pin
static const bool    ACTIVE_LOW = true;    // relay module: LOW = energised
static const char   *MDNS_NAME  = "room1-plug";
static const int     HTTP_PORT  = 8081;
static const float   WATTS      = 60.0f;   // pretend load when on (matches http_plug.py)

ESP8266WebServer server(HTTP_PORT);
bool g_on = false;

// ---- relay -----------------------------------------------------------------
static void applyRelay() {
  bool level = ACTIVE_LOW ? !g_on : g_on;   // active-low inverts
  digitalWrite(RELAY_PIN, level ? HIGH : LOW);
}

// {"on": <bool>, "power": <W>} ; power = 60 +/- 2 when on, else 0.0
static String statusJson() {
  float power = g_on ? WATTS + random(-200, 201) / 100.0f : 0.0f;
  char buf[48];
  snprintf(buf, sizeof(buf), "{\"on\":%s,\"power\":%.1f}", g_on ? "true" : "false", power);
  return String(buf);
}

static void sendStatus() {
  server.send(200, "application/json", statusJson());
}

// ---- HTTP handlers ---------------------------------------------------------
static void handleStatus() { sendStatus(); }

static void handleOn() {
  g_on = true;  applyRelay();
  Serial.println("HTTP: POST /on  -> on=true");
  sendStatus();
}

static void handleOff() {
  g_on = false; applyRelay();
  Serial.println("HTTP: POST /off -> on=false");
  sendStatus();
}

// ---- connectivity ----------------------------------------------------------
static void connectWiFi() {
  Serial.printf("WiFi: joining \"%s\" ...", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.hostname(MDNS_NAME);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print('.');
  }
  Serial.printf(" ok  IP=%s  RSSI=%d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
}

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  g_on = false;
  applyRelay();

  Serial.begin(115200);
  delay(200);
  Serial.println("\n\n== room1-plug (relay -> HTTP) ==");

  connectWiFi();
  randomSeed(micros());

  if (MDNS.begin(MDNS_NAME)) {
    MDNS.addService("http", "tcp", HTTP_PORT);
    Serial.printf("mDNS: %s.local advertising _http._tcp:%d\n", MDNS_NAME, HTTP_PORT);
  } else {
    Serial.println("mDNS: begin failed (fall back to raw IP in the TD)");
  }

  // node-wot invokes actions with POST (htv:methodName POST); allow GET too for
  // easy manual testing with a browser/curl.
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/on",  handleOn);
  server.on("/off", handleOff);
  server.begin();
  Serial.printf("HTTP server up on :%d  (routes: /status /on /off)\n", HTTP_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  server.handleClient();
  MDNS.update();

  static uint32_t last = 0;
  if (millis() - last > 10000) {
    last = millis();
    Serial.printf("[%6lus] alive  on=%s  IP=%s  RSSI=%d\n",
                  millis() / 1000, g_on ? "true" : "false",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
  }
}
