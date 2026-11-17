// room1-sensor  -  DHT temp/humidity over MQTT.
//
// Level-3 distributed firmware, assigned to the ESP32. It is the embedded twin
// of devices/sensor.py and fulfils tds/sensor.json: it publishes to the same
// topics (building/room1/temp, /humidity retained; /overheat as an event) so the
// node-wot gateway consumes it with no change to the TD or the app.
//
// If no DHT is wired (or it misreads), it falls back to a simulated random walk
// -- the firmware equivalent of sensor.py's --mock -- so the device is testable
// on the bench. Watch the serial log: it says MOCK or DHT for each reading.

#include <Arduino.h>
#include <math.h>
#include "secrets.h"

#if defined(ESP8266)
  #include <ESP8266WiFi.h>
#else
  #include <WiFi.h>
#endif
#include <PubSubClient.h>
#include <DHT.h>

// ---- config ----------------------------------------------------------------
static const char *BASE      = "building/room1";
static const uint8_t DHT_PIN = 4;          // matches the Pi's board.D4
static const uint8_t DHT_KIND = DHT11;     // hardware map specifies DHT11
static const float THRESHOLD = 35.0f;      // overheat event above this degC
static const uint32_t PERIOD_MS = 2000;    // publish cadence (as sensor.py)

DHT dht(DHT_PIN, DHT_KIND);
WiFiClient net;
PubSubClient mqtt(net);

static String g_clientId;
static bool g_hot = false;

// ---- connectivity ----------------------------------------------------------
static void connectWiFi() {
  Serial.printf("WiFi: joining \"%s\" ...", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print('.');
  }
  Serial.printf(" ok  IP=%s  RSSI=%d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
}

static void connectMQTT() {
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  while (!mqtt.connected()) {
    Serial.printf("MQTT: connecting to %s:%d as %s ...", MQTT_HOST, MQTT_PORT,
                  g_clientId.c_str());
    if (mqtt.connect(g_clientId.c_str())) {
      Serial.println(" connected");
    } else {
      Serial.printf(" failed rc=%d, retry in 2s\n", mqtt.state());
      delay(2000);
    }
  }
}

// ---- sensing ---------------------------------------------------------------
// Returns true if a real DHT reading succeeded; fills t/h either way (mock on
// failure). Mirrors sensor.py: mock = slow sine that crosses the control band.
static bool readTH(float &t, float &h) {
  float rt = dht.readTemperature();
  float rh = dht.readHumidity();
  if (!isnan(rt) && !isnan(rh)) {
    t = rt;
    h = rh;
    return true;
  }
  float secs = millis() / 1000.0f;
  t = 27.0f + 4.0f * sinf(secs / 20.0f) + random(-20, 21) / 100.0f;
  static float mh = 50.0f;
  mh = constrain(mh + random(-100, 101) / 100.0f, 0.0f, 100.0f);
  h = mh;
  return false;
}

// ---- lifecycle -------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n\n== room1-sensor (DHT->MQTT) ==");

  uint64_t mac = 0;
#if defined(ESP8266)
  g_clientId = "room1-sensor-" + String(ESP.getChipId(), HEX);
#else
  mac = ESP.getEfuseMac();
  g_clientId = "room1-sensor-" + String((uint32_t)(mac & 0xFFFFFF), HEX);
#endif
  (void)mac;

  dht.begin();
  connectWiFi();
  connectMQTT();
  randomSeed(micros());
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  float t, h;
  bool real = readTH(t, h);
  t = roundf(t * 10) / 10.0f;
  h = roundf(h * 10) / 10.0f;

  char buf[16];
  dtostrf(t, 0, 1, buf);
  mqtt.publish((String(BASE) + "/temp").c_str(), buf, true);     // retained
  dtostrf(h, 0, 1, buf);
  mqtt.publish((String(BASE) + "/humidity").c_str(), buf, true); // retained

  // one overheat event per rising crossing (matches sensor.py)
  if (t > THRESHOLD && !g_hot) {
    dtostrf(t, 0, 1, buf);
    mqtt.publish((String(BASE) + "/overheat").c_str(), buf, false);
    Serial.printf("  !! overheat event: %s degC\n", buf);
  }
  g_hot = t > THRESHOLD;

  Serial.printf("[%s] temp=%.1f C  humidity=%.1f %%\n", real ? "DHT" : "MOCK", t, h);
  delay(PERIOD_MS);
}
