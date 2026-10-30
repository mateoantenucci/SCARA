// Transmisión N1 vista por el firmware: unidades del protocolo ↔ pasos de
// motor, con el acople M1/M2 (D8). Aritmética entera, sin memoria dinámica.
//
//   J1 = θM1 / 4    J2 = (θM2 − θM1) / 4    J3 = θM3 / 4    J4 = 8 mm · vueltas de M4
//
// Unidades del protocolo (ADR 0003): J1–J3 en centésimas de grado y J4 en
// centésimas de mm. Las funciones toman el eje 0..3 (J1..J4, o el motor
// M1..M4 medido en las unidades de su articulación).
#ifndef SCARA_TRANSMISSION_H
#define SCARA_TRANSMISSION_H

#include <stdint.h>

#include "config.h"

namespace scara {

const int32_t PULLEY_RATIO = 4;      // 20T → 80T en J1–J3; 60T → 60T hasta el codo
const int32_t TURN_UNITS = 36000;    // una vuelta en centésimas de grado
const int32_t LEAD_UNITS = 800;      // ACME: 8 mm por vuelta, en centésimas de mm

constexpr int32_t greatestCommonDivisor(int32_t a, int32_t b) { return b == 0 ? a : greatestCommonDivisor(b, a % b); }

// Pasos de motor por unidad del protocolo, como fracción reducida
// STEPS_NUM/STEPS_DEN. Con 1/8: 8/45 en J1–J3 y 2/1 en J4.
const int32_t ROTARY_STEPS = STEPS_PER_REV * PULLEY_RATIO;
const int32_t ROTARY_DIVISOR = greatestCommonDivisor(ROTARY_STEPS, TURN_UNITS);
const int32_t LINEAR_DIVISOR = greatestCommonDivisor(STEPS_PER_REV, LEAD_UNITS);
constexpr int32_t STEPS_NUM[MOTOR_COUNT] = {ROTARY_STEPS / ROTARY_DIVISOR, ROTARY_STEPS / ROTARY_DIVISOR,
                                            ROTARY_STEPS / ROTARY_DIVISOR, STEPS_PER_REV / LINEAR_DIVISOR};
constexpr int32_t STEPS_DEN[MOTOR_COUNT] = {TURN_UNITS / ROTARY_DIVISOR, TURN_UNITS / ROTARY_DIVISOR,
                                            TURN_UNITS / ROTARY_DIVISOR, LEAD_UNITS / LINEAR_DIVISOR};

// Motores que da pasos el jog articular de cada articulación: J1 mueve M1 y
// M2 juntos para que J2, relativo, no cambie.
const uint8_t JOINT_MOTORS[MOTOR_COUNT] = {0x03, 0x02, 0x04, 0x08};

inline int32_t divideRounded(int32_t value, int32_t divisor) {
  return value >= 0 ? (value + divisor / 2) / divisor : -((-value + divisor / 2) / divisor);
}

// Pasos más cercanos a `units` del eje `axis`.
inline int32_t unitsToSteps(uint8_t axis, int32_t units) {
  return divideRounded(units * STEPS_NUM[axis], STEPS_DEN[axis]);
}

// Unidades más cercanas a `steps` pasos del eje `axis`.
inline int32_t stepsToUnits(uint8_t axis, int32_t steps) {
  return divideRounded(steps * STEPS_DEN[axis], STEPS_NUM[axis]);
}

// Configuración articular → pasos de cada motor. M2 sigue al ángulo absoluto
// del antebrazo, J1 + J2.
inline void jointsToMotors(const int32_t joints[MOTOR_COUNT], int32_t motors[MOTOR_COUNT]) {
  motors[0] = unitsToSteps(0, joints[0]);
  motors[1] = unitsToSteps(1, joints[0] + joints[1]);
  motors[2] = unitsToSteps(2, joints[2]);
  motors[3] = unitsToSteps(3, joints[3]);
}

// Pasos de cada motor → configuración articular.
inline void motorsToJoints(const int32_t motors[MOTOR_COUNT], int32_t joints[MOTOR_COUNT]) {
  joints[0] = stepsToUnits(0, motors[0]);
  joints[1] = stepsToUnits(1, motors[1] - motors[0]);
  joints[2] = stepsToUnits(2, motors[2]);
  joints[3] = stepsToUnits(3, motors[3]);
}

// ¿Mover el eje `axis` a `speed` unidades por segundo deja a su motor dentro
// de MOTOR_MAX_SPEED? Compara pasos por segundo sin dividir.
constexpr bool withinMotorSpeed(uint8_t axis, int32_t speed) {
  return static_cast<int64_t>(speed) * STEPS_NUM[axis] * 360 <=
         static_cast<int64_t>(MOTOR_MAX_SPEED[axis]) * STEPS_PER_REV * STEPS_DEN[axis];
}

// Unidades del protocolo por vuelta de cada motor: 90° de su articulación en
// M1–M3 (poleas 4:1) y los 8 mm del ACME en M4.
const int32_t MOTOR_TURN_UNITS[MOTOR_COUNT] = {TURN_UNITS / PULLEY_RATIO, TURN_UNITS / PULLEY_RATIO,
                                               TURN_UNITS / PULLEY_RATIO, LEAD_UNITS};
// La URC redondea cada destino a la centésima, y M2 suma dos articulaciones.
const int32_t ROUNDING_UNITS = 2;

// ¿Ir de la configuración articular `from` a `to` en `ms` milisegundos deja
// a cada motor dentro de MOTOR_MAX_SPEED? Mide el recorrido de cada motor en
// las unidades de su articulación, con el acople: M2 sigue a J1 + J2 (D45).
// No depende del microstepping. Admite ROUNDING_UNITS de más por motor.
inline bool segmentWithinMotorSpeed(const int32_t from[MOTOR_COUNT], const int32_t to[MOTOR_COUNT], int32_t ms) {
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
    int32_t travel = to[motor] - from[motor];
    if (motor == 1) travel += to[0] - from[0];
    if (travel < 0) travel = -travel;
    if (static_cast<int64_t>(travel - ROUNDING_UNITS) * 360 * 1000 >
        static_cast<int64_t>(MOTOR_MAX_SPEED[motor]) * MOTOR_TURN_UNITS[motor] * ms) {
      return false;
    }
  }
  return true;
}

}  // namespace scara

#endif
