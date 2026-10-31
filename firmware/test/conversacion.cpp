// Prueba del firmware por su protocolo, en la PC (seam 1 de la spec #2).
// Uso: conversacion ARCHIVO...
// Cada archivo es una conversación scara/1 con una capa de hardware falsa;
// el formato está en firmware/test/conversaciones/LEEME.md.
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include "../firmware.h"
#include "../transmission.h"

namespace {

// Imanes de la planta falsa, en unidades del protocolo: cada Hall se activa
// cerca de los dos extremos de su articulación (D10). Coinciden con los de
// Webots (tools/generate_world.py) y con HALL_EDGE del firmware.
const long MAGNET_LOW[scara::MOTOR_COUNT] = {-13000, -13000, -14500, 300};
const long MAGNET_HIGH[scara::MOTOR_COUNT] = {13000, 13000, 14500, 11700};

class FakeHal : public scara::Hal {
public:
  FakeHal() : now(0), enabled(true), magnets(false) {
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) {
      steps[i] = 0;
      pose[i] = 0;
      stuck[i] = -1;
    }
  }
  uint32_t millis() { return now; }
  void step(uint8_t motor, int8_t direction) { steps[motor] += direction; }
  void enableDrivers(bool on) { enabled = on; }
  // Sin "! iman", los Hall no se activan nunca.
  uint8_t readHall() {
    uint8_t bits = 0;
    int32_t motors[scara::MOTOR_COUNT], joints[scara::MOTOR_COUNT];
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) motors[i] = static_cast<int32_t>(steps[i]);
    scara::motorsToJoints(motors, joints);
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) {
      long position = pose[i] + joints[i];
      bool active = magnets && (position <= MAGNET_LOW[i] || position >= MAGNET_HIGH[i]);
      if (stuck[i] >= 0) active = stuck[i] == 1;
      if (active) bits |= static_cast<uint8_t>(1 << i);
    }
    return bits;
  }
  int readByte() {
    if (input.empty()) return -1;
    int byte = static_cast<unsigned char>(input.front());
    input.pop_front();
    return byte;
  }
  void write(const char* text) { output += text; }

  uint32_t now;
  long steps[scara::MOTOR_COUNT];
  bool enabled;  // arranca en true: el firmware tiene que cortarlos al arrancar
  bool magnets;                   // "! iman": los Hall siguen a la geometría
  long pose[scara::MOTOR_COUNT];  // pose real al arrancar, en unidades del protocolo
  int stuck[scara::MOTOR_COUNT];  // -1 libre, 0 trabado inactivo, 1 trabado activo
  std::deque<char> input;
  std::string output;
};

std::vector<std::string> fields(const std::string& line) {
  std::vector<std::string> result;
  std::istringstream stream(line);
  std::string field;
  while (stream >> field) result.push_back(field);
  return result;
}

// '*' acepta cualquier campo.
bool matches(const std::string& expected, const std::string& actual) {
  std::vector<std::string> want = fields(expected), got = fields(actual);
  if (want.size() != got.size()) return false;
  for (size_t i = 0; i < want.size(); ++i) {
    if (want[i] != "*" && want[i] != got[i]) return false;
  }
  return true;
}

bool isStatus(const std::string& line) { return line.compare(0, 2, "S ") == 0; }

class Conversation {
public:
  Conversation(const std::string& path) : path_(path), number_(0), firmware_(new scara::Firmware(hal_)) {}

  bool run() {
    std::ifstream file(path_.c_str());
    if (!file) return fail("no se pudo abrir");
    firmware_->begin();
    std::string line;
    while (std::getline(file, line)) {
      ++number_;
      if (!line.empty() && line[line.size() - 1] == '\r') line.erase(line.size() - 1);
      if (line.empty() || line[0] == '#') continue;
      std::string body = line.size() > 2 ? line.substr(2) : "";
      bool ok;
      switch (line[0]) {
        case '>': ok = send(body); break;
        case '<': ok = expect(body); break;
        case '+': ok = advance(std::atol(body.c_str()), false); break;
        case '~': ok = advance(std::atol(body.c_str()), true); break;
        case '=': ok = checkSteps(body); break;
        case '!': ok = plant(body); break;
        default: ok = fail("renglón desconocido: " + line);
      }
      if (!ok) return false;
    }
    collect();
    for (size_t i = 0; i < pending_.size(); ++i) {
      if (!isStatus(pending_[i])) return fail("la UCI envió algo no esperado: " + pending_[i]);
    }
    return true;
  }

private:
  bool fail(const std::string& message) {
    std::fprintf(stderr, "%s:%d: %s\n", path_.c_str(), number_, message.c_str());
    return false;
  }

  // Separa la salida en líneas y verifica el largo máximo del protocolo.
  void collect() {
    size_t end;
    while ((end = hal_.output.find('\n')) != std::string::npos) {
      std::string line = hal_.output.substr(0, end);
      hal_.output.erase(0, end + 1);
      if (line.size() + 1 > scara::LINE_MAX) tooLong_.push_back(line);
      pending_.push_back(line);
    }
  }

  // "\r" en el archivo representa un retorno de carro real.
  bool send(std::string text) {
    size_t at;
    while ((at = text.find("\\r")) != std::string::npos) text.replace(at, 2, "\r");
    text += '\n';
    for (size_t i = 0; i < text.size(); ++i) hal_.input.push_back(text[i]);
    firmware_->poll();
    return true;
  }

  // Las líneas S periódicas que no se esperan se ignoran.
  bool expect(const std::string& expected) {
    collect();
    if (!tooLong_.empty()) return fail("línea de más de 64 bytes: " + tooLong_.front());
    std::string skipped;
    while (!pending_.empty()) {
      std::string actual = pending_.front();
      pending_.pop_front();
      if (matches(expected, actual)) return true;
      if (!isStatus(actual)) return fail("se esperaba «" + expected + "» y llegó «" + actual + "»");
      skipped = actual;
    }
    return fail("se esperaba «" + expected + "» y la UCI no envió nada más" +
                (skipped.empty() ? "" : " (último S: «" + skipped + "»)"));
  }

  // "~ N" avanza como "+ N", pero la URC envía PING cada 250 ms, como lo
  // hace siempre: para movimientos que duran más que el watchdog.
  bool advance(long milliseconds, bool pinging) {
    if (milliseconds <= 0) return fail("el avance debe ser positivo");
    for (long i = 1; i <= milliseconds; ++i) {
      ++hal_.now;
      if (pinging && i % 250 == 0) {
        const char ping[] = "PING\n";
        for (const char* c = ping; *c; ++c) hal_.input.push_back(*c);
      }
      firmware_->poll();
    }
    return true;
  }

  // La planta, desde afuera del firmware:
  //   "! reinicio": la UCI se reinicia sin que se corte el enlace. Los motores
  //     conservan los pasos dados; el firmware arranca de cero y envía BOOT.
  //   "! iman J1 J2 J3 J4": los Hall siguen a la geometría, con el robot en
  //     esa pose real al arrancar (unidades del protocolo).
  //   "! hall j activo|inactivo|libre": traba el Hall de Jj (falla F3).
  bool plant(const std::string& body) {
    std::vector<std::string> items = fields(body);
    if (items.size() == 1 && items[0] == "reinicio") {
      firmware_.reset(new scara::Firmware(hal_));
      firmware_->begin();
      return true;
    }
    if (items.size() == 5 && items[0] == "iman") {
      hal_.magnets = true;
      for (int i = 0; i < scara::MOTOR_COUNT; ++i) hal_.pose[i] = std::atol(items[i + 1].c_str());
      return true;
    }
    if (items.size() == 3 && items[0] == "hall" && items[1].size() == 1 && items[1][0] >= '1' && items[1][0] <= '4') {
      int joint = items[1][0] - '1';
      if (items[2] == "activo") hal_.stuck[joint] = 1;
      else if (items[2] == "inactivo") hal_.stuck[joint] = 0;
      else if (items[2] == "libre") hal_.stuck[joint] = -1;
      else return fail("se esperaba activo, inactivo o libre");
      return true;
    }
    return fail("renglón ! desconocido: " + body);
  }

  // "= M1 400 M2 400 M3 0 M4 0": pasos netos emitidos a cada motor.
  // "EN 1" o "EN 0": drivers con corriente o sin ella.
  bool checkSteps(const std::string& body) {
    std::vector<std::string> items = fields(body);
    if (items.size() % 2 != 0) return fail("se esperan pares motor valor");
    for (size_t i = 0; i < items.size(); i += 2) {
      if (items[i] == "EN") {
        if (items[i + 1] != (hal_.enabled ? "1" : "0")) {
          return fail(std::string("los drivers están ") + (hal_.enabled ? "con" : "sin") + " corriente");
        }
        continue;
      }
      int motor = items[i].size() == 2 && items[i][0] == 'M' ? items[i][1] - '1' : -1;
      if (motor < 0 || motor >= scara::MOTOR_COUNT) return fail("motor desconocido: " + items[i]);
      long want = std::atol(items[i + 1].c_str());
      if (hal_.steps[motor] != want) {
        std::ostringstream message;
        message << items[i] << " dio " << hal_.steps[motor] << " pasos y se esperaban " << want;
        return fail(message.str());
      }
    }
    return true;
  }

  std::string path_;
  int number_;
  FakeHal hal_;
  std::unique_ptr<scara::Firmware> firmware_;
  std::deque<std::string> pending_;
  std::vector<std::string> tooLong_;
};

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    std::fprintf(stderr, "uso: %s CONVERSACION...\n", argv[0]);
    return 2;
  }
  int failures = 0;
  for (int i = 1; i < argc; ++i) {
    Conversation conversation(argv[i]);
    if (!conversation.run()) ++failures;
  }
  return failures == 0 ? 0 : 1;
}
