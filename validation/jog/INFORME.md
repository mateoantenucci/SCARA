# Jog cartesiano y jog verificado en Webots (issue #11)

Ensayo del 01/11/2026 en Windows 11 Pro, Webots R2025a, con el controlador `scara_uci` compilado con el `g++` 14.2 de Webots, el microstepping por defecto (1/8) y la planta N2. Decisión: D75.

## Cómo se hizo

[`ensayo_webots.py`](ensayo_webots.py) maneja la sesión real de la URC (puerto 9116) contra el controlador, con Webots minimizado, sin vista y en tiempo real, y el canal de instrumentación en el 9117. Cada jog se mantiene como lo hace la página: renovado cada 150 ms. El observador del [ensayo de transmisión](../transmision/observador.py) escribe cada 10 ms el tiempo simulado, que es el reloj del firmware (D26), y la posición física simulada. Había otro Webots abierto: la simulación corrió a 0,82× del reloj de la PC. El mundo y el controlador del observador son temporales: el ensayo los borra al terminar.

```sh
python validation/jog/ensayo_webots.py validation/jog/ensayo_webots.log
```

«Frenó» es el tiempo simulado desde que se suelta la tecla hasta que la posición física queda a menos de un paso de motor de la final (5,6 centésimas de grado; 0,5 de mm en J4).

## Resultados ([registro](ensayo_webots.log))

| Caso | Resultado |
| --- | --- |
| Jog articular de J1 | 10,04 °/s simulados; frenó en 80 ms; J2 quieto |
| Jog articular lento (Mayús) | 1,99 °/s; frenó enseguida |
| Cartesiano X − desde el brazo estirado | Toma el codo negativo (J2 = −12,83° en 1,5 s); frenó en 90 ms |
| Cartesiano Y − | 25 mm en 1,5 s; estimada a 0,055 mm de la recta y simulada a 0,171 mm; rumbo físico a 0,06° del inicial; frenó en 20 ms |
| Cartesiano X + hasta frenar | «Borde del alcance» con J2 = −2,03°: el codo no cambió |
| J4 hacia abajo hasta frenar | «J4 llegó al límite de su recorrido (120 mm)»: estimada 120,00 mm, física como mucho 119,99 mm |
| J2 hacia el pedestal, con J4 abajo | «Z-SoporteEfector-1 tocaría pedestal_de_ensayo» en J2 = 107,21°; separación física mínima 1,14 mm; para el otro lado sale |
| Sin referencia | Cartesiano rechazado; articular a 5,00 °/s (el `JOG` del firmware) |

Frenado al soltar: mediana 80 ms, como mucho 90 ms simulados, en cuatro jogs.

## Observaciones

- **La cola en el reloj de la UCI.** Las primeras corridas contaban la cola con el reloj de la PC: con Webots a 0,82×, crecía y el robot frenaba en 110–150 ms. Ahora la URC mide el ritmo de la UCI por el período de los `S`. Con otro Webots trabando la simulación, suponer que la UCI siguió avanzando sin recibir `S` llenó la cola: 320 ms. Por eso no supone avance más allá de dos períodos.
- **La medida es ruidosa con la PC cargada.** Con otro ensayo de Webots corriendo a la vez, algunas corridas dieron 110–130 ms en un jog suelto: la simulación se traba de a ratos y el observador puede escribir tarde. El ensayo exige la mediana hasta 100 ms y cada jog hasta 150 ms.
- **La cola se vacía a veces.** «La cola se vació» aparece una o dos veces en algunos jogs: el robot frena 20 ms y sigue, a una velocidad que arranca sin rampa.
- **`EV LOST 4 -75` al subir J4 desde el reposo**, en algunas corridas, sin pasos perdidos: la posición física siguió a la estimada. Es del firmware y del Hall de Webots, no del jog: `checkLostSteps` corre en todo movimiento. Queda como seguimiento.
