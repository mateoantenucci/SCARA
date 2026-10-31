# Reproducción de trayectorias en Webots (issue #13)

Ensayo del 31/10/2026 en Windows 11 Pro, Webots R2025a, con el controlador `scara_uci` compilado con el `g++` 14.2 de Webots, el microstepping por defecto (1/8) y la planta N2.

## Cómo se hizo

[`ensayo_webots.py`](ensayo_webots.py) maneja la sesión real de la URC (puerto 9114), su gestor de trayectorias y su reproducción ([`urc/playback.py`](../../urc/playback.py)) contra el controlador, con Webots minimizado, sin vista y en tiempo real. La posición física simulada llega por el canal de instrumentación (puerto 9115). El tiempo lo da el observador del [ensayo de transmisión](../transmision/observador.py), que lee el reloj de la simulación: es el reloj del firmware (D26). Webots corrió a 0,82× del reloj de la PC, porque había otro Webots abierto: medidos con el reloj de la PC, los tramos parecían un 20 % más largos. El mundo y el controlador del observador son temporales: el ensayo los borra al terminar.

```sh
python validation/reproduccion/ensayo_webots.py validation/reproduccion/ensayo_webots.log
```

Trayectoria mixta, armada con el gestor (en grados y mm; cada punto dice cómo se llega a él):

| Punto | J1, J2, J3, J4 | Tramo | Velocidad | Espera |
| --- | --- | --- | --- | --- |
| 1 | 30, −60, 10, 60 | LIN (rige la vuelta del loop) | 50 % | 0 s |
| 2 | −20, −40, 5, 30 | LIN | 100 % | 0 s |
| 3 | 20, −80, 0, 90 | PTP | 50 % | 0 s |
| 4 | 20, −80, 0, 50 | LIN (vertical) | 50 % | 1 s |

## Resultado

[`ensayo_webots.log`](ensayo_webots.log). La velocidad global es 100 %. Los tiempos medidos van del estado `S` que muestra terminado el último segmento del tramo anterior al que muestra terminado el último del tramo; el estado llega cada 50 ms.

| Paso | Qué se hizo | Qué se midió | Qué muestra |
| --- | --- | --- | --- |
| 0 | Homing y vuelta al reposo | Estimada [0, 0, 0, 12000] | Robot referenciado para reproducir. |
| 1 | Play en loop de 2 vueltas desde el reposo | Validación y arranque: 3,2 s. Ocho tramos: tramo 0 (PTP al 25 %), 2, 3, 4, la vuelta (LIN con los parámetros del punto 1) y otra vez 2, 3, 4. Cada uno duró lo planificado con a lo sumo 0,04 s de diferencia; en total, **61,45 s medidos contra 61,46 s planificados**. En los LIN, el punto de herramienta quedó a lo sumo a **0,18 mm de la recta** con la posición estimada y a 0,17 mm con la simulada. | Los tramos se encadenan sin huecos y los tiempos son los del plan, con sus esperas (D68). El LIN sigue la recta y la vuelta usa los parámetros del punto 1 (D32). |
| 2 | Play otra vez y **pausa** en el segmento 277 de 546 del tramo 2 (LIN); 1 s quieto; **reanudar** | El robot frenó con la rampa a **0,053 mm de la recta**, estimada y simulada. Al reanudar, la URC planificó 280 segmentos desde ahí hasta el punto 2. En todo el tramo 2, antes, durante la rampa y después: 0,21 mm estimada, 0,17 mm simulada, contra la recta original. La reproducción terminó normalmente. | Pausa con rampa y reanudación que conservan la recta (D69). |
| 3 | Play otra vez y **stop** a un tercio del tramo 2 | Reproducción detenida; el tramo de la sesión, cancelado en el segmento 6293 de 6653, sin nada por enviar. El robot frenó con rampa en 0,3° y 0,2 mm. | Stop frena y descarta lo pendiente. |
| 4 | F5 reinicia la UCI; play | «Para reproducir, el robot tiene que estar referenciado (homing o referencia manual)» | Sin referencia, la reproducción queda bloqueada con un mensaje claro. |

**Detalles:**

- La cota de 0,32 mm para la recta es la tolerancia del plan (0,069 mm, D54) más medio paso de M1 y de M2 con 1/8 (0,25 mm): la posición estimada se mueve en pasos enteros. Lo medido, 0,13 a 0,21 mm, es casi todo ese escalón de los pasos.
- Las diferencias de tiempo, de hasta 0,04 s, son menores que el período del estado `S` (50 ms).

Las pruebas por los endpoints HTTP ([`tests/test_playback.py`](../../tests/test_playback.py)) cubren lo mismo sin Webots, paso a paso: segmento por segmento, cada tramo es el que planifica la validación, y cubren también las esperas, el tramo 0 omitido, la velocidad global, el resaltado, la pausa en una espera, Esc, `ERR`, `EV LOST` y el loop sin fin.
