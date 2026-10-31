#include "firmware.h"

#include <string.h>

#include "transmission.h"

namespace scara {

namespace {

// Pose de reposo (D30): brazo estirado y J4 abajo, en unidades del protocolo.
const int32_t REST[MOTOR_COUNT] = {0, 0, 0, 12000};
// Una pausa larga entre llamadas no se recupera de golpe.
const uint32_t JOG_MAX_ELAPSED_MS = 100;

// El jog arranca y frena sin rampa, así que su velocidad máxima tiene que
// quedar dentro de la de cada motor (D45), también en el jog por motor.
static_assert(withinMotorSpeed(0, JOG_SPEED_MAX) && withinMotorSpeed(1, JOG_SPEED_MAX) &&
                  withinMotorSpeed(2, JOG_SPEED_MAX) && withinMotorSpeed(3, JOG_SPEED_MAX),
              "JOG_SPEED_MAX supera la velocidad de algún motor");

char* append(char* out, const char* text) {
  while (*text) *out++ = *text++;
  return out;
}

char* append(char* out, int32_t value) {
  char digits[10];
  uint8_t count = 0;
  uint32_t magnitude = value < 0 ? 0u - static_cast<uint32_t>(value) : static_cast<uint32_t>(value);
  if (value < 0) *out++ = '-';
  do {
    digits[count++] = static_cast<char>('0' + magnitude % 10);
    magnitude /= 10;
  } while (magnitude != 0);
  while (count != 0) *out++ = digits[--count];
  return out;
}

// Separa el próximo campo; devuelve 0 si no quedan.
char* nextField(char** cursor) {
  char* start = *cursor;
  while (*start == ' ') ++start;
  if (*start == '\0') return 0;
  char* end = start;
  while (*end != '\0' && *end != ' ') ++end;
  if (*end != '\0') *end++ = '\0';
  *cursor = end;
  return start;
}

bool noMoreFields(char* cursor) { return nextField(&cursor) == 0; }

// Entero sin signo de hasta 9 cifras.
bool parseUnsigned(const char* text, int32_t* value) {
  int32_t result = 0;
  uint8_t digits = 0;
  for (; *text != '\0'; ++text, ++digits) {
    if (*text < '0' || *text > '9' || digits == 9) return false;
    result = result * 10 + (*text - '0');
  }
  if (digits == 0) return false;
  *value = result;
  return true;
}

// Entero con un signo menos opcional y hasta 9 cifras.
bool parseSigned(const char* text, int32_t* value) {
  bool negative = *text == '-';
  if (!parseUnsigned(negative ? text + 1 : text, value)) return false;
  if (negative) *value = -*value;
  return true;
}

int64_t magnitude(int64_t value) { return value < 0 ? -value : value; }

int64_t divideRounded64(int64_t value, int64_t divisor) {
  return value >= 0 ? (value + divisor / 2) / divisor : -((-value + divisor / 2) / divisor);
}

}  // namespace

// Código y palabra de cada ERR. Son estables: se agregan, no se renumeran.
const int32_t ERR_COMMAND = 1;    // comando desconocido o bytes no permitidos
const int32_t ERR_ARGUMENTS = 2;  // faltan, sobran o están fuera de rango
const int32_t ERR_LENGTH = 3;     // línea de más de LINE_MAX bytes
const int32_t ERR_WATCHDOG = 4;   // sin mensajes de la URC: se frenó solo
const int32_t ERR_BUSY = 5;       // no se acepta con otro movimiento en curso
const int32_t ERR_DISABLED = 6;   // no se acepta sin corriente en los drivers
const int32_t ERR_REFERENCE = 7;  // SEG sin los cuatro ejes referenciados
const int32_t ERR_SPEED = 8;      // el segmento le pide a un motor más velocidad que la suya
const int32_t ERR_QUEUE = 9;      // SEG antes del OK del anterior, con la cola llena
const int32_t ERR_END = 10;       // el jog frenó al activarse un Hall: fin de carrera
const int32_t ERR_MISSING = 11;   // homing: el Hall no apareció en el recorrido o el tiempo máximos
const int32_t ERR_STUCK = 12;     // homing: el Hall no se apagó, está trabado activo

namespace {

// Orden del homing (D11): J4 sube primero, después J1, J2 y J3.
const uint8_t HOME_ORDER[MOTOR_COUNT] = {3, 0, 1, 2};
// Hall de los ejes que mueve cada motor solo, en el jog por motor: M1 mueve
// J1 y J2.
const uint8_t MOTOR_HALLS[MOTOR_COUNT] = {0x03, 0x02, 0x04, 0x08};
// Margen para salir de un imán, además de su ancho: tolerancia de montaje.
const int32_t HALL_MARGIN = 100;

}  // namespace

Firmware::Firmware(Hal& hal)
    : hal_(hal), length_(0), invalid_(false), overflow_(false), homed_(0), enabled_(false), motion_(NONE),
      jogMotors_(0), jogAxis_(0), jogDirection_(0), jogSpeed_(0), jogAccumulator_(0), jogSteps_(0), lastJog_(0),
      hall_(0), lastHall_(0), jogHalls_(0), jogStartHalls_(0), endHalls_(0), endMotors_(0), endDirection_(0), homeCount_(0), homeIndex_(0), homePhase_(SEARCH),
      homeStarted_(0), homedNow_(0), homeWasHomed_(0), head_(0), count_(0), holding_(false), started_(0), done_(0), rampMs_(0),
      rampStarted_(0), lastStatus_(0), lastMessage_(0) {
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) steps_[motor] = 0;
}

// Arranca sin corriente (D40): nada se mueve hasta que la URC envía ENABLE.
void Firmware::begin() {
  hal_.enableDrivers(false);
  uint32_t now = hal_.millis();
  lastJog_ = lastStatus_ = lastMessage_ = now;
  hall_ = lastHall_ = hal_.readHall();
  sendIdentity("BOOT ");
}

// BOOT o HI: protocolo y versión de firmware.
void Firmware::sendIdentity(const char* greeting) {
  char out[LINE_MAX];
  char* end = append(append(append(append(out, greeting), PROTOCOL), " "), FIRMWARE_VERSION);
  append(end, "\n")[0] = '\0';
  hal_.write(out);
}

void Firmware::poll() {
  uint32_t now = hal_.millis();
  // Primero los Hall, que pueden frenar el jog o cambiar la fase del homing;
  // después el movimiento hasta ahora con la orden vigente, y por último las
  // órdenes nuevas, que rigen desde este instante.
  lastHall_ = hall_;
  hall_ = hal_.readHall();
  // Un Hall que se apagó ya no frena nada, aunque después se active con el
  // imán del otro extremo.
  endHalls_ &= hall_;
  if (motion_ != HOMING) checkLostSteps();
  if (motion_ == JOG) checkJogHall();
  if (motion_ == HOMING) advanceHoming(now);
  advanceJog(now);
  if (motion_ == RUN) advanceRun(now);
  if (motion_ == STOPPING) advanceStopping(now);
  for (int byte = hal_.readByte(); byte >= 0; byte = hal_.readByte()) {
    if (byte == '\n') lastMessage_ = now;
    receive(byte);
  }
  // Quieto no hay nada que frenar, y frenando ya se frena. Frena como STOP
  // (D41): los drivers siguen con corriente.
  if ((motion_ == JOG || motion_ == RUN || motion_ == HOMING) && now - lastMessage_ > WATCHDOG_MS) {
    stop(now);
    sendError(ERR_WATCHDOG, "watchdog");
  }
  if (now - lastStatus_ >= STATUS_PERIOD_MS) {
    lastStatus_ = now;
    sendStatus();
  }
}

void Firmware::receive(int byte) {
  if (byte == '\r') return;
  if (byte == '\n') {
    bool overflow = overflow_, invalid = invalid_;
    overflow_ = invalid_ = false;
    line_[length_] = '\0';
    length_ = 0;
    if (overflow) {
      reject(ERR_LENGTH, "largo");
    } else if (invalid) {
      reject(ERR_COMMAND, "comando");
    } else {
      handle(line_);
    }
    return;
  }
  // Hasta LINE_MAX - 1 caracteres más el LF.
  if (length_ >= LINE_MAX - 1) {
    overflow_ = true;
    return;
  }
  // Solo ASCII imprimible: un byte nulo cortaría la línea sin avisar.
  if (byte < ' ' || byte > '~') invalid_ = true;
  line_[length_++] = static_cast<char>(byte);
}

void Firmware::handle(char* line) {
  char* cursor = line;
  char* command = nextField(&cursor);
  if (command == 0) return;
  if (strcmp(command, "JOG") == 0) {
    handleJog(cursor);
    return;
  }
  if (strcmp(command, "SEG") == 0) {
    handleSegment(cursor);
    return;
  }
  if (strcmp(command, "HOME") == 0) {
    handleHome(cursor);
    return;
  }
  // Órdenes sin argumentos.
  static const char* const SIMPLE[] = {"HELLO", "PING", "STATUS", "ENABLE", "DISABLE", "STOP", "HALT", "ZERO"};
  bool known = false;
  for (uint8_t i = 0; !known && i < sizeof SIMPLE / sizeof SIMPLE[0]; ++i) known = strcmp(command, SIMPLE[i]) == 0;
  if (!known) {
    reject(ERR_COMMAND, "comando");
  } else if (!noMoreFields(cursor)) {
    reject(ERR_ARGUMENTS, "argumentos");
  } else if (strcmp(command, "HELLO") == 0) {
    sendIdentity("HI ");
  } else if (strcmp(command, "STATUS") == 0) {
    sendStatus();
  } else if (strcmp(command, "ENABLE") == 0) {
    enabled_ = true;
    hal_.enableDrivers(true);
  } else if (strcmp(command, "DISABLE") == 0) {
    disable();
  } else if (strcmp(command, "STOP") == 0) {
    stop(hal_.millis());
  } else if (strcmp(command, "HALT") == 0) {
    // Parada inmediata (D41): como el reset de GRBL, si había movimiento la
    // referencia ya no vale.
    if (moving()) homed_ = 0;
    halt();
  } else if (strcmp(command, "ZERO") == 0) {
    // Declara que el robot está en la pose de reposo. Sin corriente, los
    // motores giran libres: no hay pose que declarar.
    if (!enabled_) {
      reject(ERR_DISABLED, "deshabilitado");
      return;
    }
    if (moving()) {
      reject(ERR_BUSY, "ocupado");
      return;
    }
    jointsToMotors(REST, steps_);
    homed_ = 0x0F;
  }
  // PING solo renueva el watchdog.
}

// JOG j ± vel | JOG Mm ± vel | JOG STOP
void Firmware::handleJog(char* arguments) {
  char* first = nextField(&arguments);
  if (first != 0 && strcmp(first, "STOP") == 0 && noMoreFields(arguments)) {
    stopJog();
    return;
  }
  char* sign = nextField(&arguments);
  char* speedText = nextField(&arguments);
  // Mm: jog por motor, un modo de prueba que no compensa el acople (D46).
  bool byMotor = first != 0 && first[0] == 'M';
  int32_t axis, speed;
  bool valid = first != 0 && sign != 0 && speedText != 0 && noMoreFields(arguments) &&
               parseUnsigned(byMotor ? first + 1 : first, &axis) && axis >= 1 && axis <= MOTOR_COUNT &&
               (strcmp(sign, "+") == 0 || strcmp(sign, "-") == 0) &&
               parseUnsigned(speedText, &speed) && speed >= 1 && speed <= JOG_SPEED_MAX;
  if (!valid) {
    reject(ERR_ARGUMENTS, "argumentos");
    return;
  }
  if (!enabled_) {
    reject(ERR_DISABLED, "deshabilitado");
    return;
  }
  // Un jog reemplaza al anterior, pero no interrumpe a los segmentos.
  if (motion_ != NONE && motion_ != JOG) {
    reject(ERR_BUSY, "ocupado");
    return;
  }
  // Sin referencia, solo jog lento (D21).
  if (homed_ != 0x0F && speed > JOG_UNREFERENCED_MAX) speed = JOG_UNREFERENCED_MAX;
  uint8_t index = static_cast<uint8_t>(axis - 1);
  uint8_t motors = byMotor ? static_cast<uint8_t>(1 << index) : JOINT_MOTORS[index];
  int8_t direction = sign[0] == '+' ? 1 : -1;
  // Lo que frenó un Hall no vuelve a empujar hacia el tope mientras el Hall
  // siga activo: solo sale para el otro lado.
  if (endHalls_ != 0 && (motors & endMotors_) != 0 && direction == endDirection_) {
    stopJog();
    sendError(ERR_END, "fin");
    return;
  }
  motion_ = JOG;
  startDrive(index, motors, direction, speed);
  jogHalls_ = byMotor ? MOTOR_HALLS[index] : static_cast<uint8_t>(1 << index);
  jogStartHalls_ = hall_ & jogHalls_;
}

// El Hall es también el fin de carrera (D21): un jog que activa el Hall de un
// eje que mueve frena en seco. Si arrancó sobre un imán, puede salir de él,
// pero frena si recorre más que el ancho del imán sin que se apague: iba
// hacia el tope.
void Firmware::checkJogHall() {
  uint8_t active = hall_ & jogHalls_;
  jogStartHalls_ &= active;  // ya salió de los que se apagaron
  bool rose = (active & ~lastHall_ & ~jogStartHalls_) != 0;
  bool deep = jogStartHalls_ != 0 && jogSteps_ > unitsToSteps(jogAxis_, HALL_WIDTH[jogAxis_] + HALL_MARGIN);
  if (rose || deep) {
    endHalls_ = active;
    endMotors_ = jogMotors_;
    endDirection_ = jogDirection_;
    stopJog();
    sendError(ERR_END, "fin");
  }
}

// F1 (D65): con el eje referenciado, su Hall se activa siempre en el mismo
// flanco. Al entrar en un imán, compara los pasos contados con los del flanco:
// si difieren en 2 pasos completos o más (medio ciclo eléctrico, D64), el
// motor se corrió sin que el firmware lo supiera, y lo informa con
// EV LOST j pasos: los reales menos los contados, en pasos completos. No
// corrige la cuenta: solo el homing vuelve a referenciar. El homing se salta
// porque es justamente el que define los flancos.
void Firmware::checkLostSteps() {
  uint8_t entered = hall_ & ~lastHall_ & homed_;
  for (uint8_t axis = 0; entered != 0 && axis < MOTOR_COUNT; ++axis) {
    if ((entered & (1 << axis)) == 0) continue;
    // J2 se mide relativo a J1 (D10): sus pasos son los de M2 menos los de M1.
    int32_t counted = axis == 1 ? steps_[1] - steps_[0] : steps_[axis];
    // Un imán en cada extremo: el que está más cerca de la posición estimada.
    int32_t middle = (HALL_EDGE[axis] + HALL_FAR_EDGE[axis]) / 2;
    int32_t edge = stepsToUnits(axis, counted) < middle ? HALL_EDGE[axis] : HALL_FAR_EDGE[axis];
    int32_t difference = unitsToSteps(axis, edge) - counted;
    if (difference < 2 * MICROSTEPS && difference > -2 * MICROSTEPS) continue;
    char out[LINE_MAX];
    char* end = append(append(append(out, "EV LOST "), static_cast<int32_t>(axis + 1)), " ");
    append(append(end, divideRounded(difference, MICROSTEPS)), "\n")[0] = '\0';
    hal_.write(out);
  }
}

void Firmware::startDrive(uint8_t axis, uint8_t motors, int8_t direction, int32_t speed) {
  jogAxis_ = axis;
  jogMotors_ = motors;
  jogDirection_ = direction;
  jogSpeed_ = speed;
  jogAccumulator_ = 0;
  jogSteps_ = 0;
}

// HOME [j]: homing de los cuatro ejes, en el orden de D11, o solo del eje j.
// Cada eje encontrado se informa con EV HOMED j. La vuelta a la pose de
// reposo la planifica la URC (D56).
void Firmware::handleHome(char* arguments) {
  char* axisText = nextField(&arguments);
  int32_t axis = 0;
  if ((axisText != 0 && (!parseUnsigned(axisText, &axis) || axis < 1 || axis > MOTOR_COUNT)) ||
      !noMoreFields(arguments)) {
    reject(ERR_ARGUMENTS, "argumentos");
    return;
  }
  if (!enabled_) {
    reject(ERR_DISABLED, "deshabilitado");
    return;
  }
  if (moving()) {
    reject(ERR_BUSY, "ocupado");
    return;
  }
  homeCount_ = 0;
  homeWasHomed_ = homed_;
  for (uint8_t i = 0; i < MOTOR_COUNT; ++i) {
    uint8_t candidate = HOME_ORDER[i];
    if (axis == 0 || candidate == axis - 1) {
      homeOrder_[homeCount_++] = candidate;
      homed_ &= static_cast<uint8_t>(~(1 << candidate));
    }
  }
  homeIndex_ = 0;
  homedNow_ = 0;
  motion_ = HOMING;
  startHomeAxis(hal_.millis());
}

// Con el Hall activo al empezar, el sensor no dice sobre qué imán está. Si el
// eje tenía referencia y está en el flanco de la suya (otro HOME después de un
// homing), retrocede como después de encontrarlo. Si no, es el imán del otro
// extremo (desde el reposo, J4 descansa abajo, sobre el suyo) y sale de él
// hacia la referencia.
void Firmware::startHomeAxis(uint32_t now) {
  uint8_t axis = homeOrder_[homeIndex_];
  homeStarted_ = now;
  if ((hall_ & (1 << axis)) == 0) {
    startHomePhase(SEARCH);
    return;
  }
  int32_t joints[MOTOR_COUNT];
  motorsToJoints(steps_, joints);
  bool onReference = (homeWasHomed_ & (1 << axis)) != 0 && joints[axis] <= HALL_EDGE[axis] + HALL_MARGIN;
  startHomePhase(onReference ? BACKOFF : LEAVE);
}

// LEAVE y SEARCH van hacia la referencia; BACKOFF y CLEAR retroceden;
// APPROACH vuelve al mismo flanco, siempre desde el mismo lado. Solo SEARCH y
// CLEAR van rápido: las fases que miden cuánto falta para salir de un imán
// van lento, así la cota del ancho del imán no depende de la velocidad.
void Firmware::startHomePhase(HomePhase phase) {
  uint8_t axis = homeOrder_[homeIndex_];
  homePhase_ = phase;
  bool back = phase == BACKOFF || phase == CLEAR;
  bool fast = phase == SEARCH || phase == CLEAR;
  startDrive(axis, JOINT_MOTORS[axis], back ? 1 : -1, fast ? HOME_FAST : HOME_SLOW);
}

// Decide con los Hall de este poll; los pasos los da advanceJog.
void Firmware::advanceHoming(uint32_t now) {
  uint8_t axis = homeOrder_[homeIndex_];
  bool active = (hall_ & (1 << axis)) != 0;
  int32_t traveled = stepsToUnits(axis, jogSteps_);
  int32_t onMagnet = HALL_WIDTH[axis] + HALL_MARGIN;
  if (now - homeStarted_ > HOME_AXIS_MS) {
    abortHoming();
    sendError(ERR_MISSING, "ausente");
    return;
  }
  switch (homePhase_) {
    case LEAVE:
      if (!active) {
        startHomePhase(SEARCH);
      } else if (traveled > onMagnet) {
        abortHoming();
        sendError(ERR_STUCK, "trabado");
      }
      break;
    case SEARCH:
      if (active) {
        startHomePhase(BACKOFF);
      } else if (traveled > HOME_SEARCH_MAX[axis]) {
        abortHoming();
        sendError(ERR_MISSING, "ausente");
      }
      break;
    case BACKOFF:
      if (!active) {
        startHomePhase(CLEAR);
      } else if (traveled > onMagnet) {
        abortHoming();
        sendError(ERR_STUCK, "trabado");
      }
      break;
    case CLEAR:
      if (traveled >= HOME_BACKOFF) startHomePhase(APPROACH);
      break;
    case APPROACH:
      if (active) {
        finishHomeAxis();
      } else if (traveled > HOME_BACKOFF + onMagnet) {
        abortHoming();
        sendError(ERR_MISSING, "ausente");
      }
      break;
  }
}

// El flanco del Hall está en HALL_EDGE. J1 mueve M1 y M2 juntos, así que
// corre los dos: J2, que todavía no tiene referencia, no cambia. J2 se mide
// relativo a J1: M2 = M1 + los pasos de J2.
void Firmware::finishHomeAxis() {
  uint8_t axis = homeOrder_[homeIndex_];
  int32_t edge = unitsToSteps(axis, HALL_EDGE[axis]);
  if (axis == 0) {
    steps_[1] += edge - steps_[0];
    steps_[0] = edge;
  } else if (axis == 1) {
    steps_[1] = steps_[0] + edge;
  } else {
    steps_[axis] = edge;
  }
  homed_ |= static_cast<uint8_t>(1 << axis);
  homedNow_ |= static_cast<uint8_t>(1 << axis);
  char out[LINE_MAX];
  append(append(append(out, "EV HOMED "), static_cast<int32_t>(axis + 1)), "\n")[0] = '\0';
  hal_.write(out);
  if (++homeIndex_ < homeCount_) {
    startHomeAxis(hal_.millis());
  } else {
    motion_ = NONE;
    jogMotors_ = 0;
  }
}

// Sin declarar referencia: los ejes de este HOME vuelven a quedar sin ella.
void Firmware::abortHoming() {
  homed_ &= static_cast<uint8_t>(~homedNow_);
  homedNow_ = 0;
  motion_ = NONE;
  jogMotors_ = 0;
}

// SEG n ms q1 q2 q3 q4: llegar a esa configuración articular en ms
// milisegundos, interpolando lineal en articulaciones (D6). El OK sale cuando
// el segmento entró en la cola; con la cola llena se demora: es el control de
// flujo.
void Firmware::handleSegment(char* arguments) {
  int32_t number, ms, units[MOTOR_COUNT];
  char* numberText = nextField(&arguments);
  char* msText = nextField(&arguments);
  bool valid = numberText != 0 && parseUnsigned(numberText, &number) && number >= 1 && msText != 0 &&
               parseUnsigned(msText, &ms) && ms >= 1 && ms <= SEG_MS_MAX;
  for (uint8_t joint = 0; valid && joint < MOTOR_COUNT; ++joint) {
    char* text = nextField(&arguments);
    valid = text != 0 && parseSigned(text, &units[joint]) && units[joint] >= -SEG_UNITS_MAX &&
            units[joint] <= SEG_UNITS_MAX;
  }
  if (!valid || !noMoreFields(arguments)) {
    reject(ERR_ARGUMENTS, "argumentos");
    return;
  }
  if (!enabled_) {
    reject(ERR_DISABLED, "deshabilitado");
    return;
  }
  // Sin referencia, la URC no sabe dónde está el robot: no hay plan que valga.
  if (homed_ != 0x0F) {
    reject(ERR_REFERENCE, "referencia");
    return;
  }
  if (motion_ != NONE && motion_ != RUN) {
    reject(ERR_BUSY, "ocupado");
    return;
  }
  // La URC espera el OK de cada SEG antes de enviar el siguiente: si ya hay
  // uno retenido, otro más es un error de la URC.
  if (holding_) {
    reject(ERR_QUEUE, "cola");
    return;
  }
  // El segmento sale del destino del anterior o, con la cola vacía, de la
  // posición estimada, que es la que informa S y desde la que planifica la URC.
  int32_t from[MOTOR_COUNT];
  if (count_ != 0) {
    for (uint8_t joint = 0; joint < MOTOR_COUNT; ++joint) from[joint] = tail_[joint];
  } else {
    motorsToJoints(steps_, from);
  }
  // La URC planifica dentro de los límites de los motores (D45). Esto la
  // protege de un error; no reemplaza al planificador.
  if (!segmentWithinMotorSpeed(from, units, ms)) {
    reject(ERR_SPEED, "velocidad");
    return;
  }
  Segment segment;
  segment.number = number;
  segment.ms = static_cast<uint16_t>(ms);
  jointsToMotors(units, segment.target);
  for (uint8_t joint = 0; joint < MOTOR_COUNT; ++joint) tail_[joint] = units[joint];
  if (count_ < QUEUE_SIZE) {
    enqueue(segment);
    sendOk(number);
  } else {
    held_ = segment;
    holding_ = true;
  }
}

void Firmware::enqueue(const Segment& segment) {
  if (count_ == 0) {
    // Con la cola vacía, el segmento arranca ya, desde donde está el robot.
    motion_ = RUN;
    started_ = hal_.millis();
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) from_[motor] = steps_[motor];
  }
  queued(count_) = segment;
  ++count_;
}

Firmware::Segment& Firmware::queued(uint8_t index) { return queue_[(head_ + index) % QUEUE_SIZE]; }

// Frena, corta la corriente y pierde la referencia (D40): sin par, los
// motores pueden girar sin que el firmware cuente los pasos.
void Firmware::disable() {
  halt();
  enabled_ = false;
  homed_ = 0;
  hal_.enableDrivers(false);
}

void Firmware::stopJog() {
  if (motion_ != JOG) return;
  motion_ = NONE;
  jogMotors_ = 0;
  jogAccumulator_ = 0;
}

// STOP y el watchdog (D41): frena y conserva la referencia. El jog para en
// seco: a su velocidad baja no pierde pasos. Los segmentos frenan con rampa y
// la cola se vacía.
void Firmware::stop(uint32_t now) {
  stopJog();
  if (motion_ == HOMING) abortHoming();
  if (motion_ == RUN) startRamp(now);
}

// Parada inmediata: descarta la cola sin rampa.
void Firmware::halt() {
  stopJog();
  if (motion_ == HOMING) abortHoming();
  count_ = 0;
  holding_ = false;
  motion_ = NONE;
}

// Cada motor sigue en el sentido del segmento en ejecución y baja su
// velocidad en línea recta hasta cero. Todos tardan lo mismo, así el robot
// sigue la misma dirección en articulaciones. La rampa dura lo que necesita
// el motor más exigido para frenar con su aceleración máxima (D45).
void Firmware::startRamp(uint32_t now) {
  const Segment& segment = queued(0);
  int64_t delta[MOTOR_COUNT];
  // Si el redondeo dejó el segmento un poco por encima de la velocidad de un
  // motor (ROUNDING_UNITS), la rampa sale de esa velocidad: se estira la
  // duración hasta respetarla y la rampa no se alarga.
  int64_t ms = segment.ms;
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
    delta[motor] = segment.target[motor] - from_[motor];
    int64_t slowest = magnitude(delta[motor]) * 360 * 1000 /
                      (static_cast<int64_t>(MOTOR_MAX_SPEED[motor]) * STEPS_PER_REV);
    if (slowest > ms) ms = slowest;
  }
  // Frenar de v = delta / ms pasos por ms con la aceleración a lleva v / a ms.
  int64_t duration = 0;
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
    int64_t perMs = static_cast<int64_t>(MOTOR_MAX_ACCELERATION[motor]) * STEPS_PER_REV * ms;
    int64_t needed = (magnitude(delta[motor]) * 360 * 1000 * 1000 + perMs - 1) / perMs;
    if (needed > duration) duration = needed;
  }
  count_ = 0;
  holding_ = false;
  motion_ = NONE;
  if (duration == 0) return;
  // Frenando de v a cero en T, cada motor recorre v · T / 2.
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
    rampFrom_[motor] = steps_[motor];
    rampDistance_[motor] = static_cast<int32_t>(divideRounded64(delta[motor] * duration, 2 * ms));
  }
  rampMs_ = static_cast<int32_t>(duration);
  rampStarted_ = now;
  motion_ = STOPPING;
}

bool Firmware::moving() const { return motion_ != NONE; }

// Integra la velocidad con aritmética entera: cada vez que el acumulador
// junta una unidad de paso, emite un paso en cada motor del jog. La velocidad
// está en unidades del eje jogAxis_, y todos sus motores dan los mismos pasos.
// El homing mueve cada eje de la misma forma.
void Firmware::advanceJog(uint32_t now) {
  uint32_t elapsed = now - lastJog_;
  lastJog_ = now;
  if (motion_ != JOG && motion_ != HOMING) return;
  if (elapsed > JOG_MAX_ELAPSED_MS) elapsed = JOG_MAX_ELAPSED_MS;
  jogAccumulator_ += jogSpeed_ * STEPS_NUM[jogAxis_] * static_cast<int32_t>(elapsed);
  const int32_t threshold = STEPS_DEN[jogAxis_] * 1000;
  while (jogAccumulator_ >= threshold) {
    jogAccumulator_ -= threshold;
    ++jogSteps_;
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
      if (jogMotors_ & (1 << motor)) {
        hal_.step(motor, jogDirection_);
        steps_[motor] += jogDirection_;
      }
    }
  }
}

// Interpola lineal en pasos de motor, que es lineal en articulaciones porque
// el acople es lineal. Los tiempos los marca el reloj del firmware: cada
// segmento empieza cuando terminó el anterior, aunque la URC lo haya enviado
// tarde, así las demoras del enlace no se notan mientras quede cola.
void Firmware::advanceRun(uint32_t now) {
  while (count_ != 0) {
    const Segment& segment = queued(0);
    uint32_t elapsed = now - started_;
    if (elapsed < segment.ms) {
      int32_t target[MOTOR_COUNT];
      for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        int32_t delta = segment.target[motor] - from_[motor];
        target[motor] = from_[motor] + divideRounded(delta * static_cast<int32_t>(elapsed), segment.ms);
      }
      stepTo(target);
      return;
    }
    stepTo(segment.target);
    done_ = segment.number;
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) from_[motor] = segment.target[motor];
    started_ += segment.ms;
    head_ = static_cast<uint8_t>((head_ + 1) % QUEUE_SIZE);
    --count_;
    // Se liberó un lugar: entra el segmento retenido y sale su OK.
    if (holding_) {
      holding_ = false;
      enqueue(held_);
      sendOk(held_.number);
    }
  }
  // Sin más segmentos, el robot queda en el destino del último.
  motion_ = NONE;
}

// A t ms de empezar, la rampa recorrió d · t (2T − t) / T²: sale con la
// velocidad del segmento, 2d / T, y llega a cero en T.
void Firmware::advanceStopping(uint32_t now) {
  int64_t elapsed = now - rampStarted_;
  if (elapsed > rampMs_) elapsed = rampMs_;
  int64_t squared = static_cast<int64_t>(rampMs_) * rampMs_;
  int32_t target[MOTOR_COUNT];
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
    target[motor] = rampFrom_[motor] + static_cast<int32_t>(divideRounded64(
                                           rampDistance_[motor] * elapsed * (2 * rampMs_ - elapsed), squared));
  }
  stepTo(target);
  if (elapsed == rampMs_) motion_ = NONE;
}

// Da los pasos que faltan para que cada motor llegue a `target`.
void Firmware::stepTo(const int32_t target[MOTOR_COUNT]) {
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
    while (steps_[motor] != target[motor]) {
      int8_t direction = steps_[motor] < target[motor] ? 1 : -1;
      hal_.step(motor, direction);
      steps_[motor] += direction;
    }
  }
}

// S modo referenciados J1 J2 J3 J4 hall libres último
void Firmware::sendStatus() {
  char out[96];  // con holgura: en uso normal la línea no pasa de 64 bytes
  const char* mode = !enabled_          ? "OFF"
                     : motion_ == JOG     ? "JOG"
                     : motion_ == HOMING  ? "HOMING"
                     : moving()           ? "RUN"
                                          : "IDLE";
  char* end = append(append(append(out, "S "), mode), " ");
  end = append(end, static_cast<int32_t>(homed_));
  // Posición estimada por pasos, en unidades del protocolo.
  int32_t joints[MOTOR_COUNT];
  motorsToJoints(steps_, joints);
  for (uint8_t joint = 0; joint < MOTOR_COUNT; ++joint) end = append(append(end, " "), joints[joint]);
  end = append(append(end, " "), static_cast<int32_t>(hal_.readHall()));
  end = append(append(end, " "), static_cast<int32_t>(QUEUE_SIZE - count_));
  end = append(append(append(end, " "), done_), "\n");
  *end = '\0';
  hal_.write(out);
}

void Firmware::sendOk(int32_t number) {
  char out[LINE_MAX];
  append(append(append(out, "OK "), number), "\n")[0] = '\0';
  hal_.write(out);
}

void Firmware::sendError(int32_t code, const char* text) {
  char out[LINE_MAX];
  char* end = append(append(append(append(out, "ERR "), code), " "), text);
  append(end, "\n")[0] = '\0';
  hal_.write(out);
}

// Rechaza una línea de la URC. Con segmentos en ejecución, además frena con
// rampa, como STOP: la URC cancela el resto del tramo ante cualquier ERR, así
// que lo encolado termina en un punto intermedio del plan, quizás a plena
// velocidad.
void Firmware::reject(int32_t code, const char* text) {
  sendError(code, text);
  if (motion_ == RUN) startRamp(hal_.millis());
}

}  // namespace scara
