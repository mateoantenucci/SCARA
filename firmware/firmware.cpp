#include "firmware.h"

#include <string.h>

namespace scara {

namespace {

// Pasos de motor por unidad del protocolo, como fracción entera (ADR 0003).
// J1–J3: 1600 pasos por vuelta (1/8, D9) y polea 4:1, así que 6400 pasos son
// 36000 centésimas de grado: 8/45. J4: ACME de 8 mm por vuelta, así que 1600
// pasos son 800 centésimas de mm: 2/1.
const int32_t STEPS_NUM[MOTOR_COUNT] = {8, 8, 8, 2};
const int32_t STEPS_DEN[MOTOR_COUNT] = {45, 45, 45, 1};
// Motores que mueve el jog de cada articulación. J1 mueve M1 y M2 juntos para
// que J2 relativo no cambie: J1 = θM1/4 y J2 = (θM2 − θM1)/4.
const uint8_t JOG_MOTORS[MOTOR_COUNT] = {0x03, 0x02, 0x04, 0x08};
// Pose de reposo (D30): brazo estirado y J4 abajo, en unidades del protocolo.
const int32_t REST[MOTOR_COUNT] = {0, 0, 0, 12000};
// Una pausa larga entre llamadas no se recupera de golpe.
const uint32_t JOG_MAX_ELAPSED_MS = 100;

int32_t divideRounded(int32_t value, int32_t divisor) {
  return value >= 0 ? (value + divisor / 2) / divisor : -((-value + divisor / 2) / divisor);
}

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

}  // namespace

Firmware::Firmware(Hal& hal)
    : hal_(hal), length_(0), overflow_(false), homed_(0), jogJoint_(-1), jogDirection_(0),
      jogSpeed_(0), jogAccumulator_(0), lastJog_(0), lastStatus_(0), lastMessage_(0) {
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) steps_[motor] = 0;
}

void Firmware::begin() {
  uint32_t now = hal_.millis();
  lastJog_ = lastStatus_ = lastMessage_ = now;
  char out[LINE_MAX];
  char* end = append(append(append(append(out, "BOOT "), PROTOCOL), " "), FIRMWARE_VERSION);
  append(end, "\n")[0] = '\0';
  hal_.write(out);
}

void Firmware::poll() {
  uint32_t now = hal_.millis();
  // Primero el movimiento hasta ahora con la orden vigente; después las
  // órdenes nuevas, que rigen desde este instante.
  advanceJog(now);
  for (int byte = hal_.readByte(); byte >= 0; byte = hal_.readByte()) {
    if (byte == '\n') lastMessage_ = now;
    receive(byte);
  }
  if (jogJoint_ >= 0 && now - lastMessage_ > WATCHDOG_MS) {
    stopJog();
    sendError(4, "watchdog");
  }
  if (now - lastStatus_ >= STATUS_PERIOD_MS) {
    lastStatus_ = now;
    sendStatus();
  }
}

void Firmware::receive(int byte) {
  if (byte == '\r') return;
  if (byte == '\n') {
    if (overflow_) {
      overflow_ = false;
      length_ = 0;
      sendError(3, "largo");
      return;
    }
    line_[length_] = '\0';
    length_ = 0;
    handle(line_);
    return;
  }
  // Hasta LINE_MAX - 1 caracteres más el LF.
  if (length_ >= LINE_MAX - 1) {
    overflow_ = true;
    return;
  }
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
  bool known = strcmp(command, "HELLO") == 0 || strcmp(command, "PING") == 0 ||
               strcmp(command, "STATUS") == 0 || strcmp(command, "ZERO") == 0;
  if (!known) {
    sendError(1, "comando");
  } else if (!noMoreFields(cursor)) {
    sendError(2, "argumentos");
  } else if (strcmp(command, "HELLO") == 0) {
    char out[LINE_MAX];
    char* end = append(append(append(append(out, "HI "), PROTOCOL), " "), FIRMWARE_VERSION);
    append(end, "\n")[0] = '\0';
    hal_.write(out);
  } else if (strcmp(command, "STATUS") == 0) {
    sendStatus();
  } else if (strcmp(command, "ZERO") == 0) {
    // Declara que el robot está en la pose de reposo.
    if (jogJoint_ >= 0) {
      sendError(5, "ocupado");
      return;
    }
    int32_t motors[MOTOR_COUNT];
    for (uint8_t joint = 0; joint < MOTOR_COUNT; ++joint) {
      motors[joint] = REST[joint] * STEPS_NUM[joint] / STEPS_DEN[joint];
    }
    steps_[0] = motors[0];
    steps_[1] = motors[0] + motors[1];
    steps_[2] = motors[2];
    steps_[3] = motors[3];
    homed_ = 0x0F;
  }
  // PING solo renueva el watchdog.
}

// JOG j ± vel | JOG STOP
void Firmware::handleJog(char* arguments) {
  char* first = nextField(&arguments);
  if (first != 0 && strcmp(first, "STOP") == 0 && noMoreFields(arguments)) {
    stopJog();
    return;
  }
  char* sign = nextField(&arguments);
  char* speedText = nextField(&arguments);
  int32_t joint, speed;
  bool valid = first != 0 && sign != 0 && speedText != 0 && noMoreFields(arguments) &&
               parseUnsigned(first, &joint) && joint >= 1 && joint <= MOTOR_COUNT &&
               (strcmp(sign, "+") == 0 || strcmp(sign, "-") == 0) &&
               parseUnsigned(speedText, &speed) && speed >= 1 && speed <= JOG_SPEED_MAX;
  if (!valid) {
    sendError(2, "argumentos");
    return;
  }
  jogJoint_ = static_cast<int8_t>(joint - 1);
  jogDirection_ = sign[0] == '+' ? 1 : -1;
  jogSpeed_ = speed;
  jogAccumulator_ = 0;
}

void Firmware::stopJog() {
  jogJoint_ = -1;
  jogAccumulator_ = 0;
}

// Integra la velocidad con aritmética entera: cada vez que el acumulador
// junta una unidad de paso, emite un paso en cada motor del jog.
void Firmware::advanceJog(uint32_t now) {
  uint32_t elapsed = now - lastJog_;
  lastJog_ = now;
  if (jogJoint_ < 0) return;
  if (elapsed > JOG_MAX_ELAPSED_MS) elapsed = JOG_MAX_ELAPSED_MS;
  jogAccumulator_ += jogSpeed_ * STEPS_NUM[jogJoint_] * static_cast<int32_t>(elapsed);
  const int32_t threshold = STEPS_DEN[jogJoint_] * 1000;
  while (jogAccumulator_ >= threshold) {
    jogAccumulator_ -= threshold;
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
      if (JOG_MOTORS[jogJoint_] & (1 << motor)) {
        hal_.step(motor, jogDirection_);
        steps_[motor] += jogDirection_;
      }
    }
  }
}

// Posición estimada por pasos de la articulación 0..3, en unidades del protocolo.
int32_t Firmware::estimated(uint8_t joint) const {
  int32_t motor = joint == 1 ? steps_[1] - steps_[0] : steps_[joint];
  return divideRounded(motor * STEPS_DEN[joint], STEPS_NUM[joint]);
}

// S modo referenciados J1 J2 J3 J4 hall libres último
void Firmware::sendStatus() {
  char out[96];  // con holgura: en uso normal la línea no pasa de 64 bytes
  char* end = append(append(append(out, "S "), jogJoint_ >= 0 ? "JOG" : "IDLE"), " ");
  end = append(end, static_cast<int32_t>(homed_));
  for (uint8_t joint = 0; joint < MOTOR_COUNT; ++joint) end = append(append(end, " "), estimated(joint));
  end = append(append(end, " "), static_cast<int32_t>(hal_.readHall()));
  end = append(append(end, " "), static_cast<int32_t>(QUEUE_SIZE));
  end = append(end, " 0\n");
  *end = '\0';
  hal_.write(out);
}

void Firmware::sendError(int32_t code, const char* text) {
  char out[LINE_MAX];
  char* end = append(append(append(append(out, "ERR "), code), " "), text);
  append(end, "\n")[0] = '\0';
  hal_.write(out);
}

}  // namespace scara
