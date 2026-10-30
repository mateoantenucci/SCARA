#include "pulsos.h"

namespace scara {

StepPulser::StepPulser() : active_(0), steps_(0), directions_(0) {
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) pending_[motor] = 0;
}

bool StepPulser::push(uint8_t motor, int8_t direction) {
  int16_t pending = pending_[motor];
  if (pending * direction >= PENDING_MAX) return false;
  pending = static_cast<int16_t>(pending + direction);
  pending_[motor] = pending;
  uint8_t bit = static_cast<uint8_t>(1 << motor);
  active_ = pending != 0 ? active_ | bit : active_ & static_cast<uint8_t>(~bit);
  return true;
}

bool StepPulser::tick() {
  // Tras un tick en alto, todos los STEP bajan juntos.
  if (steps_ != 0) {
    steps_ = 0;
    return true;
  }
  if (active_ == 0) return false;
  uint8_t bit = 1;
  for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor, bit = static_cast<uint8_t>(bit << 1)) {
    if ((active_ & bit) == 0) continue;
    int16_t pending = pending_[motor];
    bool positive = pending > 0;
    if (((directions_ & bit) != 0) != positive) {
      // DIR cambia en este tick; el pulso sale en el próximo.
      directions_ ^= bit;
      continue;
    }
    steps_ |= bit;
    pending = static_cast<int16_t>(positive ? pending - 1 : pending + 1);
    pending_[motor] = pending;
    if (pending == 0) active_ &= static_cast<uint8_t>(~bit);
  }
  return true;
}

}  // namespace scara
