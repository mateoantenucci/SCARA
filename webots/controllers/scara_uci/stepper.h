// Modelo de motor paso a paso de la planta simulada, nivel N2 (ADR 0006,
// D64): par disponible según la velocidad y pérdida de pasos cuando la carga
// o la aceleración lo superan. El firmware no se entera: sigue contando los
// pulsos que emitió.
//
// El rotor es una inercia que sigue al campo del estator con la curva
// par–ángulo del motor híbrido: T = T(ω) · sen(π/2 · e / paso completo), con e
// el atraso del rotor. El par máximo, a un paso completo de atraso, es el de
// la curva par–velocidad T(ω); a dos pasos completos (medio ciclo eléctrico)
// el equilibrio se vuelve inestable y el rotor cae al siguiente, cuatro pasos
// completos más atrás o más adelante: se pierden pasos de a cuatro. Lo
// eléctrico (corrientes, inductancia, resonancias, N3) queda resumido en la
// curva par–velocidad y en un amortiguamiento fijo.
//
// Sin Webots: lo usan la planta (scara_uci.cpp) y sus pruebas en la PC
// (test/stepper.cpp). Las fuentes y los supuestos de cada número están en
// docs/TRANSMISION.md (N2).
#ifndef SCARA_STEPPER_H
#define SCARA_STEPPER_H

#include <cmath>

namespace plant {

const double PI = 3.141592653589793;
const double GRAVITY = 9.81;          // m/s²
const int FULL_STEPS_PER_REV = 200;   // 1,8°
const double FULL_STEP = 2 * PI / FULL_STEPS_PER_REV;  // rad del eje del motor
const int STEPS_PER_CYCLE = 4;        // pasos completos por ciclo eléctrico (dos fases)

// Datos de un motor y de su driver.
struct MotorSpec {
  double holdingTorque;  // N·m, con las dos fases a la corriente nominal
  double rotorInertia;   // kg·m²
  double inductance;     // H, por fase
  double current;        // A, nominal por fase: la que se regula en el TB6600
};

// Lo que el motor mueve, visto desde su eje.
struct Load {
  double inertia;         // kg·m², reflejada por la transmisión
  double gravity;         // N·m que el peso hace sobre el eje, con signo (+: sentido positivo del motor)
  double efficiency;      // de la transmisión, cuando el motor mueve la carga
  double backEfficiency;  // cuando la carga empuja al motor (el peso de J4 al bajar o quieto)
  double friction;        // N·m de fricción seca, contra el movimiento
};

// Supuestos comunes (D64): los TB6600 con 24 V; con micropasos, las
// corrientes senoidales dan alrededor de 1/√2 del par de retención a baja
// velocidad; el sistema queda amortiguado con ζ = 0,6.
const double SUPPLY_VOLTAGE = 24.0;
const double LOW_SPEED_FACTOR = 0.7;
const double DAMPING_RATIO = 0.6;

// Velocidad de esquina, en rad/s del eje: hasta ahí el driver alcanza a
// llevar la corriente a su valor en cada paso; más rápido, la inductancia
// la recorta y el par cae como 1/ω (potencia constante). En pasos completos
// por segundo es V / (2 L I).
inline double cornerSpeed(const MotorSpec& spec) {
  return SUPPLY_VOLTAGE / (2 * spec.inductance * spec.current) * FULL_STEP;
}

// Par disponible a la velocidad `speed` (rad/s del eje), con el driver a la
// fracción `current` de su corriente nominal (falla F1). A baja velocidad el
// par es proporcional a la corriente; arriba de la esquina lo limita la
// tensión, y una corriente menor no lo cambia.
inline double availableTorque(const MotorSpec& spec, double speed, double current) {
  double low = LOW_SPEED_FACTOR * spec.holdingTorque * current;
  double corner = cornerSpeed(spec);
  double magnitude = std::fabs(speed);
  double limited = magnitude <= corner ? LOW_SPEED_FACTOR * spec.holdingTorque
                                       : LOW_SPEED_FACTOR * spec.holdingTorque * corner / magnitude;
  return low < limited ? low : limited;
}

class Stepper {
public:
  // `pulsesPerRev`: pulsos por vuelta con el microstepping del driver.
  Stepper(const MotorSpec& spec, int pulsesPerRev)
      : spec_(spec), pulse_(2 * PI / pulsesPerRev), microsteps_(pulsesPerRev / FULL_STEPS_PER_REV) {
    reset(0);
  }

  // El rotor queda quieto y en equilibrio con el estator, en `pulses`: al
  // arrancar, y cuando el motor vuelve a tener corriente donde quedó (D60).
  void reset(long pulses) {
    stator_ = pulses;
    lost_ = 0;
    angle_ = pulses * pulse_;
    speed_ = 0;
    fieldSpeed_ = 0;
  }

  // Avanza `dt` segundos, en los que el estator pasó de su posición anterior
  // a `stator` pulsos. Los pulsos se reparten parejos en el intervalo, como
  // los emite el firmware. `current`: fracción de la corriente nominal.
  void advance(long stator, double dt, const Load& load, double current) {
    const double inertia = spec_.rotorInertia + load.inertia;
    const double h = dt / SUBSTEPS;
    const long from = stator_;
    // Velocidad media del campo, filtrada: la referencia del amortiguamiento.
    double tickSpeed = (stator - from) * pulse_ / dt;
    fieldSpeed_ += (tickSpeed - fieldSpeed_) * dt / (FIELD_FILTER + dt);
    for (int k = 1; k <= SUBSTEPS; ++k) {
      double field = (from + (stator - from) * static_cast<double>(k) / SUBSTEPS - lost_) * pulse_;
      double lag = field - angle_;
      double available = availableTorque(spec_, speed_, current);
      // Rigidez de la curva par–ángulo cerca del equilibrio, y el
      // amortiguamiento que le corresponde con esa inercia.
      double stiffness = available * PI / (2 * FULL_STEP);
      double damping = 2 * DAMPING_RATIO * std::sqrt(stiffness * inertia);
      double torque = available * std::sin(PI / 2 * lag / FULL_STEP) + damping * (fieldSpeed_ - speed_);
      if (torque > available) torque = available;
      if (torque < -available) torque = -available;
      speed_ += (torque + external(load)) / inertia * h;
      angle_ += speed_ * h;
      // A más de medio ciclo eléctrico, el rotor cae al equilibrio siguiente.
      const double half = STEPS_PER_CYCLE / 2 * FULL_STEP;
      while (field - angle_ > half) {
        lost_ += STEPS_PER_CYCLE * microsteps_;
        field -= STEPS_PER_CYCLE * FULL_STEP;
      }
      while (field - angle_ < -half) {
        lost_ -= STEPS_PER_CYCLE * microsteps_;
        field += STEPS_PER_CYCLE * FULL_STEP;
      }
    }
    stator_ = stator;
  }

  // Un tope mecánico frena el eje en `pulses`: el rotor queda ahí, quieto,
  // aunque el estator siga avanzando (y el motor pierda pasos contra el tope).
  void stopAt(double pulses) {
    angle_ = pulses * pulse_;
    speed_ = 0;
  }

  // Pulsos que el rotor no siguió, múltiplo de 4 pasos completos: su
  // equilibrio está en los pulsos emitidos menos estos.
  long lost() const { return lost_; }
  // Posición del rotor, en pulsos (con fracción), y su velocidad en rad/s.
  double position() const { return angle_ / pulse_; }
  double speed() const { return speed_; }

private:
  static const int SUBSTEPS = 10;     // por paso de Webots: con 2 ms, 0,2 ms
  static constexpr double FIELD_FILTER = 0.01;  // s

  // Par de la carga sobre el eje. El peso, a través del tornillo, pesa más al
  // subir (1/η) que al bajar o quieto (η inversa). Las transiciones se
  // suavizan cerca de velocidad cero para no rebotar entre los dos casos.
  double external(const Load& load) const {
    const double still = 0.05;  // rad/s
    double against = 0.5 * (1 - std::tanh(speed_ * (load.gravity >= 0 ? 1 : -1) / still));
    double gravity = load.gravity * (load.backEfficiency + (1 / load.efficiency - load.backEfficiency) * against);
    return gravity - load.friction * std::tanh(speed_ / still);
  }

  MotorSpec spec_;
  double pulse_;      // rad por pulso
  int microsteps_;
  long stator_;       // pulsos emitidos al motor
  long lost_;
  double angle_;      // rad
  double speed_;      // rad/s
  double fieldSpeed_;
};

// --- Los motores del SCARA y lo que mueve cada uno (D64) ------------------

// Catálogo. El maestro nombra los modelos; sus hojas de datos exactas no
// aparecieron, así que se toman de la familia más cercana o son supuestos
// típicos (docs/TRANSMISION.md, N2):
//   M1, M2: Minebea 23KM-K381-P1. Familia 23KM-K3 (cuerpo de 50 mm), bipolar
//           23KM-K349B: 0,80 N·m, 180 g·cm², 11,8 mH, 1,4 A.
//   M3:     Shinano Kenshi STP-42D221-03. Del STP-42D201-37: 0,31 N·m;
//           inercia, inductancia y corriente, supuestos de un NEMA 17 de 40 mm.
//   M4:     42D265, 1,9 V y 0,7 A del maestro; par, inercia e inductancia,
//           supuestos de un NEMA 17 corto a esa corriente.
const MotorSpec MOTORS[4] = {
    {0.80, 180e-7, 11.8e-3, 1.4},
    {0.80, 180e-7, 11.8e-3, 1.4},
    {0.31, 54e-7, 8e-3, 0.8},
    {0.20, 35e-7, 4e-3, 0.7},
};

// Transmisión (D8): poleas 2GT 4:1 en M1–M3 y ACME de 8 mm por vuelta en M4.
const double PULLEY_RATIO = 4.0;
const double LEAD = 0.008;           // m por vuelta
const double BELT_EFFICIENCY = 0.95;  // supuesto típico de correa dentada
// ACME de 8 mm de avance sobre unos 7 mm de diámetro medio (ángulo de hélice
// de 20°) con tuerca de bronce y fricción 0,15: η ≈ 0,67 al subir y 0,55
// cuando el peso empuja. Es reversible: sin corriente, J4 cae (D60).
const double SCREW_EFFICIENCY = 0.67;
const double SCREW_BACK_EFFICIENCY = 0.55;
// Fricción seca en el eje del motor (rodamientos, retén): 3 % del par de
// retención, supuesto.
const double FRICTION_FACTOR = 0.03;

// Masas e inercias de SCARA.proto (config/scara.json), en kg, m y kg·m².
const double L1 = 0.25, L2 = 0.25;  // hombro–codo y codo–muñeca
const double ARM_INERTIA = 0.0074;   // brazo (0,3 kg) alrededor de J1
const double FOREARM_INERTIA = 0.0124;  // antebrazo (0,5 kg) alrededor del codo
const double FOREARM_MASS = 0.5;
const double WRIST_MASS = 0.35;      // conjunto Z, sobre el eje de J3
const double WRIST_INERTIA = 0.00034;
const double TOOL_RADIUS = 0.03;     // la herramienta y su carga, sobre el eje de J3
// Pistón y soporte, sin carga: el toolMass de SCARA.proto. La carga del banco
// de ensayo se suma a esta masa, hasta los 5 kg con los que se verificaron los
// límites (D76, D85).
const double TOOL_MASS = 0.15;
const double TOOL_MAX = 5.0;

// Lo que mueve el motor `motor` (0..3) con `tool` kg en la herramienta
// (toolMass del proto: pistón, soporte y carga). M1 gira el brazo con todo
// lo que cuelga del codo; M2, el ángulo absoluto del antebrazo con la muñeca
// (D8). Se toman las inercias con el brazo estirado, la pose más exigente, y
// sin los términos cruzados entre M1 y M2. J1–J3 giran en el plano: el peso no
// les hace par.
inline Load loadOf(int motor, double tool) {
  const double reduction = PULLEY_RATIO * PULLEY_RATIO * BELT_EFFICIENCY;
  Load load = {0, 0, BELT_EFFICIENCY, BELT_EFFICIENCY, FRICTION_FACTOR * MOTORS[motor].holdingTorque};
  switch (motor) {
    case 0:
      load.inertia = (ARM_INERTIA + (FOREARM_MASS + WRIST_MASS + tool) * L1 * L1) / reduction;
      break;
    case 1:
      load.inertia = (FOREARM_INERTIA + (WRIST_MASS + tool) * L2 * L2) / reduction;
      break;
    case 2:
      load.inertia = (WRIST_INERTIA + tool * TOOL_RADIUS * TOOL_RADIUS / 2) / reduction;
      break;
    default: {
      // J4 positivo hacia abajo: el peso empuja a M4 en sentido positivo.
      const double radius = LEAD / (2 * PI);
      load.inertia = tool * radius * radius;
      load.gravity = tool * GRAVITY * radius;
      load.efficiency = SCREW_EFFICIENCY;
      load.backEfficiency = SCREW_BACK_EFFICIENCY;
    }
  }
  return load;
}

}  // namespace plant

#endif
