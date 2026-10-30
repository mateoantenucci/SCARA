// Interfaz de capa de hardware del firmware (ADR 0002).
// El núcleo solo conoce esto. El Arduino la implementa con pines, serie y
// timers; el controlador de Webots, con un socket TCP y la planta simulada; las
// pruebas en la PC, con una versión falsa.
#ifndef SCARA_HAL_H
#define SCARA_HAL_H

#include <stdint.h>

#include "config.h"

namespace scara {

class Hal {
public:
  // Milisegundos desde el arranque; puede dar la vuelta (se usan restas).
  virtual uint32_t millis() = 0;
  // Un pulso de paso del motor 0..3 (M1..M4); direction es +1 o -1.
  virtual void step(uint8_t motor, int8_t direction) = 0;
  // Corriente de los cuatro drivers (ENABLE común, D18). Sin corriente, los
  // motores giran libres y J4 cae.
  virtual void enableDrivers(bool on) = 0;
  // Bit n = Hall de la articulación Jn+1 activo.
  virtual uint8_t readHall() = 0;
  // Próximo byte recibido del enlace, o -1 si no hay.
  virtual int readByte() = 0;
  // Texto hacia la URC; el núcleo escribe líneas completas terminadas en LF.
  virtual void write(const char* text) = 0;

protected:
  ~Hal() {}
};

}  // namespace scara

#endif
