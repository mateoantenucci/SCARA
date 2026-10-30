// Generador de pulsos STEP/DIR del UNO, sin dependencias de Arduino para
// poder probarlo en la PC (firmware/arduino/test/pulsos.cpp).
//
// El núcleo decide cuándo dar cada paso y llama a Hal::step; la capa de
// hardware lo deja pendiente acá y la interrupción del timer lo convierte en
// un pulso con los tiempos del TB6600: DIR estable al menos un tick antes del
// flanco, un tick en alto y al menos uno en bajo. Así el ancho de pulso no
// depende de cuánto tarde poll() y la serie no se frena esperando pulsos.
#ifndef SCARA_PULSOS_H
#define SCARA_PULSOS_H

#include <stdint.h>

#include "hal.h"

namespace scara {

class StepPulser {
public:
  // Pasos pendientes por motor. A la tasa máxima de la UCI son centésimas de
  // segundo de atraso; si se llena, la capa de hardware espera (no pierde pasos).
  static const int16_t PENDING_MAX = 255;

  StepPulser();
  // Deja pendiente un paso del motor 0..3 en el sentido +1 o -1. Un paso en
  // sentido contrario a los pendientes descuenta uno: la posición final es la
  // misma. Devuelve false, sin cambiar nada, si el motor ya tiene PENDING_MAX.
  // En el UNO se llama con las interrupciones deshabilitadas.
  bool push(uint8_t motor, int8_t direction);
  // Avanza un tick del timer. Devuelve si cambió alguna salida.
  bool tick();
  // Salidas tras el último tick: bit n = motor n. STEP en alto; DIR en alto
  // es sentido positivo (la inversión por cableado la aplica la capa de hardware).
  uint8_t steps() const { return steps_; }
  uint8_t directions() const { return directions_; }
  // Sin pasos pendientes y con todos los STEP en bajo.
  bool idle() const { return active_ == 0 && steps_ == 0; }

private:
  int16_t pending_[MOTOR_COUNT];
  uint8_t active_;  // bit n = el motor n tiene pasos pendientes
  uint8_t steps_;
  uint8_t directions_;
};

}  // namespace scara

#endif
