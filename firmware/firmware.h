// Núcleo del firmware de la UCI: protocolo scara/1, corriente de los
// drivers, jog articular, paradas, watchdog y conversión de unidades articulares a pasos con el acople M1/M2.
// Portable al Arduino UNO: sin memoria dinámica, buffers fijos y sin
// flotantes. Ver docs/PROTOCOLO_SCARA_1.md.
#ifndef SCARA_FIRMWARE_H
#define SCARA_FIRMWARE_H

#include <stdint.h>

#include "hal.h"

namespace scara {

const char PROTOCOL[] = "scara/1";
const int32_t FIRMWARE_VERSION = 1;
const uint8_t LINE_MAX = 64;            // bytes por mensaje, incluido el LF (D4)
const uint32_t STATUS_PERIOD_MS = 50;   // estado S a 20/s (D27)
const uint32_t WATCHDOG_MS = 1000;      // sin mensajes de la URC => frena (D27)
const int32_t JOG_SPEED_MAX = 1000;     // centésimas por segundo
const uint8_t QUEUE_SIZE = 16;          // segmentos (D27); todavía sin cola

class Firmware {
public:
  explicit Firmware(Hal& hal);
  // Anuncia el arranque con BOOT. Se llama una vez, al encender la UCI.
  void begin();
  // Atiende el enlace, genera pasos e informa el estado. Se llama sin pausa.
  void poll();

private:
  void receive(int byte);
  void handle(char* line);
  void handleJog(char* arguments);
  void sendIdentity(const char* greeting);
  void disable();
  void stopMotion();
  bool moving() const;
  void advanceJog(uint32_t now);
  void sendStatus();
  void sendError(int32_t code, const char* text);
  int32_t estimated(uint8_t joint) const;

  Hal& hal_;
  char line_[LINE_MAX];
  uint8_t length_;
  bool invalid_;                 // la línea en curso tiene bytes no permitidos
  bool overflow_;
  int32_t steps_[MOTOR_COUNT];   // pasos netos de cada motor desde la referencia
  uint8_t homed_;                // máscara de ejes referenciados
  bool enabled_;                 // drivers con corriente
  int8_t jogJoint_;              // 0..3, o -1 sin jog
  int8_t jogDirection_;
  int32_t jogSpeed_;             // centésimas por segundo
  int32_t jogAccumulator_;
  uint32_t lastJog_;
  uint32_t lastStatus_;
  uint32_t lastMessage_;
};

}  // namespace scara

#endif
