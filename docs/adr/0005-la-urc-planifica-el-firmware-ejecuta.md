---
status: accepted
---

# La URC planifica los movimientos y el firmware los ejecuta con su reloj

La URC resuelve la cinemática inversa, traza rectas y calcula el perfil de velocidad. Envía a la UCI segmentos cortos con su duración; el firmware los encola, los ejecuta con su propio reloj y genera los pasos. La UCI responde `OK` cuando un segmento entró en la cola, y eso regula el ritmo de envío. Es la misma división de trabajo que usan GRBL (control CNC sobre Arduino) y Klipper (impresoras 3D). Decidido el 29/10/2026.

## Considered Options

- **El firmware recibe puntos y resuelve la cinemática** (descartado): un Arduino UNO no puede calcular la inversa a la frecuencia que exige una recta.
- **La URC manda posiciones en tiempo real, sin cola** (descartado): las demoras de la red o del puerto serie se convertirían en tirones del robot.
