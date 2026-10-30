---
status: accepted
---

# El protocolo habla en unidades articulares, no en pasos de motor

El protocolo transporta posiciones articulares como enteros de punto fijo: centésimas de grado para J1–J3 y centésimas de milímetro para J4. El firmware las convierte a pasos y resuelve el acople M1/M2. Microstepping, poleas y acople son hechos del hardware que el programa externo no necesita conocer: cambiar un driver o una polea solo toca la configuración del firmware. Decidido el 29/10/2026.

## Considered Options

- **Pasos crudos de motor** (descartado): es el nivel más bajo y el firmware queda más simple, pero obliga al programa externo a conocer la mecánica y vuelve ilegible la telemetría. El estado puede igual incluir pasos crudos para depurar.
- **Números con decimales** (descartado): parsear e imprimir flotantes es lento en un Arduino AVR, y `printf` no los soporta por defecto.
