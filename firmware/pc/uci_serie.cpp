// UCI de PC por puerto serie: el núcleo del firmware con una capa de hardware
// POSIX que hace de Arduino UNO detrás de un puerto serie virtual (un PTY).
// Sirve para ensayar el camino serie + socat hacia la URC sin la placa (#16):
// socat abre este puerto con la misma receta que abre el USB del UNO.
//
// Uso: uci_serie
//   Crea el PTY e informa su nombre por stderr («puerto serie en /dev/pty0»).
// Imita al UNO por USB (D36, D43): abrir el puerto lo reinicia, así que el
// firmware arranca de cero y envía BOOT cuando llega lo primero por el puerto;
// lo que llega antes del primer LF se pierde, como en el bootloader. Cerrar el
// puerto apaga el firmware. Entonces crea un PTY nuevo y anuncia su nombre:
// en Cygwin (MSYS2) un PTY cerrado no se puede volver a abrir.
// No tiene planta: los pasos no mueven nada y los Hall nunca se activan. La
// posición que informa es la estimada por pasos del núcleo.
// Ver docs/ARDUINO_UNO.md.
#define _GNU_SOURCE 1  // posix_openpt y compañía con -std=c++11 en glibc y Cygwin

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "../firmware.h"

namespace {

class PtyHal : public scara::Hal {
public:
  PtyHal() : fd_(-1), open_(false), start_(now()), pendingLength_(0), pendingNext_(0) {}

  // Crea un PTY, y cierra el anterior; devuelve el nombre que abre socat, o 0.
  const char* create() {
    if (fd_ >= 0) ::close(fd_);
    fd_ = posix_openpt(O_RDWR | O_NOCTTY);
    if (fd_ < 0 || grantpt(fd_) != 0 || unlockpt(fd_) != 0) return 0;
    if (fcntl(fd_, F_SETFL, O_NONBLOCK) != 0) return 0;
    return ptsname(fd_);
  }

  // Espera a que alguien abra el puerto y envíe una línea. Lo que siga a ese
  // primer LF queda para el firmware.
  void waitForOpen() {
    for (;;) {
      usleep(10000);
      char chunk[64];
      ssize_t count = ::read(fd_, chunk, sizeof chunk);
      if (count <= 0) continue;  // nadie lo abrió todavía (EAGAIN o EIO)
      const char* lf = static_cast<const char*>(memchr(chunk, '\n', static_cast<size_t>(count)));
      if (lf == 0) continue;
      size_t rest = static_cast<size_t>(chunk + count - (lf + 1));
      memcpy(pending_, lf + 1, rest);
      pendingLength_ = rest;
      pendingNext_ = 0;
      open_ = true;
      return;
    }
  }

  bool open() const { return open_; }

  // Hasta 1 ms esperando datos: el núcleo hace poll() a ~1 kHz.
  void wait() {
    pollfd entry = {fd_, POLLIN, 0};
    ::poll(&entry, 1, 1);
  }

  uint32_t millis() { return static_cast<uint32_t>(now() - start_); }
  void step(uint8_t, int8_t) {}
  void enableDrivers(bool) {}
  uint8_t readHall() { return 0; }

  int readByte() {
    if (pendingNext_ < pendingLength_) return static_cast<unsigned char>(pending_[pendingNext_++]);
    if (!open_) return -1;
    unsigned char byte;
    ssize_t count = ::read(fd_, &byte, 1);
    if (count == 1) return byte;
    if (count < 0 && (errno == EAGAIN || errno == EINTR)) return -1;
    open_ = false;  // 0 o EIO: socat cerró el puerto
    return -1;
  }

  // Si nadie lee el puerto, lo que no entra se descarta: el puente USB del UNO
  // hace lo mismo, y el firmware no se traba. El cierre lo detecta readByte().
  void write(const char* text) {
    size_t left = strlen(text);
    while (left > 0 && open_) {
      ssize_t count = ::write(fd_, text, left);
      if (count > 0) {
        text += count;
        left -= static_cast<size_t>(count);
      } else if (count < 0 && errno == EINTR) {
        continue;
      } else {
        return;
      }
    }
  }

private:
  static uint64_t now() {
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<uint64_t>(ts.tv_sec) * 1000u + static_cast<uint64_t>(ts.tv_nsec) / 1000000u;
  }

  int fd_;
  bool open_;
  uint64_t start_;
  char pending_[64];
  size_t pendingLength_;
  size_t pendingNext_;
};

}  // namespace

int main(int argc, char** argv) {
  if (argc != 1) {
    fprintf(stderr, "uso: %s\n", argv[0]);
    return 2;
  }
  PtyHal hal;
  for (;;) {
    const char* name = hal.create();
    if (name == 0) {
      fprintf(stderr, "uci_serie: no se pudo crear el PTY: %s\n", strerror(errno));
      return 1;
    }
    fprintf(stderr, "uci_serie: puerto serie en %s\n", name);
    hal.waitForOpen();
    // Un firmware nuevo por apertura: como el UNO, arranca de cero.
    scara::Firmware* firmware = new scara::Firmware(hal);
    firmware->begin();
    fprintf(stderr, "uci_serie: puerto abierto, BOOT\n");
    while (hal.open()) {
      hal.wait();
      firmware->poll();
    }
    delete firmware;
    fprintf(stderr, "uci_serie: puerto cerrado\n");
  }
}
