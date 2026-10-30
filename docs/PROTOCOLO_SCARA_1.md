# Protocolo `scara/1`

Especificación del contrato de mensajes entre la URC y el firmware de la UCI. Reemplaza al borrador de la [investigación del 29/10/2026](INVESTIGACION_TEACH_AND_PLAY_2026-10-29.md#5-protocolo-propuesto-scara1-borrador) y, cuando se retire (issue #17), al banco provisional [`scara-dev/1`](PROTOCOLO_SCARA_DEV_1.md).

**Estado:** completo desde el issue #6 para conexión, corriente, jog, paradas, watchdog y reinicio. `HOME`, `SEG`, `OK` y `EV` tienen su forma fijada acá, pero los implementan el homing (#8), los segmentos (#9) y la pérdida de pasos (#15); hasta entonces el firmware responde `ERR 1 comando` a `HOME` y `SEG`, y la URC no los envía. Las decisiones están en el [registro](REGISTRO_DE_DECISIONES.md): D4, D5, D24, D27, D35–D37, D40–D43 y D46.

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
| `STOP` | Frena todo y conserva la referencia (D41). Con los segmentos (#9), frena con rampa y vacía la cola. | — |
| `HALT` | Parada inmediata. Si había movimiento, la referencia se pierde (D41). | — |
| `ZERO` | Referencia manual: declara que el robot está en la pose de reposo (D30) y deja los cuatro ejes referenciados. | `ERR 6` sin corriente; `ERR 5` con movimiento |
| `HOME [j]` | Homing de todos los ejes o de `j` (D11). **Issue #8.** | |
| `SEG n ms q1 q2 q3 q4` | Encola el segmento `n`: llegar a esa configuración articular en `ms` milisegundos, interpolando lineal en articulaciones (D6). **Issue #9.** | |

`STOP` y `HALT` dejan los drivers con corriente: J4 no cae. Para cortarla está `DISABLE`.

## UCI → URC

| Mensaje | Cuándo |
| --- | --- |
| `BOOT scara/1 <versión>` | Una vez, al arrancar el firmware. Arranca sin corriente y sin referencia: toda referencia anterior se perdió. |
| `HI scara/1 <versión>` | En respuesta a `HELLO`. |
| `S modo ref J1 J2 J3 J4 hall libres último` | 20 veces por segundo y ante `STATUS`. |
| `ERR código palabra` | Ante una orden rechazada o un evento que frena. |
| `OK n` | Cuando el segmento `n` entró en la cola; es el control de flujo (D6). **Issue #9.** |
| `EV HOMED j` | Eje `j` referenciado por el homing. **Issue #8.** |
| `EV LOST j pasos` | Al cruzar el Hall de `j`, la cuenta de pasos difiere en `pasos` de lo esperado (F1). **Issue #15.** |

Campos de `S`:

| Campo | Significado |
| --- | --- |
| `modo` | `OFF` (drivers sin corriente), `IDLE` (quieto, con corriente) o `JOG`. Llegarán `HOMING` (#8) y `RUN` (#9). |
| `ref` | Máscara de ejes referenciados: bit 0 = J1 … bit 3 = J4; 15 = todos. |
| `J1`–`J4` | Posición estimada por pasos. Sin referencia, cuenta desde el arranque. |
| `hall` | Bits de los Hall (bit 0 = J1). Siempre 0 hasta el issue #8. |
| `libres` | Lugares libres en la cola de segmentos. Siempre 16 hasta el issue #9. |
| `último` | Último segmento terminado. Siempre 0 hasta el issue #9. |

Códigos de `ERR`. Son estables: un código nuevo se agrega al final y ninguno se renumera. La URC muestra los que no conoce como «código desconocido».

| Código | Palabra | Causa |
| --- | --- | --- |
| 1 | `comando` | Comando desconocido, o bytes fuera de ASCII imprimible. |
| 2 | `argumentos` | Faltan, sobran o están fuera de rango. |
| 3 | `largo` | Línea de más de 64 bytes con el LF. |
| 4 | `watchdog` | Más de 1 s sin mensajes de la URC: el robot frenó solo (F4). |
| 5 | `ocupado` | La orden no se acepta mientras hay movimiento. |
| 6 | `deshabilitado` | La orden no se acepta con los drivers sin corriente. |

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
