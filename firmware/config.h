// Configuración del hardware, compartida por el núcleo del firmware, la capa
// de hardware del Arduino UNO y la planta simulada de Webots (D44).
#ifndef SCARA_CONFIG_H
#define SCARA_CONFIG_H

#include <stdint.h>

// Microstepping de los cuatro TB6600 (D9): pulsos por paso completo. Es el
// único lugar donde se cambia, y las llaves DIP de los drivers tienen que
// coincidir. Las pruebas lo sobrescriben al compilar (-DSCARA_MICROSTEPS=16).
#ifndef SCARA_MICROSTEPS
#define SCARA_MICROSTEPS 8
#endif

namespace scara {

const uint8_t MOTOR_COUNT = 4;

const int32_t MICROSTEPS = SCARA_MICROSTEPS;
static_assert(MICROSTEPS == 1 || MICROSTEPS == 2 || MICROSTEPS == 4 || MICROSTEPS == 8 || MICROSTEPS == 16 ||
                  MICROSTEPS == 32,
              "el TB6600 admite 1, 2, 4, 8, 16 o 32 micropasos");
const int32_t FULL_STEPS_PER_REV = 200;  // NEMA 23 y NEMA 17 de 1,8°
const int32_t STEPS_PER_REV = FULL_STEPS_PER_REV * MICROSTEPS;

// Límites de cada motor en su eje, en grados por segundo y por segundo²
// (D45). Parámetro provisional hasta tener las curvas de par (N2, #15):
// dejan a cada articulación dentro de los límites conservadores del modelo.
// Los de las articulaciones se derivan por la transmisión, con el acople.
constexpr int32_t MOTOR_MAX_SPEED[MOTOR_COUNT] = {80, 80, 112, 1350};
constexpr int32_t MOTOR_MAX_ACCELERATION[MOTOR_COUNT] = {136, 136, 204, 2700};

// Sensores Hall (D10, D56): un KY-003 por articulación y dos imanes, centrados
// en los extremos de su recorrido. El homing busca el imán del lado negativo
// (J4: arriba) y toma como referencia el flanco donde el Hall se activa, en
// unidades del protocolo. Parámetro provisional: en el robot real se mide; en
// Webots sale de dónde están el imán y el sensor (tools/generate_world.py).
constexpr int32_t HALL_EDGE[MOTOR_COUNT] = {-13000, -13000, -14500, 300};
// Ancho del imán del lado alcanzable: desde el flanco hasta el tope.
constexpr int32_t HALL_WIDTH[MOTOR_COUNT] = {500, 500, 500, 300};

}  // namespace scara

#endif
