// Prueba en la PC del generador de pulsos del UNO (scara_uci/pulsos.h).
// Uso: pulsos. Sale con 0 si todo pasa; si no, dice qué falló.
#include <cstdio>

#include "../scara_uci/pulsos.h"

namespace {

int failures = 0;

void check(bool condition, const char* what) {
  if (!condition) {
    std::fprintf(stderr, "falla: %s\n", what);
    ++failures;
  }
}

// Ticks hasta que no queden pulsos, contando flancos de subida por motor.
int run(scara::StepPulser& pulser, int risings[scara::MOTOR_COUNT], int limit = 1000) {
  for (int m = 0; m < scara::MOTOR_COUNT; ++m) risings[m] = 0;
  uint8_t before = pulser.steps();
  int ticks = 0;
  while (!pulser.idle() && ticks < limit) {
    pulser.tick();
    ++ticks;
    uint8_t now = pulser.steps();
    for (int m = 0; m < scara::MOTOR_COUNT; ++m) {
      if ((now & (1 << m)) && !(before & (1 << m))) ++risings[m];
    }
    before = now;
  }
  return ticks;
}

void startsIdleWithEverythingLow() {
  scara::StepPulser pulser;
  check(pulser.idle(), "arranca sin pulsos pendientes");
  check(pulser.steps() == 0, "arranca con STEP en bajo");
  check(pulser.directions() == 0, "arranca con DIR en bajo");
}

// tick() dice si cambiaron las salidas: sin pasos, la interrupción no escribe los puertos.
void tickReportsChanges() {
  scara::StepPulser pulser;
  check(!pulser.tick(), "sin pasos, nada cambia");
  pulser.push(1, +1);
  check(pulser.tick(), "cambia DIR");
  check(pulser.tick(), "sube STEP");
  check(pulser.tick(), "baja STEP");
  check(!pulser.tick(), "sin más pasos, nada cambia");
}

// Un pulso dura un tick en alto y lo sigue al menos un tick en bajo.
void pulseIsOneTickHighThenLow() {
  scara::StepPulser pulser;
  check(pulser.push(0, -1), "acepta un paso");
  pulser.tick();
  check(pulser.steps() == 0x01, "el paso negativo sale sin esperar: DIR ya estaba en bajo");
  check(pulser.directions() == 0x00, "DIR en bajo es sentido negativo");
  pulser.tick();
  check(pulser.steps() == 0, "el pulso baja en el tick siguiente");
  check(pulser.idle(), "no quedan pulsos");
}

// Cambiar DIR y pulsar en el mismo tick violaría el tiempo de preparación del
// TB6600: el pulso sale un tick después.
void directionSettlesBeforePulse() {
  scara::StepPulser pulser;
  pulser.push(2, +1);
  pulser.tick();
  check(pulser.directions() == 0x04, "DIR de M3 pasa a alto");
  check(pulser.steps() == 0, "sin pulso en el tick del cambio de DIR");
  pulser.tick();
  check(pulser.steps() == 0x04, "el pulso sale con DIR ya estable");
}

// J1 mueve M1 y M2 juntos: sus pulsos salen en el mismo tick.
void coupledMotorsPulseTogether() {
  scara::StepPulser pulser;
  for (int i = 0; i < 3; ++i) {
    pulser.push(0, +1);
    pulser.push(1, +1);
  }
  int risings[scara::MOTOR_COUNT];
  uint8_t seen = 0;
  for (int i = 0; i < 20 && !pulser.idle(); ++i) {
    pulser.tick();
    if (pulser.steps() != 0) seen |= pulser.steps() == 0x03 ? 1 : 2;
  }
  check(seen == 1, "M1 y M2 pulsan siempre en el mismo tick");
  pulser.push(0, +1);
  pulser.push(1, +1);
  run(pulser, risings);
  check(risings[0] == 1 && risings[1] == 1, "un pulso por motor");
}

// N pasos pendientes salen como N pulsos, a un pulso cada dos ticks.
void pendingStepsBecomePulses() {
  scara::StepPulser pulser;
  for (int i = 0; i < 100; ++i) pulser.push(3, -1);
  for (int i = 0; i < 40; ++i) pulser.push(1, +1);
  int risings[scara::MOTOR_COUNT];
  int ticks = run(pulser, risings);
  check(risings[3] == 100, "M4 da los 100 pulsos");
  check(risings[1] == 40, "M2 da los 40 pulsos");
  check(risings[0] == 0 && risings[2] == 0, "M1 y M3 no pulsan");
  check(ticks == 200, "la tasa máxima es un pulso cada dos ticks");
}

// Un paso en sentido contrario a uno pendiente lo cancela: la posición final es la misma.
void oppositeStepCancelsPending() {
  scara::StepPulser pulser;
  pulser.push(0, +1);
  pulser.push(0, -1);
  check(pulser.idle(), "+1 y -1 se cancelan");
}

// Con la cola de un motor llena, push lo rechaza y no pierde la cuenta.
void fullQueueRejects() {
  scara::StepPulser pulser;
  for (int i = 0; i < scara::StepPulser::PENDING_MAX; ++i) check(pulser.push(1, -1), "acepta hasta el máximo");
  check(!pulser.push(1, -1), "rechaza el paso de más");
  check(pulser.push(1, +1), "acepta el sentido contrario: descuenta");
  check(pulser.push(0, -1), "los otros motores siguen aceptando");
  int risings[scara::MOTOR_COUNT];
  run(pulser, risings, 10000);
  check(risings[1] == scara::StepPulser::PENDING_MAX - 1, "salen los pasos aceptados, ni uno más");
}

}  // namespace

int main() {
  startsIdleWithEverythingLow();
  tickReportsChanges();
  pulseIsOneTickHighThenLow();
  directionSettlesBeforePulse();
  coupledMotorsPulseTogether();
  pendingStepsBecomePulses();
  oppositeStepCancelsPending();
  fullQueueRejects();
  return failures == 0 ? 0 : 1;
}
