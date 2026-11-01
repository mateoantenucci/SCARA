# UCI en Webots y URC: el camino nuevo

El sistema que reemplazó al banco `scara-dev/1` (D16), ya retirado (issue #17). Hoy cubre la bala trazadora (issue #5), el protocolo completo (issue #6) y la transmisión N1 (issue #7): corriente de los drivers, jog articular de J1–J4 y jog por motor desde la página de la URC, paradas, watchdog y reinicio, de punta a punta, atravesando todas las capas.

## Cómo funciona

```text
navegador ──HTTP 8766──► URC (urc/, Python) ◄──TCP 9000, scara/1── UCI: controlador de Webots (C++)
                                                                     ├─ firmware/  (el mismo núcleo del Arduino)
                                                                     ├─ capa de hardware de simulación
                                                                     └─ planta simulada ──► articulaciones de Webots
```

1. **La URC escucha** en el puerto 9000 (D1) y sirve la página en el 8766.
2. **Webots se conecta como cliente** desde el controlador `scara_uci`. Si la URC no está levantada, reintenta cada segundo sin frenar la simulación (el socket es no bloqueante).
3. **El firmware arranca con la primera conexión** y envía `BOOT` (D36), con los drivers sin corriente (D40). La URC saluda con `HELLO` y la UCI responde `HI`.
4. **«Habilitar motores»** envía `ENABLE`. Sin corriente, el firmware rechaza el jog y `ZERO` con `ERR 6 deshabilitado`.
5. **Al mantener una tecla de jog** (A/D J1, W/S J2, Q/E J3, R/F J4), la página pide jog a la URC cada 150 ms; la URC envía una sola vez, por ejemplo, `JOG 1 + 1000` (10 °/s con referencia; sin ella, 5 °/s) y lo frena con `JOG STOP` al soltar la tecla o si la página deja de renovar el pedido por 500 ms (D37). Con referencia, también lo frena antes del límite de recorrido y de un choque (D70). Con la casilla «Jog por motor (M1–M4)», las mismas teclas envían `JOG M1 + 1000` … `JOG M4 …` (D46).
6. **El firmware genera los pasos** con aritmética entera ([`transmission.h`](../firmware/transmission.h)): para J1 emite el mismo paso a M1 y a M2. Así J2 = (θM2 − θM1)/4 no cambia (acople de la cadena híbrida). En el jog por motor, mueve uno solo.
7. **La planta simulada** cuenta los pasos de cada motor y los convierte en ángulos con la transmisión: el microstepping de [`config.h`](../firmware/config.h) (1/8, 1600 pasos por vuelta, D9 y D44), poleas 4:1 y ACME de 8 mm. Cada rotor sigue a sus pasos con el par de su curva par–velocidad y, si la carga o la aceleración lo superan, pierde pasos sin que el firmware lo sepa (N2, D64); las articulaciones de Webots van adonde están los rotores. Detalle y evidencia: [Transmisión](TRANSMISION.md#transmisión-n1-en-el-firmware-y-en-la-planta).
8. **El estado `S`** vuelve a la URC 20 veces por segundo con la posición estimada por pasos, que la página muestra.
9. **Seguridad del enlace:** la URC envía `PING` cada 250 ms; si el firmware pasa más de 1 s sin mensajes, frena el jog (watchdog, D27).
10. **Paradas (D41):** «Stop» o <kbd>Esc</kbd> envía `STOP` (frena y conserva la referencia); «Parada inmediata» envía `HALT` (si había movimiento, pierde la referencia); «Deshabilitar motores» envía `DISABLE` (corta la corriente y pierde la referencia).

La planta todavía no modela el driver sin corriente: en Webots J4 no cae con `DISABLE`. Llega con las fallas (F2).

`ZERO` (botón «Referencia manual») declara que el robot está en la pose de reposo: J1 = J2 = J3 = 0 y J4 abajo (120 mm). El mundo `scara_uci.wbt` arranca exactamente en esa pose (D38); el desvío aleatorio llega con el homing (issue #8).

## Archivos

| Archivo | Qué es |
| --- | --- |
| [`firmware/config.h`](../firmware/config.h) | Configuración del hardware: el microstepping (un solo parámetro, D44) y los límites de los motores (D45). La incluyen el núcleo, la capa del UNO y la planta. |
| [`firmware/hal.h`](../firmware/hal.h) | Interfaz de capa de hardware: pasos, corriente de los drivers, Hall, reloj y enlace. |
| [`firmware/transmission.h`](../firmware/transmission.h) | Conversión de unidades del protocolo a pasos y acople M1/M2. |
| [`firmware/firmware.cpp`](../firmware/firmware.cpp) | Núcleo portable: parser de `scara/1`, corriente, jog articular y por motor, paradas, watchdog y estado. Sin memoria dinámica ni flotantes. |
| [`firmware/test/`](../firmware/test/) | Capa de hardware falsa y conversaciones de conformidad ([formato](../firmware/test/conversaciones/LEEME.md)). |
| [`webots/controllers/scara_uci/`](../webots/controllers/scara_uci/) | Controlador C++: cliente TCP, reloj simulado y planta simulada. |
| [`webots/worlds/scara_uci.wbt`](../webots/worlds/scara_uci.wbt) | Mundo con el mismo robot y el controlador nuevo. |
| [`urc/`](../urc/) | URC: gramática de `scara/1` (`protocol.py`), sesión, servidor HTTP y página. |
| [`docs/PROTOCOLO_SCARA_1.md`](PROTOCOLO_SCARA_1.md) | Mensajes de `scara/1`. |

## Compilar el controlador

Webots no compila solo los controladores C++: hay que compilarlo una vez, y de nuevo cada vez que cambia el firmware.

**Desde el editor de Webots (cualquier sistema):** abrir `scara_uci.wbt`, abrir `scara_uci.cpp` en el editor de texto de Webots (clic derecho sobre el robot → *Edit Controller*) y apretar **Build** (ícono del engranaje, o F7). Después, **Reload World**. Esta vía no se probó todavía; la de terminal, sí.

**macOS (terminal):** hacen falta las Command Line Tools de Xcode (`xcode-select --install`).

```sh
WEBOTS_HOME=/Applications/Webots.app make -C webots/controllers/scara_uci
```

**Windows (terminal):** no hace falta instalar nada: Webots trae su propio MSYS2 con `g++` 14.2 y `make`. Hay que usar *su* `bash`, con las DLL de C++ de Webots en el PATH:

```powershell
& "C:\Program Files\Webots\msys64\usr\bin\bash.exe" -lc "export PATH=/mingw64/bin:/mingw64/bin/cpp:/usr/bin WEBOTS_HOME='C:/Program Files/Webots'; make -C webots/controllers/scara_uci"
```

Hay que correrlo desde la raíz del repo. Llamar a ese `make` desde Git Bash no funciona: los dos MSYS no se pasan las variables de entorno.

## Usarlo

1. `python3 -m urc.app` (Windows: `python -m urc.app`) y abrir <http://127.0.0.1:8766>.
2. En Webots, abrir `webots/worlds/scara_uci.wbt` y darle play. La consola anuncia `UCI: conectada a la URC`. El orden no importa: si Webots arranca primero, reintenta.
3. Apretar **Habilitar motores** y después **Homing…**: la página dibuja la pose de reposo y pide confirmarla. La simulación arranca cerca del reposo, con un desvío al azar de hasta ±10° en J1–J3 (`--desvio` en `controllerArgs`; 0 arranca justo en el reposo). El homing referencia J4, J1, J2 y J3 con sus sensores Hall y vuelve solo al reposo. **Referencia manual…** declara la pose de reposo sin homing, y **Estacionar…** lleva el robot al reposo con un PTP.
4. Mantener **D** o **A** con la página enfocada: J1 gira y el antebrazo sigue alineado con el brazo. **W/S** mueven J2, **Q/E** J3 y **R/F** J4 (R sube).
5. Para ver el acople, marcar **«Jog por motor (M1–M4)»** y mantener **D**: solo gira M1, el antebrazo conserva su orientación en el mundo y el rumbo de la herramienta no cambia.
6. En **«Ir a una pose (PTP)»**, escribir J1–J4 (o X, Y, Z y rumbo) y apretar **«Ir a la pose…»**: la URC verifica límites y choques, muestra la duración y pide confirmación. Las cuatro articulaciones se mueven a la vez y llegan juntas. **Esc** o **Stop** frenan con rampa.

Con Webots, la página muestra además el panel «Banco de ensayo (solo simulación)»: el controlador se conecta al puerto 9001 con el canal de instrumentación (`--sim-port` en `controllerArgs`; 0 lo apaga). Muestra la posición física simulada junto a la estimada e inyecta las fallas F2–F5, la carga y la recarga del mundo ([validación](../validation/instrumentacion/INFORME.md)).

El panel aparece recién cuando el controlador se conecta al 9001. Si no aparece, el controlador está compilado con un firmware anterior al canal: compilarlo de nuevo ([arriba](#compilar-el-controlador)) y recargar el mundo. Sirve, por ejemplo, para ensayar el watchdog sin soltar la tecla: con **D** apretada, marcar con el mouse «F4 · Cortar el enlace scara/1» (un clic en la misma página no frena el jog); el brazo tiene que frenar solo en menos de 1 s.

No se puede usar a la vez con el banco viejo: los dos quieren el puerto 9000 (en uno escucha la URC; en el otro, Webots).

## Resultado en Windows (D19)

Probado el 30/10/2026 en Windows 11 Pro con Webots R2025a y el `g++` 14.2.0 (MSYS2) que trae Webots:

- El controlador compila sin advertencias con `-Wall -Wextra` y corre.
- Webots se conecta a la URC, envía `BOOT` y responde `HELLO`.
- Con D apretada 5 s, la posición estimada de J1 pasó de 0° a 21,7° y J2 quedó en 0°. La simulación corría a ~0,82× tiempo real, así que avanzó ~4,3 s simulados a 5 °/s, como manda D26. Las capturas de Webots antes y después muestran el brazo girado y el antebrazo alineado: [evidencia](../validation/bala_trazadora/INFORME.md).
- Al cortar la URC, Webots anuncia el enlace perdido y reintenta; al volver la URC se reconecta sin `BOOT` y conserva la referencia.
- Las pruebas del firmware corren con el mismo `g++`.

macOS queda pendiente de verificar en la Mac del grupo.

## Ensayo del protocolo completo (issue #6)

El 30/10/2026, en Windows 11 con Webots R2025a, [`validation/protocolo/ensayo_webots.py`](../validation/protocolo/ensayo_webots.py) manejó la sesión real de la URC contra el controlador compilado, en un Webots minimizado, sin vista y a tiempo real ([registro](../validation/protocolo/ensayo_webots.log)):

1. La UCI arranca sin corriente (`S OFF`) y rechaza el jog con `ERR 6 deshabilitado`.
2. `ENABLE` y `ZERO` la dejan quieta y referenciada.
3. `STOP` tras 2 s de jog a 5 °/s: J1 queda en ~8,5°, quieto y referenciado.
4. `HALT` en pleno jog: frena y pierde la referencia.
5. Con la URC cortada en pleno jog, el firmware frena solo (watchdog). Al volver la URC, la UCI se reconecta sin `BOOT`, quieta y referenciada.
6. `DISABLE` deja `S OFF` sin referencia.
7. Al reiniciar Webots, la URC lee el `BOOT` y marca el robot sin referencia.

No se pudo comprobar mirando la ventana de Webots: se ensayó por el protocolo, con Webots minimizado.
