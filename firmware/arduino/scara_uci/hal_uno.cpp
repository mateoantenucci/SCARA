#include "hal_uno.h"

#include <avr/interrupt.h>

#include "pulsos.h"

namespace scara {

namespace {

const uint8_t MASKS = 1 << MOTOR_COUNT;

StepPulser pulser;
// Todos los STEP comparten un puerto (PORTD) y todos los DIR otro (PORTC): la
// interrupción los escribe de una vez y los pulsos de M1 y M2 salen juntos.
// Las tablas traducen una máscara de motores (bit n = motor n) a los bits de
// su puerto, para no recorrer los motores dentro de la interrupción.
volatile uint8_t* stepOut;
volatile uint8_t* dirOut;
uint8_t stepPort[MASKS];
uint8_t dirPort[MASKS];

}  // namespace

void HalUno::begin() {
  // ENA en alto deja al TB6600 sin corriente: se fija antes de hacerlo salida.
  digitalWrite(PIN_ENABLE, HIGH);
  pinMode(PIN_ENABLE, OUTPUT);
  stepOut = portOutputRegister(digitalPinToPort(PIN_STEP[0]));
  dirOut = portOutputRegister(digitalPinToPort(PIN_DIR[0]));
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
    digitalWrite(PIN_STEP[motor], LOW);
    digitalWrite(PIN_DIR[motor], LOW);
    pinMode(PIN_STEP[motor], OUTPUT);
    pinMode(PIN_DIR[motor], OUTPUT);
    // El KY-003 tira a masa con el imán cerca; el pull-up interno asegura el alto.
    pinMode(PIN_HALL[motor], INPUT_PULLUP);
  }
  for (uint8_t mask = 0; mask < MASKS; ++mask) {
    stepPort[mask] = dirPort[mask] = 0;
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
      if ((mask & (1 << motor)) == 0) continue;
      stepPort[mask] |= digitalPinToBitMask(PIN_STEP[motor]);
      dirPort[mask] |= digitalPinToBitMask(PIN_DIR[motor]);
    }
  }
  Serial.begin(SERIAL_BAUD);
  // Timer1 en CTC, sin prescaler: una interrupción cada 1/TICK_HZ s.
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = _BV(WGM12) | _BV(CS10);
  TCNT1 = 0;
  OCR1A = F_CPU / TICK_HZ - 1;
  TIMSK1 = _BV(OCIE1A);
  interrupts();
}

uint32_t HalUno::millis() { return ::millis(); }

// Si el motor ya tiene la cola llena, espera a que la interrupción la vacíe:
// el núcleo se atrasa, pero ningún paso contado se deja de dar.
void HalUno::step(uint8_t motor, int8_t direction) {
  for (;;) {
    noInterrupts();
    bool queued = pulser.push(motor, direction);
    interrupts();
    if (queued) return;
  }
}

// TB6600 con cátodo común (ENA- a masa): ENA+ en alto corta la corriente.
void HalUno::enableDrivers(bool on) { digitalWrite(PIN_ENABLE, on ? LOW : HIGH); }

uint8_t HalUno::readHall() {
  uint8_t active = 0;
  for (uint8_t joint = 0; joint < MOTOR_COUNT; ++joint) {
    if (digitalRead(PIN_HALL[joint]) == LOW) active |= static_cast<uint8_t>(1 << joint);
  }
  return active;
}

int HalUno::readByte() { return Serial.read(); }

void HalUno::write(const char* text) { Serial.write(text); }

}  // namespace scara

// Sin pasos pendientes, la interrupción sale enseguida sin tocar los puertos.
ISR(TIMER1_COMPA_vect) {
  using namespace scara;
  if (!pulser.tick()) return;
  // DIR antes que STEP; el generador nunca cambia los dos de un motor en el mismo tick.
  *dirOut = static_cast<uint8_t>((*dirOut & ~dirPort[MASKS - 1]) | dirPort[pulser.directions() ^ DIR_INVERT]);
  *stepOut = static_cast<uint8_t>((*stepOut & ~stepPort[MASKS - 1]) | stepPort[pulser.steps()]);
}
