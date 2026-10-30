// Controlador de Webots que hace de UCI: aloja el firmware compartido
// (firmware/, ADR 0002) con una capa de hardware de simulación.
//   - Enlace: cliente TCP hacia la URC (D1), con reintentos.
//   - Reloj: tiempo simulado (D26).
//   - Planta simulada mínima: cuenta los pasos de M1..M4 y los convierte en
//     posiciones de J1..J4 con la transmisión y el acople M1/M2 (D8, N1 sin
//     pérdida de pasos todavía).
// Argumentos (controllerArgs): --host 127.0.0.1 --port 9000
#include <webots/Motor.hpp>
#include <webots/Node.hpp>
#include <webots/Supervisor.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
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

// --- Planta simulada mínima (N1 sin pérdida de pasos) --------------------

// Hechos del hardware simulado. Coinciden con los que supone el firmware,
// pero son independientes: la planta es el robot, no lo que el firmware cree.
const double STEPS_PER_REV = 200.0 * 8.0;  // NEMA de 200 pasos, TB6600 a 1/8 (D9)
const double PULLEY_RATIO = 4.0;           // poleas 2GT 20:80
const double LEAD_M = 0.008;               // ACME de 8 mm por vuelta
const double TWO_PI = 6.283185307179586;
// Pose inicial de la simulación: la pose de reposo (D30), en radianes y metros.
const double REST[scara::MOTOR_COUNT] = {0.0, 0.0, 0.0, 0.12};
const char* const JOINT_BODIES[scara::MOTOR_COUNT] = {"ARM", "FOREARM", "WRIST", "TOOL"};

class Plant {
public:
  explicit Plant(webots::Supervisor& robot) {
    webots::Node* self = robot.getSelf();
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) {
      steps_[i] = 0;
      char name[16];
      std::snprintf(name, sizeof name, "j%d_motor", i + 1);
      motors_[i] = robot.getMotor(name);
      // El cuerpo que mueve cada articulación cuelga de su joint.
      webots::Node* body = self ? self->getFromProtoDef(JOINT_BODIES[i]) : 0;
      webots::Node* joint = body ? body->getParentNode() : 0;
      if (joint) {
        joint->setJointPosition(REST[i]);
      } else {
        std::printf("UCI: no se encontró la articulación J%d; queda en la pose del mundo\n", i + 1);
      }
    }
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
      double target = REST[i] + joints[i];
      double low = motors_[i]->getMinPosition(), high = motors_[i]->getMaxPosition();
      if (low < high) target = std::max(low, std::min(high, target));  // 0 y 0: sin límites
      motors_[i]->setPosition(target);
    }
  }

private:
  long steps_[scara::MOTOR_COUNT];
  webots::Motor* motors_[scara::MOTOR_COUNT];
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
  uint8_t readHall() { return 0; }  // los Hall llegan con el homing (#8)
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
  for (int i = 1; i + 1 < argc; i += 2) {
    if (std::strcmp(argv[i], "--host") == 0) host = argv[i + 1];
    else if (std::strcmp(argv[i], "--port") == 0) port = std::atoi(argv[i + 1]);
  }
  webots::Supervisor robot;
  const int timestep = static_cast<int>(robot.getBasicTimeStep());
  Plant plant(robot);
  TcpClient link(host, port);
  WebotsHal hal(robot, plant, link);
  scara::Firmware firmware(hal);
  bool booted = false;
  while (robot.step(timestep) != -1) {
    link.service();
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
