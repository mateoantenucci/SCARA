// Núcleo del firmware de la UCI: protocolo scara/1, corriente de los
// drivers, jog articular y por motor, cola de segmentos temporizados,
// paradas, watchdog y conversión de unidades articulares a pasos con el
// acople M1/M2 (transmission.h).
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
const uint8_t QUEUE_SIZE = 16;          // segmentos (D27), contando el que se ejecuta
const int32_t SEG_MS_MAX = 1000;        // duración máxima de un segmento
const int32_t SEG_UNITS_MAX = 99999;    // |q| máximo de un segmento, en centésimas
const int32_t JOG_UNREFERENCED_MAX = 500;  // jog sin referencia: lento (D21)
// Homing (D11, D56), en centésimas y centésimas por segundo.
const int32_t HOME_FAST = 800;
const int32_t HOME_SLOW = 100;
const int32_t HOME_BACKOFF = 300;       // retroceso después de que el Hall se apaga
const int32_t HOME_SEARCH_MAX[MOTOR_COUNT] = {28000, 28000, 31000, 12500};  // todo el recorrido y algo más
const uint32_t HOME_AXIS_MS = 60000;    // tiempo máximo por eje

class Firmware {
public:
  explicit Firmware(Hal& hal);
  // Anuncia el arranque con BOOT. Se llama una vez, al encender la UCI.
  void begin();
  // Atiende el enlace, genera pasos e informa el estado. Se llama sin pausa.
  void poll();

private:
  // Qué mueve los motores. Uno por vez: una orden de otro movimiento se
  // rechaza con ERR 5 hasta volver a NONE.
  enum Motion { NONE, JOG, RUN, STOPPING, HOMING };
  // Fases del homing de un eje (D11): salir del imán si está encima, buscar
  // rápido, retroceder hasta que se apague y un poco más, y acercarse lento
  // al mismo flanco.
  enum HomePhase { LEAVE, SEARCH, BACKOFF, CLEAR, APPROACH };

  // Un segmento encolado: llegar a `target`, en pasos de cada motor, en `ms`
  // milisegundos. 22 bytes en el UNO: la cola entera ocupa unos 370.
  struct Segment {
    int32_t number;
    uint16_t ms;
    int32_t target[MOTOR_COUNT];
  };

  void receive(int byte);
  void handle(char* line);
  void handleJog(char* arguments);
  void handleSegment(char* arguments);
  void handleHome(char* arguments);
  void startDrive(uint8_t axis, uint8_t motors, int8_t direction, int32_t speed);
  void startHomeAxis(uint32_t now);
  void startHomePhase(HomePhase phase);
  void advanceHoming(uint32_t now);
  void finishHomeAxis();
  void abortHoming();
  void checkJogHall();
  void sendIdentity(const char* greeting);
  void disable();
  void stopJog();
  void stop(uint32_t now);
  void startRamp(uint32_t now);
  void halt();
  bool moving() const;
  void advanceJog(uint32_t now);
  void advanceRun(uint32_t now);
  void advanceStopping(uint32_t now);
  void stepTo(const int32_t target[MOTOR_COUNT]);
  void enqueue(const Segment& segment);
  Segment& queued(uint8_t index);
  void sendStatus();
  void sendOk(int32_t number);
  void sendError(int32_t code, const char* text);
  void reject(int32_t code, const char* text);

  Hal& hal_;
  char line_[LINE_MAX];
  uint8_t length_;
  bool invalid_;                 // la línea en curso tiene bytes no permitidos
  bool overflow_;
  int32_t steps_[MOTOR_COUNT];   // pasos netos de cada motor desde la referencia
  uint8_t homed_;                // máscara de ejes referenciados
  bool enabled_;                 // drivers con corriente
  Motion motion_;
  uint8_t jogMotors_;            // máscara de motores del jog; 0 sin jog
  uint8_t jogAxis_;              // 0..3: eje en cuyas unidades va jogSpeed_
  int8_t jogDirection_;
  int32_t jogSpeed_;             // centésimas por segundo
  int32_t jogAccumulator_;
  int32_t jogSteps_;             // pasos dados por el jog o la fase de homing en curso
  uint32_t lastJog_;
  uint8_t hall_;                 // Hall leídos en este poll y en el anterior
  uint8_t lastHall_;
  uint8_t jogHalls_;             // Hall de los ejes que mueve el jog
  uint8_t jogStartHalls_;        // de esos, los activos al arrancar: el jog puede salir de ellos
  // El último jog frenado por un Hall: con ese Hall activo, otro jog de los
  // mismos motores en el mismo sentido no arranca (iría hacia el tope).
  uint8_t endHalls_;
  uint8_t endMotors_;
  int8_t endDirection_;
  // Homing: ejes en orden, el que se busca y su fase.
  uint8_t homeOrder_[MOTOR_COUNT];
  uint8_t homeCount_;
  uint8_t homeIndex_;
  HomePhase homePhase_;
  uint32_t homeStarted_;         // inicio del eje en curso
  uint8_t homedNow_;             // ejes referenciados por este HOME
  uint8_t homeWasHomed_;         // ejes con referencia antes de este HOME
  // Cola circular: queue_[head_] es el segmento en ejecución.
  Segment queue_[QUEUE_SIZE];
  uint8_t head_;
  uint8_t count_;
  Segment held_;                 // llegó con la cola llena: su OK espera lugar
  bool holding_;
  int32_t tail_[MOTOR_COUNT];    // destino del último segmento aceptado, en centésimas
  int32_t from_[MOTOR_COUNT];    // pasos al empezar el segmento en ejecución
  uint32_t started_;             // cuándo empezó, en el reloj del firmware
  int32_t done_;                 // último segmento terminado
  // Rampa de STOP: desde rampFrom_, rampDistance_ pasos en rampMs_ ms.
  int32_t rampFrom_[MOTOR_COUNT];
  int32_t rampDistance_[MOTOR_COUNT];
  int32_t rampMs_;
  uint32_t rampStarted_;
  uint32_t lastStatus_;
  uint32_t lastMessage_;
};

}  // namespace scara

#endif
