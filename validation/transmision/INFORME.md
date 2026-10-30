# Transmisión N1 en Webots (issue #7)

Ensayo del 30/10/2026 en Windows 11 Pro, Webots R2025a, con el controlador `scara_uci` compilado con el `g++` 14.2 de Webots y el microstepping por defecto, 1/8.

## Cómo se hizo

[`ensayo_webots.py`](ensayo_webots.py) maneja la sesión real de la URC contra el controlador, en el puerto 9101, con Webots minimizado, sin vista y en tiempo real. Un robot supervisor aparte, [`observador.py`](observador.py), mide la **posición física simulada** con la orientación de los cuerpos del SCARA, sin tocar al robot. El ensayo la compara con la **posición estimada por pasos** que informa el firmware en `S`. El mundo y el controlador del observador son temporales: el ensayo los borra al terminar.

```sh
python validation/transmision/ensayo_webots.py validation/transmision/ensayo_webots.log
```

## Resultado

[`ensayo_webots.log`](ensayo_webots.log), en unidades de `scara/1` (centésimas de grado; J4 en centésimas de mm):

| Paso | Qué se ordenó | Estimada por pasos | Cambio físico simulado | Qué muestra |
| --- | --- | --- | --- | --- |
| 1 | `JOG 1 + 500` | J1 = 624 | J1 +624,4; J2, J3 y J4 sin cambio | El firmware compensa el acople: J2 no cambia |
| 2 | `JOG 2 + 500` | J2 = 624 | J2 +624,4; el resto sin cambio | J2 se mueve solo |
| 3 | `JOG 3 + 500` | J3 = 602 | J3 +601,8; el resto sin cambio | J3 se mueve solo |
| 4 | `JOG 4 - 500` | J4 = 11370 | J4 −629,6; el resto sin cambio | J4 sube solo |
| 5 | `JOG M1 + 500` | J1 = 1249, J2 = 0 | J1 +624,3, J2 −624,3, J3 sin cambio; rumbo 1850,6 antes y después | Con M1 solo, J2 cambia al revés que J1 y el rumbo de la herramienta no cambia |
| 6 | `JOG 3 + 10` durante 6 s | — | J3 pasa por 0, 1, 2 … 8 pasos de 5,625 centésimas; al frenar queda en 8,000 pasos | La resolución observada es un paso de 1/8: 0,05625° |

Con el robot quieto, la física y la estimada coinciden dentro de un paso: J1 físico 624,4 son exactamente 111 pasos de 5,625, y `S` informa 624 porque redondea a la centésima.

**Detalles que no son la transmisión:**

- Webots lleva cada articulación a la posición que ordena la planta con un control de posición de velocidad, aceleración y par limitados. Cada paso de J3 tarda unos 0,2 s en asentarse: un tercio de las muestras del paso 6 cae en plena transición. Las demás están a menos de una décima de paso de un escalón.
- J4 sostiene su peso con ese mismo control, y cede alrededor de 0,1 mm mientras el brazo acelera; vuelve al frenar.

## Qué mirar en la QA humana

El ensayo no se vio en la ventana de Webots: se denegó computer use. En `scara_uci.wbt`, con la URC (`python -m urc.app`), «Habilitar motores» y «Referencia manual»:

1. **A/D** (J1): el brazo gira y el antebrazo sigue alineado con él.
2. **W/S** (J2), **Q/E** (J3) y **R/F** (J4, R sube): cada uno mueve solo su articulación.
3. Con la casilla **«Modo de prueba: jog por motor»**, **D** (M1): el brazo gira y el antebrazo **conserva su orientación en el mundo**. En la página, J2 cambia al revés que J1 y el rumbo de la herramienta queda fijo.
4. Con **W** (M2) en el modo de prueba: solo gira el antebrazo.
