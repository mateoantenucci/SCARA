# Sensores Hall y homing en Webots (issue #8)

Ensayo del 31/10/2026 en Windows 11 Pro, Webots R2025a, con el controlador `scara_uci` compilado con el `g++` 14.2 de Webots y el microstepping por defecto, 1/8. Repetido el mismo día con el modelo de motores N2 (#15) y el homing más rápido de D70: búsqueda a 15 °/s (J4 a 10 mm/s) y vuelta al reposo al 100 %.

## Cómo se hizo

[`ensayo_webots.py`](ensayo_webots.py) maneja la sesión real de la URC contra el controlador, en el puerto 9103, con Webots minimizado, sin vista y en tiempo real.

- **Hall.** Son los del modelo: un KY-003 (`Receiver`) en la pieza fija y dos imanes (`Emitter` con su alcance) en la que se mueve, en `SCARA.proto`. La planta activa el Hall por la distancia entre los dos nodos (D57).
- **Física.** El observador del [ensayo de transmisión](../transmision/observador.py), en modo absoluto, mide la posición física simulada desde el brazo estirado.
- **Choques.** El ensayo pasa todo el camino físico, desde el arranque, por el chequeo de colisiones del repositorio (`scara/collisions.py`), de a pares de muestras cada 50 ms. El modelo de Webots no tiene choques entre las piezas del robot (`selfCollision FALSE`), así que este es el chequeo que dice si el brazo toca la torre.

Dos corridas: A arranca justo en la pose de reposo (`--desvio 0`), y B con un desvío al azar de hasta ±10° en J1–J3, que es el valor por defecto del mundo.

```sh
python validation/homing/ensayo_webots.py validation/homing/ensayo_webots.log
```

## Resultado

[`ensayo_webots.log`](ensayo_webots.log), en unidades de `scara/1` (centésimas de grado; J4 en centésimas de mm).

| Corrida | Qué se hizo | Qué se midió |
| --- | --- | --- |
| A | Arranque en reposo, sin referencia | Hall `1000`: solo J4, que descansa abajo sobre su imán de fin. Los imanes de J1–J3 están lejos. |
| A | Jog de J4 hacia arriba pedido a 10 mm/s, sin referencia | Fue a 5,00 mm/s (D58). Salió del imán de abajo y frenó solo, con `ERR 10 fin`, en J4 = 3,0 mm: el flanco del imán de arriba está en 3 mm. De vuelta hacia abajo, frenó en 117,0 mm (flanco: 117 mm). |
| A | Homing | Ejes en orden J4, J1, J2, J3. En los flancos, la física quedó a menos de 0,05° (0,01 mm en J4) de la referencia: J1 −129,99°, J2 −129,99°, J3 −145,02°, J4 3,0 mm. |
| A | Vuelta al reposo | La URC la envió sola: PTP de 13,6 s al 100 % (antes, 26,3 s al 50 %). Física final en el reposo, a menos de 0,01 mm en J4; estimada (0, 0, 0, 120 mm); referenciado; Hall `1000`. |
| A | Choques | Todo el camino físico, del arranque al reposo final, sin choques: ni con la torre ni con el pedestal. |
| B | Arranque con desvío, homing y vuelta al reposo | Los cuatro ejes, en el mismo orden, y física final otra vez a menos de 0,14° del reposo. La corrida entera, del arranque al reposo, duró un 36 % menos que con la búsqueda a 8 °/s (5863 muestras contra 9115). El desvío del arranque se anota en el registro. |

**El atraso de Webots (antes de N2).** En la primera corrida, Webots llevaba cada articulación a la posición de los pasos con un control de posición que seguía unas décimas de segundo atrás. Cuando la física activaba el Hall, el firmware ya había dado unos pasos más, así que la referencia quedaba corrida en esa cantidad:

- Llegando a 1 °/s: dos pasos, 0,11°; en J4, 0,1 mm.
- En el jog a 5 mm/s: medio milímetro.

Con N2, el rotor de cada motor sigue a los pulsos con menos de un paso completo de atraso (D64), y la referencia queda a menos de 0,05°.

Con motores paso a paso reales no pasa: el eje está donde dicen los pasos. Por eso el homing hace lentas las fases que miden cuánto falta para salir de un imán (D56).

Las conversaciones de conformidad prueban el homing sin Webots, paso a paso:

- [`homing.txt`](../../firmware/test/conversaciones/homing.txt): desde el reposo, un segundo homing sobre la referencia y `STOP` a mitad de camino.
- [`homing_hall_trabado.txt`](../../firmware/test/conversaciones/homing_hall_trabado.txt) y [`homing_hall_ausente.txt`](../../firmware/test/conversaciones/homing_hall_ausente.txt): Hall trabado activo e inactivo; el homing aborta sin declarar referencia (F3).
- [`jog_hall.txt`](../../firmware/test/conversaciones/jog_hall.txt): jog lento sin referencia, frenado por el Hall.

[`tests/test_hall.py`](../../tests/test_hall.py) calcula los flancos desde la geometría del proto y verifica que coincidan con el firmware.
