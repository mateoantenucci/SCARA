# Pérdida de pasos (N2) y F1 con `EV LOST` en Webots

Issue #15, decisiones D64–D67. Fecha: 31/10/2026. Windows 11, Webots R2025a, controlador `scara_uci` compilado con el `g++` 14.2 de Webots, paso de simulación de 2 ms, tiempo real.

## Qué se ensayó

[`ensayo_webots.py`](ensayo_webots.py) levanta la sesión real de la URC (`scara/1`, puerto 9110) y el canal de instrumentación real (`scara-sim/1`, puerto 9111) contra el controlador, en un Webots minimizado y sin vista, con `--desvio 0`. En cada paso compara la posición física simulada («Simulado», del canal) con la estimada por pasos (del estado `S`), y los pasos que la planta dice que perdió cada motor con lo que informó el firmware con `EV LOST`. Registro: [`ensayo_webots.log`](ensayo_webots.log).

| Paso | Qué se hace | Resultado |
| --- | --- | --- |
| 0 | Homing de los cuatro ejes y vuelta al reposo (PTP de la URC) | 131 s. Ningún `EV LOST`, aunque J4 cruza su imán de abajo al estacionar. Simulado − estimado: 0; 0; 0; −0,25 pasos completos (J4 cede bajo su peso). Pasos perdidos: ninguno |
| 1 | 5 kg en la herramienta, con la corriente nominal: J4 sube a 10 mm a 30 mm/s y vuelve al reposo | Sin pasos perdidos, diferencia de 0,5 pasos completos en J4 arriba, ningún `EV LOST` al cruzar el Hall de abajo (D66) |
| 2 | F1 por carga: J4 a 60 mm, driver de M4 al 50 %, PTP a 10 mm | J4 no sube: estimado 10,00 mm, simulado 60,43 mm. Diferencia 1260,75 pasos completos; la planta perdió 1260, múltiplo de 4. Con M4 al 100 % y de vuelta al reposo, el Hall de abajo da `EV LOST 4 1261` y la URC avisa «La referencia es dudosa» |
| 3 | F1 por aceleración: driver de M1 al 20 % y 5 kg, jog de J1 a 10 °/s, que arranca sin rampa | Al arrancar, la planta perdió 4 pasos completos (diferencia 3,89: el rotor todavía se atrasa en movimiento). Al llegar a su imán, `EV LOST 1 4` y `ERR 10 fin` |
| 4 | Corriente nominal, herramienta sola y homing de nuevo | La referencia deja de ser dudosa; diferencia de vuelta en menos de un paso |

`ENSAYO OK`. La simulación siguió estable con el paso de 2 ms durante todo el ensayo, incluidos los 5 kg y el motor ahogado.

## Qué muestra

- «Simulado» se aparta de lo estimado en múltiplos de cuatro pasos completos, y solo cuando la carga o la aceleración superan el par: con la corriente nominal no pasa, ni con 5 kg (D64, D66).
- El firmware lo descubre sin encoders, al entrar en un imán, con los mismos pasos que perdió la planta (±1 por la lectura del Hall en movimiento, bajo la tolerancia de 2 pasos completos, D65).
- Cruzar los Hall sin pasos perdidos (homing, estacionar, subir y bajar con 5 kg) no da falsos `EV LOST`.

## Además

Con la planta nueva se volvieron a correr los ensayos de [protocolo](../protocolo/ensayo_webots.log), [transmisión](../transmision/INFORME.md), [segmentos](../segmentos/INFORME.md), [homing](../homing/INFORME.md) y del [canal de instrumentación](../instrumentacion/INFORME.md): los cinco pasan (`ENSAYO OK`). Para eso hizo falta que la fuerza de cada articulación suba en rampa al volver la corriente (D64): sin la rampa, J4, apoyado en su tope, saltaba unos 2 mm al habilitar los motores.

## Cómo repetirlo

Desde la raíz del repo, con el controlador compilado ([UCI en Webots](../../docs/UCI_WEBOTS.md)):

```sh
python validation/perdida_pasos/ensayo_webots.py validation/perdida_pasos/ensayo_webots.log
```

Dura unos 5 minutos. Usa los puertos 9110 y 9111, así que puede correr con otro Webots abierto en 9000 y 9001.

## Límites

- Los parámetros de los motores son de la familia más cercana o supuestos declarados ([Transmisión, N2](../../docs/TRANSMISION.md#par-de-los-motores-y-pérdida-de-pasos-n2)): el ensayo prueba el mecanismo, no el par de los motores reales.
- Las inercias se toman con el brazo estirado y sin los términos cruzados entre M1 y M2.
- Sin modelo eléctrico (N3): no hay resonancias de media frecuencia.
