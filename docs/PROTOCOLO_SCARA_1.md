# Protocolo `scara/1`

Especificación del contrato de mensajes entre la URC y el firmware de la UCI. Reemplaza al borrador de la [investigación del 29/10/2026](INVESTIGACION_TEACH_AND_PLAY_2026-10-29.md#5-protocolo-propuesto-scara1-borrador) y, cuando se retire (issue #17), al banco provisional [`scara-dev/1`](PROTOCOLO_SCARA_DEV_1.md).

**Estado:** completo para conexión, corriente, jog, paradas, watchdog y reinicio (issue #6), y para los segmentos temporizados `SEG` y `OK` (issue #9). `HOME` y `EV` tienen su forma fijada acá, pero los implementan el homing (#8) y la pérdida de pasos (#15); hasta entonces el firmware responde `ERR 1 comando` a `HOME`, y la URC no lo envía. Las decisiones están en el [registro](REGISTRO_DE_DECISIONES.md): D4, D5, D24, D27, D35–D37, D40–D43, D46 y D50–D53.

## Transporte y formato

- La URC escucha en TCP 9000 y la UCI se conecta (D1, D24). Con el robot real, socat puentea el USB del Arduino a ese puerto; por serie, 115200 baudios.
- ASCII imprimible (bytes 32 a 126), una línea por mensaje terminada en LF. El CR se ignora, así funciona el `println` de Arduino.
- Hasta 64 bytes con el LF. Una línea más larga se descarta entera y la UCI responde `ERR 3 largo`. Una línea con un byte fuera de ASCII imprimible se descarta entera con `ERR 1 comando` (un byte nulo cortaría la línea sin avisar).
- Campos separados por uno o más espacios. Una línea vacía no es un mensaje.
- Los números son enteros (ADR 0003): centésimas de grado en J1–J3 (`9000` = 90,00°) y centésimas de mm en J4 (`12000` = 120,00 mm).
- Se puede hablar a mano (D4): `nc -l 9000` hace de URC frente a Webots, y el monitor serie del IDE de Arduino, frente a la UCI real.

## URC → UCI

Ninguna orden tiene respuesta si sale bien: el efecto se ve en el próximo `S` (D35). Si sale mal, la UCI responde `ERR`. La forma (comando, argumentos, largo) se revisa antes que el estado: un `JOG` mal escrito es `ERR 2` aunque los drivers estén sin corriente.

| Mensaje | Efecto | Errores |
| --- | --- | --- |
| `HELLO` | Saludo. La URC lo envía al aceptar cada conexión. Responde `HI`. | — |
| `PING` | Renueva el watchdog. La URC lo envía cada 250 ms. | — |
| `STATUS` | Pide el estado ya. Responde `S`. | — |
| `ENABLE` | Da corriente a los cuatro drivers (D40). Si ya tenían, no cambia nada. | — |
| `DISABLE` | Frena, corta la corriente y pierde la referencia (D40). | — |
| `JOG j ± vel` | Jog articular de `j` (1–4) a `vel` centésimas por segundo (1–1000). Reemplaza al jog anterior. | `ERR 6` sin corriente |
| `JOG Mm ± vel` | Jog por motor, un modo de prueba (D46): mueve solo el motor `m` (1–4), sin compensar el acople M1/M2. `vel` va en las unidades de la articulación de ese motor (θM/4 en M1–M3, mm de J4 en M4), 1–1000. Reemplaza al jog anterior. | `ERR 6` sin corriente |
| `JOG STOP` | Frena el jog, articular o por motor. | — |
| `STOP` | Frena todo y conserva la referencia (D41). Los segmentos frenan con rampa y la cola se vacía (D52); el jog, en seco. | — |
| `HALT` | Parada inmediata. Si había movimiento, la referencia se pierde (D41). | — |
| `ZERO` | Referencia manual: declara que el robot está en la pose de reposo (D30) y deja los cuatro ejes referenciados. | `ERR 6` sin corriente; `ERR 5` con movimiento |
| `HOME [j]` | Homing de todos los ejes o de `j` (D11). **Issue #8.** | |
| `SEG n ms q1 q2 q3 q4` | Encola el segmento `n` (1–999999999): llegar a la configuración articular `q1`–`q4` (enteros de hasta ±99999) en `ms` milisegundos (1–1000), interpolando lineal en articulaciones (D6). Responde `OK n` cuando entra en la cola. Ver [Segmentos](#segmentos). | `ERR 6` sin corriente; `ERR 7` sin referencia; `ERR 5` con jog o frenando; `ERR 8` si un motor no llega; `ERR 9` si el anterior todavía espera su `OK` |

`STOP` y `HALT` dejan los drivers con corriente: J4 no cae. Para cortarla está `DISABLE`.

## UCI → URC

| Mensaje | Cuándo |
| --- | --- |
| `BOOT scara/1 <versión>` | Una vez, al arrancar el firmware. Arranca sin corriente y sin referencia: toda referencia anterior se perdió. |
| `HI scara/1 <versión>` | En respuesta a `HELLO`. |
| `S modo ref J1 J2 J3 J4 hall libres último` | 20 veces por segundo y ante `STATUS`. |
| `ERR código palabra` | Ante una orden rechazada o un evento que frena. |
| `OK n` | Cuando el segmento `n` entró en la cola; es el control de flujo (D6, D50). |
| `EV HOMED j` | Eje `j` referenciado por el homing. **Issue #8.** |
| `EV LOST j pasos` | Al cruzar el Hall de `j`, la cuenta de pasos difiere en `pasos` de lo esperado (F1). **Issue #15.** |

Campos de `S`:

| Campo | Significado |
| --- | --- |
| `modo` | `OFF` (drivers sin corriente), `IDLE` (quieto, con corriente), `JOG` o `RUN` (ejecutando segmentos o frenando con la rampa de `STOP`). Llegará `HOMING` (#8). |
| `ref` | Máscara de ejes referenciados: bit 0 = J1 … bit 3 = J4; 15 = todos. |
| `J1`–`J4` | Posición estimada por pasos. Sin referencia, cuenta desde el arranque. |
| `hall` | Bits de los Hall (bit 0 = J1). Siempre 0 hasta el issue #8. |
| `libres` | Lugares libres en la cola de segmentos, de 16; el que se ejecuta ocupa uno. |
| `último` | Número del último segmento terminado; 0 si todavía no terminó ninguno desde el arranque. |

Códigos de `ERR`. Son estables: un código nuevo se agrega al final y ninguno se renumera. La URC muestra los que no conoce como «código desconocido».

| Código | Palabra | Causa |
| --- | --- | --- |
| 1 | `comando` | Comando desconocido, o bytes fuera de ASCII imprimible. |
| 2 | `argumentos` | Faltan, sobran o están fuera de rango. |
| 3 | `largo` | Línea de más de 64 bytes con el LF. |
| 4 | `watchdog` | Más de 1 s sin mensajes de la URC: el robot frenó solo (F4). |
| 5 | `ocupado` | La orden no se acepta mientras hay movimiento. |
| 6 | `deshabilitado` | La orden no se acepta con los drivers sin corriente. |
| 7 | `referencia` | `SEG` sin los cuatro ejes referenciados. |
| 8 | `velocidad` | El segmento le pide a un motor más velocidad que su límite (D45, D51). |
| 9 | `cola` | `SEG` antes del `OK` del anterior, con la cola llena: la URC envió de más. |

Con segmentos en ejecución, todo `ERR` frena con rampa, como `STOP` (D52).

## Segmentos

La URC planifica y el firmware ejecuta (D6, [ADR 0005](adr/0005-la-urc-planifica-el-firmware-ejecuta.md)). La URC parte cada tramo en segmentos de 20 ms y los envía con `SEG`; el firmware los encola y los ejecuta con su reloj.

**Ejecución.** Cada segmento va desde el destino del anterior hasta el suyo, en `ms` milisegundos, interpolando lineal en articulaciones: el firmware interpola en pasos de motor, que es lo mismo porque el acople es lineal. Un segmento empieza cuando termina el anterior, no cuando llega: los tiempos los marca el reloj del firmware, y una demora del enlace no se nota mientras quede cola. Si la cola se vacía, el robot se queda en el último destino y el próximo segmento arranca cuando llega; para que eso no sea un salto de velocidad, la URC planifica cada tramo hasta velocidad cero. Un segmento sin movimiento es una espera.

**Control de flujo (D50).** La cola tiene 16 lugares, y el segmento en ejecución ocupa uno. `OK n` sale cuando el segmento `n` entró en la cola. La URC envía un `SEG` y espera su `OK` antes de enviar el siguiente. Con la cola llena, el firmware retiene el segmento recibido y demora su `OK` hasta que termine el que se ejecuta: la URC espera y nunca envía de más. Un `SEG` antes de ese `OK` es un error de la URC (`ERR 9 cola`).

**Validación en el firmware (D51).** `SEG` exige corriente (`ERR 6`), los cuatro ejes referenciados (`ERR 7`) y ningún otro movimiento (`ERR 5`: con jog o frenando). Además, el firmware verifica que ningún motor supere su velocidad de D45 en el segmento, con el acople: M2 sigue a J1 + J2. Admite 2 centésimas de más por el redondeo de la URC (`ERR 8 velocidad`). No verifica aceleraciones, límites articulares ni choques: eso es del planificador.

**Paradas (D52).**

- `STOP` y el watchdog frenan con rampa: cada motor sigue en el sentido del segmento en ejecución y baja su velocidad en línea recta hasta cero, todos en el mismo tiempo, con la aceleración del motor más exigido (D45). La cola se vacía y la referencia se conserva. Mientras frena, `S` sigue en `RUN` con 16 lugares libres.
- `HALT` para en seco y descarta la cola; si había movimiento, pierde la referencia (D41).
- Con segmentos en ejecución, todo `ERR` frena con rampa como `STOP`. La URC, ante cualquier `ERR`, deja de enviar el tramo: los dos lados dan el tramo por terminado.

**Números.** `n` va de 1 a 999999999. La URC no los repite en una sesión, así un `OK` que llega tarde, después de un `STOP`, no se confunde con el de un tramo nuevo. `último` en `S` dice hasta dónde llegó el tramo.

## Seguridad del enlace

**Watchdog (D27, D37; falla F4).** Si el firmware pasa más de 1 s sin recibir una línea completa de la URC mientras hay movimiento, frena y envía `ERR 4 watchdog`. Quieto no hay nada que frenar y no avisa. Los drivers siguen con corriente y la referencia se conserva: frenar el jog lento no pierde pasos. La URC envía `PING` cada 250 ms, así que un corte de un segundo son cuatro `PING` perdidos.

**Reinicio de la UCI (D36, D43; falla F5).** El firmware anuncia `BOOT` al arrancar. Para la URC, todo `BOOT` significa robot sin referencia: descarta el estado y las órdenes pendientes y olvida el jog en curso. Si llega a mitad de una conexión, después de que la UCI ya había hablado, avisa «BOOT inesperado». Con USB, abrir el puerto reinicia la mayoría de los Arduino, así que un `BOOT` al principio de la conexión es lo normal; en Webots, el firmware arranca solo con la primera conexión (D36).

**Líneas inválidas.** Ningún lado se cuelga: la UCI responde `ERR` y sigue; la URC registra la línea como «no entendida» y sigue. La URC, además, nunca envía una orden que el firmware rechazaría por su forma: la revisa antes, con el mismo código.

## Conformidad

Las conversaciones de [`firmware/test/conversaciones`](../firmware/test/conversaciones/) son la definición ejecutable de este documento ([formato](../firmware/test/conversaciones/LEEME.md)). Se corren contra los dos lados con `python -m unittest discover` (D42):

- **Firmware** (`tests/test_firmware.py`): el núcleo real, compilado para la PC con una capa de hardware falsa, recibe las órdenes `>` y tiene que responder las líneas `<`.
- **URC** (`tests/test_conformidad.py`): una UCI falsa se conecta por TCP a la URC real y le envía las líneas `<`; la URC tiene que entenderlas y poder enviar cada orden `>`, salvo las que el firmware rechaza por su forma, que tiene que negarse a enviar con el mismo código.

## Ejemplos

Arranque, corriente y referencia manual ([`habilitar.txt`](../firmware/test/conversaciones/habilitar.txt)):

```text
UCI → BOOT scara/1 1
URC → HELLO
UCI → HI scara/1 1
URC → JOG 1 + 450
UCI → ERR 6 deshabilitado          (arranca sin corriente)
URC → ENABLE
URC → ZERO                         (está en la pose de reposo)
UCI → S IDLE 15 0 0 0 12000 0 16 0
```

Jog de J1 y parada ([`jog_j1.txt`](../firmware/test/conversaciones/jog_j1.txt), [`stop_halt.txt`](../firmware/test/conversaciones/stop_halt.txt)):

```text
URC → JOG 1 + 450                  (4,5 °/s)
UCI → S JOG 15 225 0 0 12000 0 16 0
URC → PING
URC → STOP
UCI → S IDLE 15 450 0 0 12000 0 16 0
```

J1 avanza 4,5° y J2 no cambia, porque el firmware mueve M1 y M2 juntos (J2 = (θM2 − θM1)/4).

Jog por motor de M1 ([`jog_motor.txt`](../firmware/test/conversaciones/jog_motor.txt)):

```text
URC → JOG M1 + 450
URC → JOG STOP                     (1 s después: 80 pasos de M1, M2 quieto)
URC → STATUS
UCI → S IDLE 0 450 -450 0 0 0 16 0
```

El brazo gira y el antebrazo conserva su orientación: J2 cambia al revés que J1 y el rumbo J1 + J2 + J3 no cambia.

Segmentos y `OK` ([`seg_interpolacion.txt`](../firmware/test/conversaciones/seg_interpolacion.txt)):

```text
URC → SEG 1 500 900 0 0 12000      (J1 sube 9° en 500 ms: M1 y M2 juntos)
UCI → OK 1
URC → SEG 2 500 900 -900 0 12000   (J2 baja 9°: solo M2)
UCI → OK 2
UCI → S RUN 15 900 0 0 12000 0 15 1   (a los 500 ms: terminó el 1)
UCI → S IDLE 15 900 -900 0 12000 0 16 2
```

Cola llena ([`seg_cola.txt`](../firmware/test/conversaciones/seg_cola.txt)):

```text
URC → SEG 16 20 0 0 0 11840
UCI → OK 16                        (16 en la cola: llena)
URC → SEG 17 20 0 0 0 11830
           … sin OK: el 17 espera lugar y la URC no envía el 18 …
UCI → OK 17                        (a los 20 ms terminó el 1)
```

`STOP` con rampa ([`seg_stop.txt`](../firmware/test/conversaciones/seg_stop.txt)):

```text
URC → SEG 1 1000 1800 0 0 12000    (J1 a 18 °/s)
UCI → OK 1
URC → STOP                         (a los 500 ms, con J1 en 9°)
UCI → S RUN 15 1260 0 0 12000 0 16 0  (frenando, cola vacía)
UCI → S IDLE 15 1378 0 0 12000 0 16 0 (530 ms después: 4,8° más, v²/2a)
```

Corte de la URC ([`watchdog.txt`](../firmware/test/conversaciones/watchdog.txt)):

```text
URC → JOG 1 + 450
           … más de 1 s sin mensajes …
UCI → ERR 4 watchdog
UCI → S IDLE 0 900 0 0 0 0 16 0
```

Reinicio inesperado ([`reinicio.txt`](../firmware/test/conversaciones/reinicio.txt)):

```text
UCI → S JOG 15 450 0 0 12000 0 16 0
           … la UCI se reinicia sin cortar el enlace …
UCI → BOOT scara/1 1               (la URC: «BOOT inesperado», sin referencia)
URC → STATUS
UCI → S OFF 0 0 0 0 0 0 16 0
```
