// Prueba del firmware por su protocolo, en la PC (seam 1 de la spec #2).
// Uso: conversacion ARCHIVO...
// Cada archivo es una conversación scara/1 con una capa de hardware falsa;
// el formato está en firmware/test/conversaciones/LEEME.md.
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "../firmware.h"

namespace {

class FakeHal : public scara::Hal {
public:
  FakeHal() : now(0) {
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) steps[i] = 0;
  }
  uint32_t millis() { return now; }
  void step(uint8_t motor, int8_t direction) { steps[motor] += direction; }
  uint8_t readHall() { return 0; }  // los Hall a voluntad llegan con el homing (#8)
  int readByte() {
    if (input.empty()) return -1;
    int byte = static_cast<unsigned char>(input.front());
    input.pop_front();
    return byte;
  }
  void write(const char* text) { output += text; }

  uint32_t now;
  long steps[scara::MOTOR_COUNT];
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
  Conversation(const std::string& path) : path_(path), number_(0), firmware_(hal_) {}

  bool run() {
    std::ifstream file(path_.c_str());
    if (!file) return fail("no se pudo abrir");
    firmware_.begin();
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
        case '+': ok = advance(std::atol(body.c_str())); break;
        case '=': ok = checkSteps(body); break;
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
    firmware_.poll();
    return true;
  }

  // Las líneas S periódicas que no se esperan se ignoran.
  bool expect(const std::string& expected) {
    collect();
    if (!tooLong_.empty()) return fail("línea de más de 64 bytes: " + tooLong_.front());
    while (!pending_.empty()) {
      std::string actual = pending_.front();
      pending_.pop_front();
      if (matches(expected, actual)) return true;
      if (!isStatus(actual)) return fail("se esperaba «" + expected + "» y llegó «" + actual + "»");
    }
    return fail("se esperaba «" + expected + "» y la UCI no envió nada más");
  }

  bool advance(long milliseconds) {
    if (milliseconds <= 0) return fail("el avance debe ser positivo");
    for (long i = 0; i < milliseconds; ++i) {
      ++hal_.now;
      firmware_.poll();
    }
    return true;
  }

  // "= M1 400 M2 400 M3 0 M4 0": pasos netos emitidos a cada motor.
  bool checkSteps(const std::string& body) {
    std::vector<std::string> items = fields(body);
    if (items.size() % 2 != 0) return fail("se esperan pares motor valor");
    for (size_t i = 0; i < items.size(); i += 2) {
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
  scara::Firmware firmware_;
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
