// room1-fan  -  relay actuator exposed as a CoAP server.
//
// Level-3 distributed firmware, assigned to ESP8266 #1 (B4:E6:2D:6A:B7:44).
// Embedded twin of devices/coap_relay.py, fulfils tds/fan-coap.json:
//   GET  coap://<host>:5683/status  -> {"on": bool}  (application/json, 2.05 Content)
//   PUT  coap://<host>:5683/on                        -> relay on,  2.04 Changed
//   PUT  coap://<host>:5683/off                       -> relay off, 2.04 Changed
// The node-wot gateway consumes this TD unchanged; the app never learns the IP.
//
// Reachable as room1-fan.local via mDNS so the TD survives DHCP changes.
// No relay wired yet is fine: the GPIO just toggles a pin; state is still tracked.

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <ESP8266mDNS.h>
#include <coap-simple.h>
#include "secrets.h"

// ---- config ----------------------------------------------------------------
static const uint8_t RELAY_PIN = 5;        // D1 / GPIO5 - safe, not a boot-strap pin
static const bool    ACTIVE_LOW = true;    // SRD-05VDC-SL-C: LOW = energised
static const char   *MDNS_NAME  = "room1-fan";
static const int     COAP_PORT  = 5683;

WiFiUDP udp;
Coap coap(udp);
bool g_on = false;

// ---- relay -----------------------------------------------------------------
static void applyRelay() {
  // on  -> active level; off -> idle level
  bool level = ACTIVE_LOW ? !g_on : g_on;   // active-low inverts
  digitalWrite(RELAY_PIN, level ? HIGH : LOW);
}

static void setFan(bool on, CoapPacket &p, IPAddress ip, int port) {
  g_on = on;
  applyRelay();
  Serial.printf("CoAP: switch%s -> on=%s\n", on ? "On" : "Off", g_on ? "true" : "false");
  // 2.04 Changed, empty body, echo the client's token so the response matches.
  coap.sendResponse(ip, port, p.messageid, "", 0, COAP_CHANGED,
                    COAP_APPLICATION_JSON, p.token, p.tokenlen);
}

// ---- CoAP resource callbacks ----------------------------------------------
static void onStatus(CoapPacket &p, IPAddress ip, int port) {
  char body[20];
  int n = snprintf(body, sizeof(body), "{\"on\":%s}", g_on ? "true" : "false");
  coap.sendResponse(ip, port, p.messageid, body, n, COAP_CONTENT,
                    COAP_APPLICATION_JSON, p.token, p.tokenlen);
  Serial.printf("CoAP: GET /status -> %s\n", body);
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
  Serial.println("\n\n== room1-fan (relay -> CoAP) ==");

  connectWiFi();

  if (MDNS.begin(MDNS_NAME)) {
    MDNS.addService("coap", "udp", COAP_PORT);
    Serial.printf("mDNS: %s.local advertising _coap._udp:%d\n", MDNS_NAME, COAP_PORT);
  } else {
    Serial.println("mDNS: begin failed (fall back to raw IP in the TD)");
  }

  coap.server(onStatus, "status");
  coap.server([](CoapPacket &p, IPAddress ip, int port) { setFan(true,  p, ip, port); }, "on");
  coap.server([](CoapPacket &p, IPAddress ip, int port) { setFan(false, p, ip, port); }, "off");
  coap.start(COAP_PORT);
  Serial.printf("CoAP server up on :%d  (resources: /status /on /off)\n", COAP_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  coap.loop();
  MDNS.update();

  static uint32_t last = 0;
  if (millis() - last > 10000) {
    last = millis();
    Serial.printf("[%6lus] alive  on=%s  IP=%s  RSSI=%d\n",
                  millis() / 1000, g_on ? "true" : "false",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
  }
}
