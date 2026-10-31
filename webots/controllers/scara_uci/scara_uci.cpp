// Controlador de Webots que hace de UCI: aloja el firmware compartido
// (firmware/, ADR 0002) con una capa de hardware de simulación.
//   - Enlace: cliente TCP hacia la URC (D1), con reintentos.
//   - Reloj: tiempo simulado (D26).
//   - Planta simulada, transmisión N1 y par N2 (D8, D64): cuenta los pasos de
//     M1..M4; cada rotor los sigue con el par que tiene a su velocidad
//     (stepper.h) y pierde pasos si la carga o la aceleración lo superan. Los
//     rotores se convierten en posiciones de J1..J4 con las poleas 4:1, el
//     acople M1/M2 y el ACME.
//   - Sensores Hall: imanes y KY-003 del modelo; se activan por distancia (D10, D57).
//   - Arranque cerca de la pose de reposo, con un desvío al azar (D11).
//   - Canal de instrumentación (ADR 0004): la verdad del simulador y las fallas
//     F1–F5, la carga y la recarga, por otro puerto.
// Argumentos (controllerArgs): --host 127.0.0.1 --port 9000 --sim-port 9001 --desvio 10
// (grados; 0 arranca justo en la pose de reposo, como usan los ensayos).
#include <webots/Emitter.hpp>
#include <webots/Motor.hpp>
#include <webots/Node.hpp>
#include <webots/PositionSensor.hpp>
#include <webots/Receiver.hpp>
#include <webots/Supervisor.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
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
#include "stepper.h"

namespace {

// --- Enlace TCP no bloqueante: la simulación nunca espera a la red -------

class TcpClient {
public:
  TcpClient(const std::string& host, int port, const char* label = "UCI") : host_(host), port_(port), label_(label),
      socket_(NO_SOCKET), connected_(false), announced_(false) {
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
    std::printf("%s: conectada a la URC en %s:%d\n", label_, host_.c_str(), port_);
    std::fflush(stdout);
  }

  void retryLater() {
    if (!announced_) {
      std::printf("%s: esperando a la URC en %s:%d; reintento cada %d ms\n", label_, host_.c_str(), port_, RETRY_MS);
      std::fflush(stdout);
      announced_ = true;
    }
    close();
    retryAt_ = Clock::now() + std::chrono::milliseconds(RETRY_MS);
  }

  void drop(const char* reason) {
    std::printf("%s: enlace perdido (%s)\n", label_, reason);
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
  const char* label_;  // en los mensajes de la consola
  Socket socket_;
  bool connected_;
  bool announced_;
  Clock::time_point retryAt_;
  std::string input_, output_;
};

// --- Planta simulada: transmisión N1 y par de los motores N2 -------------

// Hechos del hardware simulado. La mecánica coincide con la que supone el
// firmware, pero se escribe aparte: la planta es el robot, no lo que el
// firmware cree. El microstepping, en cambio, es uno solo (config.h, D44): en
// el robot real son las llaves DIP de los TB6600.
const double STEPS_PER_REV = scara::STEPS_PER_REV;  // NEMA de 200 pasos y el microstepping de config.h
const double TWO_PI = 6.283185307179586;
// Radianes o metros de cada articulación por pulso de su motor: poleas 2GT
// 20:80 en J1–J3 y ACME de 8 mm por vuelta en J4 (los de stepper.h).
const double UNIT[scara::MOTOR_COUNT] = {TWO_PI / STEPS_PER_REV / plant::PULLEY_RATIO,
                                         TWO_PI / STEPS_PER_REV / plant::PULLEY_RATIO,
                                         TWO_PI / STEPS_PER_REV / plant::PULLEY_RATIO, plant::LEAD / STEPS_PER_REV};
// Fracción de la distancia al rotor que la articulación corrige en cada paso.
const double TRACKING = 0.5;
// Pasos de Webots en que la fuerza de una articulación llega al máximo al
// volver la corriente: 0,1 s con 2 ms.
const int RAMP_TICKS = 50;
// Distancia a la que la articulación se queda de sus topes: 1/8 de paso
// completo en J1–J3 y un cuarto en J4.
const double STOP_MARGIN[scara::MOTOR_COUNT] = {1e-4, 1e-4, 1e-4, 1e-5};
// Pose de reposo (D30), en radianes y metros: la simulación arranca cerca.
const double REST[scara::MOTOR_COUNT] = {0.0, 0.0, 0.0, 0.12};
const char* const JOINT_BODIES[scara::MOTOR_COUNT] = {"ARM", "FOREARM", "WRIST", "TOOL"};

class Plant {
public:
  // Arranca cerca de la pose de reposo: J1–J3 con un desvío al azar de hasta
  // deviation grados, como un robot real que nadie dejó exacto (D11). J4,
  // abajo. El firmware arranca igual sin referencia.
  Plant(webots::Supervisor& robot, double deviation)
      : rotors_{plant::Stepper(plant::MOTORS[0], scara::STEPS_PER_REV),
                plant::Stepper(plant::MOTORS[1], scara::STEPS_PER_REV),
                plant::Stepper(plant::MOTORS[2], scara::STEPS_PER_REV),
                plant::Stepper(plant::MOTORS[3], scara::STEPS_PER_REV)} {
    webots::Node* self = robot.getSelf();
    // La carga de la herramienta (toolMass, en kg) la cambia el banco de ensayo.
    tool_ = self ? self->getField("toolMass") : 0;
    std::mt19937 random(static_cast<unsigned>(std::random_device()()));
    std::uniform_real_distribution<double> spread(-deviation, deviation);
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) {
      steps_[i] = 0;
      current_[i] = 1.0;
      ramp_[i] = 0;
      start_[i] = REST[i] + (i < 3 ? spread(random) * TWO_PI / 360.0 : 0.0);
      char name[16];
      std::snprintf(name, sizeof name, "j%d_motor", i + 1);
      motors_[i] = robot.getMotor(name);
      effort_[i] = !motors_[i] ? 0.0 : motors_[i]->getType() == webots::Motor::LINEAR ? motors_[i]->getMaxForce()
                                                                                       : motors_[i]->getMaxTorque();
      // La verdad del simulador, solo para el canal de instrumentación (D2).
      std::snprintf(name, sizeof name, "j%d_sensor", i + 1);
      truth_[i] = robot.getPositionSensor(name);
      if (truth_[i]) truth_[i]->enable(static_cast<int>(robot.getBasicTimeStep()));
      stuck_[i] = -1;
      // El cuerpo que mueve cada articulación cuelga de su joint.
      webots::Node* body = self ? self->getFromProtoDef(JOINT_BODIES[i]) : 0;
      webots::Node* joint = body ? body->getParentNode() : 0;
      if (joint) {
        joint->setJointPosition(start_[i]);
      } else {
        std::printf("UCI: no se encontró la articulación J%d; queda en la pose del mundo\n", i + 1);
      }
      // La articulación va a la posición del rotor con control de velocidad
      // y sin límite de aceleración: la dinámica ya la puso el rotor (D64).
      // Va después de setJointPosition, que deja el motor en control de posición.
      if (motors_[i]) {
        motors_[i]->setPosition(INFINITY);
        motors_[i]->setVelocity(0.0);
        motors_[i]->setAcceleration(-1);
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
    drivers_ = false;
    failed_ = 0;
    powered_ = 0;
    apply(0.0);
  }

  // Un motor sin corriente no avanza con los pulsos: esos pasos se pierden.
  void step(uint8_t motor, int8_t direction) {
    if (powered_ & (1 << motor)) steps_[motor] += direction;
  }

  // ENABLE común de los drivers (D18) y, aparte, drivers que el banco de
  // ensayo deja sin corriente (falla F2).
  void setDrivers(bool on) {
    drivers_ = on;
    updatePower();
  }
  void setFailed(uint8_t motors) {
    failed_ = motors;
    updatePower();
  }
  uint8_t powered() const { return powered_; }
  uint8_t failed() const { return failed_; }

  // Cada `dt` segundos, después de que el firmware dio sus pasos: cada rotor
  // sigue a su estator con el par que tiene (stepper.h), y cada articulación
  // va adonde la llevan los rotores, con la transmisión:
  // J1 = θM1/4, J2 = (θM2 − θM1)/4, J3 = θM3/4, J4 = 8 mm · vueltas de M4.
  // Sin corriente, el motor no hace fuerza: el eje queda libre, y J4 cae por
  // su peso (falla F2).
  void apply(double dt) {
    double tool = tool_ ? tool_->getSFFloat() : 0.0;
    for (int i = 0; dt > 0 && i < scara::MOTOR_COUNT; ++i) {
      if (powered_ & (1 << i)) rotors_[i].advance(steps_[i], dt, plant::loadOf(i, tool), current_[i]);
    }
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) {
      if (!motors_[i]) continue;
      bool free = (powered_ & (1 << i)) == 0;
      // Al volver la corriente, la fuerza sube en rampa: si el eje descansa en
      // su tope (J4 abajo), ODE le aplica de más en el primer paso que el motor
      // lo saca de ahí, y lo haría saltar milímetros.
      if (!free && ramp_[i] < RAMP_TICKS) ++ramp_[i];
      double effort = free ? 0.0 : effort_[i] * ramp_[i] / RAMP_TICKS;
      if (motors_[i]->getType() == webots::Motor::LINEAR) {
        motors_[i]->setAvailableForce(effort);
      } else {
        motors_[i]->setAvailableTorque(effort);
      }
      if (free) continue;
      // En orden: si el tope frena a J1, J2 (relativo) cambia con M2.
      double target = start_[i] + joint(i);
      double low = motors_[i]->getMinPosition(), high = motors_[i]->getMaxPosition();
      if (low < high && (target < low || target > high)) {  // 0 y 0: sin límites
        // El tope mecánico frena la articulación y el rotor, aunque el motor
        // siga recibiendo pulsos; el firmware no se entera (no hay encoders).
        target = std::max(low, std::min(high, target));
        double pulses = (target - start_[i]) / UNIT[i];
        rotors_[i].stopAt(i == 1 ? rotors_[0].position() + pulses : pulses);
      }
      // Sin apoyarse en el tope: un motor de ODE que empuja contra él vibra.
      // Ahí la velocidad del rotor ya no se suma: llevaría el eje al tope.
      double feed = jointSpeed(i);
      if (low < high && (target < low + STOP_MARGIN[i] || target > high - STOP_MARGIN[i])) {
        target = std::max(low + STOP_MARGIN[i], std::min(high - STOP_MARGIN[i], target));
        feed = 0.0;
      }
      // Control de velocidad hacia el rotor: su velocidad, más la mitad de lo
      // que falta por paso de Webots. Corregir todo en un paso hace rebotar a
      // J4 contra su tope.
      double now = physical(i), speed = 0.0;
      if (dt > 0 && !std::isnan(now)) speed = feed + TRACKING * (target - now) / dt;
      double fastest = motors_[i]->getMaxVelocity();
      motors_[i]->setVelocity(std::max(-fastest, std::min(fastest, speed)));
    }
  }

  // Corriente del driver del motor `motor`, como fracción de la nominal
  // (falla F1: un TB6600 regulado de menos tiene menos par).
  void setCurrent(int motor, double fraction) { current_[motor] = fraction; }
  double current(int motor) const { return current_[motor]; }
  // Pasos completos que el motor se corrió de los pulsos que recibió: la
  // verdad del simulador, para el banco de ensayo. Positivo: el eje quedó
  // más adelante de lo que contó el firmware.
  long lost(int motor) const { return -rotors_[motor].lost() / (scara::STEPS_PER_REV / plant::FULL_STEPS_PER_REV); }

  // Posición física simulada de Jj+1, en radianes o metros.
  double physical(int joint) const { return truth_[joint] ? truth_[joint]->getValue() : 0.0; }

  // Hall trabado (falla F3): -1 libre, 0 inactivo, 1 activo.
  void setStuck(int joint, int state) { stuck_[joint] = state; }
  int stuck(int joint) const { return stuck_[joint]; }

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
      if (stuck_[i] == 0) hall_ &= static_cast<uint8_t>(~(1 << i));
      if (stuck_[i] == 1) hall_ |= static_cast<uint8_t>(1 << i);
    }
  }

  uint8_t hall() const { return hall_; }

private:
  // Desplazamiento de la articulación `j` desde el arranque, en radianes o
  // metros, según dónde están los rotores. J2 es relativo: M2 menos M1.
  double joint(int j) const {
    double pulses = rotors_[j].position() - (j == 1 ? rotors_[0].position() : 0.0);
    return pulses * UNIT[j];
  }

  // Velocidad de la articulación `j` que dan los rotores, en rad/s o m/s.
  double jointSpeed(int j) const {
    double speed = rotors_[j].speed() - (j == 1 ? rotors_[0].speed() : 0.0);  // rad/s de los ejes de los motores
    return speed * STEPS_PER_REV / TWO_PI * UNIT[j];
  }

  // Al volver la corriente, el motor retiene el eje donde quedó: los pasos
  // cuentan desde ahí. Lo que se movió sin corriente, el firmware no lo sabe.
  void updatePower() {
    uint8_t now = drivers_ ? static_cast<uint8_t>(0x0F & ~failed_) : 0;
    uint8_t gained = static_cast<uint8_t>(now & ~powered_);
    powered_ = now;
    if (gained == 0) return;
    for (int i = 0; i < scara::MOTOR_COUNT; ++i) {
      if (gained & (1 << i)) {
        rotors_[i].reset(steps_[i]);
        ramp_[i] = 0;
      }
    }
    for (int j = 0; j < scara::MOTOR_COUNT; ++j) {
      // J2 depende de M1 y M2 (el acople).
      uint8_t motors = j == 1 ? 0x03 : static_cast<uint8_t>(1 << j);
      if ((gained & motors) != 0 && truth_[j]) start_[j] = physical(j) - joint(j);
    }
  }

  bool drivers_;
  uint8_t failed_;
  uint8_t powered_;
  double effort_[scara::MOTOR_COUNT];  // fuerza o par máximo de cada articulación de Webots
  plant::Stepper rotors_[scara::MOTOR_COUNT];
  double current_[scara::MOTOR_COUNT];  // fracción de la corriente nominal de cada driver (F1)
  int ramp_[scara::MOTOR_COUNT];        // pasos de Webots desde que el motor recuperó la corriente
  webots::Field* tool_;
  webots::PositionSensor* truth_[scara::MOTOR_COUNT];
  int stuck_[scara::MOTOR_COUNT];
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
      : robot_(robot), plant_(plant), link_(link), cut_(false) {}
  uint32_t millis() { return static_cast<uint32_t>(std::llround(robot_.getTime() * 1000.0)); }
  void step(uint8_t motor, int8_t direction) { plant_.step(motor, direction); }
  void enableDrivers(bool on) {
    plant_.setDrivers(on);
    std::printf("UCI: drivers %s\n", on ? "con corriente" : "sin corriente");
    std::fflush(stdout);
  }
  uint8_t readHall() { return plant_.hall(); }
  // Con el enlace cortado (falla F4), lo que llega se pierde y lo que sale no
  // llega: como un cable desenchufado. La conexión TCP sigue abierta.
  int readByte() {
    int byte = link_.readByte();
    while (cut_ && byte >= 0) byte = link_.readByte();
    return byte;
  }
  void write(const char* text) {
    if (!cut_) link_.write(text);
  }
  void cut(bool on) { cut_ = on; }
  bool cut() const { return cut_; }

private:
  webots::Supervisor& robot_;
  Plant& plant_;
  TcpClient& link_;
  bool cut_;
};

// --- Canal de instrumentación (ADR 0004, D59) -----------------------------

// Lo que solo existe en la simulación, por otro puerto (9001) y con otro
// protocolo de texto, scara-sim/1. El robot real no lo tiene: la URC funciona
// igual sin él. Hacia la URC, 20 veces por segundo:
//   SIM J1 J2 J3 J4 hall corriente f2 f3 f4 carga i1 i2 i3 i4 p1 p2 p3 p4
// con la posición física simulada en unidades de scara/1, los Hall que ve el
// firmware, la máscara de motores con corriente, las fallas (f3: un carácter
// por articulación, "-" libre, "A" trabado activo, "I" inactivo), la carga
// en gramos, la corriente de cada driver en % de la nominal (F1) y los pasos
// completos que perdió cada motor (D64). Órdenes de la URC: F1 m porcentaje,
// F2 0|1, F3 j activo|inactivo|libre, F4 0|1, F5, CARGA gramos, RECARGA.
class Bench {
public:
  Bench(webots::Supervisor& robot, Plant& plant, WebotsHal& hal, TcpClient& link, bool enabled)
      : robot_(robot), plant_(plant), hal_(hal), link_(link), enabled_(enabled), greeted_(false), reboot_(false),
        lastState_(-1.0) {
    webots::Node* self = robot.getSelf();
    load_ = self ? self->getField("toolMass") : 0;
  }

  // Atiende las órdenes y envía el estado. Devuelve true si hay que reiniciar
  // el firmware (F5). Con --sim-port 0 no hay canal: los ensayos que no lo
  // usan no se conectan a la URC de otro.
  bool service() {
    if (!enabled_) return false;
    link_.service();
    if (!link_.connected()) {
      greeted_ = false;
      return false;
    }
    if (!greeted_) {
      link_.write("SIM HELLO scara-sim/1\n");
      greeted_ = true;
    }
    for (int byte = link_.readByte(); byte >= 0; byte = link_.readByte()) {
      if (byte == '\n') {
        handle(line_);
        line_.clear();
      } else if (byte != '\r' && line_.size() < 64) {
        line_ += static_cast<char>(byte);
      }
    }
    if (robot_.getTime() - lastState_ >= 0.05) {
      lastState_ = robot_.getTime();
      sendState();
    }
    link_.flush();
    bool reboot = reboot_;
    reboot_ = false;
    return reboot;
  }

private:
  // sscanf lee un prefijo: %n dice cuánto leyó, y la orden vale solo si
  // ocupa la línea entera ("F2 1x" no es "F2 1").
  void handle(const std::string& line) {
    char argument[16] = "";
    int joint = 0, used = -1;
    long value = 0;
    const int length = static_cast<int>(line.size());
    auto whole = [&](int fields, int expected) {
      bool ok = fields == expected && used == length;
      used = -1;
      return ok;
    };
    if (whole(std::sscanf(line.c_str(), "F1 %d %ld%n", &joint, &value, &used), 2) && joint >= 1 && joint <= 4 &&
        value >= 10 && value <= 100) {
      plant_.setCurrent(joint - 1, value / 100.0);  // aquí `joint` es el motor Mm
    } else if (whole(std::sscanf(line.c_str(), "F2 %ld%n", &value, &used), 1) && (value == 0 || value == 1)) {
      plant_.setFailed(value ? 0x08 : 0x00);  // el driver de M4: J4 cae
    } else if (whole(std::sscanf(line.c_str(), "F3 %d %15s%n", &joint, argument, &used), 2) && joint >= 1 &&
               joint <= 4 && (std::strcmp(argument, "activo") == 0 || std::strcmp(argument, "inactivo") == 0 ||
                              std::strcmp(argument, "libre") == 0)) {
      plant_.setStuck(joint - 1, argument[0] == 'a' ? 1 : argument[0] == 'i' ? 0 : -1);
    } else if (whole(std::sscanf(line.c_str(), "F4 %ld%n", &value, &used), 1) && (value == 0 || value == 1)) {
      hal_.cut(value == 1);
    } else if (line == "F5") {
      reboot_ = true;
    } else if (whole(std::sscanf(line.c_str(), "CARGA %ld%n", &value, &used), 1) && value >= 0 && value <= 5000) {
      if (load_) load_->setSFFloat(value / 1000.0);
    } else if (line == "RECARGA") {
      std::printf("SIM: recarga del mundo pedida por la URC\n");
      std::fflush(stdout);
      robot_.worldReload();
    } else {
      link_.write("SIM ERR orden\n");
    }
  }

  long percent(int motor) const { return std::lround(plant_.current(motor) * 100.0); }

  void sendState() {
    char out[192], stuck[5];
    long units[scara::MOTOR_COUNT];
    for (int j = 0; j < scara::MOTOR_COUNT; ++j) {
      // Radianes → centésimas de grado; metros → centésimas de mm.
      double scale = j < 3 ? 36000.0 / TWO_PI : 100000.0;
      units[j] = std::lround(plant_.physical(j) * scale);
      stuck[j] = plant_.stuck(j) == 1 ? 'A' : plant_.stuck(j) == 0 ? 'I' : '-';
    }
    stuck[4] = '\0';
    long grams = load_ ? std::lround(load_->getSFFloat() * 1000.0) : 0;
    std::snprintf(out, sizeof out, "SIM %ld %ld %ld %ld %d %d %d %s %d %ld %ld %ld %ld %ld %ld %ld %ld %ld\n",
                  units[0], units[1], units[2], units[3], plant_.hall(), plant_.powered(), plant_.failed() ? 1 : 0,
                  stuck, hal_.cut() ? 1 : 0, grams, percent(0), percent(1), percent(2), percent(3), plant_.lost(0),
                  plant_.lost(1), plant_.lost(2), plant_.lost(3));
    link_.write(out);
  }

  webots::Supervisor& robot_;
  Plant& plant_;
  WebotsHal& hal_;
  TcpClient& link_;
  webots::Field* load_;  // toolMass del SCARA.proto, en kg
  bool enabled_;
  bool greeted_;
  bool reboot_;
  double lastState_;
  std::string line_;
};

}  // namespace

int main(int argc, char** argv) {
  std::string host = "127.0.0.1";
  int port = 9000;
  int simPort = 9001;
  double deviation = 10.0;
  for (int i = 1; i + 1 < argc; i += 2) {
    if (std::strcmp(argv[i], "--host") == 0) host = argv[i + 1];
    else if (std::strcmp(argv[i], "--port") == 0) port = std::atoi(argv[i + 1]);
    else if (std::strcmp(argv[i], "--sim-port") == 0) simPort = std::atoi(argv[i + 1]);
    else if (std::strcmp(argv[i], "--desvio") == 0) deviation = std::atof(argv[i + 1]);
  }
  webots::Supervisor robot;
  const int timestep = static_cast<int>(robot.getBasicTimeStep());
  Plant plant(robot, deviation);
  TcpClient link(host, port);
  WebotsHal hal(robot, plant, link);
  TcpClient simLink(host, simPort, "SIM");
  Bench bench(robot, plant, hal, simLink, simPort != 0);
  std::unique_ptr<scara::Firmware> firmware(new scara::Firmware(hal));
  bool booted = false;
  while (robot.step(timestep) != -1) {
    link.service();
    plant.sense();
    // Reinicio de la UCI pedido por el banco de ensayo (falla F5): el
    // firmware vuelve a arrancar y anuncia BOOT; los motores no se mueven.
    if (bench.service() && booted) {
      firmware.reset(new scara::Firmware(hal));
      firmware->begin();
    }
    // Como el UNO, que se reinicia cuando se abre el puerto USB, el firmware
    // arranca con la primera conexión y anuncia BOOT. Las reconexiones
    // siguientes no lo reinician: la URC saluda con HELLO.
    if (!booted && link.connected()) {
      firmware->begin();
      booted = true;
    }
    if (booted) firmware->poll();
    link.flush();
    plant.apply(timestep / 1000.0);
  }
  return 0;
}
