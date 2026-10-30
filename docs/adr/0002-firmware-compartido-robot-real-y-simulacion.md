---
status: accepted
---

# Un único firmware para el robot real y la simulación

El profesor pidió que Webots opere al nivel del Arduino, para que el día de construir el robot el reemplazo sea transparente y no haya que desarrollar nada nuevo. Por eso el firmware se escribe una sola vez en C++ y se compila tanto para el Arduino como dentro del controlador de Webots. Solo cambia una capa fina de hardware: pines, serie y timers en el Arduino; socket TCP, planta simulada y API de Webots en la simulación. Decidido el 29/10/2026.

## Considered Options

- **Emulador en Python que imite al firmware** (descartado): más rápido de escribir hoy, pero el firmware del Arduino habría que programarlo y depurarlo desde cero más adelante. Es justamente el trabajo nuevo que se quiere evitar.

## Consequences

- El controlador de Webots pasa a ser C++ (la consigna admite `.cpp`) y reemplaza al puente Python `scara_bridge`.
- El firmware respeta las restricciones del Arduino UNO: sin memoria dinámica, buffers de tamaño fijo y sin flotantes en la interrupción de pasos.
- Cada integrante necesita un compilador de C++. Compilar en Windows (MSYS2) está pendiente de verificar.
- El firmware se puede probar con pruebas automáticas en la PC, sin Webots ni Arduino.
