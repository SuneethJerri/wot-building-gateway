// ESP8266 / ESP32 health checker.
//
// Level-3 bring-up tool for the WoT building gateway: flash this to each board
// as you plug it in to confirm it is healthy before giving it a device role.
// It prints chip / flash / power / radio diagnostics once at boot with a
// PASS / FAIL summary, then blinks the onboard LED as a "still alive" heartbeat
// and reprints free heap every few seconds so you can watch for memory leaks or
// brownout resets.
//
// Dual-architecture on purpose: the same tool covers ESP8266 (NodeMCU Amica)
// and ESP32 dev boards. Arch-specific bits are behind #if guards.
// Nothing here is WoT-specific: it is a pure hardware sanity check.

#include <Arduino.h>

#if defined(ESP8266)
  #include <ESP8266WiFi.h>
  // Read internal supply voltage on the VCC pin. Requires A0/TOUT unconnected
  // (NodeMCU Amica leaves A0 free by default).
  ADC_MODE(ADC_VCC);
  #define LED_ON()  digitalWrite(LED, LOW)    // ESP-12E LED (GPIO2) is active-LOW
  #define LED_OFF() digitalWrite(LED, HIGH)
#elif defined(ESP32)
  #include <WiFi.h>
  #ifndef LED_BUILTIN
    #define LED_BUILTIN 2                       // generic ESP32 devkit LED
  #endif
  #define LED_ON()  digitalWrite(LED, HIGH)    // ESP32 devkit LED is active-HIGH
  #define LED_OFF() digitalWrite(LED, LOW)
#else
  #error "Unsupported target: build for ESP8266 or ESP32"
#endif

static const uint8_t LED = LED_BUILTIN;

static bool g_allPass = true;

static void check(const char *label, bool ok, const String &detail) {
  Serial.printf("  [%s] %-22s %s\n", ok ? "PASS" : "FAIL", label, detail.c_str());
  if (!ok) g_allPass = false;
}

static void banner(const char *text) {
  Serial.println();
  Serial.println(F("========================================"));
  Serial.print(F("  "));
  Serial.println(text);
  Serial.println(F("========================================"));
}

static void scanRadio() {
  banner("WiFi radio scan");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  int n = WiFi.scanNetworks();
  if (n < 0) {
    check("WiFi scan", false, "scanNetworks() returned error");
    return;
  }
  // A working radio almost always sees at least one AP in a lab. Zero is a soft
  // warning (shielded room?) but still proves the scan ran, so we only fail on
  // an outright scan error above.
  check("WiFi scan", true, String(n) + " network(s) visible");
  for (int i = 0; i < n && i < 10; i++) {
    Serial.printf("      %2d) %-24s  ch%-2d  %4d dBm  %s\n",
                  i + 1,
                  WiFi.SSID(i).c_str(),
                  WiFi.channel(i),
                  WiFi.RSSI(i),
#if defined(ESP8266)
                  WiFi.encryptionType(i) == ENC_TYPE_NONE ? "open" : "enc");
#else
                  WiFi.encryptionType(i) == WIFI_AUTH_OPEN ? "open" : "enc");
#endif
  }
  WiFi.scanDelete();
}

static void report() {
  banner("HEALTH CHECK");

  // --- Identity (common) ---
  Serial.printf("  MAC (STA)      : %s\n", WiFi.macAddress().c_str());
  Serial.printf("  CPU freq       : %u MHz\n", ESP.getCpuFreqMHz());
  Serial.printf("  SDK            : %s\n", ESP.getSdkVersion());

#if defined(ESP8266)
  Serial.printf("  Chip ID        : %06X\n", ESP.getChipId());
  Serial.printf("  Core           : %s\n", ESP.getCoreVersion().c_str());
  Serial.printf("  Reset reason   : %s\n", ESP.getResetReason().c_str());
  uint32_t realSize = ESP.getFlashChipRealSize();
  uint32_t confSize = ESP.getFlashChipSize();
  Serial.printf("  Flash chip ID  : %08X\n", ESP.getFlashChipId());
  Serial.printf("  Flash real     : %u KB\n", realSize / 1024);
  Serial.printf("  Flash config   : %u KB\n", confSize / 1024);
#elif defined(ESP32)
  Serial.printf("  Chip model     : %s rev %d\n", ESP.getChipModel(), ESP.getChipRevision());
  Serial.printf("  Cores          : %d\n", ESP.getChipCores());
  uint32_t confSize = ESP.getFlashChipSize();
  Serial.printf("  Flash config   : %u KB\n", confSize / 1024);
  Serial.printf("  PSRAM          : %u KB\n", ESP.getPsramSize() / 1024);
#endif
  Serial.println();

  banner("DIAGNOSTIC SUMMARY");

#if defined(ESP8266)
  // Flash mismatch is the #1 cause of clones that upload fine but crash at
  // runtime, so it is a hard check.
  check("Flash size match", realSize == confSize,
        realSize == confSize ? "ok" : "CLONE? real != configured");
#elif defined(ESP32)
  // ESP32 can't read the chip's true size at runtime; esptool verified it on
  // connect. Just confirm the firmware was built with a sane, non-zero size.
  check("Flash config sane", confSize >= 2 * 1024 * 1024,
        String(confSize / 1024) + " KB");
#endif

  // Free heap: both parts should have plenty free at boot.
  uint32_t heap = ESP.getFreeHeap();
  check("Free heap", heap > 20000, String(heap) + " bytes");

#if defined(ESP8266)
  // Heap fragmentation (0 = none). High at boot is abnormal. (ESP8266 only.)
  uint8_t frag = ESP.getHeapFragmentation();
  check("Heap fragmentation", frag < 20, String(frag) + " %");

  // Supply voltage. USB-powered the 3V3 rail reads ~3.0-3.3 V. Low -> weak
  // USB cable/port -> brownouts under WiFi TX.
  float vcc = ESP.getVcc() / 1000.0f;
  check("Supply voltage", vcc > 2.9f && vcc < 3.6f, String(vcc, 3) + " V");
#elif defined(ESP32)
  // No runtime VCC on ESP32. The on-die temp sensor is a rough liveness/thermal
  // sanity signal (info only; early-silicon reading is approximate).
  Serial.printf("  [info] Die temperature      %.1f C\n", temperatureRead());
#endif

  Serial.println();
  Serial.printf("  >>> OVERALL: %s <<<\n", g_allPass ? "PASS" : "CHECK FAILURES ABOVE");
  Serial.println();
}

void setup() {
  pinMode(LED, OUTPUT);
  LED_OFF();

  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println();

  report();
  scanRadio();

  Serial.println(F("Entering heartbeat loop (LED blink + heap watch)...\n"));
}

void loop() {
  static uint32_t last = 0;
  // Fast double-blink heartbeat so a healthy board is obvious at a glance.
  LED_ON();  delay(60);
  LED_OFF(); delay(120);
  LED_ON();  delay(60);
  LED_OFF();

  if (millis() - last > 5000) {
    last = millis();
#if defined(ESP8266)
    Serial.printf("[%6lus] free heap: %u B   frag: %u%%   Vcc: %.3f V\n",
                  millis() / 1000, ESP.getFreeHeap(),
                  ESP.getHeapFragmentation(), ESP.getVcc() / 1000.0f);
#elif defined(ESP32)
    Serial.printf("[%6lus] free heap: %u B   temp: %.1f C\n",
                  millis() / 1000, ESP.getFreeHeap(), temperatureRead());
#endif
  }
  delay(760);
}
