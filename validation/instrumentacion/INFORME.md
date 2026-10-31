# Canal de instrumentación y fallas F2–F5 en Webots (issue #14)

Ensayo del 31/10/2026 en Windows 11 Pro, Webots R2025a, con el controlador `scara_uci` compilado con el `g++` 14.2 de Webots y el microstepping por defecto, 1/8.

## Cómo se hizo

[`ensayo_webots.py`](ensayo_webots.py) corre contra el controlador, con Webots minimizado, sin vista, a tiempo real y arrancando justo en el reposo. Usa la sesión real de la URC (`scara/1`, puerto 9104) y el canal de instrumentación real (`urc/instrumentation.py`, `scara-sim/1`, puerto 9105).

Mira lo mismo que el panel «Banco de ensayo» de la página: la posición física simulada que manda el canal, leída de los sensores de posición de Webots, junto a la estimada por pasos que informa el firmware en `S`.

```sh
python validation/instrumentacion/ensayo_webots.py validation/instrumentacion/ensayo_webots.log
```

## Resultado

[`ensayo_webots.log`](ensayo_webots.log), en unidades de `scara/1` (centésimas de grado; J4 en centésimas de mm):

| Paso | Qué se hizo | Qué se vio |
| --- | --- | --- |
| 0 | Arranque, `ENABLE` y referencia manual | El canal se conecta solo (`SIM HELLO scara-sim/1`). Simulado y estimado coinciden: (0, 0, 0, 120 mm); los cuatro motores con corriente. |
| 1 | Carga de 500 g | `toolMass` del modelo pasa a 0,5 kg y el canal lo informa. |
| 2 | F2 con J4 en 60 mm | M4 queda sin corriente. J4 simulado **cae a 120 mm** y la estimada **sigue en 60 mm**: 60 mm de diferencia que el firmware no ve. Al quitar la falla, el motor retiene J4 donde quedó (D60). |
| 3 | F3: Hall de J4 trabado activo | El firmware lo ve activo a mitad de carrera. El homing aborta con `ERR 12 trabado`, sin referencia. |
| 4 | F4 en pleno jog de J1 | El estado `S` deja de llegar (2,6 s sin estado) y J1 simulado se queda quieto: el watchdog del firmware frenó solo. Al volver el enlace, el robot está en `IDLE`; el `ERR 4` salió con el enlace cortado y se perdió, como con un cable desenchufado. |
| 5 | F5 | La URC avisa «BOOT inesperado… (F5)» y marca el robot sin referencia. La UCI arranca sin corriente (D40): J1 sigue en 5,23° y J4 cae de 116 a 120 mm. |
| 6 | Recarga del mundo | Los dos canales se cortan y se vuelven a conectar solos. La UCI arranca de nuevo, sin referencia; el robot vuelve al reposo y la carga, a 150 g. |

Las pruebas automáticas cubren lo que no necesita Webots ([`tests/test_instrumentation.py`](../../tests/test_instrumentation.py)):

- **Sin canal, no hay banco:** la URC funciona igual, `/api/banco` responde `connected: false` y la página no muestra el panel.
- **Capturar y planificar no usan el canal:** la sesión, el planificador, la validación y el protocolo no importan `urc/instrumentation.py`. Con una posición simulada distinta de la estimada, el tramo PTP sale de la estimada.
- **Las órdenes del banco:** se validan antes de enviarse, y las líneas mal formadas del canal se descartan sin cortarlo.

## Qué mirar en la QA humana

El recorrido está en el PR del issue #14 y es la QA de la R6.
