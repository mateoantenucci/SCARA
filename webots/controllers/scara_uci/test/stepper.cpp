// Prueba del modelo de motor de la planta (N2, D64), en la PC y sin Webots.
// tests/test_planta.py la compila y la corre. Con --tabla imprime el margen de
// par de cada motor en los límites de D45 (docs/TRANSMISION.md).
#include <cmath>
#include <cstdio>
#include <cstring>
#include <initializer_list>

#include "../stepper.h"
#include "config.h"
#include "firmware.h"
#include "transmission.h"

namespace {

int failures = 0;

void check(bool condition, const char* what, double a, double b) {
  if (condition) return;
  std::fprintf(stderr, "%s (%g, %g)\n", what, a, b);
  ++failures;
}

const double DT = 0.002;  // el paso de Webots
const double NOMINAL_TOOL = plant::TOOL_MASS;     // kg: la herramienta sin carga
const double HEAVY_TOOL = plant::TOOL_MAX;        // kg: con la carga máxima del banco de ensayo (D85)
const long CYCLE = plant::STEPS_PER_CYCLE * scara::MICROSTEPS;  // pulsos de 4 pasos completos

// Pulsos por grado del eje del motor.
double pulsesPerDegree() { return scara::STEPS_PER_REV / 360.0; }

struct Run {
  long lost;
  double maxLag;    // pasos completos
  double finalLag;  // pasos completos, ya quieto
};

// El estator recorre `travel` pulsos con un perfil trapezoidal (`speed`
// pulsos/s, `acceleration` pulsos/s²; 0: arranca y frena sin rampa, como el
// jog), redondeado a pulsos enteros como los da el firmware cada 2 ms.
Run drive(int motor, double tool, double current, double speed, double acceleration, double travel) {
  plant::Stepper stepper(plant::MOTORS[motor], scara::STEPS_PER_REV);
  plant::Load load = plant::loadOf(motor, tool);
  double sign = travel < 0 ? -1 : 1, distance = std::fabs(travel), position = 0, velocity = 0;
  Run run = {0, 0, 0};
  long stator = 0;
  for (int tick = 0; tick < 20000; ++tick) {
    double remaining = distance - position;
    if (acceleration <= 0) {
      velocity = remaining > 0 ? speed : 0;
    } else if (remaining <= velocity * velocity / (2 * acceleration)) {
      velocity = std::fmax(0.0, velocity - acceleration * DT);
    } else {
      velocity = std::fmin(speed, velocity + acceleration * DT);
    }
    position = std::fmin(distance, position + velocity * DT);
    stator = std::lround(sign * position);
    stepper.advance(stator, DT, load, current);
    double lag = std::fabs(stator - stepper.lost() - stepper.position()) / scara::MICROSTEPS;
    if (lag > run.maxLag) run.maxLag = lag;
    if (position >= distance && tick > 1000 && std::fabs(stepper.speed()) < 1e-4) break;
  }
  run.lost = stepper.lost();
  run.finalLag = (stator - stepper.lost() - stepper.position()) / scara::MICROSTEPS;
  return run;
}

double maxSpeed(int motor) { return scara::MOTOR_MAX_SPEED[motor] * pulsesPerDegree(); }
double maxAcceleration(int motor) { return scara::MOTOR_MAX_ACCELERATION[motor] * pulsesPerDegree(); }
// Una velocidad del firmware sin rampa (centésimas/s de la articulación), en pulsos/s del motor.
double pulsesPerSecond(int motor, int32_t speed) {
  return static_cast<double>(speed) * scara::STEPS_NUM[motor] / scara::STEPS_DEN[motor];
}
// El jog más rápido del firmware.
double jogSpeed(int motor) { return pulsesPerSecond(motor, scara::JOG_SPEED_MAX); }

// Curva par–velocidad: plana hasta la esquina, después cae como 1/ω. Con
// menos corriente, baja el par de baja velocidad pero no el limitado por la
// tensión.
void torqueCurve() {
  for (int motor = 0; motor < 4; ++motor) {
    const plant::MotorSpec& spec = plant::MOTORS[motor];
    double corner = plant::cornerSpeed(spec);
    double low = plant::LOW_SPEED_FACTOR * spec.holdingTorque;
    check(std::fabs(plant::availableTorque(spec, 0, 1) - low) < 1e-12, "a baja velocidad, 0,7 del de retención",
          plant::availableTorque(spec, 0, 1), low);
    check(std::fabs(plant::availableTorque(spec, -corner / 2, 1) - low) < 1e-12, "plana hasta la esquina",
          plant::availableTorque(spec, -corner / 2, 1), low);
    check(std::fabs(plant::availableTorque(spec, 2 * corner, 1) - low / 2) < 1e-12, "al doble, la mitad",
          plant::availableTorque(spec, 2 * corner, 1), low / 2);
    check(std::fabs(plant::availableTorque(spec, 0, 0.5) - low / 2) < 1e-12, "media corriente, medio par",
          plant::availableTorque(spec, 0, 0.5), low / 2);
    check(std::fabs(plant::availableTorque(spec, 4 * corner, 0.5) - low / 4) < 1e-12,
          "rápido, la tensión limita igual", plant::availableTorque(spec, 4 * corner, 0.5), low / 4);
  }
}

// Los límites de D45 dejan margen: con la corriente nominal, ningún motor
// pierde pasos a su velocidad y aceleración máximas, ni arrancando sin rampa
// a la del jog o a la de búsqueda del homing, con la herramienta sola o con 5 kg. El atraso no llega a un
// paso completo, donde la curva par–ángulo da su máximo.
void d45HasMargin() {
  for (int motor = 0; motor < 4; ++motor) {
    for (double tool : {NOMINAL_TOOL, HEAVY_TOOL}) {
      for (double sign : {1.0, -1.0}) {
        Run profile = drive(motor, tool, 1, maxSpeed(motor), maxAcceleration(motor), sign * 4 * scara::STEPS_PER_REV);
        check(profile.lost == 0, "D45 sin pasos perdidos", motor + 1, tool);
        check(profile.maxLag < 1, "D45 con menos de un paso completo de atraso", motor + 1, profile.maxLag);
        Run jog = drive(motor, tool, 1, jogSpeed(motor), 0, sign * scara::STEPS_PER_REV);
        check(jog.lost == 0, "jog sin rampa sin pasos perdidos", motor + 1, tool);
        check(jog.maxLag < 1, "jog con menos de un paso completo de atraso", motor + 1, jog.maxLag);
        Run search = drive(motor, tool, 1, pulsesPerSecond(motor, scara::HOME_FAST[motor]), 0, sign * scara::STEPS_PER_REV);
        check(search.lost == 0, "búsqueda del homing sin pasos perdidos", motor + 1, tool);
        check(search.maxLag < 1, "búsqueda con menos de un paso completo de atraso", motor + 1, search.maxLag);
      }
    }
  }
}

// Quieto y sin carga, el rotor no se mueve; con 5 kg, J4 se asienta un poco
// por debajo del equilibrio (la curva par–ángulo cede) sin perder pasos.
void atRest() {
  Run idle = drive(0, NOMINAL_TOOL, 1, 0, 0, 0);
  check(idle.lost == 0 && std::fabs(idle.finalLag) < 1e-6, "quieto no se mueve", idle.lost, idle.finalLag);
  Run held = drive(3, HEAVY_TOOL, 1, 0, 0, 0);
  check(held.lost == 0, "J4 sostiene 5 kg", held.lost, 0);
  check(held.finalLag < -0.1 && held.finalLag > -1, "y cede menos de un paso completo", held.finalLag, 0);
}

// Por carga: con el driver de M4 a media corriente, 5 kg no suben. El motor
// pierde pasos de a 4 pasos completos y queda abajo de lo que contó (los
// pulsos subían, en sentido negativo, y el rotor no los siguió).
void lostByLoad() {
  Run lift = drive(3, HEAVY_TOOL, 0.5, jogSpeed(3), 0, -scara::STEPS_PER_REV);
  check(lift.lost < 0, "sin par para subir, pierde pasos", lift.lost, 0);
  check(lift.lost % CYCLE == 0, "de a 4 pasos completos", lift.lost, CYCLE);
  // Bajar sí puede: el peso ayuda.
  Run lower = drive(3, HEAVY_TOOL, 0.5, jogSpeed(3), 0, scara::STEPS_PER_REV);
  check(lower.lost == 0, "bajar con el peso a favor", lower.lost, 0);
}

// Por aceleración: con el driver de M1 al 20 % y 5 kg, el jog de J1 que
// arranca sin rampa pierde pasos al arrancar; con una rampa suave (136 °/s²
// en el eje, la de D45 hasta D76), a la misma velocidad, no. Con la rampa del
// planificador también los pierde: un driver regulado de menos no da el par
// que D76 supone.
void lostByAcceleration() {
  Run jerk = drive(0, HEAVY_TOOL, 0.2, jogSpeed(0), 0, scara::STEPS_PER_REV);
  check(jerk.lost != 0, "arrancar sin rampa pierde pasos", jerk.lost, 0);
  check(jerk.lost % CYCLE == 0, "de a 4 pasos completos", jerk.lost, CYCLE);
  Run gentle = drive(0, HEAVY_TOOL, 0.2, jogSpeed(0), 136 * pulsesPerDegree(), scara::STEPS_PER_REV);
  check(gentle.lost == 0, "con rampa suave no", gentle.lost, 0);
  Run planned = drive(0, HEAVY_TOOL, 0.2, jogSpeed(0), maxAcceleration(0), scara::STEPS_PER_REV);
  check(planned.lost != 0, "con la rampa del planificador, sí", planned.lost, 0);
}

// Contra un tope mecánico, el estator sigue y el rotor no: pierde pasos.
void againstAStop() {
  plant::Stepper stepper(plant::MOTORS[2], scara::STEPS_PER_REV);
  plant::Load load = plant::loadOf(2, NOMINAL_TOOL);
  for (long stator = 1; stator <= 200; ++stator) {
    stepper.advance(stator, DT, load, 1);
    stepper.stopAt(0);
  }
  check(stepper.lost() > 0 && stepper.lost() % CYCLE == 0, "contra el tope pierde de a 4", stepper.lost(), CYCLE);
  check(200 - stepper.lost() < 2 * scara::MICROSTEPS, "y queda a menos de medio ciclo", stepper.lost(), 200);
}

// Un esfuerzo externo por encima del par disponible hace saltar ciclos
// aunque el firmware no emita pulsos. Al retirarlo conserva el corrimiento.
void externalLoad() {
  plant::Stepper stepper(plant::MOTORS[0], scara::STEPS_PER_REV);
  plant::Load load = plant::loadOf(0, HEAVY_TOOL);
  for (int tick = 0; tick < 1000; ++tick) stepper.advance(0, DT, load, 1, -0.9);
  check(stepper.lost() > CYCLE, "carga externa supera retención y pierde pasos", stepper.lost(), CYCLE);
  for (int tick = 0; tick < 3000; ++tick) stepper.advance(0, DT, load, 1);
  long lost = stepper.lost();
  double position = stepper.position();
  check(std::fabs(position + lost) < 1, "al retirar la carga queda en el equilibrio corrido", position, lost);
  for (int tick = 0; tick < 500; ++tick) stepper.advance(0, DT, load, 1);
  check(stepper.lost() == lost && std::fabs(stepper.position() - position) < 1,
        "el esfuerzo retirado no recupera pasos", stepper.lost(), lost);
}

// Un empujón horizontal breve en la punta (C3): por debajo del par de
// retención cede dentro del ciclo eléctrico y vuelve al equilibrio al soltar;
// por encima salta ciclos completos y conserva el corrimiento sin aviso.
void pushImpulse() {
  plant::Load load = plant::loadOf(0, NOMINAL_TOOL);
  const double effortGentle[4] = {-0.50 * 5.0, -0.25 * 5.0, 0, 0};
  const double reactionGentle = plant::motorReaction(0, effortGentle);
  plant::Stepper gentle(plant::MOTORS[0], scara::STEPS_PER_REV);
  double maxDeflection = 0;
  for (int tick = 0; tick < 500; ++tick) {
    gentle.advance(0, DT, load, 1, reactionGentle);
    maxDeflection = std::fmax(maxDeflection, std::fabs(gentle.position()));
  }
  for (int tick = 0; tick < 2000; ++tick) gentle.advance(0, DT, load, 1, 0);
  check(maxDeflection > 1 && maxDeflection < 2 * scara::MICROSTEPS,
        "empujón suave cede dentro del ciclo", maxDeflection, 2 * scara::MICROSTEPS);
  check(gentle.lost() == 0 && std::fabs(gentle.position()) < 0.5,
        "empujón suave vuelve al equilibrio sin perder pasos", gentle.position(), gentle.lost());

  const double effortStrong[4] = {-0.50 * 12.0, -0.25 * 12.0, 0, 0};
  const double reactionStrong = plant::motorReaction(0, effortStrong);
  plant::Stepper strong(plant::MOTORS[0], scara::STEPS_PER_REV);
  for (int tick = 0; tick < 500; ++tick) strong.advance(0, DT, load, 1, reactionStrong);
  for (int tick = 0; tick < 2000; ++tick) strong.advance(0, DT, load, 1, 0);
  check(strong.lost() != 0 && strong.lost() % CYCLE == 0,
        "empujón fuerte pierde múltiplos de 4 pasos", strong.lost(), CYCLE);
  check(std::fabs(strong.position() + strong.lost()) < 1,
        "empujón fuerte deja corrimiento permanente", strong.position(), -strong.lost());
}

// El contacto inmoviliza el cuerpo y su rotor, pero el estator sigue. Al
// quitar el obstáculo solo queda la elasticidad de medio ciclo eléctrico;
// los pulsos siguientes parten desde la posición corrida, sin alcanzarla.
void contactRelease() {
  plant::Stepper stepper(plant::MOTORS[0], scara::STEPS_PER_REV);
  plant::Load load = plant::loadOf(0, HEAVY_TOOL);
  const long commanded = 203;
  for (long pulse = 1; pulse <= commanded; ++pulse) {
    stepper.advanceContact(pulse, DT, load, 1, 0, 0, -0.56);
  }
  long lost = stepper.lost();
  check(lost > 0 && lost % CYCLE == 0, "bloqueado pierde ciclos completos", lost, commanded);
  double maxRelease = 0;
  for (int tick = 0; tick < 2000; ++tick) {
    stepper.advance(commanded, DT, load, 1);
    maxRelease = std::fmax(maxRelease, std::fabs(stepper.position()));
  }
  check(maxRelease < 2 * scara::MICROSTEPS, "liberado no salta al objetivo anterior", maxRelease, commanded);
  check(stepper.lost() == lost, "al liberar no recupera pasos", stepper.lost(), lost);
  double released = stepper.position();
  for (long tick = 1; tick <= 500; ++tick) stepper.advance(commanded + tick, DT, load, 1);
  for (int tick = 0; tick < 2000; ++tick) stepper.advance(commanded + 500, DT, load, 1);
  check(stepper.lost() == lost, "pulsos nuevos conservan pérdida", stepper.lost(), lost);
  check(std::fabs(stepper.position() - released - 500) < 1, "continúa desde donde quedó", stepper.position() - released, 500);
}

// El motor de J1 no dispone del par de M2: ese segundo accionamiento actúa
// en J2 y su reacción en el brazo se cancela mediante la transmisión fija.
void actuatorCapacity() {
  const double motorTorque[4] = {0.56, 0.56, 0.217, 0.14};
  check(std::fabs(plant::jointCapacity(0, motorTorque) - 2.128) < 1e-9,
        "accionamiento J1 limitado por M1", plant::jointCapacity(0, motorTorque), 2.128);
  const double effort[4] = {4.256, 2.128, 0, 0};
  check(std::fabs(plant::motorReaction(0, effort) + 0.56) < 1e-9 &&
        std::fabs(plant::motorReaction(1, effort) + 0.56) < 1e-9,
        "esfuerzo acoplado realizable con ambos motores al límite", plant::motorReaction(0, effort), -0.56);
}

// Una superficie puede sostener todo el peso sin par del accionamiento:
// su reacción compensa la gravedad, no la agrega otra vez al rotor.
void contactSupportsWeight() {
  plant::Stepper stepper(plant::MOTORS[3], scara::STEPS_PER_REV);
  plant::Load load = plant::loadOf(3, HEAVY_TOOL);
  for (int tick = 0; tick < 1000; ++tick) stepper.advanceContact(0, DT, load, 1, 0, 0, 0);
  check(stepper.position() == 0 && stepper.speed() == 0 && stepper.lost() == 0,
        "contacto soporta peso sin duplicar gravedad", stepper.position(), stepper.lost());
}

// Margen de par en los límites de D45, a la velocidad máxima: el disponible
// contra el que piden la aceleración máxima, el peso (al subir) y la fricción.
void table() {
  std::printf("motor  esquina(°/s)  disponible(N·m)  pedido sin carga  margen  pedido con 5 kg  margen\n");
  for (int motor = 0; motor < 4; ++motor) {
    const plant::MotorSpec& spec = plant::MOTORS[motor];
    double speed = scara::MOTOR_MAX_SPEED[motor] * plant::PI / 180;
    double acceleration = scara::MOTOR_MAX_ACCELERATION[motor] * plant::PI / 180;
    double available = plant::availableTorque(spec, speed, 1);
    std::printf("M%d     %12.0f  %15.3f", motor + 1, plant::cornerSpeed(spec) * 180 / plant::PI, available);
    for (double tool : {NOMINAL_TOOL, HEAVY_TOOL}) {
      plant::Load load = plant::loadOf(motor, tool);
      double asked = (spec.rotorInertia + load.inertia) * acceleration + std::fabs(load.gravity) / load.efficiency +
                     load.friction;
      std::printf("  %14.4f  %6.1f", asked, available / asked);
    }
    std::printf("\n");
  }
}

}  // namespace

int main(int argc, char** argv) {
  if (argc > 1 && std::strcmp(argv[1], "--tabla") == 0) {
    table();
    return 0;
  }
  torqueCurve();
  d45HasMargin();
  atRest();
  lostByLoad();
  lostByAcceleration();
  againstAStop();
  externalLoad();
  pushImpulse();
  contactRelease();
  actuatorCapacity();
  contactSupportsWeight();
  return failures == 0 ? 0 : 1;
}
