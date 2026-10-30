// Firmware de la UCI para el Arduino UNO: el mismo núcleo que corre en Webots
// (firmware/) con la capa de hardware del UNO. Compilar con:
//   arduino-cli compile --fqbn arduino:avr:uno --library firmware firmware/arduino/scara_uci
// Ver docs/ARDUINO_UNO.md.
#include "firmware.h"
#include "hal_uno.h"

scara::HalUno hal;
scara::Firmware firmware(hal);

void setup() {
  hal.begin();
  firmware.begin();
}

void loop() { firmware.poll(); }
