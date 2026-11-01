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
// (D45, valores de D76). Con la corriente nominal y 5 kg, el par pedido queda
// al menos 2 veces por debajo del disponible en M1–M3 (M4: 1,4, por el peso);
// M4 pide 8000 pulsos/s con 1/8, dentro de los 10 000 del UNO. Los de las
// articulaciones se derivan por la transmisión, con el acople.
constexpr int32_t MOTOR_MAX_SPEED[MOTOR_COUNT] = {360, 360, 720, 1800};
constexpr int32_t MOTOR_MAX_ACCELERATION[MOTOR_COUNT] = {560, 560, 1440, 5400};

// Sensores Hall (D10, D56): un KY-003 por articulación y dos imanes, centrados
// en los extremos de su recorrido. El homing busca el imán del lado negativo
// (J4: arriba) y toma como referencia el flanco donde el Hall se activa, en
// unidades del protocolo. Parámetro provisional: en el robot real se mide; en
// Webots sale de dónde están el imán y el sensor (tools/generate_world.py).
constexpr int32_t HALL_EDGE[MOTOR_COUNT] = {-13000, -13000, -14500, 300};
// Flanco del imán del otro extremo (J4: abajo), donde el Hall se activa al
// llegar desde el centro del recorrido. El homing no lo usa; la detección de
// pasos perdidos, sí (D65).
constexpr int32_t HALL_FAR_EDGE[MOTOR_COUNT] = {13000, 13000, 14500, 11700};
// Ancho del imán del lado alcanzable: desde el flanco hasta el tope.
constexpr int32_t HALL_WIDTH[MOTOR_COUNT] = {500, 500, 500, 300};

}  // namespace scara

#endif
