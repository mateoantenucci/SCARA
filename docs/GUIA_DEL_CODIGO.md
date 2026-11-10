# Guía del código (uso interno del grupo)

Documento de estudio para que cualquiera del grupo pueda contestar preguntas del profesor sobre el código. **No se entrega.** A diferencia del informe, acá se citan las decisiones (D*n*, en `docs/REGISTRO_DE_DECISIONES.md`) y los ADR (`docs/adr/`).

Cómo leerla:

- Las referencias van como `ruta:línea` (o `ruta:desde-hasta`), relativas a la raíz del repo, sobre el commit `675208d` de `main`. Si alguien cambia un archivo, los números de línea se corren: buscá el nombre de la función.
- Todo sale del código o de los documentos. Cuando un documento viejo contradice al código, manda el código; la sección 10 junta las contradicciones que encontramos.
- Unidades de `scara/1`: centésimas de grado en J1–J3 y centésimas de mm en J4 (ADR 0003). «1/8» es el microstepping por defecto (D9).
- El vocabulario es el de `GLOSSARY.md`: URC, UCI, firmware, controlador de Webots, planta simulada, canal de instrumentación, banco de ensayo, posición estimada por pasos y posición física simulada, segmento, tramo, punto de trayectoria.

## Contenido

1. Mapa general
2. Ejemplo de punta a punta: una tecla de jog desde la página hasta el motor
3. Firmware (`firmware/`)
4. Controlador de Webots (`webots/controllers/scara_uci/`)
5. Proto, mundo y mallas (`webots/protos`, `webots/worlds`, `cad/`, `tools/`)
6. URC (`urc/`)
7. Cinemática y colisiones (`scara/`)
8. Pruebas (`tests/`, `firmware/test/`, conversaciones de conformidad)
9. Herramientas y campaña de validación (`tools/`, `validation/campana/`)
10. Problemas conocidos y textos viejos
11. Índice rápido: qué decisión explica qué

---

## 1. Mapa general

```text
navegador ──HTTP 8766──► URC (urc/, Python, en la PC)
                           │  planifica: cinemática inversa, PTP, LIN, jog verificado, validación
                           │
                           ├──TCP 9000, scara/1──────► UCI
                           │                            ├─ firmware/ (núcleo C++ compartido)
                           │                            └─ capa de hardware (Hal)
                           │                                 · Webots: TcpClient + planta simulada (N1/N2, Hall)
                           │                                 · Arduino UNO: pines, Timer1, serie (+ socat)
                           │                                 · PC: PTY (para ensayar socat sin placa)
                           │
                           └──TCP 9001, scara-sim/1──► canal de instrumentación (solo simulación)
```

| Proceso / hilo | Dónde | Qué hace |
| --- | --- | --- |
| Servidor HTTP | `urc/app.py:242` (`ThreadingHTTPServer` en `127.0.0.1:8766`) | Sirve la página y la API; un hilo por pedido. |
| Hilo `scara-uci` | `urc/session.py:106`, bucle en `urc/session.py:783-819` | Dueño del socket con la UCI: recibe líneas, envía órdenes, `PING`, segmentos. |
| Hilo `scara-sim` | `urc/instrumentation.py:83`, bucle en `urc/instrumentation.py:236-276` | Dueño del socket del canal de instrumentación. |
| Hilo `scara-reproduccion` | `urc/playback.py:75`, bucle en `urc/playback.py:237-245` | Cada 20 ms sigue la reproducción y encola tramos. |
| Controlador `scara_uci` | `webots/controllers/scara_uci/scara_uci.cpp:965-1007` | Un bucle por paso de Webots (2 ms): enlace, Hall, firmware, planta. |

Quién es servidor: **la URC escucha** (9000 y 9001) y la UCI se conecta (D1, D24). La URC no conoce la mecánica (ADR 0003); el firmware no conoce cinemática ni choques (ADR 0005); la URC nunca usa el canal de instrumentación para planificar (ADR 0004).

| Carpeta | Lenguaje | Rol |
| --- | --- | --- |
| `firmware/` | C++11 sin memoria dinámica | Núcleo de la UCI y sus capas de hardware (UNO, PC) y pruebas. |
| `webots/controllers/scara_uci/` | C++ | Controlador de Webots: aloja el firmware, la planta simulada y el canal de instrumentación. |
| `webots/protos/`, `webots/worlds/` | VRML (Webots) | Robot generado y mundo. |
| `urc/` | Python (solo biblioteca estándar) + HTML/JS | URC: sesión, planificador, jog, validación, trayectorias, reproducción, página. |
| `scara/` | Python | Cinemática, colisiones, marcos, cajas equivalentes. |
| `config/` | JSON | `scara.json` (geometría, límites, entorno, chequeo de choques) y `cad_integration.json`. |
| `tests/` | Python `unittest` | Toda la suite; compila y corre también las pruebas C++. |
| `tools/` | Python | Pipeline CAD → Webots, chequeos CAD, utilidades. |
| `validation/` | Python + registros | Ensayos en Webots por issue y la campaña. |
| `trayectorias/` | JSON | Las tres demos (D74). |

---

## 2. Ejemplo de punta a punta: una tecla de jog desde la página hasta el motor

Caso: el robot está **referenciado** en la pose de reposo, modo articular, y el operador mantiene **D** (J1 +).

### 2.1 En la página

1. `keydown` con `KeyD` → `KEYS.KeyD = [1, "+"]` (`urc/index.html:431-434`). El manejador (`urc/index.html:635-660`) ignora la tecla si se está escribiendo en un campo o hay un diálogo abierto, y llama a `startJog(1, "+", event.shiftKey)`.
2. `startJog` (`urc/index.html:563-576`) arma `{joint: 1, direction: "+", motor: false, mode: "articular", slow: false}` y hace `POST /api/jog` **cada 150 ms** (`REFRESH_MS`, `urc/index.html:435`), con un timeout de 300 ms por pedido para que un pedido viejo no llegue tarde (`urc/index.html:573`).
3. Al soltar (`keyup`, `urc/index.html:661-671`), al perder el foco o al ocultarse la pestaña (`urc/index.html:672-676`), `stopJog` deja de renovar y hace `POST /api/jog/stop` (`urc/index.html:579-585`). Es el primer freno de D37.

### 2.2 En la URC

4. `do_POST` (`urc/app.py:156-211`) verifica el `Origin`, que sea JSON y de 1 B a 1 KiB, y llama a `session.jog(...)` (`urc/app.py:172-174`).
5. `Session.jog` (`urc/session.py:207-256`) valida los argumentos y, como el robot está referenciado y no es jog por motor, va a `_jog_segments` (`urc/session.py:243-245`).
6. `_jog_segments` (`urc/session.py:365-386`) renueva el plazo `jog_deadline = ahora + 0,5 s` (`JOG_HOLD`, `urc/session.py:30`): **si la página deja de renovar 500 ms, el jog se termina** (segundo freno de D37). La primera vez verifica ya un paso con `jogging.step` para rechazar enseguida si no se puede, y crea `jog_plan`.
7. El hilo del enlace (`urc/session.py:783-819`) da vueltas cada 10 ms mientras hay jog por segmentos (`JOG_POLL`, `urc/session.py:38`, `urc/session.py:788`). En cada vuelta, `_send_pending` (`urc/session.py:756-781`) pide a `_feed_jog` (`urc/session.py:388-428`) el próximo segmento:
   - espera al robot quieto para arrancar desde la posición estimada (`urc/session.py:399-404`);
   - no deja más de **tres** segmentos en la cola del firmware (`JOG_QUEUE`, `urc/session.py:36`), contados en el reloj de la UCI que estima por el período de los `S` (`_uci_rate`, `urc/session.py:430-439`; D75);
   - calcula el paso con `urc/jog.py:67-89`: J1 avanza 1000 centésimas/s × 0,02 s = 20 centésimas, verifica recorrido, (en cartesiano) codo, y choques con `CollisionChecker`;
   - arma la línea con `segment_line` (`urc/protocol.py:99-101`), que pasa por `check_order`: **`SEG 1 20 20 0 0 12000`**.
8. Solo hay un `SEG` sin confirmar por vez (`in_flight`, D50). El hilo envía todo con `sendall` y un `PING` cada 250 ms (`urc/session.py:777-781`).

### 2.3 En la UCI (Webots)

9. `TcpClient::service` (`webots/controllers/scara_uci/scara_uci.cpp:80-107`) acumula los bytes. En el mismo paso de Webots, `firmware->poll()` (`webots/controllers/scara_uci/scara_uci.cpp:1002`) los lee con `WebotsHal::readByte` (`webots/controllers/scara_uci/scara_uci.cpp:742-746`).
10. `Firmware::poll` (`firmware/firmware.cpp:139-169`) arma la línea en `receive` (`firmware/firmware.cpp:171-195`) y `handle` la despacha a `handleSegment` (`firmware/firmware.cpp:510-570`): valida la forma, que haya corriente, los cuatro ejes referenciados, ningún otro movimiento, y la velocidad de cada motor con el acople (`segmentWithinMotorSpeed`, `firmware/transmission.h:87-98`).
11. `jointsToMotors` (`firmware/transmission.h:54-59`) convierte 20 centésimas de J1 a pasos: con 1/8, 8 pasos cada 45 centésimas → `round(20·8/45) = 4` pasos para M1, y **otros 4 para M2**, porque M2 sigue a J1 + J2. `enqueue` lo pone en la cola y responde **`OK 1`** (`firmware/firmware.cpp:563-566`, `firmware/firmware.cpp:763-767`).
12. En cada `poll`, `advanceRun` (`firmware/firmware.cpp:686-714`) interpola lineal entre el origen y el destino con el reloj del firmware, y `stepTo` (`firmware/firmware.cpp:732-740`) llama a `hal_.step(motor, ±1)` por cada paso que falta.

### 2.4 En la planta simulada y en Webots

13. `WebotsHal::step` → `Plant::step` (`webots/controllers/scara_uci/scara_uci.cpp:733`, `webots/controllers/scara_uci/scara_uci.cpp:392-394`) suma el paso al contador del motor si tiene corriente.
14. Después del `poll`, `plant.apply(0,002)` (`webots/controllers/scara_uci/scara_uci.cpp:1004`): cada rotor sigue a sus pulsos con el modelo N2 (`Stepper::advance`, `webots/controllers/scara_uci/stepper.h:98-130`). La articulación J1 de Webots se lleva hacia donde está el rotor con control de velocidad (`webots/controllers/scara_uci/scara_uci.cpp:545-567`). El brazo se mueve en la ventana.
15. Cada 50 ms el firmware envía el estado (`sendStatus`, `firmware/firmware.cpp:743-761`), por ejemplo `S RUN 15 23 0 0 12000 8 15 1`: modo, máscara de referenciados, **posición estimada por pasos** (4 pasos = 22,5 → 23 centésimas), Hall (8 = el de J4, que en reposo está sobre su imán de abajo), lugares libres de la cola y último segmento terminado.

### 2.5 De vuelta en la URC y al soltar

16. `_receive` (`urc/session.py:642-721`) interpreta el `S` con `parse_message` (`urc/protocol.py:111-149`), guarda el estado y llama a `_follow_homing`, `_guard_jog` y a los chequeos de tramo. El `OK 1` libera `in_flight` (`urc/session.py:698-701`) y sale el `SEG 2 20 40 0 0 12000`.
17. La página pide `GET /api/estado` cada 200 ms (`urc/index.html:949-1006`) y dibuja la posición.
18. Al soltar **D**, `jog_stop` (`urc/session.py:258-270`) termina el jog **sin enviar nada**: el robot ejecuta lo encolado (≤ 3 segmentos, 60 ms) y frena porque la cola se vacía (D75). Si la URC o el enlace se caen, el tercer freno es el watchdog del firmware: 1 s sin mensajes → frena con `ERR 4` (`firmware/firmware.cpp:161-164`).

### 2.6 La misma tecla sin referencia

Sin referencia la URC no puede verificar nada (D21, D28). `Session.jog` envía **una sola vez** `JOG 1 + 500` (`urc/session.py:246-256`; 500 = 5 °/s, `JOG_SPEED_UNREFERENCED`, `urc/session.py:28`), y las renovaciones solo estiran el plazo. Si vence, `_send_pending` envía `JOG STOP` (`urc/session.py:759-762`). En el firmware, `handleJog` (`firmware/firmware.cpp:255-299`) usa `JOINT_MOTORS[0] = 0x03`: M1 y M2 juntos (`firmware/transmission.h:36`), y además limita a 5 °/s por su cuenta (`firmware/firmware.cpp:284`). `advanceJog` (`firmware/firmware.cpp:663-680`) integra la velocidad con un acumulador entero. El Hall hace de fin de carrera (`checkJogHall`, `firmware/firmware.cpp:305-317`, D58).

---

## 3. Firmware (`firmware/`)

### 3.1 Qué hace

Es el programa de la UCI: interpreta `scara/1`, comanda la corriente de los drivers, genera los pasos del jog, del homing y de la cola de segmentos, frena (STOP con rampa, HALT, watchdog), hace homing con los Hall, detecta pasos perdidos y convierte unidades articulares a pasos con el acople M1/M2. **Es el mismo código en Webots, en el Arduino UNO y en la PC** (D3, ADR 0002); solo cambia la capa de hardware.

Restricciones de diseño (`firmware/firmware.h:1-6`): sin memoria dinámica, buffers fijos, sin flotantes, portable al UNO (2 KB de RAM).

| Archivo | Qué es |
| --- | --- |
| `firmware/hal.h` | Interfaz abstracta `Hal`: lo único que el núcleo sabe del hardware. |
| `firmware/config.h` | Microstepping, límites de los motores, flancos de los Hall. Compartido con el UNO y la planta. |
| `firmware/transmission.h` | Unidades ↔ pasos, acople M1/M2, chequeo de velocidad por segmento. Todo entero. |
| `firmware/firmware.h`, `firmware/firmware.cpp` | Clase `Firmware`: el núcleo. |
| `firmware/arduino/scara_uci/` | Sketch del UNO: `HalUno` (pines, serie, Timer1) y `StepPulser`. |
| `firmware/pc/uci_serie.cpp` | UCI de PC detrás de un PTY, para ensayar socat sin placa. |
| `firmware/test/` | Capa de hardware falsa, conversaciones de conformidad y prueba de transmisión. |
| `firmware/arduino/test/pulsos.cpp` | Prueba en la PC del generador de pulsos del UNO. |

### 3.2 `hal.h`: la costura

`class Hal` (`firmware/hal.h:14-32`) tiene seis métodos virtuales puros:

| Método | Contrato |
| --- | --- |
| `millis()` | Milisegundos desde el arranque; se usan restas, así que puede dar la vuelta. |
| `step(motor, direction)` | Un pulso de paso del motor 0..3, sentido ±1. |
| `enableDrivers(on)` | ENABLE común de los cuatro drivers (D18). Sin corriente, J4 cae. |
| `readHall()` | Máscara: bit n = Hall de Jn+1 activo. |
| `readByte()` | Próximo byte del enlace o −1. |
| `write(text)` | Línea completa terminada en LF hacia la URC. |

Hay cuatro implementaciones: `WebotsHal` (`webots/controllers/scara_uci/scara_uci.cpp:728-764`), `HalUno` (`firmware/arduino/scara_uci/hal_uno.h:32-42`), `PtyHal` (`firmware/pc/uci_serie.cpp:33-119`) y `FakeHal` de las pruebas (`firmware/test/conversacion.cpp:25-69`).

### 3.3 `config.h`

| Constante | Valor | Línea | Decisión |
| --- | --- | --- | --- |
| `SCARA_MICROSTEPS` | 8 (sobrescribible con `-D`) | `firmware/config.h:11-13` | D9, D44 |
| `STEPS_PER_REV` | 200 × 8 = 1600 | `firmware/config.h:23-24` | |
| `MOTOR_MAX_SPEED` (°/s del eje del motor) | 360, 360, 720, 1800 | `firmware/config.h:31` | D45, valores de D76 |
| `MOTOR_MAX_ACCELERATION` (°/s²) | 560, 560, 1440, 5400 | `firmware/config.h:32` | D76 |
| `HALL_EDGE` (flanco de la referencia) | −13000, −13000, −14500, 300 | `firmware/config.h:39` | D10, D56 |
| `HALL_FAR_EDGE` (flanco del otro imán) | 13000, 13000, 14500, 11700 | `firmware/config.h:43` | D65 |
| `HALL_WIDTH` | 500, 500, 500, 300 | `firmware/config.h:45` | D58 |

Un `static_assert` limita el microstepping a lo que admite el TB6600 (`firmware/config.h:20-22`).

### 3.4 `transmission.h`: transmisión N1 en enteros

```text
J1 = θM1 / 4    J2 = (θM2 − θM1) / 4    J3 = θM3 / 4    J4 = 8 mm · vueltas de M4
```

- Pasos por unidad como fracción reducida `STEPS_NUM/STEPS_DEN` (`firmware/transmission.h:26-32`). Con 1/8: **8/45** en J1–J3 (6400 pasos por 36000 centésimas) y **2/1** en J4 (1600 pasos por 800 centésimas de mm).
- `unitsToSteps` y `stepsToUnits` redondean al más cercano (`firmware/transmission.h:38-50`); ir y volver no acumula error (lo prueba `firmware/test/transmision.cpp`).
- `jointsToMotors`: **M2 = J1 + J2** (`firmware/transmission.h:54-59`); `motorsToJoints`: J2 = M2 − M1 (`firmware/transmission.h:62-67`).
- `JOINT_MOTORS = {0x03, 0x02, 0x04, 0x08}` (`firmware/transmission.h:36`): el jog articular de J1 mueve M1 y M2 juntos, así J2 no cambia.
- `withinMotorSpeed` (`firmware/transmission.h:71-74`) se usa en `static_assert` para que el jog y la búsqueda del homing, que arrancan sin rampa, no pasen la velocidad de ningún motor (`firmware/firmware.cpp:18-24`).
- `segmentWithinMotorSpeed` (`firmware/transmission.h:87-98`): mide el recorrido de cada motor en unidades de su articulación (con el acople) y admite `ROUNDING_UNITS = 2` de más por el redondeo de la URC. No depende del microstepping (D51).

### 3.5 `firmware.cpp`: el núcleo por dentro

**Estado.** Lo que mueve los motores es uno solo: `enum Motion { NONE, JOG, RUN, STOPPING, HOMING }` (`firmware/firmware.h:46`). Una orden de otro movimiento se rechaza con `ERR 5 ocupado`. La posición estimada es `steps_[4]`, pasos netos por motor (`firmware/firmware.h:96`); `homed_` es la máscara de ejes referenciados y `found_` recuerda qué ejes tienen una cuenta que salió de una referencia aunque un `STOP` se la haya quitado (`firmware/firmware.h:122-126`, D72).

**El bucle.** `poll()` (`firmware/firmware.cpp:139-169`) hace, en este orden:

1. Lee los Hall (y borra la marca de fin de carrera de los que se apagaron).
2. Si no está en homing, `checkLostSteps`; si está en jog, `checkJogHall`; si está en homing, `advanceHoming`.
3. Avanza el movimiento vigente: `advanceJog`, `advanceRun` o `advanceStopping`.
4. Lee las órdenes nuevas (rigen desde este instante). Cada LF renueva el watchdog.
5. Watchdog: con JOG, RUN u HOMING y más de 1000 ms sin mensajes → `stop()` y `ERR 4 watchdog`.
6. Cada 50 ms, el estado `S`.

**Parser.** `receive` (`firmware/firmware.cpp:171-195`): ignora CR, corta en LF, más de 63 caracteres → `ERR 3 largo`, bytes fuera de ASCII imprimible → `ERR 1 comando`. `handle` (`firmware/firmware.cpp:197-252`) separa campos con `nextField` y valida enteros con `parseUnsigned`/`parseSigned` de hasta 9 cifras (`firmware/firmware.cpp:44-77`).

| Orden | Qué hace | Errores posibles |
| --- | --- | --- |
| `HELLO` | Responde `HI scara/1 1` | 2 si lleva argumentos |
| `PING` | Solo renueva el watchdog | |
| `STATUS` | Envía `S` ya | |
| `ENABLE` / `DISABLE` | Corriente de los drivers. `DISABLE` frena y **pierde la referencia** (`firmware/firmware.cpp:587-592`, D40) | |
| `STOP` | Jog: para en seco. Segmentos: rampa. Homing: aborta. **Conserva la referencia** (`firmware/firmware.cpp:604-608`, D41, D52) | |
| `HALT` | Para en seco y vacía la cola; si había movimiento, pierde la referencia (`firmware/firmware.cpp:232-236`, D41) | |
| `ZERO` | Declara la pose de reposo `{0, 0, 0, 12000}`: referenciado (`firmware/firmware.cpp:237-250`) | 6 sin corriente, 5 en movimiento |
| `JOG j ± v`, `JOG Mm ± v`, `JOG STOP` | Jog articular, por motor (D46) o freno (`firmware/firmware.cpp:255-299`) | 2, 6, 5, 10 |
| `HOME [j]` | Homing de todos o de un eje (`firmware/firmware.cpp:356-384`) | 2, 6, 5; durante: 11, 12, 4 |
| `SEG n ms q1 q2 q3 q4` | Encola un segmento (`firmware/firmware.cpp:510-570`) | 2, 6, 7, 5, 9, 8 |

Los códigos `ERR` están en `firmware/firmware.cpp:88-99` y son estables: se agregan, no se renumeran. La URC tiene la misma tabla en `urc/protocol.py:22-35`.

Mensajes UCI → URC: `BOOT scara/1 1` al arrancar (`firmware/firmware.cpp:123-129`, arranca **sin corriente**), `HI`, `S modo referenciados J1 J2 J3 J4 hall libres último` (`firmware/firmware.cpp:743-761`; el modo `STOPPING` se informa como `RUN`), `OK n`, `ERR código palabra`, `EV HOMED j`, `EV LOST j pasos`.

**Jog y fin de carrera.** `advanceJog` (`firmware/firmware.cpp:663-680`) suma `velocidad × STEPS_NUM × ms` en un acumulador y emite un paso cada vez que junta `STEPS_DEN × 1000`: es una integración entera exacta. Una pausa larga entre llamadas se recorta a 100 ms (`firmware/firmware.cpp:14`). `checkJogHall` (`firmware/firmware.cpp:305-317`): si se activa un Hall de un eje que mueve el jog, frena en seco con `ERR 10 fin`; si arrancó sobre un imán puede salir, pero si recorre más que el ancho del imán + 1° sin que se apague, iba al tope y frena. Mientras siga activo ese Hall, otro jog de los mismos motores en el mismo sentido no arranca (`firmware/firmware.cpp:290-294`, D58).

**Homing** (D11, D56, D72). Orden J4, J1, J2, J3 (`HOME_ORDER`, `firmware/firmware.cpp:104`). Cada eje pasa por fases (`enum HomePhase`, `firmware/firmware.h:50`), decididas en `advanceHoming` (`firmware/firmware.cpp:419-468`); los pasos los da `advanceJog`:

| Fase | Sentido | Velocidad | Termina cuando | Error |
| --- | --- | --- | --- | --- |
| `LEAVE` (si arrancó sobre un imán) | hacia la referencia (−) | lenta, 1 °/s | el Hall se apaga → `SEARCH`; o recorre > ancho + margen → era el de la referencia → `BACKOFF` | |
| `SEARCH` | − | rápida: 15 °/s, J4 10 mm/s (`HOME_FAST`, `firmware/firmware.h:29`) | el Hall se activa → `BACKOFF` | recorre > `HOME_SEARCH_MAX` → `ERR 11 ausente` |
| `BACKOFF` | + | lenta | el Hall se apaga → `CLEAR` | recorre > ancho + margen → `ERR 12 trabado` |
| `CLEAR` | + | rápida | recorre 3° (3 mm) (`HOME_BACKOFF`) → `APPROACH` | |
| `APPROACH` | − | lenta | el Hall se activa → **flanco = referencia**, `EV HOMED j` | se pasa → `ERR 11` |

Además, cada eje tiene un tope de **60 s** de su reloj (`HOME_AXIS_MS`, `firmware/firmware.h:33`; chequeo en `firmware/firmware.cpp:424-428`) que aborta con `ERR 11`. `startHomeAxis` (`firmware/firmware.cpp:392-403`) decide la primera fase: si el Hall está activo y el eje tiene `found_` y está en su flanco, retrocede directo (`BACKOFF`); si no, supone el imán del otro extremo (`LEAVE`). `finishHomeAxis` (`firmware/firmware.cpp:473-496`) fija la cuenta en `HALL_EDGE`; para J1 corre también M2, así J2 no cambia. `abortHoming` (`firmware/firmware.cpp:499-504`) quita la referencia de los ejes de ese `HOME`. **La vuelta al reposo no la hace el firmware**: la planifica la URC (D56).

**Cola de segmentos** (D6, D50, D51). Cola circular de 16 (`QUEUE_SIZE`, `firmware/firmware.h:22`; `Segment` de 22 bytes, `firmware/firmware.h:54-58`). `OK n` sale cuando el segmento entró; con la cola llena, guarda uno aparte (`held_`) y demora su `OK` hasta que se libera un lugar (`firmware/firmware.cpp:563-569`, `firmware/firmware.cpp:705-710`). Otro `SEG` con uno retenido es `ERR 9 cola`. Cada segmento empieza **cuando termina el anterior en el reloj del firmware** (`started_ += segment.ms`, `firmware/firmware.cpp:702`): las demoras del enlace no se notan mientras quede cola (16 × 20 ms = 320 ms). Si la cola se vacía, el robot queda en el último destino.

**Rampa de STOP** (D52). `startRamp` (`firmware/firmware.cpp:623-655`): cada motor sigue en el sentido del segmento actual y baja su velocidad linealmente hasta cero; todos tardan lo mismo (lo que necesita el motor más exigido con su aceleración máxima), así el robot sigue la misma dirección en articulaciones. `advanceStopping` (`firmware/firmware.cpp:718-729`) recorre `d · t (2T − t) / T²`. Toda orden rechazada con segmentos en ejecución también frena con rampa (`reject`, `firmware/firmware.cpp:780-783`).

**Pérdida de pasos** (F1, D65). `checkLostSteps` (`firmware/firmware.cpp:326-342`): con el eje referenciado, al **entrar** en un imán compara los pasos contados con los del flanco más cercano (`HALL_EDGE` o `HALL_FAR_EDGE`); si difieren en 2 pasos completos o más, envía `EV LOST j pasos` (reales − contados, en pasos completos). **No corrige la cuenta ni frena**: decide la URC. J2 se mide como M2 − M1.

### 3.6 Versión Arduino (`firmware/arduino/scara_uci/`)

- `scara_uci.ino` (`firmware/arduino/scara_uci/scara_uci.ino:8-16`): crea `HalUno` y `Firmware`; `setup()` llama a `hal.begin()` y `firmware.begin()`; `loop()` llama a `firmware.poll()`.
- Pines (`firmware/arduino/scara_uci/hal_uno.h:13-19`, D47): STEP en D2, D3, D5, D6 (todos en PORTD), DIR en A0–A3 (PORTC), ENABLE en D7, Hall en D8, D9, A4, A5. Quedan libres D4 y D10–D13 para un shield Ethernet. Serie a 115200.
- `HalUno::step` **no saca el pulso**: lo deja pendiente en `StepPulser` con las interrupciones apagadas, y si el motor ya tiene 255 pendientes espera (`firmware/arduino/scara_uci/hal_uno.cpp:62-69`): nunca descarta un paso contado (D48).
- Timer1 en CTC a 20 kHz (`TICK_HZ`, `firmware/arduino/scara_uci/hal_uno.h:19`; configuración en `firmware/arduino/scara_uci/hal_uno.cpp:48-55`). La ISR (`firmware/arduino/scara_uci/hal_uno.cpp:89-95`) escribe DIR y STEP de los cuatro motores de una vez con tablas precalculadas: los pulsos de M1 y M2 salen juntos. `StepPulser::tick` (`firmware/arduino/scara_uci/pulsos.cpp:19-42`) cambia DIR un tick antes del flanco, da un tick en alto y al menos uno en bajo: hasta 10 000 pasos/s por motor. Un `static_assert` verifica que alcance para la velocidad máxima de cada motor (`firmware/arduino/scara_uci/hal_uno.h:21-28`).
- ENABLE: TB6600 con cátodo común, ENA+ en alto corta la corriente (`firmware/arduino/scara_uci/hal_uno.cpp:71-72`). Hall: KY-003 con pull-up, `LOW` es activo (`firmware/arduino/scara_uci/hal_uno.cpp:74-80`).
- Se compila con `arduino-cli compile --fqbn arduino:avr:uno --library firmware firmware/arduino/scara_uci` (`firmware/arduino/scara_uci/scara_uci.ino:3`). **No se probó con la placa** (README, D49).

### 3.7 Versión PC (`firmware/pc/uci_serie.cpp`)

`PtyHal` crea un puerto serie virtual (`posix_openpt`) y anuncia su nombre por stderr (`firmware/pc/uci_serie.cpp:38-44`, `firmware/pc/uci_serie.cpp:135`). Imita al UNO por USB (D36, D49): el firmware arranca de cero cuando alguien abre el puerto, y lo que llega antes del primer LF se pierde, como en el bootloader (`firmware/pc/uci_serie.cpp:48-63`). Cerrar el puerto apaga el firmware y crea un PTY nuevo (`firmware/pc/uci_serie.cpp:129-147`). **No tiene planta**: los pasos no mueven nada y los Hall nunca se activan (`firmware/pc/uci_serie.cpp:74-76`). La usa `tests/test_serie_socat.py` con la misma receta de socat que el UNO.

### 3.8 Cómo se prueba

- **Conversaciones de conformidad** contra el núcleo con `FakeHal` (sección 8.2): `tests/test_firmware.py:73-79`.
- **Transmisión con todos los microstepping** (1, 2, 4, 8, 16, 32): `tests/test_firmware.py:81-88` compila `firmware/test/transmision.cpp` con `-DSCARA_MICROSTEPS=n`.
- **Sin memoria dinámica:** compila el núcleo con `-fno-exceptions -fno-rtti` y busca `malloc`, `new`, etc. con `nm -u` (`tests/test_firmware.py:20-25`, `tests/test_firmware.py:90-98`).
- **Generador de pulsos del UNO** en la PC: `tests/test_uno.py:37-71` con `firmware/arduino/test/pulsos.cpp`.
- **Entra en el UNO** (flash ≤ 32 256 B, RAM global ≤ 75 % de 2048 B): `tests/test_uno.py:74-87`, solo con `arduino-cli`.
- **Camino serie con socat:** `tests/test_serie_socat.py`, solo con socat.

Todo compila con `-std=c++11 -Wall -Wextra -Werror -pedantic` (`tests/test_firmware.py:20`).

### 3.9 Preguntas probables del profesor

- **¿Por qué un solo firmware y no un emulador en Python?** Para que el día del robot real no haya que escribir nada nuevo: solo cambia la capa de hardware (D3, ADR 0002). Lo que se prueba en Webots es el mismo código que va al UNO.
- **¿Cómo hace el mismo código para correr en Webots y en el UNO?** Por la interfaz `Hal` (`firmware/hal.h:14-32`): reloj, pasos, corriente, Hall y enlace. Cada plataforma la implementa.
- **¿Por qué sin flotantes ni memoria dinámica?** El UNO tiene 2 KB de RAM y un AVR sin unidad de punto flotante; la memoria dinámica fragmenta. La prueba lo verifica con `nm` (D39).
- **¿Qué es el acople M1/M2 y dónde está en el código?** M2 fija el ángulo absoluto del antebrazo: J1 + J2 = θM2/4. Está en `jointsToMotors` y `motorsToJoints` (`firmware/transmission.h:54-67`) y en `JOINT_MOTORS` (el jog de J1 mueve M1 y M2).
- **¿Por qué el protocolo no habla en pasos?** Para que la URC no conozca la mecánica: cambiar un driver o el microstepping no la toca (D5, ADR 0003).
- **¿Qué pasa si la URC manda un segmento demasiado rápido?** El firmware lo rechaza con `ERR 8 velocidad` y frena con rampa si había segmentos (D51, `firmware/firmware.cpp:554-557`). Protege a los motores de un error de la URC; no reemplaza al planificador.
- **¿Cómo evita la URC desbordar la cola?** Espera el `OK` de cada `SEG` antes de mandar el siguiente; con la cola llena el firmware demora el `OK` (D50). Es el *send-response* de GRBL.
- **¿Quién marca los tiempos de los segmentos?** El reloj del firmware: cada segmento empieza cuando termina el anterior (`firmware/firmware.cpp:702`). Así una demora de red no se ve mientras haya cola.
- **¿Qué diferencia hay entre STOP, HALT y DISABLE?** STOP frena (con rampa si hay segmentos) y conserva la referencia; HALT para en seco y la pierde si había movimiento; DISABLE corta la corriente y siempre la pierde (D40, D41, D52).
- **¿Cómo se hace el homing?** Ver la tabla de fases (3.5). La referencia es el flanco del Hall al que se llega lento y siempre desde el mismo lado: repetible (D56).
- **¿Por qué el firmware no vuelve solo al reposo después del homing?** Porque desde J1 y J2 en −130° hay que verificar choques en el camino, y eso es de la URC (D56, ADR 0005).
- **¿Cómo detecta la pérdida de pasos sin encoders?** Con el Hall, la única medida absoluta: al entrar en un imán compara la cuenta con el flanco (D65). Tolera 2 pasos completos porque lo mínimo que se pierde son 4.
- **¿Por qué no corrige la cuenta cuando detecta pasos perdidos?** Escondería la falla con una medida menos precisa que la del homing, y frenar es decisión de la URC (D65).
- **¿Cómo genera los pulsos el UNO sin que dependan de lo que tarda `poll()`?** El núcleo deja los pasos pendientes y la ISR del Timer1 a 20 kHz los convierte en pulsos con los tiempos del TB6600 (D48).

---

## 4. Controlador de Webots (`webots/controllers/scara_uci/`)

### 4.1 Qué hace

Es la UCI de la simulación: un programa C++ que Webots ejecuta y que aloja **el firmware compartido** con una capa de hardware de simulación, la **planta simulada** (motores, transmisión, Hall) y el **canal de instrumentación** (`webots/controllers/scara_uci/scara_uci.cpp:1-15`). Argumentos: `--host`, `--port 9000`, `--sim-port 9001` (0 lo apaga), `--desvio 10` grados (`webots/controllers/scara_uci/scara_uci.cpp:965-975`).

El bucle principal (`webots/controllers/scara_uci/scara_uci.cpp:985-1005`), una vez por paso de Webots (2 ms):

1. `link.service()`: conecta, recibe y envía por TCP.
2. `plant.sense()`: calcula los Hall por distancia.
3. `plant.spin()`: gira las poleas visuales.
4. `bench.service()`: canal de instrumentación; si pidió F5, crea un firmware nuevo y llama a `begin()` (envía `BOOT`).
5. Con la primera conexión, `firmware->begin()` (D36). Las reconexiones no reinician el firmware.
6. `firmware->poll()`: una vez por paso de Webots, con `millis()` = tiempo simulado.
7. `link.flush()` y `plant.apply(0,002)`: los motores siguen a los pasos dados y se mueven las articulaciones.

| Clase | Líneas | Rol |
| --- | --- | --- |
| `TcpClient` | `webots/controllers/scara_uci/scara_uci.cpp:59-248` | Cliente TCP no bloqueante con reintento cada 1 s: la simulación nunca espera a la red. Sin conexión, lo escrito se pierde. |
| `Plant` | `webots/controllers/scara_uci/scara_uci.cpp:292-724` | La planta simulada: rotores N2, articulaciones, Hall, contacto, empujón, poleas. |
| `WebotsHal` | `webots/controllers/scara_uci/scara_uci.cpp:728-764` | Implementa `scara::Hal` sobre `Plant` y `TcpClient`. |
| `Bench` | `webots/controllers/scara_uci/scara_uci.cpp:780-961` | Canal de instrumentación `scara-sim/1`. |
| `plant::Stepper` y compañía | `webots/controllers/scara_uci/stepper.h` | Modelo N2 del motor paso a paso, sin dependencias de Webots. |

### 4.2 `WebotsHal`

- `millis()` es **tiempo simulado**: `robot_.getTime() * 1000` (`webots/controllers/scara_uci/scara_uci.cpp:732`). Por eso el watchdog cuenta tiempo simulado y la simulación tiene que ir a 1× o menos (D26, issue #51; ver 10.1).
- `step` → `Plant::step`; `enableDrivers` → `Plant::setDrivers`; `readHall` → `Plant::hall`.
- F4: con `cut_`, lo que llega se descarta y lo que sale no se envía, **con la conexión TCP abierta**, como un cable desenchufado (`webots/controllers/scara_uci/scara_uci.cpp:742-756`, D61).
- `write` intercepta `EV HOMED j` para poner en cero los pasos perdidos de ese motor en el banco (`webots/controllers/scara_uci/scara_uci.cpp:749-753`, D86).

### 4.3 Planta simulada: N1 + N2

**N1 (transmisión).** `UNIT` da radianes o metros de cada articulación por pulso: 2π/1600/4 en J1–J3 y 8 mm/1600 en J4 (`webots/controllers/scara_uci/scara_uci.cpp:260-262`). La planta escribe la mecánica **aparte del firmware** («la planta es el robot, no lo que el firmware cree», `webots/controllers/scara_uci/scara_uci.cpp:252-255`); comparte solo el microstepping de `config.h`.

**N2 (par y pérdida de pasos)** en `stepper.h` (D64, ADR 0006):

- Curva par–velocidad: `availableTorque` (`webots/controllers/scara_uci/stepper.h:67-74`): plana hasta la velocidad de esquina `V/(2·L·I)` (`webots/controllers/scara_uci/stepper.h:59-61`) y cae como 1/ω arriba; a baja velocidad vale 0,7 del par de retención (`LOW_SPEED_FACTOR`) y escala con la corriente (F1).
- Curva par–ángulo: el rotor es una inercia que sigue al campo con `T = T(ω)·sen(π/2·e/paso completo)` más amortiguamiento ζ = 0,6 (`webots/controllers/scara_uci/stepper.h:111-115`). Se integra en 10 subpasos por paso de Webots (`SUBSTEPS`, `webots/controllers/scara_uci/stepper.h:162`).
- Si el atraso supera **dos pasos completos** (medio ciclo eléctrico), el rotor cae al equilibrio siguiente y se pierden **4 pasos completos** (`webots/controllers/scara_uci/stepper.h:118-127`). El firmware no se entera.
- Carga de cada motor: `loadOf` (`webots/controllers/scara_uci/stepper.h:236-259`) con las masas del proto, brazo estirado, sin términos cruzados entre M1 y M2; el peso de J4 pasa por el ACME con eficiencia 0,67 al subir y 0,55 al bajar (`webots/controllers/scara_uci/stepper.h:210-211`).
- Motores (`webots/controllers/scara_uci/stepper.h:196-201`): M1 y M2 de la familia Minebea 23KM-K3 (0,80 N·m), M3 del STP-42D201-37 (0,31 N·m), M4 supuesto (0,20 N·m). **Las hojas exactas no aparecieron**: son parámetros provisionales.

**De rotores a articulaciones.** `Plant::apply` (`webots/controllers/scara_uci/scara_uci.cpp:427-569`):

1. Detecta contacto con un obstáculo de ensayo comparando puntos de contacto (`webots/controllers/scara_uci/scara_uci.cpp:432-453`).
2. Lee el esfuerzo de cada articulación y cancela la reacción de J2 sobre el brazo, porque M2 está fijo a la bancada (`webots/controllers/scara_uci/scara_uci.cpp:465-471`).
3. Aplica el empujón, si hay (`webots/controllers/scara_uci/scara_uci.cpp:472-494`, D92).
4. Avanza cada rotor con su carga (`webots/controllers/scara_uci/scara_uci.cpp:497-519`); si un contacto retiene el eje, usa `advanceContact` (D89).
5. Lleva cada articulación de Webots hacia la posición del rotor con **control de velocidad**: velocidad del rotor + la mitad de lo que falta por paso (`TRACKING = 0,5`, `webots/controllers/scara_uci/scara_uci.cpp:564-567`). Los motores de Webots están en velocidad, sin límite de aceleración (`webots/controllers/scara_uci/scara_uci.cpp:357-361`).
6. Los topes mecánicos frenan articulación y rotor aunque sigan llegando pulsos (`webots/controllers/scara_uci/scara_uci.cpp:544-553`): el motor pierde pasos contra el tope.
7. Al volver la corriente, la fuerza sube en rampa durante 50 pasos (0,1 s) para que J4 no salte desde su tope (`RAMP_TICKS`, `webots/controllers/scara_uci/scara_uci.cpp:267`, `webots/controllers/scara_uci/scara_uci.cpp:526`).

**Sin corriente** (D60, F2). `updatePower` (`webots/controllers/scara_uci/scara_uci.cpp:675-692`): un motor sin corriente no avanza con los pulsos (`Plant::step` los descarta) y su articulación queda con fuerza 0 (`webots/controllers/scara_uci/scara_uci.cpp:537-543`): **J4 cae**. Al volver la corriente, el rotor se reinicia donde está el eje: lo que se movió sin corriente el firmware no lo sabe. F2 deja sin corriente solo el driver de M4 (`webots/controllers/scara_uci/scara_uci.cpp:837-838`).

**Arranque** (D11). La simulación arranca cerca de la pose de reposo con un desvío al azar de hasta ±`--desvio` grados en J1–J3 (`webots/controllers/scara_uci/scara_uci.cpp:312-319`) y J4 abajo (120 mm), puesto con `setJointPosition` (por eso el robot es `supervisor TRUE`). El firmware arranca sin referencia.

**Esfuerzo máximo.** Al arrancar, la planta sobrescribe los campos `j1MaxTorque`… del proto con la capacidad que da N2 (`webots/controllers/scara_uci/scara_uci.cpp:327-332`): quien limita es el modelo del motor, no Webots (D64).

**Poleas visuales.** `spin()` gira cuatro poleas según las articulaciones, no los rotores (la correa las une a la salida) (`webots/controllers/scara_uci/scara_uci.cpp:279-289`, `webots/controllers/scara_uci/scara_uci.cpp:649-657`). No cambia la física.

### 4.4 Hall por distancia (D57)

Cada KY-003 es un `Receiver` en la pieza fija y cada imán un `Emitter` (con su `range`) en la que se mueve, dos por articulación (`iman1_inicio`, `iman1_fin`…). Webots **no entrega paquetes entre dispositivos del mismo robot**, así que `Plant::sense` (`webots/controllers/scara_uci/scara_uci.cpp:628-643`) mide la distancia entre las posiciones de los nodos en el mundo y activa el Hall si un imán está dentro de su alcance. La activación sale de la geometría del modelo, **no de leer la posición de la articulación** (eso hacía `scara-dev/1` y estaba descartado, D10). F3 fuerza el bit (`webots/controllers/scara_uci/scara_uci.cpp:640-641`). El alcance lo calcula `tools/generate_world.py:43-47` para que la zona activa mida ±5° (±3 mm en J4).

### 4.5 Canal de instrumentación `scara-sim/1` (ADR 0004, D59)

| Sentido | Mensaje | Qué |
| --- | --- | --- |
| UCI → URC | `SIM HELLO scara-sim/1` | Saludo (`webots/controllers/scara_uci/scara_uci.cpp:799-802`) |
| UCI → URC, 20/s | `SIM J1 J2 J3 J4 hall corriente f2 f3 f4 carga i1..i4 p1..p4` | Posición física simulada (de los `PositionSensor`), Hall, motores con corriente, fallas, carga en g, corriente de cada driver en %, pasos perdidos (`webots/controllers/scara_uci/scara_uci.cpp:920-935`) |
| UCI → URC | `SIM OBSTACULO …`, `SIM CONTACTO …` | Obstáculo de ensayo, cuerpo en contacto, esfuerzo actual, pico y límite (`webots/controllers/scara_uci/scara_uci.cpp:936-946`) |
| URC → UCI | `F1 m %` | Corriente del driver de Mm (10–100 %) |
| URC → UCI | `F2 0\|1` | Driver de M4 sin corriente |
| URC → UCI | `F3 j activo\|inactivo\|libre` | Hall trabado |
| URC → UCI | `F4 0\|1` | Enlace `scara/1` cortado |
| URC → UCI | `F5` | Reinicia solo el firmware (`BOOT`) |
| URC → UCI | `CARGA g` | Carga agregada a la herramienta, 0–4850 g (D85) |
| URC → UCI | `MANO j pos` | Mover a mano con todos los drivers sin corriente (D91) |
| URC → UCI | `EMPUJON cN dir ms` | Empujón en la punta (D92) |
| URC → UCI | `OBSTACULO maceta X Y`, `OBSTACULO mesa X Y h`, `OBSTACULO ninguno` | Obstáculo de ensayo, importado al mundo |
| URC → UCI | `RECARGA` | `worldReload()` (`webots/controllers/scara_uci/scara_uci.cpp:902-905`) |

El parser (`webots/controllers/scara_uci/scara_uci.cpp:824-909`) acepta una orden solo si ocupa la línea entera (`%n` de `sscanf`); si no, `SIM ERR orden`.

### 4.6 Compilar

`Makefile` (`webots/controllers/scara_uci/Makefile:4-15`): compila `scara_uci.cpp` junto con `../../../firmware/firmware.cpp`, con `-I` al firmware, usando el `Makefile.include` de Webots. En macOS: `WEBOTS_HOME=/Applications/Webots.app make -C webots/controllers/scara_uci` (`docs/UCI_WEBOTS.md:56-60`). **El binario no se versiona**: hay que compilarlo en cada máquina y cada vez que cambia el firmware.

### 4.7 Cómo se prueba

- `tests/test_planta.py:18-29` compila `webots/controllers/scara_uci/test/stepper.cpp` (sin Webots) y verifica: forma de la curva de par, que los límites de D76 no pierdan pasos ni con 5 kg (también el jog y la búsqueda del homing sin rampa), que se pierde de a 4 pasos completos por carga y por aceleración, el comportamiento contra un tope, con carga externa, empujón y contacto (`webots/controllers/scara_uci/test/stepper.cpp:80-262`).
- `tests/test_hall.py` lee el proto generado, calcula los flancos por distancia y verifica que sean los de `HALL_EDGE`/`HALL_FAR_EDGE` y los de la planta falsa de las conversaciones.
- El controlador completo solo se prueba en Webots: los ensayos de `validation/*/ensayo_webots.py` y la campaña (sección 9).

### 4.8 Preguntas probables del profesor

- **¿Qué es la planta simulada?** La parte del controlador que reemplaza el hardware que comanda el firmware: drivers, motores, transmisión, Hall (glosario). Está en `Plant` y `stepper.h`.
- **¿Por qué no usan el control de posición de Webots con par limitado?** Se atrasa por su propia ganancia y por los límites del proto, daba pérdidas de pasos falsas y no puede repartir el par de M1 y M2 con el acople. Un modelo aparte además se prueba sin Webots (D64).
- **¿Cómo pierde pasos un motor simulado?** Cuando el atraso del rotor pasa de dos pasos completos cae al equilibrio siguiente: 4 pasos completos (`webots/controllers/scara_uci/stepper.h:118-127`). Es lo que hace un híbrido real.
- **¿El Hall de Webots es trampa? ¿Lee la posición de la articulación?** No: mide la distancia entre el nodo del imán y el del sensor (D57). Si se mueve un imán en el modelo, se mueve el flanco.
- **¿Por qué el firmware usa el reloj simulado?** Para que los tiempos sean los del robot simulado aunque la PC no llegue a 1×. La contracara es que no se puede correr en modo Fast con la URC (D26, #51).
- **¿Qué pasa con DISABLE en Webots?** Los motores quedan sin fuerza y J4 cae; al volver la corriente, el motor retiene el eje donde quedó y el firmware no lo sabe (D60).
- **¿Cómo se simula el reinicio de la UCI (F5)?** Se crea un `Firmware` nuevo en el mismo controlador: envía `BOOT` sin corriente ni referencia, y la planta no se reinicia (`webots/controllers/scara_uci/scara_uci.cpp:991-994`, D61).
- **¿Por qué el robot de Webots es supervisor?** Para poner la pose inicial, buscar los cuerpos del proto, importar obstáculos y recargar el mundo (`webots/controllers/scara_uci/scara_uci.cpp:350`, `webots/controllers/scara_uci/scara_uci.cpp:879`, `webots/controllers/scara_uci/scara_uci.cpp:905`).

---

## 5. Proto, mundo y mallas

### 5.1 `webots/protos/SCARA.proto`

**Generado** por `tools/generate_world.py` (`webots/protos/SCARA.proto:2`; escritura en `tools/generate_world.py:226-228`). No se edita a mano. Estructura:

- `DEF BASE Robot` con `supervisor TRUE` y `selfCollision FALSE` (`webots/protos/SCARA.proto:25-27`): no hay choques entre piezas del robot en Webots; los choques los verifica la URC.
- Cadena R-R-R-P: `HingeJoint` J1 → `DEF ARM Solid`, `HingeJoint` J2 → `DEF FOREARM`, `HingeJoint` J3 → `DEF WRIST`, `SliderJoint` J4 → `DEF TOOL` (`webots/protos/SCARA.proto:97-104`, `151-158`, `220-227`, `266-271`). J1 cuelga de un `J1_MOUNT` fijo para poder medir su esfuerzo (`webots/protos/SCARA.proto:95-96`).
- Dispositivos: `j1_motor`…`j4_motor` (rotacionales; J4 lineal), `j1_sensor`…`j4_sensor` (`PositionSensor`, la verdad para el canal de instrumentación), `hall1`…`hall4` (`Receiver`) e `iman1_inicio`/`iman1_fin`… (`Emitter`).
- Recorridos: J1 y J2 ±2,356 rad (±135°), J3 ±2,618 rad (±150°), J4 de 0 a 0,12 m (`webots/protos/SCARA.proto:101-102`, `224-225`, `269`). Coinciden con `config/scara.json`.
- Campos: `toolMass` (lo cambia el banco con `CARGA`), `j1MaxTorque`… `j4MaxForce` (los sobrescribe la planta), `housingTransparency` y los `spin_*` de las poleas (`webots/protos/SCARA.proto:3-24`).
- Visual: 45 usos de 38 mallas STL distintas, de `cad/derivados/stl/` y de la torre por cuerpos (`cad/derivados/torre_por_cuerpos/stl/`), con `boundingObject` y `physics` de cajas equivalentes provisionales.

### 5.2 `webots/worlds/`

| Mundo | Qué es |
| --- | --- |
| `webots/worlds/scara_uci.wbt` | El que se usa. `basicTimeStep 2` (`webots/worlds/scara_uci.wbt:9`), suelo y pedestal de ensayo (los obstáculos que conoce el chequeo de choques), y `DEF SCARA SCARA { controller "scara_uci" … }` con los esfuerzos subidos (`webots/worlds/scara_uci.wbt:66-72`). Se mantiene a mano (`tools/generate_world.py:226`). |
| `webots/worlds/scara_cad_inspeccion.wbt` | Vista fija de las colocaciones CAD recuperadas, sin motores ni física. La genera `tools/generate_cad_preview.py`. |

### 5.3 De dónde salen las mallas

Pipeline (`docs/PROCESO_Y_ARCHIVOS.md:58-68`); necesita el Python con OCP (`tools/requirements-cad.txt`), que **no hace falta para usar el robot**:

1. `tools/convertir_cad.py`: `.SLDPRT` de `Modelos3D/` → STEP con el conversor `sldprt2step` (revisión fijada, `tools/convertir_cad.py:26-27`, con parches en `tools/patches/`) → validación con OpenCascade → STL en `cad/derivados/`. Deja `cad/derivados/informe.json`.
2. `tools/exportar_torre_cuerpos.py`: la torre por sus tres sólidos (`cad/derivados/torre_por_cuerpos/`).
3. `tools/extraer_ensamble.py`: recupera las colocaciones guardadas en el XML de los ensambles (`cad/ensambles/xml/`); no resuelve mates.
4. `tools/extraer_ejes_cad.py`: contrasta los ejes propuestos con cilindros del STEP (de ahí los 250 mm entre ejes).
5. `tools/registrar_subensambles.py`: relaciona subensambles por piezas compartidas.
6. `tools/integrate_cad.py`: con `config/cad_integration.json` asigna piezas a cuerpos y calcula colocaciones locales; con `--update-config` actualiza la geometría de `config/scara.json`. Escribe `cad/ensambles/integracion_articulada.json`.
7. `tools/generate_world.py`: arma el proto (visual, colisión, física, Hall). Falla si la geometría está desactualizada (`tools/generate_world.py:101-105`).

`tools/calcular_propiedades_cad.py` calcula volúmenes y tensores geométricos (`cad/propiedades/`) sin asignar materiales. Los `tools/check_*.py` son auditorías CAD (choques con el pedestal, interferencias internas, poleas, rodamientos); dejan JSON en `validation/` y requieren OCP.

### 5.4 Preguntas probables del profesor

- **¿Por qué convertir todas las piezas no arma el robot?** La forma de una pieza no dice su colocación, su cuerpo rígido ni sus articulaciones (`docs/PROCESO_Y_ARCHIVOS.md:72`).
- **¿Las masas e inercias son del CAD?** No del todo: son cajas equivalentes provisionales (`config/scara.json`, `model_status`); el CAD da volúmenes, no materiales (ADR 0001).
- **¿Por qué `selfCollision FALSE`?** Las envolventes simplificadas se tocarían entre piezas vecinas; los choques los verifica la URC con `scara/collisions.py` antes de mover.
- **¿El proto se edita a mano?** No, se regenera con `tools/generate_world.py`; el mundo `scara_uci.wbt` sí se mantiene a mano.

---

## 6. URC (`urc/`)

Solo biblioteca estándar de Python (`urc/app.py:3`). Se levanta con `python3 -m urc.app` (opciones `--port 8766`, `--uci-port 9000`, `--sim-port 9001`, `--trayectorias`, `--aproximacion`, `urc/app.py:228-236`).

### 6.1 `app.py` y la API HTTP

`handler_for(session, bench, manager, player)` (`urc/app.py:99-225`) crea la clase del servidor. Seguridad: escucha solo en loopback (`urc/app.py:242`), rechaza `POST` con `Origin` de otra página (403, `urc/app.py:158-161`), exige `application/json` (415) y cuerpo de 1 B a 1 KiB (`urc/app.py:21`, `urc/app.py:166-168`).

| Método y ruta | Qué hace | Código |
| --- | --- | --- |
| `GET /`, `/avisos.js`, `/banco.js`, `/trajectories.js` | Página y scripts | `urc/app.py:139-142` |
| `GET /api/estado` | `Session.snapshot()` | `urc/app.py:143-144` |
| `GET /api/banco` | `Instrumentation.snapshot()` o `{connected: false}` | `urc/app.py:145-146` |
| `GET /api/trayectoria`, `/api/trayectorias` | Trayectoria en edición; archivos de la carpeta | `urc/app.py:147-150` |
| `GET /api/reproduccion` | Estado de la reproducción | `urc/app.py:151-152` |
| `GET /api/eventos?desde=v` | Eventos nuevos desde la versión v | `urc/app.py:135-138` |
| `POST /api/jog`, `/api/jog/stop` | Jog (renovado cada 150 ms) y soltar | `urc/app.py:172-174`, `urc/app.py:24-32` |
| `POST /api/stop`, `/api/halt`, `/api/enable`, `/api/disable`, `/api/home`, `/api/zero`, `/api/park` | Órdenes simples | `urc/app.py:24-32`, `urc/app.py:191-201` |
| `POST /api/ptp` | Sin `confirm` solo planifica (200, duración); con `confirm` mueve (202) | `urc/app.py:175-183`, `urc/app.py:43-63` |
| `POST /api/banco` | Orden al canal de instrumentación | `urc/app.py:184-190` |
| `POST /api/reproduccion/{reproducir,pausa,reanudar,stop}` | Reproducción | `urc/app.py:67-72` |
| `POST /api/trayectoria/{capturar,punto,editar,sobrescribir,borrar,mover,ir,nueva,guardar,cargar}` | Gestor de trayectorias | `urc/trajectories.py:434-445` |

Errores: `Conflict` → 409 (una pregunta, la página confirma y repite); `ConnectionError` → 409; `Rejection` → 400 con `error` y `detail` (D77); `ValueError` → 400; error de archivo → 500 (`urc/app.py:212-223`). Las órdenes del operador se anotan en el registro de eventos antes de ejecutarlas, salvo el jog y la edición (`QUIET`, `urc/app.py:77-90`, D78).

### 6.2 `session.py`: la sesión con la UCI

Un hilo es dueño de los sockets; la interfaz HTTP solo consulta el estado (con `self.lock`) y deja órdenes en una cola (`urc/session.py:1-10`).

| Parte | Líneas | Qué hace |
| --- | --- | --- |
| Constantes | `urc/session.py:26-53` | `PING` 0,25 s; jog 1000/500/200; plazo del jog 0,5 s; 3 segmentos en cola; reposo; orden del homing; `LINK_LATE` 1 s. |
| `__init__` | `urc/session.py:57-107` | Socket que escucha, colas, estado; lee `config/scara.json`, crea el `CollisionChecker`, límites y recorridos; arranca el hilo. |
| `order` | `urc/session.py:111-124` | Orden cruda validada con `check_order`; un `SEG` va a la cola de segmentos. |
| `move_ptp` | `urc/session.py:126-157` | PTP desde la posición estimada: exige referenciado y quieto, valida con `validation.check_ptp`; `dry_run` solo devuelve la duración. |
| `run_segments` | `urc/session.py:159-185` | Encola segmentos ya validados (lo usa la reproducción); `follows` encadena tramos en un mismo movimiento. |
| `home`, `park` | `urc/session.py:187-205` | `HOME` y el PTP al reposo al 100 %. |
| `jog`, `jog_stop` | `urc/session.py:207-270` | Ver sección 2. |
| `stop`, `halt`, `disable` → `_stop` | `urc/session.py:272-282`, `urc/session.py:339-350` | Terminan el jog, cancelan el tramo y el homing, y envían la orden. |
| `snapshot` | `urc/session.py:290-324` | Lo que muestra la página: estado `S`, punto de herramienta, codo, tramo, homing, referencia dudosa, tráfico, errores. |
| `_jog_blocked`, `_guard_jog` | `urc/session.py:455-504` | Freno del jog por motor con referencia: mira 0,15 s adelante el recorrido y 0,15/0,3 s los choques (D70). |
| `_follow_homing`, `_end_homing`, `_park_after_homing` | `urc/session.py:515-560` | Sigue el homing por el modo de `S`; con los cuatro `EV HOMED` y quieto, estaciona. |
| `_watch_link` | `urc/session.py:562-573` | Evento de error si pasa más de 1 s sin `S`. |
| `_receive` | `urc/session.py:642-721` | Interpreta cada línea de la UCI (ver abajo). |
| `_booted` | `urc/session.py:737-754` | Todo `BOOT` deja al robot sin referencia y cancela todo; un `BOOT` a mitad de conexión es F5 (D43, D87). |
| `_send_pending`, `_run` | `urc/session.py:756-819` | Envía órdenes, un `SEG` por vez, el jog por segmentos y el `PING`. |

`_receive` por tipo de mensaje: `S` actualiza el estado y dispara los chequeos (homing, jog, tramo detenido antes de terminar, limpieza de dudas); `EV LOST` marca la referencia dudosa de ese eje (`_lost_steps`, `urc/session.py:723-735`); `EV HOMED` limpia la duda y suma el eje al homing; `OK` libera `in_flight`; `ERR` cancela el tramo y el jog, y los códigos 4, 11 y 12 abortan el homing (`urc/session.py:702-720`). Una línea mala se informa y se descarta sin cortar el enlace (`urc/session.py:642-662`).

### 6.3 `protocol.py`: la gramática del lado de la URC

`check_order` (`urc/protocol.py:50-77`) valida cada orden URC → UCI **con las mismas reglas que el firmware** y la rechaza con el mismo código (`ProtocolError.code`): la URC nunca envía lo que el firmware rechazaría por su forma. `parse_message` (`urc/protocol.py:111-149`) interpreta `BOOT`/`HI` (verifica `scara/1`), `S`, `EV HOMED`, `EV LOST`, `OK`, `ERR` (un código desconocido se muestra igual). Las conversaciones de conformidad obligan a los dos lados a coincidir (D42).

### 6.4 `planner.py`: tramos PTP y LIN

Módulo puro, sin red ni estado (ADR 0005).

- Límites: los del modelo (`config/scara.json`, `default_limits`, `urc/planner.py:60-64`) y los de los motores en unidades de su articulación (`MOTOR_SPEED`, `MOTOR_ACCELERATION`, `urc/planner.py:29-30`). Una prueba verifica que coincidan con `firmware/config.h` (`tests/test_planner.py:147-163`).
- **PTP** (`plan_ptp`, `urc/planner.py:72-95`, D53): un mismo perfil s(t) de 0 a 1 para todas las articulaciones; sus máximos los fija la restricción más exigente entre articulaciones y motores, con M2 = J1 + J2 (`motor_travel`, `urc/planner.py:67-69`). Perfil trapezoidal o triangular (`_trapezoid`, `urc/planner.py:236-261`). Se parte en segmentos de 20 ms estirando el perfil para que entren justos (`_samples`, `urc/planner.py:98-105`); el último es el destino exacto. La fracción de velocidad baja las velocidades, no la aceleración.
- **LIN** (`plan_lin`, `urc/planner.py:136-181`, D54, D76): el punto de herramienta recorre la recta y el rumbo va de uno al otro con el mismo perfil; en cada muestra resuelve la inversa del plano con el codo del tramo (`arm_angles`). Límites: 150 mm/s y 300 mm/s² en la recta, 90 °/s de rumbo; la componente vertical no pasa de M4. La fracción baja también la aceleración. `lin_elbow` (`urc/planner.py:124-133`) rechaza cambiar de codo. `_deviation` mide cuánto se aparta de la recta lo que ejecuta el firmware (interpola lineal en articulaciones) y `lin_tolerance` da la cota: redondeo + cuerda (`urc/planner.py:198-233`).
- Conversiones: `SCALE` (`urc/planner.py:38`), `units_to_si`/`si_to_units`, `joints_from_pose` (XYZ en mm y rumbo en grados → J1–J4, `urc/planner.py:289-306`), `travel`, `inside_range`.

### 6.5 `jog.py`: el jog verificado

Módulo puro (`urc/jog.py:1-20`, D28, D75). `step(q, command, elbow, …)` (`urc/jog.py:67-89`) devuelve la configuración al final del próximo segmento de 20 ms, **sin redondear** (así el punto de herramienta no acumula redondeo; `rounded` redondea solo para el `SEG`, `urc/jog.py:161-163`), o levanta `Blocked` con el motivo.

- Articular: suma velocidad × 0,02 s a una articulación: 10 °/s, 2 °/s con Mayús (`JOINT_SPEED`, `urc/jog.py:37`).
- Cartesiano: A/D mueven el punto de herramienta en Y, W/S en X (20 mm/s, 4 con Mayús, `urc/jog.py:38`); Q/E giran el rumbo con J3 y R/F mueven J4. `_planar` (`urc/jog.py:92-135`) resuelve la inversa con el codo fijo; si algún motor pasaría de 10 °/s (velocidad sin rampa), acorta el paso por bisección; si lo que acorta es el alcance, frena: «borde del alcance».
- Verificaciones: recorrido (desde afuera solo deja volver, `urc/jog.py:142-148`), codo (|J2| no baja de 2°, `ELBOW_MIN`, `urc/jog.py:41`, `urc/jog.py:86-87`) y choques (dentro de la zona de margen solo deja alejarse, `urc/jog.py:151-158`).

### 6.6 `validation.py`: validación previa

Nunca arranca un tramo que no puede terminar (D14, D55). Lanza `Rejection` con un mensaje corto (tramo, qué pasa, qué cambiar) y `detail` con el porqué (`urc/validation.py:35-70`, D77).

- `check_ptp` (`urc/validation.py:117-139`): destino dentro del recorrido y choques en la recta en articulaciones con `first_conflict_leaving` (puede salir de la zona de margen si se aleja, D71). El inicio puede estar afuera: un PTP lo trae de vuelta.
- `check_lin` (`urc/validation.py:142-177`): extremos dentro del recorrido, mismo codo, que la recta no pase cerca de la torre (`_check_reach`, `urc/validation.py:180-198`), recorrido en cada segmento, velocidades y aceleraciones de articulaciones y motores segmento a segmento (`_check_speeds`, `urc/validation.py:201-234`) y choques en cada segmento.
- Un LIN imposible sugiere PTP (`_suggestion`, `urc/validation.py:81-105`).

### 6.7 `trajectories.py`: el gestor de trayectorias

La trayectoria en edición vive en la URC; la página solo la muestra (D13, D29). Cada **punto de trayectoria** es un punto de herramienta X, Y, Z y rumbo, más tipo de tramo, velocidad y espera; **el codo no se guarda** (D88, `urc/trajectories.py:1-15`).

- Formato `scara-trayectoria` versión 2 (`urc/trajectories.py:28-35`); la versión 1 (con articulaciones) se carga descartando el codo (`urc/trajectories.py:236-252`). Ejemplo: `trayectorias/demo-cuadrado-lin.json`.
- `capture` (Espacio, `urc/trajectories.py:97-103`): toma la **posición estimada por pasos** con `robot_pose` (referenciado, quieto y `S` de menos de 1 s, `urc/trajectories.py:351-368`), la valida (`_check_point`: recorrido y choque en reposo, `urc/trajectories.py:257-267`) y la guarda como XYZ con la cinemática directa (`_tool`, `urc/trajectories.py:90-95`).
- `_resolve` y `_joints_for` (`urc/trajectories.py:286-314`): las articulaciones de cada punto se calculan **en cadena**, con el codo del punto anterior mientras llegue; si no, el otro. El primero empieza por J2 negativo (D31).
- `go` («Ir al punto», `urc/trajectories.py:145-157`): PTP al 25 %, planifica y pide confirmación.
- Archivos: `save`, `load` (valida formato, unidades, nombre y cada punto, y dice qué punto falla), `new`; nombres seguros para Windows (`urc/trajectories.py:412-431`).

### 6.8 `playback.py`: la reproducción

(D29, D32, D33, D68, D69.)

- `play` → `_prepare` (`urc/playback.py:191-221`): **valida todos los tramos antes de mover**: el tramo de aproximación (PTP al 25 % × velocidad global, omitido si el robot ya está a menos de un paso del punto, `AT_POINT`, `urc/playback.py:30`), cada tramo de la trayectoria y, con loop, la vuelta del último al primero con los parámetros del punto 1. Exige referencia y que no haya referencia dudosa (`_require_sure`, `urc/playback.py:342-344`).
- `_feed` (`urc/playback.py:278-298`): encola tramos enteros (con sus esperas como segmentos sin movimiento de hasta 1 s) mientras queden menos de 50 segmentos por enviar (1 s): el robot los encadena con su reloj.
- `_follow` (`urc/playback.py:247-276`), cada 20 ms: si el tramo se canceló, si otro movimiento lo reemplazó o si aparece una referencia dudosa (F1), termina la reproducción.
- `pause` (`urc/playback.py:126-134`) es el `STOP` con rampa del firmware; `_paused` (`urc/playback.py:300-319`) guarda lo que faltaba. `resume` (`urc/playback.py:136-162`) recalcula el resto del tramo desde la pose de la pausa, con el mismo tipo (un LIN sigue sobre la misma recta).
- `stop` (`urc/playback.py:164-172`) descarta lo pendiente y frena. Esc pasa por acá (`urc/app.py:191-194`).

### 6.9 `instrumentation.py`: el banco del lado de la URC

Escucha el 9001 y habla `scara-sim/1` (`urc/instrumentation.py:1-46`). `order` (`urc/instrumentation.py:107-122`) traduce el pedido de la página con `order_line` (`urc/instrumentation.py:279`) y anota qué tiene que confirmarse; `_confirm` y `_expire` registran en eventos si el simulador lo aplicó o no en 2 s (D79). **Ningún módulo de la sesión, el planificador ni la validación lo importa**: lo verifica una prueba con `ast` (`tests/test_instrumentation.py:184-191`). Capturar y planificar usan la posición estimada, como con el robot real.

### 6.10 `events.py`: registro de eventos

`EventLog` (`urc/events.py:24-59`, D78): eventos numerados con hora, nivel (`info`, `ok`, `aviso`, `error`), fuente y texto; guarda los últimos 200; uno igual al anterior dentro de 3 s suma una repetición. La página pide lo nuevo con `GET /api/eventos?desde=v`.

### 6.11 La página

| Archivo | Qué hace |
| --- | --- |
| `urc/index.html` | Estructura y script principal: jog por teclado y botones (`urc/index.html:426-690`), Habilitar/Stop/Parada inmediata/Deshabilitar, homing y referencia manual con el dibujo de la pose de reposo, PTP, barra de estado y polling cada 200 ms (`urc/index.html:949-1006`). Esc → `/api/stop`; Tab cambia de modo; Mayús, lento. |
| `urc/avisos.js` | Avisos emergentes y registro de eventos a partir de `/api/eventos` (`urc/avisos.js:1-20`). Los errores quedan hasta cerrarlos. |
| `urc/banco.js` | Panel «Banco de ensayo (solo simulación)»: fallas F1–F5, carga, obstáculos, empujón, mover a mano, «Recargar el mundo…» (`urc/banco.js:51`). Sin canal no aparece. |
| `urc/trajectories.js` | Gestor de trayectorias y reproducción; Espacio captura, Retroceso borra, Enter guarda (`urc/trajectories.js:343-350`). |

### 6.12 Cómo se prueba

`tests/test_urc.py` (sesión, jog, segmentos, homing, pérdida de pasos, HTTP con `FakeUci`), `tests/test_conformidad.py`, `tests/test_planner.py`, `tests/test_lin.py`, `tests/test_jog.py`, `tests/test_trajectories.py`, `tests/test_playback.py`, `tests/test_demos.py`, `tests/test_instrumentation.py`, `tests/test_eventos.py` (detalle en la sección 8).

### 6.13 Preguntas probables del profesor

- **¿La URC es un backend?** Es la Unidad Remota de Coordinación, el «programa externo» de la consigna; su rol de red no la define (glosario). Sirve la página y es servidor TCP de la UCI (D1, D15).
- **¿Por qué la URC escucha y la UCI se conecta?** Con el robot real, quien se conecta es socat al abrir el USB; la URC queda siempre esperando y el robot puede reiniciarse sin tocarla (D1).
- **¿Por qué la cinemática y la planificación están en la URC?** El UNO no puede calcular la inversa a la frecuencia de una recta; ejecutar con el reloj del firmware evita tirones por la red. Es la división de GRBL/Klipper (D6, ADR 0005).
- **¿Cómo frena el jog si se cae el navegador, la URC o el enlace?** Tres frenos: la página (150 ms, blur), la URC (500 ms sin renovar) y el watchdog del firmware (1 s) (D37).
- **¿Qué verifica el jog con referencia?** Cada segmento antes de enviarlo: recorrido, codo (cartesiano) y choques (D75). Como el robot frena en el último segmento enviado, que ya está verificado, no hace falta mirar más adelante.
- **¿Por qué al soltar la tecla no se manda STOP?** El STOP frena con rampa y tarda más que lo encolado (73 ms contra 60 ms a 10 °/s); el robot frena al vaciarse la cola (D75).
- **¿Qué diferencia hay entre un tramo PTP y uno LIN en el código?** PTP: un perfil común en articulaciones, recta en el espacio articular (`plan_ptp`). LIN: perfil sobre la recta del punto de herramienta e inversa en cada muestra de 20 ms (`plan_lin`).
- **¿Qué pasa si una recta es imposible?** `check_lin` la rechaza antes de mover nada, dice el tramo, el motivo y qué punto cambiar, y sugiere PTP (D14, D55, D77).
- **¿Qué se guarda en una trayectoria?** Puntos de herramienta (X, Y, Z, rumbo) con tipo, velocidad y espera; no el camino ni el codo (D13, D88).
- **¿Desde qué posición se captura?** Siempre desde la posición estimada por pasos, nunca desde el simulador (D21, ADR 0004).
- **¿Qué es el tramo 0?** El tramo de aproximación: PTP lento desde donde está el robot hasta el primer punto, calculado al dar play y no guardado (D32, D33).
- **¿Qué hace la pausa?** Un STOP con rampa; al reanudar, la URC recalcula lo que faltaba del tramo desde la pose de la pausa (D69).
- **¿Qué hace la URC con un `EV LOST`?** Marca la referencia del eje como dudosa, lo avisa, frena una reproducción en curso y no deja dar play hasta un homing (D65, `urc/playback.py:264-268`).

---

## 7. Cinemática y colisiones (`scara/`)

### 7.1 `kinematics.py`

Convención: SI, Z vertical, **J4 positivo hacia abajo** (`scara/kinematics.py:1`). Geometría de `config/scara.json`: l1 = l2 = 0,25 m, `shoulder_z`, `elbow_z_offset`, `tool_z_offset`.

| Función | Qué hace | Líneas |
| --- | --- | --- |
| `load_config` | Lee `config/scara.json` | `scara/kinematics.py:9-12` |
| `validate_joints` | Verifica que J1–J4 estén dentro del recorrido (con holgura) | `scara/kinematics.py:29-35` |
| `forward` (directa) | `x = l1 cos q1 + l2 cos(q1+q2)`, `y = …`, `z = shoulder_z + elbow_z_offset + tool_z_offset − q4`, rumbo = q1+q2+q3 envuelto | `scara/kinematics.py:38-48` |
| `arm_angles` (inversa del plano) | q1 y q2 para un punto (x, y) con el codo del signo pedido, **sin límites** (ley del coseno) | `scara/kinematics.py:51-61` |
| `inverse` (inversa completa) | Con XYZ y rumbo: prueba los dos codos (o el pedido) y vueltas de ±2π en J1 y J3, descarta lo que sale del recorrido y elige la solución más cercana a `current` normalizando por el recorrido | `scara/kinematics.py:64-102` |
| `trajectory_duration`, `interpolate` | Perfil quíntico del banco viejo | `scara/kinematics.py:105-128` |

**Dónde se usa cada una:**

| Función | Usada por | Para qué |
| --- | --- | --- |
| `forward` | `planner.tool_point` (`urc/planner.py:184-186`) | Punto de herramienta que muestra la página (`urc/session.py:326-330`); captura como XYZ (`urc/trajectories.py:90-95`); extremos de la recta LIN (`urc/planner.py:155`); desvío de la recta (`urc/planner.py:198-210`); jog cartesiano (`urc/jog.py:99`); cercanía a la torre (`urc/validation.py:191`); auditoría `tools/check_collisions.py:176`. |
| `arm_angles` | `plan_lin` (`urc/planner.py:172`), `jog._planar` (`urc/jog.py:107`), y dentro de `inverse` | Inversa rápida en cada muestra de 20 ms con el codo ya fijado. |
| `inverse` | solo vía `planner.joints_from_pose` (`urc/planner.py:289-306`) | «Ir a una pose» por XYZ (`urc/app.py:57-60`) y resolver los puntos de trayectoria en cadena (`urc/trajectories.py:305`). |
| `trajectory_duration`, `interpolate` | solo `tests/test_kinematics.py` | Resto del banco viejo; el PTP actual usa trapezoidal (D53 descartó el quíntico). |

**El firmware no tiene cinemática**: solo transmisión (ADR 0005).

### 7.2 `collisions.py`

`CollisionChecker` (`scara/collisions.py:36-200`), sin OCP ni encoders:

- Carga las cajas por instancia CAD de `cad/ensambles/integracion_articulada.json` (`piece_boxes`, `scara/collisions.py:21-33`) y falla si la geometría no coincide con `config/scara.json` (`scara/collisions.py:40-41`).
- Obstáculos: el entorno de `config/scara.json` (`suelo_de_ensayo`, `pedestal_de_ensayo`) ampliado por el margen (1 mm), y las cajas de la base fija **solo contra la herramienta y la carga** (`scara/collisions.py:50-67`). **No compara otros pares internos** (`scara/collisions.py:1-5`; `collision_check.scope` en `config/scara.json`).
- `first_conflict(start, target)` (`scara/collisions.py:69-77`, `142-192`): acota **todo** el camino lineal en articulaciones. Por intervalo, toma la caja en el punto medio ampliada por una cota del desplazamiento XY de sus vértices (que depende del recorrido de J1, J1+J2 y J1+J2+J3); si no prueba separación, subdivide; al llegar a la resolución (0,25 mm) o a 4096 intervalos, **rechaza**. Es conservador: puede rechazar de más, nunca aprobar un choque dentro del modelo de cajas.
- `first_conflict_leaving` (`scara/collisions.py:79-111`, D71): deja salir de la zona de margen si la separación crece.
- `clearance(q)` (`scara/collisions.py:113-132`): separación quieta, la usa el jog para decidir si se aleja.

Lo usan: la sesión (`urc/session.py:97`), `validation.check_ptp`/`check_lin`, el jog (`urc/jog.py:151-158`, `urc/session.py:479-485`) y el gestor (`urc/trajectories.py:257-267`).

### 7.3 `frames.py` y `dynamics.py`

- `frames.py`: transformaciones rígidas 4×4 y `chain_frames(q, config)` (`scara/frames.py:25-33`), los marcos de BASE, ARM, FOREARM, WRIST y TOOL. Lo usan `collisions.py` y `tools/integrate_cad.py`.
- `dynamics.py`: `box_with_payload` (`scara/dynamics.py:4-25`), masa, centro e inercia de una caja equivalente más un cubo de carga de 40 mm. Lo usa `tools/generate_world.py` para el `toolMass`, el centro de masa y la inercia de la herramienta del proto.

### 7.4 Preguntas probables del profesor

- **¿Dónde usan la directa y dónde la inversa?** Ver la tabla de 7.1. Resumen: la directa para mostrar y guardar el punto de herramienta; `arm_angles` en cada muestra del LIN y del jog cartesiano; `inverse` para poses escritas y puntos de trayectoria.
- **¿Cómo eligen entre las dos soluciones de la inversa?** Por la configuración del codo: J2 negativo preferido (D31); en trayectorias, el codo del punto anterior mientras llegue (D88); en la inversa completa, la solución más cercana a la configuración actual.
- **¿Qué pasa en la singularidad del brazo estirado?** Un LIN no puede cruzarla (cambio de codo, D31); el jog cartesiano frena con |J2| < 2° (`urc/jog.py:41`).
- **¿Cómo verifican choques en un camino continuo y no solo en puntos?** Con cotas de desplazamiento por intervalo y subdivisión (`scara/collisions.py:152-192`): demuestra separación en todo el intervalo o rechaza.
- **¿Verifican choques entre el brazo y el antebrazo?** No: el alcance es robot contra entorno y herramienta contra la base fija (`config/scara.json`, `collision_check.scope`). Es un límite declarado.
- **¿Por qué cajas y no las mallas?** Para que sea rápido a 50 segmentos por segundo; las poses invasivas se contrastaron con BREP (`tests/test_collisions.py:1-5`).

---

## 8. Pruebas

### 8.1 Cómo se corren

```sh
python3 -m unittest discover -v                                   # todo, sin Webots ni Internet
python3 -m unittest tests.test_firmware tests.test_conformidad -v  # firmware y conformidad
python3 tools/verificar_enlaces.py                                # enlaces internos de los .md
```

Corrida en esta rama (macOS, `c++` de Apple, sin socat, sin `arduino-cli`, sin OCP, sin `mistune`): **218 pruebas, OK, 8 omitidas, 76 s**. Coincide con lo registrado en `validation/campana/INFORME.md:103`.

| Se omite | Por qué | Pruebas |
| --- | --- | --- |
| Propiedades CAD con BREP | Falta el Python con OCP (OpenCascade) | 3, `tests/test_cad_properties.py:81-82` |
| Exportar maestro | Falta `mistune` (`tools/requirements-docs.txt`) | 2, `tests/test_exportar_maestro.py:7` |
| Camino serie | Falta socat (y un compilador POSIX; en Windows, los de MSYS2) | 2, `tests/test_serie_socat.py:51` |
| Compilar para el UNO | Falta `arduino-cli` (o `ARDUINO_CLI`) | 1, `tests/test_uno.py:74` |
| Todo lo C++ | Sin compilador (`CXX`, `c++`, `g++`, `clang++` o el `g++` de Webots) | `tests/test_firmware.py:28-38` |

### 8.2 Las tres costuras (seams)

Las pruebas siguen las tres costuras de la spec #2:

1. **Seam 1, firmware por su protocolo:** el núcleo real compilado en la PC con `FakeHal` corre las conversaciones de conformidad.
2. **Seam 2, URC por sus dos bordes:** las mismas conversaciones contra la URC real con una UCI falsa por TCP, y los endpoints HTTP; el planificador y la validación como módulos puros.
3. **Seam 3, Webots:** los ensayos y la campaña de `validation/` (sección 9), fuera de `unittest`.

**La capa de hardware falsa** (`firmware/test/conversacion.cpp:25-69`): reloj controlable (`now`), contadores de pasos por motor, estado de los drivers (arranca en `true` para verificar que el firmware los corte al arrancar), y una planta de Hall con los imanes en los extremos de cada articulación con la misma geometría que Webots (`firmware/test/conversacion.cpp:22-23`), Hall trabados (F3) y deslizamiento de un motor (F1). El programa `conversacion` (`firmware/test/conversacion.cpp:91-248`) lee cada archivo y lo ejecuta renglón por renglón.

**Formato de una conversación** (`firmware/test/conversaciones/LEEME.md`):

| Renglón | Significado |
| --- | --- |
| `> LÍNEA` | La URC envía. |
| `< LÍNEA` | La UCI tiene que haber enviado (`*` = cualquier campo). Los `S` periódicos no esperados se saltean. |
| `+ N` / `~ N` | Avanza el reloj N ms de a 1 ms; con `~`, la URC manda `PING` cada 250 ms. |
| `= M1 a M2 b … EN e` | Pasos netos emitidos a cada motor; drivers con o sin corriente. |
| `! reinicio`, `! iman J1..J4`, `! hall j estado`, `! desliza Mm n` | La planta: F5, Hall por geometría, F3, F1. |

Ejemplo real (`firmware/test/conversaciones/jog_j1.txt:4-10`): `> JOG 1 + 450`, `+ 1000`, `= M1 80 M2 80 M3 0 M4 0`, `< S JOG 0 450 0 0 0 0 16 0`. En 1 s a 4,5 °/s, M1 y M2 dan los mismos 80 pasos: el acople.

**La UCI falsa en Python** (`FakeUci`, `tests/test_urc.py:26-65`): un socket que se conecta a la URC como Webots o socat, con `send`, `receive` (ignora `PING`) y `silent`. `tests/test_conformidad.py:54-123` reproduce cada conversación desde el lado de la URC: cada `>` la URC tiene que poder enviarla (o negarse con el mismo `ERR 1/2/3` del firmware; un `SEG` que el firmware rechazaría con `ERR 9` la URC no lo envía), y cada `<` la UCI falsa la envía y la URC tiene que entenderla (estado, `BOOT`, `OK`, `EV LOST`, `ERR`). `+`, `=` y `!` no los ve la URC.

### 8.3 Qué cubre cada archivo

| Archivo | Pruebas | Qué cubre |
| --- | --- | --- |
| `tests/test_firmware.py` | 3 | Conversaciones contra el núcleo; transmisión con 1/1 a 1/32; sin memoria dinámica. |
| `tests/test_conformidad.py` | 1 (24 subtests) | Las mismas conversaciones contra la URC. |
| `tests/test_uno.py` | 2 | Generador de pulsos en la PC; compilación y presupuesto del UNO. |
| `tests/test_serie_socat.py` | 2 | URC ↔ socat ↔ PTY ↔ `uci_serie`: opera el firmware; cerrar socat desconecta y reabrir da `BOOT`. |
| `tests/test_planta.py` | 1 | Modelo N2 (`stepper.cpp`). |
| `tests/test_hall.py` | 4 | Flancos de los Hall del proto contra `config.h`; imanes en los dos extremos; en reposo solo J4 activo; ancho. |
| `tests/test_urc.py` | 51 | Sesión, jog por motor y por segmentos, tramos, homing, pérdida de pasos, HTTP. |
| `tests/test_planner.py` | 14 | PTP: llegada conjunta, M2 = J1 + J2, perfil, límites iguales a `config.h`, poses por XYZ. |
| `tests/test_lin.py` | 20 | LIN: recta, tolerancia, rumbo, velocidad, codo; rechazos (alcance, codo, límite, velocidad, choque) y sus mensajes. |
| `tests/test_jog.py` | 7 | Jog verificado como módulo puro. |
| `tests/test_trajectories.py` | 18 | Gestor por HTTP: capturar, escribir, editar, guardar, cargar, versión 1, codo en cadena. |
| `tests/test_playback.py` | 22 | Reproducción por HTTP: validación previa, aproximación, loop, pausa, stop, ERR, F1. |
| `tests/test_demos.py` | 2 | Las tres demos cargan y se reproducen 2 vueltas desde el reposo. |
| `tests/test_instrumentation.py` | 13 | Canal de instrumentación con un controlador falso; ningún módulo del robot lo importa. |
| `tests/test_eventos.py` | 14 | Registro de eventos y confirmación de órdenes del banco. |
| `tests/test_kinematics.py` | 5 | Directa/inversa, límites, rumbo, quíntico, carga. |
| `tests/test_collisions.py` | 11 | Pedestal, margen, salida de la zona, torre, carga, muestreo independiente. |
| `tests/test_cad_integration.py` | 5 | Colocaciones CAD y poleas siguen a las articulaciones. |
| `tests/test_cad_properties.py` | 5 | Propiedades geométricas (3 con OCP). |
| `tests/test_campana.py` | 5 | Escenarios completos, puertos, última campaña aprobada y versión identificada. |
| `tests/test_defensa.py` | 8 | `docs/DEFENSA.md` cita decisiones, rutas, comandos y textos de la página que existen. |
| `tests/test_exportar_maestro.py` | 2 | Exportación del maestro a HTML. |
| `tests/test_verificar_enlaces.py` | 3 | Ningún enlace interno roto en los `.md`. |

Las 24 conversaciones (`firmware/test/conversaciones/`): `saludo`, `estado_periodico`, `errores`, `habilitar`, `zero`, `stop_halt`, `watchdog`, `reinicio` (F5), `jog_j1`, `jog_ejes`, `jog_motor`, `jog_hall`, `homing`, `homing_repetido`, `homing_hall_trabado` y `homing_hall_ausente` (F3), `perdida_pasos` y `perdida_pasos_acople` (F1), `seg_interpolacion`, `seg_cola`, `seg_demora`, `seg_errores`, `seg_stop`, `seg_watchdog`.

### 8.4 Preguntas probables del profesor

- **¿Cómo prueban el firmware sin placa y sin Webots?** Compilando el núcleo real en la PC con una capa de hardware falsa y corriendo conversaciones de texto (D39).
- **¿Qué es una conversación de conformidad?** Un intercambio de ejemplo de `scara/1` que se ejecuta contra el firmware y contra la URC: la definición ejecutable del protocolo (glosario, D42).
- **¿Cómo se aseguran de que la URC y el firmware entienden igual el protocolo?** Las mismas conversaciones corren contra los dos lados; si uno cambia y el otro no, falla (`tests/test_firmware.py`, `tests/test_conformidad.py`).
- **¿Prueban el UNO?** Se prueba el generador de pulsos en la PC, la compilación y el presupuesto de memoria con `arduino-cli`, y el camino serie con socat y un PTY. No con la placa (D49).
- **¿Qué no cubren las pruebas automáticas?** Webots: eso lo cubre la campaña. Y lo visual de la ventana, que queda para QA humana.

---

## 9. Herramientas y campaña de validación

### 9.1 `tools/espiar_enlace.py`

Se interpone entre la UCI y la URC sin cambiar nada y anota cada línea con su hora relativa y su sentido (`tools/espiar_enlace.py:1-12`). Escucha en 9000 y 9001 y reenvía a una URC levantada en 9010 y 9011 (`tools/espiar_enlace.py:60-72`). Uso:

```sh
python3 -m urc.app --uci-port 9010 --sim-port 9011
python3 tools/espiar_enlace.py --registro /tmp/dialogo.log
```

Con esto se sacaron las transcripciones del informe (`docs/informe/dialogo/`).

### 9.2 `tools/exportar_maestro.py`

Convierte `docs/maestro/SCARA-Master-v2.md` a HTML con `mistune` y lo imprime a PDF con Edge o Chrome sin interfaz (`tools/exportar_maestro.py:1-29`). `<!-- SALTO DE PAGINA -->` fuerza un salto. Requiere `tools/requirements-docs.txt` (`docs/maestro/README.md`).

### 9.3 Otras

| Herramienta | Qué hace |
| --- | --- |
| `tools/verificar_enlaces.py` | Enlaces internos rotos en los `.md` (ignora código y `historico/`). |
| `tools/generate_world.py` | Genera `SCARA.proto` (sección 5). |
| `tools/convertir_cad.py`, `tools/integrate_cad.py` y el resto del pipeline CAD | Sección 5.3. Requieren OCP. |
| `tools/check_*.py` | Auditorías CAD; resultados en `validation/*.json`. |

### 9.4 La campaña (`validation/campana/`)

- `validation/campana/campana.py`: **un ejecutor** (D73). Compila el controlador, corre de a uno los **diez** ensayos en Webots (`ENSAYOS`, `validation/campana/campana.py:46-57`: protocolo, transmisión, segmentos, homing, instrumentación, pérdida de pasos, reproducción, campaña, físicas, movido a mano), cada uno en sus puertos (9100–9133, así no choca con una URC abierta) y con un tiempo máximo. Escribe `campana.json` con el commit, el SHA-256 del controlador compilado, del mundo, del proto y de las demos, y el resultado por escenario. Solo registra una campaña completa con el árbol sin cambios.
- `validation/campana/ensayo_webots.py`: lo que ningún ensayo cubría (`validation/campana/ensayo_webots.py:1-22`): F3 con Hall de J1 inactivo, homing repetido, teach & play con puntos capturados, las tres demos, F5 en plena reproducción. Arranca con el desvío al azar, como el operador.
- `validation/campana/INFORME.md`: escenarios C1–C4, H1–H2, T1–T3, F1–F5, P1–P3, todos **OK** en la campaña del 06/11/2026, commit `39df64d`, macOS 27.2 con Webots R2025a (`validation/campana/INFORME.md:9-19`, `validation/campana/INFORME.md:37-56`).
- `validation/campana/registros/`: un registro por ensayo.

Cada ensayo maneja la **sesión real de la URC** (las clases `Session`, `Player`, `TrajectoryManager`, `Instrumentation`) contra el controlador compilado, verifica tolerancias con `assert` y termina con `ENSAYO OK`.

### 9.5 Preguntas probables del profesor

- **¿Cómo saben qué versión validaron?** Por el commit y el SHA-256 del binario del controlador, del mundo, del proto y de las demos en `campana.json`; el ejecutor compila antes de correr (D73).
- **¿Por qué los ensayos corren de a uno?** Webots tiene que ir a tiempo real; dos a la vez lo atrasan (D26, D73).
- **¿La campaña prueba un robot?** No: prueba el diseño simulado con parámetros provisionales (ADR 0001, `validation/campana/INFORME.md:105-111`).
- **¿Cómo se ve lo que pasa por el enlace?** Con `tools/espiar_enlace.py`, o en el panel de diagnóstico de la página (tráfico de los últimos mensajes, `urc/session.py:66`).

---

## 10. Problemas conocidos y textos viejos

### 10.1 Homing intermitente que no terminó

**Qué pasó.** En una corrida parcial de la campaña, previa a la campaña registrada, el homing del paso 2 del ensayo de la campaña (el que se repite después del aborto por F3) siguió «en curso» **más de 240 s**. No se repitió en otras tres corridas. Queda como **intermitente, sin causa encontrada** (`validation/campana/INFORME.md:78`; también `docs/informe/INFORME-SCARA.md:684`). El hallazgo se agregó al informe con la campaña de los límites de D76 (commit `0dcb466`, 01/11/2026), cuando las corridas eran en Windows 11 (`validation/campana/INFORME.md:107`). La campaña registrada del 06/11 en macOS pasó H1, H2 y F3b (`validation/campana/registros/campana.log`, pasos 1–2), y la reproducción de #51 completó 6 de 6 homings con `basicTimeStep 2` (`validation/homing/reproduccion_51.log`).

**Lo que se puede afirmar desde el código** (no es la causa; acota qué tuvo que pasar):

- El ensayo espera el fin del homing **240 s del reloj de la PC** (`validation/campana/ensayo_webots.py:73-78`).
- El firmware no puede quedar en homing indefinidamente: cada eje tiene un tope de 60 s **de su reloj**, que en Webots es tiempo simulado, y aborta con `ERR 11` (`firmware/firmware.h:33`, `firmware/firmware.cpp:424-428`). Un homing normal dura unos 55 s simulados (D72).
- La URC cambia el estado «en curso» solo al recibir mensajes: los cuatro `EV HOMED`, un `S` que deja de decir `HOMING` sin los cuatro ejes, un `ERR 4/11/12`, un `BOOT`, o si en 1 s el `S` nunca mostró `HOMING` (`urc/session.py:515-535`, `urc/session.py:690-697`, `urc/session.py:719-720`, `urc/session.py:742`). Una desconexión de la UCI **no** cierra el homing (`_detach`, `urc/session.py:633-640`).
- Entonces, para seguir «en curso» 240 s reales hizo falta una de dos: que el `S` siguiera diciendo `HOMING` porque la simulación iba muy por debajo del tiempo real (menos de ~0,25× para estirar 55 s simulados a 240 s reales), o que los `S` dejaran de llegar (UCI desconectada sin reconectarse, o Webots trabado). El ensayo no registra los eventos de la URC, así que no se puede distinguir. **Son hipótesis, no verificadas.** En otra corrida de esa época, la UCI se desconectó en pleno jog con Webots a ~0,66× (`docs/DEFENSA.md:59`).

**Qué hacer si aparece en la demo:**

1. Mirar la barra de estado y Webots. ¿El modo dice «Homing» y el brazo se mueve? ¿El indicador de velocidad de Webots está cerca de 1×? Si se mueve, **esperar**: cada eje aborta solo a los 60 s simulados.
2. Si no se mueve o aparece «Sin estado de la UCI hace más de 1 s» (`urc/session.py:569-570`): **Esc o «Stop»**. La URC cierra el homing («frenado por el operador») y envía `STOP` (`urc/session.py:339-350`); el firmware aborta el homing sin declarar referencia (`firmware/firmware.cpp:604-608`).
3. **Repetir «Homing…».** Después de un `STOP` se puede repetir: el firmware recuerda qué ejes tienen una cuenta que salió de una referencia (`found_`, D72; conversación `homing_repetido.txt`).
4. Si el estado no vuelve: comprobar que Webots esté en **Real-time** y que no haya otro Webots abierto (D26). Si sigue trabado, **«Recargar el mundo…»** en el banco de ensayo (`urc/banco.js:51`, `RECARGA` → `worldReload()`): la UCI arranca de nuevo, sin referencia; «Habilitar motores» y homing otra vez.
5. Plan B si el tiempo apremia y el robot está en la pose de reposo: **«Referencia manual…»** (`ZERO`, exige corriente y robot quieto, `firmware/firmware.cpp:237-250`). Es menos precisa que el homing (D30), pero permite seguir con teach & play.
6. Qué decirle al profesor: es un hallazgo registrado en la campaña, una vez en cuatro corridas y sin causa encontrada; el sistema queda del lado seguro, porque el firmware acota cada eje a 60 s y `Stop` siempre corta.

### 10.2 Watchdog y velocidad de Webots (issue #51)

El watchdog cuenta tiempo simulado (`webots/controllers/scara_uci/scara_uci.cpp:732`) y la URC manda `PING` cada 250 ms reales (`urc/session.py:26`). A más de 3× el margen se achica, y a 4× o más el watchdog salta solo con `ERR 4`. La reproducción aislada dio 6/6 homings sin aborto (3 en Real-time, 3 en Fast a 2,38–2,70×) y 1/1 aborto con `basicTimeStep 8` a 12,77× (`validation/homing/reproduccion_51.log`, `docs/UCI_WEBOTS.md:25-29`). Regla: **Real-time, ~1× o menos**. Desacoplar el watchdog de la velocidad de Webots queda como trabajo futuro (`docs/informe/INFORME-SCARA.md:690`).

### 10.3 Otros hallazgos de la campaña

(`validation/campana/INFORME.md:74-80`.)

- La posición física se aparta de la recta un poco más que la estimada (sigue a los pasos con el atraso del rotor N2): tolerancias de 0,38 mm la estimada y 0,46 mm la física.
- Con D76, el `EV LOST` de J4 se lee con hasta 2 pasos completos de error: el Hall se lee una vez cada 2 ms y J4 cruza a 40 mm/s.
- La pausa no siempre frena a 0,05 mm de la recta (0,164 mm en la corrida registrada): es el escalón de los pasos.
- Dos ensayos tenían esperas frágiles; se corrigieron sin aflojar lo que miden.

### 10.4 Límites declarados del código

- **Sin placa:** el firmware compila para el UNO y el camino serie se probó con un PTY y socat, no con hardware (README, D49).
- **Parámetros provisionales:** motores de N2 (familia más cercana o supuestos), ubicación de los Hall, límites articulares, envolventes de colisión (ADR 0001, D64, D10).
- **N2 sin términos cruzados entre M1 y M2 ni modelo eléctrico** (ADR 0006, `webots/controllers/scara_uci/stepper.h:230-235`).
- **Choques:** solo robot contra entorno y herramienta contra la base; Webots con `selfCollision FALSE`.
- **F2 no se detecta** hasta el próximo cruce de un Hall: J4 cae y la estimada no cambia (`docs/DEFENSA.md:454`).
- **Build desde el editor de Webots** no se probó; la vía de terminal sí (`docs/UCI_WEBOTS.md:54`). En macOS, `--minimize` con `--no-rendering` deja Webots sin iniciar controladores (`docs/UCI_WEBOTS.md:95`).

### 10.5 Textos viejos: contradicciones con el código

Manda el código. Encontramos:

| Texto | Qué dice | Qué hace el código |
| --- | --- | --- |
| `docs/UCI_WEBOTS.md:32` | «La planta todavía no modela el driver sin corriente: en Webots J4 no cae con `DISABLE`.» | Sí lo modela: sin corriente la fuerza es 0 y J4 cae (`webots/controllers/scara_uci/scara_uci.cpp:537-543`, `675-692`; D60). |
| `docs/UCI_WEBOTS.md:34` | El mundo arranca exactamente en la pose de reposo; el desvío llega con el homing. | El desvío ya está: ±10° por defecto (`webots/controllers/scara_uci/scara_uci.cpp:969`), y el mundo no pasa `--desvio` (`webots/worlds/scara_uci.wbt:66-72`). |
| `docs/UCI_WEBOTS.md:79` | El banco inyecta «las fallas F2–F5». | También F1 (`webots/controllers/scara_uci/scara_uci.cpp:834-836`), además de obstáculos, empujón y mover a mano. |
| `docs/UCI_WEBOTS.md:3` | Cubre bala trazadora, protocolo y transmisión. | Cubre todo el sistema (homing, segmentos, LIN, jog verificado, banco…). |
| `docs/DEFENSA.md:29` | Campaña del commit `6ddc4ca`, puertos 9100–9121, unos 15 min. | La registrada es `39df64d`, con diez ensayos en 9100–9133 y unos 18–20 min (`validation/campana/INFORME.md:13`, `31`; `validation/campana/campana.py:46-57`). |
| `docs/DEFENSA.md:466` | «No se probó […] en macOS.» | La campaña registrada es en macOS 27.2 (`validation/campana/INFORME.md:18`, `107`). Con la placa, sigue sin probarse. |
| `docs/DEFENSA.md:37` | La suite tarda unos 3 minutos. | ~76–79 s (esta corrida y `validation/campana/INFORME.md:103`). |
| D56 en `docs/REGISTRO_DE_DECISIONES.md` | Búsqueda a 8 °/s y vuelta al reposo al 50 %. | 15 °/s y 10 mm/s (`firmware/firmware.h:29`) y reposo al 100 % (`urc/session.py:50`); lo dice D72. |
| D73 | «Los ocho ensayos.» | Son diez (`validation/campana/campana.py:46-57`). |
| D62 | Formato versión 1 con articulaciones. | Versión 2 con punto de herramienta (`urc/trajectories.py:28`); D88. |
| `validation/campana/campana.py:16` | La campaña dura ~25 min. | El informe registra 18–20 min (`validation/campana/INFORME.md:31`). |

---

## 11. Índice rápido: qué decisión explica qué

| Tema | Decisiones y ADR | Código |
| --- | --- | --- |
| Simulación sin hardware, parámetros provisionales | ADR 0001 | `config/scara.json` |
| Un firmware para Webots y Arduino | D3, ADR 0002, D39 | `firmware/hal.h` |
| Protocolo en unidades articulares | D4, D5, D27, ADR 0003 | `firmware/transmission.h`, `urc/protocol.py` |
| Canal de instrumentación aparte | D2, D59, D61, ADR 0004 | `Bench`, `urc/instrumentation.py` |
| La URC planifica, el firmware ejecuta | D6, D50–D53, ADR 0005 | `urc/planner.py`, cola en `firmware/firmware.cpp` |
| Modelo de motores N1/N2 y pérdida de pasos | D8, D64, D65, D67, ADR 0006 | `webots/controllers/scara_uci/stepper.h`, `checkLostSteps` |
| Jog desde la URC | D12, D28, D37, D46, D58, D70, D75, ADR 0007 | `urc/jog.py`, `Session.jog`, `handleJog` |
| Homing y Hall | D10, D11, D56, D57, D72 | `advanceHoming`, `Plant::sense`, `tools/generate_world.py` |
| Paradas | D40, D41, D52 | `stop`, `halt`, `disable`, `startRamp` |
| Trayectorias y reproducción | D13, D14, D22, D29, D32, D33, D54, D55, D68, D69, D77, D88 | `urc/trajectories.py`, `urc/playback.py`, `urc/validation.py` |
| Límites de los motores | D45, D76 | `firmware/config.h`, `urc/planner.py:29-36` |
| Tiempo real en Webots | D26, issue #51 | `WebotsHal::millis` |
| Campaña | D73, D74 | `validation/campana/` |
