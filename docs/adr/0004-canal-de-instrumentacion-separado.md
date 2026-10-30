---
status: accepted
---

# Lo que solo existe en simulación va por un canal aparte

El protocolo entre la URC y la UCI solo transporta lo que un Arduino real podría saber: pasos, Hall y modo. Todo lo exclusivo de la simulación viaja por un canal de instrumentación separado, otro puerto TCP que el robot real no tiene: posición física real, inyección de fallas, carga y recarga del mundo. Así la URC no puede depender sin querer de información que el hardware no da, y la interfaz separa a la vista la verdad del simulador de lo que sabe el robot. El protocolo provisional `scara-dev/1` mezclaba ambas cosas en el mismo mensaje de estado. Decidido el 29/10/2026.

## Consequences

- El canal vive en el mismo controlador de Webots que aloja al firmware. Ya tiene permisos de supervisor, y las fallas actúan sobre la planta simulada de ese mismo proceso. Igual que en el protocolo principal, la URC escucha y el controlador se conecta: puerto 9000 para `scara/1` y 9001 para instrumentación.
- La interfaz conserva la columna «Simulado» en un panel separado del banco de ensayo. Capturar puntos y planificar usan siempre la posición estimada por pasos.
