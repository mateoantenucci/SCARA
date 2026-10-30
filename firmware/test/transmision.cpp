// Prueba de la conversión a pasos y del acople M1/M2, en la PC.
// tests/test_firmware.py la compila con cada microstepping del TB6600
// (-DSCARA_MICROSTEPS=1 … 32): las propiedades valen para todos.
#include <cstdio>
#include <cstdlib>

#include "../transmission.h"

namespace {

int failures = 0;

void check(bool condition, const char* what, long a, long b) {
  if (condition) return;
  std::fprintf(stderr, "1/%d: %s (%ld, %ld)\n", SCARA_MICROSTEPS, what, a, b);
  ++failures;
}

long distance(long a, long b) { return a > b ? a - b : b - a; }

// Una vuelta de articulación son 4 vueltas de motor; una vuelta de M4, 8 mm.
void oneTurn() {
  const long motorTurn = 200L * SCARA_MICROSTEPS;
  for (uint8_t axis = 0; axis < 3; ++axis) {
    check(scara::unitsToSteps(axis, 36000) == 4 * motorTurn, "una vuelta de J1–J3 = 4 de motor",
          scara::unitsToSteps(axis, 36000), 4 * motorTurn);
    check(scara::stepsToUnits(axis, 4 * motorTurn) == 36000, "4 vueltas de motor = una de J1–J3",
          scara::stepsToUnits(axis, 4 * motorTurn), 36000);
  }
  check(scara::unitsToSteps(3, 800) == motorTurn, "8 mm de J4 = una vuelta de M4", scara::unitsToSteps(3, 800),
        motorTurn);
  check(scara::unitsToSteps(3, -800) == -motorTurn, "el signo se conserva", scara::unitsToSteps(3, -800),
        -motorTurn);
}

// Ir y volver no se aleja más de medio paso: el redondeo no acumula.
void roundTrip() {
  for (uint8_t axis = 0; axis < scara::MOTOR_COUNT; ++axis) {
    // Medio paso en unidades del protocolo, por exceso.
    long halfStep = (scara::STEPS_DEN[axis] + 2 * scara::STEPS_NUM[axis] - 1) / (2 * scara::STEPS_NUM[axis]);
    for (long units = -54000; units <= 54000; units += 7) {
      long back = scara::stepsToUnits(axis, scara::unitsToSteps(axis, static_cast<int32_t>(units)));
      check(distance(back, units) <= halfStep, "ida y vuelta dentro de medio paso", units, back);
    }
    // Si un paso es más fino que la unidad del protocolo (J4 desde 1/8: 0,005
    // mm por paso), dos pasos se informan igual.
    if (scara::STEPS_NUM[axis] > scara::STEPS_DEN[axis]) continue;
    for (long steps = -3000; steps <= 3000; ++steps) {
      long back = scara::unitsToSteps(axis, scara::stepsToUnits(axis, static_cast<int32_t>(steps)));
      check(back == steps, "un paso siempre se distingue del siguiente", steps, back);
    }
  }
}

// J1 = θM1/4, J2 = (θM2 − θM1)/4, J3 = θM3/4.
void coupling() {
  int32_t motors[scara::MOTOR_COUNT], joints[scara::MOTOR_COUNT];
  // Mover solo J1 mueve M1 y M2 lo mismo.
  const int32_t onlyJ1[scara::MOTOR_COUNT] = {4500, 0, 0, 0};
  scara::jointsToMotors(onlyJ1, motors);
  check(motors[0] == motors[1] && motors[0] != 0, "J1 solo: M1 y M2 iguales", motors[0], motors[1]);
  check(motors[2] == 0 && motors[3] == 0, "J1 solo: M3 y M4 quietos", motors[2], motors[3]);
  // Mover solo J2 mueve solo M2.
  const int32_t onlyJ2[scara::MOTOR_COUNT] = {0, -4500, 0, 0};
  scara::jointsToMotors(onlyJ2, motors);
  check(motors[0] == 0 && motors[1] < 0, "J2 solo: M1 quieto, M2 se mueve", motors[0], motors[1]);
  // Con M1 solo, J1 y J2 cambian en sentidos opuestos y el rumbo
  // J1 + J2 + J3 queda igual: el antebrazo conserva su orientación.
  const int32_t onlyM1[scara::MOTOR_COUNT] = {scara::unitsToSteps(0, 4500), 0, 0, 0};
  scara::motorsToJoints(onlyM1, joints);
  check(joints[0] == 4500 && joints[1] == -4500, "M1 solo: J2 = −J1", joints[0], joints[1]);
  check(joints[0] + joints[1] + joints[2] == 0, "M1 solo: el rumbo no cambia", joints[0] + joints[1] + joints[2], 0);
  // De articulaciones a motores y de vuelta, en toda la carrera.
  for (int32_t j1 = -13500; j1 <= 13500; j1 += 1350) {
    for (int32_t j2 = -13500; j2 <= 13500; j2 += 1350) {
      const int32_t pose[scara::MOTOR_COUNT] = {j1, j2, -j2, 6000};
      scara::jointsToMotors(pose, motors);
      scara::motorsToJoints(motors, joints);
      for (uint8_t axis = 0; axis < scara::MOTOR_COUNT; ++axis) {
        long resolution = (scara::STEPS_DEN[axis] + scara::STEPS_NUM[axis] - 1) / scara::STEPS_NUM[axis];
        check(distance(joints[axis], pose[axis]) <= resolution, "articulaciones → motores → articulaciones",
              pose[axis], joints[axis]);
      }
    }
  }
}

// La pose de reposo tiene J4 = 120 mm: un número entero de pasos.
void restIsExact() {
  check(scara::unitsToSteps(3, 12000) * scara::STEPS_DEN[3] == 12000 * scara::STEPS_NUM[3],
        "J4 = 120 mm es un número entero de pasos", scara::unitsToSteps(3, 12000), 0);
}

}  // namespace

int main() {
  oneTurn();
  roundTrip();
  coupling();
  restIsExact();
  return failures == 0 ? 0 : 1;
}
