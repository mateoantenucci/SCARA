# Segmentos temporizados y tramo PTP en Webots (issue #9)

Ensayo del 30/10/2026 en Windows 11 Pro, Webots R2025a, con el controlador `scara_uci` compilado con el `g++` 14.2 de Webots y el microstepping por defecto, 1/8.

## Cómo se hizo

[`ensayo_webots.py`](ensayo_webots.py) maneja la sesión real de la URC contra el controlador, en el puerto 9102, con Webots minimizado, sin vista y en tiempo real. La URC planifica cada tramo PTP con su planificador (`urc/planner.py`) y lo envía en segmentos de 20 ms con el control de flujo de `OK`. El observador del [ensayo de transmisión](../transmision/observador.py), un supervisor aparte, mide la **posición física simulada** cada 10 ms sin tocar al robot. Los tiempos son de la simulación, que es el reloj del firmware (D26). El mundo y el controlador del observador son temporales: el ensayo los borra al terminar.

```sh
python validation/segmentos/ensayo_webots.py validation/segmentos/ensayo_webots.log
```

## Resultado

[`ensayo_webots.log`](ensayo_webots.log), en unidades de `scara/1` (centésimas de grado; J4 en centésimas de mm). Todos los tramos van al 100 % de la velocidad.

| Paso | Qué se hizo | Qué se midió | Qué muestra |
| --- | --- | --- | --- |
| 1 | PTP de la pose de reposo a J1 = 30°, J2 = −60°, J3 = 20°, J4 = 80 mm: 179 segmentos, 3,58 s | Las cuatro arrancan dentro de 0,04 s y llegan dentro de 0,10 s. En ninguna muestra el avance de una articulación se aparta más del 0,2 % del camino del avance de otra. Duración física: 3,61 s. J2 llega a 20,05 °/s, su máximo en el modelo; las demás quedan debajo de sus límites y de los de los motores. | Un tramo PTP llega con todas las articulaciones a la vez y respeta los límites (D53). |
| 2 | Otro PTP de 3,60 s. Al segundo, la URC deja de enviar segmentos durante 200 ms, como si esperara un `OK` que no llega | La cola baja a 3 segmentos de 16 sin vaciarse. El firmware está en `RUN` 3,59 s seguidos, sin detenerse. Avance de las articulaciones: el mismo 0,2 %. | Una demora del enlace o de la URC menor que la cola no se nota: los tiempos los marca el reloj del firmware (D6, D50). |
| 3 | Lo mismo, pero durante 600 ms, casi el doble de lo que dura la cola (320 ms) | La cola se vacía y el firmware queda quieto 0,20 s en medio del tramo. Al llegar el siguiente segmento, arranca de golpe a velocidad de crucero: en Webots, J1 se atrasa, se pasa del destino y tarda casi un segundo más en asentarse; el avance de las articulaciones se separa hasta el 3,0 %. | Es el tirón que la cola evita. En el robot real, ese arranque de golpe es una aceleración que pierde pasos (ADR 0006). |
| 4 | PTP de J1 de 30° a −90° y `STOP` a los 2,5 s, a 20 °/s | J1 empieza a frenar 0,12 s después de que la URC envía `STOP` y se detiene en 0,65 s y 6,7°; lo teórico con 34 °/s² es 0,59 s y 5,9°. Queda en `IDLE`, con la cola vacía (16 libres), referenciado, y la física coincide con la estimada. | `STOP` frena con rampa, vacía la cola y conserva la referencia (D52). |

**Detalles que no son del firmware:**

- Webots lleva cada articulación a la posición que ordena la planta con un control de posición de velocidad limitada (`maxVelocity`, 0,35 rad/s en J1 y J2). Cuando el tramo pide justo ese máximo, la física sigue al firmware con unas centésimas de segundo de atraso: por eso las llegadas físicas tardan hasta 0,08 s más que lo planificado y el frenado del paso 4 recorre un grado más que la rampa del firmware. El firmware, medido por `S`, ejecuta el tramo en el tiempo planificado.
- Los 0,12 s entre enviar `STOP` y ver frenar la física son la espera del hilo de la URC (hasta 50 ms), el paso de simulación y ese mismo atraso del seguimiento.
- En el paso 3, la diferencia de avance sale de que J1 tiene más inercia que las demás y Webots la acelera con par limitado: tras el arranque de golpe, J1 queda atrás y las demás no.

Las conversaciones de conformidad prueban lo mismo sin Webots, paso a paso: [`seg_interpolacion.txt`](../../firmware/test/conversaciones/seg_interpolacion.txt), [`seg_cola.txt`](../../firmware/test/conversaciones/seg_cola.txt) (cola llena y `OK` demorado), [`seg_demora.txt`](../../firmware/test/conversaciones/seg_demora.txt), [`seg_stop.txt`](../../firmware/test/conversaciones/seg_stop.txt), [`seg_watchdog.txt`](../../firmware/test/conversaciones/seg_watchdog.txt) y [`seg_errores.txt`](../../firmware/test/conversaciones/seg_errores.txt).

## Qué mirar en la QA humana

El ensayo no se vio en la ventana de Webots: se denegó computer use. En `scara_uci.wbt`, con la URC (`python -m urc.app`), «Habilitar motores» y «Referencia manual»:

1. En **«Ir a una pose (PTP)»**, escribir J1 = 30, J2 = −60, J3 = 20, J4 = 80 y apretar **«Ir a la pose…»**. La URC muestra la duración (unos 12 s al 25 %) y pide confirmación. Al confirmar, **las cuatro articulaciones arrancan juntas, aceleran, frenan y llegan a la vez**; el extremo no va en línea recta. La página muestra el avance del tramo y, en la posición estimada, el modo «Ejecutando segmentos».
2. Con **Punto de herramienta**, escribir X = 433, Y = 0, Z = 14,7 y rumbo −10: es la misma pose, con el codo preferido (J2 negativo). Con «J2 positivo», el codo dobla para el otro lado.
3. Desde el reposo, ir a J1 = −90 al 100 % y apretar **Esc** a mitad de camino: el brazo **frena suave, sin golpe**, a unos 6° de donde estaba, y la página sigue mostrando «Referenciado».
4. Desde el reposo, pedir J2 = 135: la URC lo rechaza antes de mover, con «Recorrido rechazado» y la pieza que podría chocar.
