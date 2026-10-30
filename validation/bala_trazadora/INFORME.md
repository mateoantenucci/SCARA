# Bala trazadora: jog de J1 en Webots (issue #5)

Ensayo del 30/10/2026 en Windows 11 Pro, Webots R2025a, `g++` 14.2.0 del MSYS2 de Webots y Python 3.12.7. Revisión: rama `claude/t05-bala-trazadora-98a03e`, antes del merge del PR que cierra #5.

## Procedimiento

1. `python -m urc.app`; página en <http://127.0.0.1:8766>.
2. Webots con `webots/worlds/scara_uci.wbt`, en tiempo real.
3. Tecla D mantenida 5 s en la página; después A 3 s; después «Referencia manual» (`ZERO`).
4. URC detenida y relanzada para ver la reconexión, y detenida a mitad de un jog para ver el watchdog.

Las teclas se enviaron como eventos de teclado a la página (`keydown`/`keyup` con `KeyD` y `KeyA`), que ejercitan los mismos manejadores que el teclado físico.

## Resultados

| Paso | Observado |
| --- | --- |
| Conexión | Tráfico: `> HELLO`, `< BOOT scara/1 1`, `< HI scara/1 1`. Consola de Webots: `UCI: conectada a la URC en 127.0.0.1:9000`. |
| D, 5 s | URC envió `JOG 1 + 500` y, al soltar, `JOG STOP`. Estimada: J1 de 0,00° a 21,71°; J2, J3 y J4 sin cambios. Webots corría a ~0,82×: ~4,3 s simulados a 5 °/s. |
| Webots | [Antes](01_webots_antes_jog.jpg) y [después](02_webots_despues_D.jpg): el brazo (rojo) giró y el antebrazo (azul) siguió alineado con él, es decir, J2 relativo no cambió. |
| A, 3 s | J1 volvió a 8,94°. |
| `ZERO` | Referenciado; estimada 0°, 0°, 0°, 120 mm. |
| URC caída | Consola: `UCI: enlace perdido (error al recibir)` y `esperando a la URC … reintento cada 1000 ms`. Al relanzarla: `> HELLO`, `< HI scara/1 1`, sin `BOOT`; la referencia se conservó. |
| URC caída en pleno jog | Durante ~10 s sin URC, J1 se movió 5,9° en total (incluido el arranque y el freno), no los ~40° de un jog sin watchdog. El `ERR 4 watchdog` no llega a la URC porque no hay enlace; el caso exacto lo cubre la conversación [`watchdog.txt`](../../firmware/test/conversaciones/watchdog.txt). |

## Límites

- `ZERO` se ensayó con J1 en 8,94°, solo para ejercitar el mensaje: referenciar fuera de la pose de reposo es un error de operación que la planta no detecta.
- La posición física simulada no se informa todavía (canal de instrumentación, issue #14). La comparación de J2 es visual.
- macOS no se ensayó en esta máquina.
