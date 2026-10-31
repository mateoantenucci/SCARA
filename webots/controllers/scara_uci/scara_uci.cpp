// Controlador de Webots que hace de UCI: aloja el firmware compartido
// (firmware/, ADR 0002) con una capa de hardware de simulación.
//   - Enlace: cliente TCP hacia la URC (D1), con reintentos.
//   - Reloj: tiempo simulado (D26).
//   - Planta simulada, transmisión N1 (D8): cuenta los pasos de M1..M4 y los
//     convierte en posiciones de J1..J4 con el microstepping, las poleas 4:1,
//     el acople M1/M2 y el ACME. Todavía sin pérdida de pasos (N2, #15).
//   - Sensores Hall: imanes y KY-003 del modelo; se activan por distancia (D10, D57).
//   - Arranque cerca de la pose de reposo, con un desvío al azar (D11).
// Argumentos (controllerArgs): --host 127.0.0.1 --port 9000 --desvio 10
// (grados; 0 arranca justo en la pose de reposo, como usan los ensayos).
#include <webots/Emitter.hpp>
#include <webots/Motor.hpp>
#include <webots/Node.hpp>
#include <webots/Receiver.hpp>
#include <webots/Supervisor.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET Socket;
const Socket NO_SOCKET = INVALID_SOCKET;
#else
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int Socket;
const Socket NO_SOCKET = -1;
#endif

#include "config.h"
#include "firmware.h"

namespace {

// --- Enlace TCP no bloqueante: la simulación nunca espera a la red -------

class TcpClient {
public:
  TcpClient(const std::string& host, int port) : host_(host), port_(port), socket_(NO_SOCKET),
      connected_(false), announced_(false) {
#ifdef _WIN32
    WSADATA data;
    WSAStartup(MAKEWORD(2, 2), &data);
#endif
    retryAt_ = Clock::now();
  }

  ~TcpClient() {
    close();
#ifdef _WIN32
    WSACleanup();
#endif
  }

  bool connected() const { return connected_; }

  // Avanza la conexión, recibe lo disponible y envía lo pendiente.
  void service() {
    if (socket_ == NO_SOCKET) {
      if (Clock::now() >= retryAt_) startConnect();
      return;
    }
    if (!connected_) {
      finishConnect();
      return;
    }
    char chunk[256];
    for (;;) {
      int count = static_cast<int>(recv(socket_, chunk, sizeof chunk, 0));
      if (count > 0) {
        input_.append(chunk, count);
        continue;
      }
      if (count == 0) {
        drop("la URC cerró la conexión");
        return;
      }
      if (!wouldBlock()) {
        drop("error al recibir");
        return;
      }
      break;
    }
    flush();
  }

  int readByte() {
    if (input_.empty()) return -1;
    int byte = static_cast<unsigned char>(input_[0]);
    input_.erase(0, 1);
    return byte;
  }

  // Sin conexión, lo escrito se pierde, como en un puerto serie sin nadie.
  void write(const char* text) {
    if (connected_) output_ += text;
  }

  void flush() {
    while (connected_ && !output_.empty()) {
      int count = static_cast<int>(send(socket_, output_.data(), static_cast<int>(output_.size()), SEND_FLAGS));
      if (count > 0) {
        output_.erase(0, count);
      } else {
        if (!wouldBlock()) drop("error al enviar");
        return;
      }
    }
  }

private:
  typedef std::chrono::steady_clock Clock;
#ifdef MSG_NOSIGNAL
  static const int SEND_FLAGS = MSG_NOSIGNAL;
#else
  static const int SEND_FLAGS = 0;
#endif
  static const int RETRY_MS = 1000;

  static bool wouldBlock() {
#ifdef _WIN32
    int error = WSAGetLastError();
    return error == WSAEWOULDBLOCK || error == WSAEINPROGRESS;
#else
    return errno == EWOULDBLOCK || errno == EAGAIN || errno == EINPROGRESS;
#endif
  }

  void startConnect() {
    socket_ = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (socket_ == NO_SOCKET) {
      retryLater();
      return;
    }
#ifdef _WIN32
    u_long nonBlocking = 1;
    ioctlsocket(socket_, FIONBIO, &nonBlocking);
#else
    fcntl(socket_, F_SETFL, fcntl(socket_, F_GETFL, 0) | O_NONBLOCK);
#ifdef SO_NOSIGPIPE
    int one = 1;
    setsockopt(socket_, SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof one);
#endif
#endif
    int noDelay = 1;
    setsockopt(socket_, IPPROTO_TCP, TCP_NODELAY, reinterpret_cast<const char*>(&noDelay), sizeof noDelay);
    sockaddr_in address;
    std::memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_port = htons(static_cast<unsigned short>(port_));
    if (inet_pton(AF_INET, host_.c_str(), &address.sin_addr) != 1) {
      std::printf("UCI: dirección IPv4 inválida: %s\n", host_.c_str());
      std::fflush(stdout);
      std::exit(EXIT_FAILURE);
    }
    if (::connect(socket_, reinterpret_cast<sockaddr*>(&address), sizeof address) == 0) {
      connectedNow();
    } else if (!wouldBlock()) {
      retryLater();
    }
  }

  void finishConnect() {
    fd_set writable, failed;
    FD_ZERO(&writable);
    FD_ZERO(&failed);
    FD_SET(socket_, &writable);
    FD_SET(socket_, &failed);
    timeval immediate = {0, 0};
    if (select(static_cast<int>(socket_) + 1, 0, &writable, &failed, &immediate) <= 0) return;
    int error = 0;
    socklen_t size = sizeof error;
    getsockopt(socket_, SOL_SOCKET, SO_ERROR, reinterpret_cast<char*>(&error), &size);
    if (error == 0 && FD_ISSET(socket_, &writable) && !FD_ISSET(socket_, &failed)) {
      connectedNow();
    } else {
      retryLater();
    }
  }

  void connectedNow() {
    connected_ = true;
    std::printf("UCI: conectada a la URC en %s:%d\n", host_.c_str(), port_);
    std::fflush(stdout);
  }

  void retryLater() {
    if (!announced_) {
      std::printf("UCI: esperando a la URC en %s:%d; reintento cada %d ms\n", host_.c_str(), port_, RETRY_MS);
      std::fflush(stdout);
      announced_ = true;
    }
    close();
    retryAt_ = Clock::now() + std::chrono::milliseconds(RETRY_MS);
  }

  void drop(const char* reason) {
    std::printf("UCI: enlace perdido (%s)\n", reason);
    std::fflush(stdout);
    announced_ = false;
    retryLater();
  }

  void close() {
    if (socket_ != NO_SOCKET) {
#ifdef _WIN32
      closesocket(socket_);
#else
      ::close(socket_);
#endif
    }
    socket_ = NO_SOCKET;
    connected_ = false;
    input_.clear();
    output_.clear();
  }

  std::string host_;
  int port_;
  Socket socket_;
  bool connected_;
  bool announced_;
  Clock::time_point retryAt_;
  std::string input_, output_;
};

// --- Planta simulada: transmisión N1, sin pérdida de pasos ---------------

// Hechos del hardware simulado. La mecánica coincide con la que supone el
// firmware, pero se escribe aparte: la planta es el robot, no lo que el
// firmware cree. El microstepping, en cambio, es uno solo (config.h, D44): en
// el robot real son las llaves DIP de los TB6600.
const double STEPS_PER_REV = scara::STEPS_PER_REV;  // NEMA de 200 pasos y el microstepping de config.h
const double PULLEY_RATIO = 4.0;                    // poleas 2GT 20:80
const double LEAD_M = 0.008;               // ACME de 8 mm por vuelta
const double TWO_PI = 6.283185307179586;
// Pose de reposo (D30), en radianes y metros: la simulación arranca cerca.
const double REST[scara::MOTOR_COUNT] = {0.0, 0.0, 0.0, 0.12};
const char* const JOINT_BODIES[scara::MOTOR_COUNT] = {"ARM", "FOREARM", "WRIST", "TOOL"};

class Plant {
public:
  // Arranca cerca de la pose de reposo: J1–J3 con un desvío al azar de hasta
  // deviation grados, como un robot real que nadie dejó exacto (D11). J4,
  // abajo. El firmware arranca igual sin referencia.
  Plant(webots::Supervisor& robot, double deviation) {
    webots::Node* self = robot.getSelf();
    std::mt19937 random(static_cast<unsigned>(std::random_device()()));
    std::uniform_real_distribution<double> spread(-deviation, deviation);
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) {
      steps_[i] = 0;
      start_[i] = REST[i] + (i < 3 ? spread(random) * TWO_PI / 360.0 : 0.0);
      char name[16];
      std::snprintf(name, sizeof name, "j%d_motor", i + 1);
      motors_[i] = robot.getMotor(name);
      // El cuerpo que mueve cada articulación cuelga de su joint.
      webots::Node* body = self ? self->getFromProtoDef(JOINT_BODIES[i]) : 0;
      webots::Node* joint = body ? body->getParentNode() : 0;
      if (joint) {
        joint->setJointPosition(start_[i]);
      } else {
        std::printf("UCI: no se encontró la articulación J%d; queda en la pose del mundo\n", i + 1);
      }
      // Sensores Hall (D10, D57): un KY-003 (Receiver) y dos imanes (Emitter
      // con su alcance) por articulación, en SCARA.proto.
      std::snprintf(name, sizeof name, "hall%d", i + 1);
      webots::Receiver* sensor = robot.getReceiver(name);
      sensors_[i] = sensor ? robot.getFromDevice(sensor) : 0;
      for (int end = 0; end < 2; ++end) {
        std::snprintf(name, sizeof name, "iman%d_%s", i + 1, end == 0 ? "inicio" : "fin");
        webots::Emitter* magnet = robot.getEmitter(name);
        magnets_[2 * i + end] = magnet ? robot.getFromDevice(magnet) : 0;
        reach_[2 * i + end] = magnet ? magnet->getRange() : 0.0;
      }
      if (!sensors_[i] || !magnets_[2 * i] || !magnets_[2 * i + 1]) {
        std::printf("UCI: faltan el sensor o los imanes de J%d en el modelo; su Hall no se activa\n", i + 1);
      }
    }
    std::printf("UCI: arranca a %.2f°, %.2f°, %.2f° de la pose de reposo\n", (start_[0] - REST[0]) * 360 / TWO_PI,
                (start_[1] - REST[1]) * 360 / TWO_PI, (start_[2] - REST[2]) * 360 / TWO_PI);
    std::fflush(stdout);
    hall_ = 0;
    apply();
  }

  void step(uint8_t motor, int8_t direction) { steps_[motor] += direction; }

  // J1 = θM1/4, J2 = (θM2 − θM1)/4, J3 = θM3/4, J4 = 8 mm · vueltas de M4.
  void apply() {
    double turns[scara::MOTOR_COUNT];
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) turns[i] = steps_[i] / STEPS_PER_REV;
    double joints[scara::MOTOR_COUNT] = {
        TWO_PI * turns[0] / PULLEY_RATIO,
        TWO_PI * (turns[1] - turns[0]) / PULLEY_RATIO,
        TWO_PI * turns[2] / PULLEY_RATIO,
        LEAD_M * turns[3],
    };
    // Los topes mecánicos frenan la articulación aunque el motor siga dando
    // pasos; el firmware no se entera (no hay encoders).
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) {
      if (!motors_[i]) continue;
      double target = start_[i] + joints[i];
      double low = motors_[i]->getMinPosition(), high = motors_[i]->getMaxPosition();
      if (low < high) target = std::max(low, std::min(high, target));  // 0 y 0: sin límites
      motors_[i]->setPosition(target);
    }
  }

  // El KY-003 se activa si uno de sus imanes está más cerca que su alcance.
  // Es la regla del Emitter de radio de Webots, pero Webots no entrega
  // paquetes entre dispositivos del mismo robot: la planta mide la distancia
  // entre las posiciones de los dos nodos en el mundo (D57). Sale de la
  // geometría del modelo, no de la posición de las articulaciones.
  void sense() {
    hall_ = 0;
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) {
      if (!sensors_[i]) continue;
      const double* sensor = sensors_[i]->getPosition();
      for (int end = 0; end < 2; ++end) {
        webots::Node* magnet = magnets_[2 * i + end];
        if (!magnet) continue;
        const double* position = magnet->getPosition();
        double dx = position[0] - sensor[0], dy = position[1] - sensor[1], dz = position[2] - sensor[2];
        if (std::sqrt(dx * dx + dy * dy + dz * dz) <= reach_[2 * i + end]) hall_ |= static_cast<uint8_t>(1 << i);
      }
    }
  }

  uint8_t hall() const { return hall_; }

private:
  long steps_[scara::MOTOR_COUNT];
  double start_[scara::MOTOR_COUNT];  // pose real al arrancar, en radianes y metros
  webots::Motor* motors_[scara::MOTOR_COUNT];
  webots::Node* sensors_[scara::MOTOR_COUNT];
  webots::Node* magnets_[2 * scara::MOTOR_COUNT];
  double reach_[2 * scara::MOTOR_COUNT];  // alcance de cada imán, en metros
  uint8_t hall_;
};

// --- Capa de hardware de simulación ------------------------------------

class WebotsHal : public scara::Hal {
public:
  WebotsHal(webots::Supervisor& robot, Plant& plant, TcpClient& link)
      : robot_(robot), plant_(plant), link_(link) {}
  uint32_t millis() { return static_cast<uint32_t>(std::llround(robot_.getTime() * 1000.0)); }
  void step(uint8_t motor, int8_t direction) { plant_.step(motor, direction); }
  // La planta todavía no modela el driver sin corriente: J4 no cae (falla F2,
  // con las fallas). El firmware igual no da pasos sin corriente.
  void enableDrivers(bool on) {
    std::printf("UCI: drivers %s\n", on ? "con corriente" : "sin corriente");
    std::fflush(stdout);
  }
  uint8_t readHall() { return plant_.hall(); }
  int readByte() { return link_.readByte(); }
  void write(const char* text) { link_.write(text); }

private:
  webots::Supervisor& robot_;
  Plant& plant_;
  TcpClient& link_;
};

}  // namespace

int main(int argc, char** argv) {
  std::string host = "127.0.0.1";
  int port = 9000;
  double deviation = 10.0;
  for (int i = 1; i + 1 < argc; i += 2) {
    if (std::strcmp(argv[i], "--host") == 0) host = argv[i + 1];
    else if (std::strcmp(argv[i], "--port") == 0) port = std::atoi(argv[i + 1]);
    else if (std::strcmp(argv[i], "--desvio") == 0) deviation = std::atof(argv[i + 1]);
  }
  webots::Supervisor robot;
  const int timestep = static_cast<int>(robot.getBasicTimeStep());
  Plant plant(robot, deviation);
  TcpClient link(host, port);
  WebotsHal hal(robot, plant, link);
  scara::Firmware firmware(hal);
  bool booted = false;
  while (robot.step(timestep) != -1) {
    link.service();
    plant.sense();
    // Como el UNO, que se reinicia cuando se abre el puerto USB, el firmware
    // arranca con la primera conexión y anuncia BOOT. Las reconexiones
    // siguientes no lo reinician: la URC saluda con HELLO.
    if (!booted && link.connected()) {
      firmware.begin();
      booted = true;
    }
    if (booted) firmware.poll();
    link.flush();
    plant.apply();
  }
  return 0;
}
