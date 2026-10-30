# UCI en Webots y URC: el camino nuevo

El camino que reemplaza al banco `scara-dev/1` (D16). Hoy cubre la bala trazadora (issue #5): jog articular de J1 desde la página de la URC, de punta a punta, atravesando todas las capas. El banco viejo sigue igual en `client/`, `scara/` y `webots/worlds/scara.wbt`.

## Cómo funciona

```text
navegador ──HTTP 8766──► URC (urc/, Python) ◄──TCP 9000, scara/1── UCI: controlador de Webots (C++)
                                                                     ├─ firmware/  (el mismo núcleo del Arduino)
                                                                     ├─ capa de hardware de simulación
                                                                     └─ planta simulada ──► articulaciones de Webots
```

1. **La URC escucha** en el puerto 9000 (D1) y sirve la página en el 8766.
2. **Webots se conecta como cliente** desde el controlador `scara_uci`. Si la URC no está levantada, reintenta cada segundo sin frenar la simulación (el socket es no bloqueante).
3. **El firmware arranca con la primera conexión** y envía `BOOT` (D36). La URC saluda con `HELLO` y la UCI responde `HI`.
4. **Al mantener D**, la página pide jog a la URC cada 150 ms; la URC envía una sola vez `JOG 1 + 500` y lo frena con `JOG STOP` al soltar la tecla o si la página deja de renovar el pedido por 500 ms (D37).
5. **El firmware genera los pasos** con aritmética entera: para J1 emite el mismo paso a M1 y a M2. Así J2 = (θM2 − θM1)/4 no cambia (acople de la cadena híbrida).
6. **La planta simulada** cuenta los pasos de cada motor y los convierte en ángulos con la transmisión: 1600 pasos por vuelta (1/8, D9), poleas 4:1 y ACME de 8 mm. Ordena esas posiciones a las articulaciones de Webots. Todavía no pierde pasos: eso es N2 (issue #15).
7. **El estado `S`** vuelve a la URC 20 veces por segundo con la posición estimada por pasos, que la página muestra.
8. **Seguridad del enlace:** la URC envía `PING` cada 250 ms; si el firmware pasa más de 1 s sin mensajes, frena el jog (watchdog, D27).

`ZERO` (botón «Referencia manual») declara que el robot está en la pose de reposo: J1 = J2 = J3 = 0 y J4 abajo (120 mm). El mundo `scara_uci.wbt` arranca exactamente en esa pose (D38); el desvío aleatorio llega con el homing (issue #8).

## Archivos

| Archivo | Qué es |
| --- | --- |
| [`firmware/hal.h`](../firmware/hal.h) | Interfaz de capa de hardware: pasos, Hall, reloj y enlace. |
| [`firmware/firmware.cpp`](../firmware/firmware.cpp) | Núcleo portable: parser de `scara/1`, jog, acople M1/M2, watchdog y estado. Sin memoria dinámica ni flotantes. |
| [`firmware/test/`](../firmware/test/) | Capa de hardware falsa y conversaciones de prueba ([formato](../firmware/test/conversaciones/LEEME.md)). |
| [`webots/controllers/scara_uci/`](../webots/controllers/scara_uci/) | Controlador C++: cliente TCP, reloj simulado y planta simulada. |
| [`webots/worlds/scara_uci.wbt`](../webots/worlds/scara_uci.wbt) | Mundo con el mismo robot y el controlador nuevo. |
| [`urc/`](../urc/) | URC: sesión `scara/1`, servidor HTTP y página. |
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
3. Mantener **D** o **A** con la página enfocada: J1 gira y el antebrazo sigue alineado con el brazo.

No se puede usar a la vez con el banco viejo: los dos quieren el puerto 9000 (en uno escucha la URC; en el otro, Webots).

## Resultado en Windows (D19)

Probado el 30/10/2026 en Windows 11 Pro con Webots R2025a y el `g++` 14.2.0 (MSYS2) que trae Webots:

- El controlador compila sin advertencias con `-Wall -Wextra` y corre.
- Webots se conecta a la URC, envía `BOOT` y responde `HELLO`.
- Con D apretada 5 s, la posición estimada de J1 pasó de 0° a 21,7° y J2 quedó en 0°. La simulación corría a ~0,82× tiempo real, así que avanzó ~4,3 s simulados a 5 °/s, como manda D26. Las capturas de Webots antes y después muestran el brazo girado y el antebrazo alineado: [evidencia](../validation/bala_trazadora/INFORME.md).
- Al cortar la URC, Webots anuncia el enlace perdido y reintenta; al volver la URC se reconecta sin `BOOT` y conserva la referencia.
- Las pruebas del firmware corren con el mismo `g++`.

macOS queda pendiente de verificar en la Mac del grupo.
