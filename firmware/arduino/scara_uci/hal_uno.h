// Capa de hardware del Arduino UNO (ADR 0002): pines, serie y timer.
// Cableado y razones en docs/ARDUINO_UNO.md.
#ifndef SCARA_HAL_UNO_H
#define SCARA_HAL_UNO_H

#include <Arduino.h>

#include "hal.h"

namespace scara {

// Asignación de pines (D47). Deja libres D4 y D10–D13 para un shield Ethernet.
const uint8_t PIN_STEP[MOTOR_COUNT] = {2, 3, 5, 6};        // PORTD: un solo acceso
const uint8_t PIN_DIR[MOTOR_COUNT] = {A0, A1, A2, A3};     // PORTC 0–3
const uint8_t PIN_ENABLE = 7;                              // ENA+ de los cuatro TB6600
const uint8_t PIN_HALL[MOTOR_COUNT] = {8, 9, A4, A5};      // KY-003 de J1–J4
const uint32_t SERIAL_BAUD = 115200;                       // D27
// Tick del generador de pulsos: hasta 10 000 pasos por segundo por motor.
const uint32_t TICK_HZ = 20000;
// Pasos por segundo que pide el motor n a su velocidad máxima (D45).
constexpr int32_t maxStepRate(uint8_t motor) {
  return MOTOR_MAX_SPEED[motor] * STEPS_PER_REV / 360;
}
constexpr bool tickFits(uint8_t motor) {
  return motor == MOTOR_COUNT || (maxStepRate(motor) <= static_cast<int32_t>(TICK_HZ / 2) && tickFits(motor + 1));
}
// Un pulso ocupa dos ticks: con más micropasos (D44) puede hacer falta un tick más rápido.
static_assert(tickFits(0), "TICK_HZ no alcanza para la velocidad máxima de algún motor");
// Bit n = invertir DIR del motor n, si el motor quedó cableado al revés.
const uint8_t DIR_INVERT = 0x00;

class HalUno : public Hal {
public:
  // Configura pines, serie y timer, con los drivers sin corriente.
  void begin();
  uint32_t millis();
  void step(uint8_t motor, int8_t direction);
  void enableDrivers(bool on);
  uint8_t readHall();
  int readByte();
  void write(const char* text);
};

}  // namespace scara

#endif
