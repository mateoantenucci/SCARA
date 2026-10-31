# Protocolo `scara/1`

Especificación del contrato de mensajes entre la URC y el firmware de la UCI. Reemplaza al borrador de la [investigación del 29/10/2026](INVESTIGACION_TEACH_AND_PLAY_2026-10-29.md#5-protocolo-propuesto-scara1-borrador) y, cuando se retire (issue #17), al banco provisional [`scara-dev/1`](PROTOCOLO_SCARA_DEV_1.md).

**Estado:** completo para conexión, corriente, jog, paradas, watchdog y reinicio (issue #6), para los segmentos temporizados `SEG` y `OK` (issue #9) para el homing, `HOME` y `EV HOMED` (issue #8) y para la detección de pasos perdidos, `EV LOST` (issue #15). Las decisiones están en el [registro](REGISTRO_DE_DECISIONES.md): D4, D5, D24, D27, D35–D37, D40–D43, D46, D50–D53, D56–D58 y D65.

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
| `JOG j ± vel` | Jog articular de `j` (1–4) a `vel` centésimas por segundo (1–1000). Reemplaza al jog anterior. Sin referencia, el firmware lo baja a 500 (D58). Frena solo si activa el Hall del eje: `ERR 10 fin`. | `ERR 6` sin corriente; `ERR 5` con otro movimiento |
| `JOG Mm ± vel` | Jog por motor, un modo de prueba (D46): mueve solo el motor `m` (1–4), sin compensar el acople M1/M2. `vel` va en las unidades de la articulación de ese motor (θM/4 en M1–M3, mm de J4 en M4), 1–1000. Reemplaza al jog anterior. Igual que el articular, lento sin referencia y frenado por los Hall de los ejes que mueve (M1: J1 y J2). | `ERR 6` sin corriente; `ERR 5` con otro movimiento |
| `JOG STOP` | Frena el jog, articular o por motor. | — |
| `STOP` | Frena todo y conserva la referencia (D41). Los segmentos frenan con rampa y la cola se vacía (D52); el jog, en seco. | — |
| `HALT` | Parada inmediata. Si había movimiento, la referencia se pierde (D41). | — |
| `ZERO` | Referencia manual: declara que el robot está en la pose de reposo (D30) y deja los cuatro ejes referenciados. | `ERR 6` sin corriente; `ERR 5` con movimiento |
| `HOME [j]` | Homing de los cuatro ejes, en el orden J4, J1, J2, J3, o solo de `j` (1–4). Envía `EV HOMED j` por cada eje. Ver [Homing](#homing). | `ERR 6` sin corriente; `ERR 5` con movimiento; `ERR 11` o `ERR 12` si aborta |
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
| `EV HOMED j` | Eje `j` referenciado por el homing (D56). |
| `EV LOST j pasos` | Al entrar en un imán de `j`, con `j` referenciado, la cuenta de pasos difiere de la del flanco en 2 pasos completos o más (F1, D65). `pasos` son los reales menos los contados, en pasos completos del motor, con signo: no dependen del microstepping. Ver [Pérdida de pasos](#pérdida-de-pasos). |

Campos de `S`:

| Campo | Significado |
| --- | --- |
| `modo` | `OFF` (drivers sin corriente), `IDLE` (quieto, con corriente), `JOG`, `RUN` (ejecutando segmentos o frenando con la rampa de `STOP`) u `HOMING`. |
| `ref` | Máscara de ejes referenciados: bit 0 = J1 … bit 3 = J4; 15 = todos. |
| `J1`–`J4` | Posición estimada por pasos. Sin referencia, cuenta desde el arranque. |
| `hall` | Bits de los Hall (bit 0 = J1), 1 = imán cerca del sensor. En la pose de reposo vale 8: J4 descansa abajo, sobre su imán de fin. |
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
| 10 | `fin` | El jog frenó al activarse el Hall de un eje que mueve: fin de carrera (D58). |
| 11 | `ausente` | Homing abortado: el Hall no apareció dentro del recorrido o del tiempo máximos (Hall trabado inactivo, F3). |
| 12 | `trabado` | Homing abortado: el Hall no se apagó dentro del ancho del imán (Hall trabado activo, F3). |

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

## Homing

Un sensor Hall por articulación y dos imanes, centrados en los extremos del recorrido (D10). La referencia es el flanco del lado negativo, donde el Hall se activa: J1 y J2 en −130°, J3 en −145° y J4 a 3 mm de arriba (D56).

- `HOME` busca J4, J1 (M1 y M2 juntos: J2 no cambia), J2 (M2 solo) y J3, en ese orden (D11). `HOME j`, solo el eje `j`.
- En cada eje: si el Hall está activo al empezar, sale del imán; busca a 8 °/s (8 mm/s) hasta que se activa; retrocede hasta que se apaga y 3° (3 mm) más; vuelve a 1 °/s al mismo flanco. Ahí fija la referencia y envía `EV HOMED j`.
- La búsqueda está acotada en recorrido y en 60 s por eje. Si el Hall no aparece, `ERR 11 ausente`; si no se apaga, `ERR 12 trabado`. Al abortar, y también con `STOP`, `HALT`, `DISABLE` o el watchdog, los ejes de ese `HOME` quedan sin referencia.
- `S` informa `HOMING` mientras dura. El firmware termina en los flancos; la URC vuelve sola a la pose de reposo con un tramo PTP («Estacionar»).
- Sin referencia, el jog va a 5 °/s como máximo, y el Hall lo frena como fin de carrera (D58). Con ese Hall todavía activo, un jog hacia el mismo lado se rechaza con `ERR 10 fin`: solo sale para el otro.

## Pérdida de pasos

Sin encoders, el firmware no ve los pasos que un motor no siguió (F1, [ADR 0006](adr/0006-modelo-de-motores-pasos-y-perdida-de-pasos.md)). Lo descubre al pasar por un Hall (D65):

- Con el eje referenciado, su Hall se activa siempre en el mismo lugar: al entrar en el imán de abajo, en el flanco de la referencia (`HALL_EDGE`); al entrar en el del otro extremo, en `HALL_FAR_EDGE` (J1 y J2 en +130°, J3 en +145°, J4 a 117 mm). El firmware elige el imán más cercano a la posición estimada.
- Si los pasos contados difieren de los del flanco en 2 pasos completos o más, envía `EV LOST j pasos`. Dos pasos completos son medio ciclo eléctrico: un motor pierde pasos de a cuatro, y lo que puede errar la lectura del Hall en movimiento queda por debajo.
- Para J2, que se mide relativo a J1, cuentan los pasos de M2 menos los de M1: un paso perdido por M1 se ve en J1 y, al revés, en J2.
- No corrige la cuenta ni frena: la referencia la vuelve a fijar el homing. Durante el homing no compara, porque es el que define los flancos. Sin referencia, no hay con qué comparar.
- La URC marca la referencia de `j` como dudosa y lo avisa en el mensaje y en la lista de errores. La duda se limpia con el `EV HOMED j` de ese eje, con un `BOOT` o cuando el eje pierde la referencia; no con `ZERO`, que es menos preciso que el homing.
- El firmware no distingue un motor que perdió pasos de un Hall que miente: un Hall trabado activo (F3) a mitad de carrera también da `EV LOST`, con muchos pasos. En los dos casos la referencia es dudosa.

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

Homing ([`homing.txt`](../firmware/test/conversaciones/homing.txt)), desde la pose de reposo:

```text
URC → HOME
UCI → S HOMING 0 0 0 0 0 8 16 0       (J4 abajo, sobre su imán de fin)
UCI → EV HOMED 4                      (J4 sube, sale del imán y busca el de arriba)
UCI → EV HOMED 1
UCI → EV HOMED 2
UCI → EV HOMED 3
UCI → S IDLE 15 -12999 -12999 -14501 300 15 16 0
```

Hall trabado ([`homing_hall_trabado.txt`](../firmware/test/conversaciones/homing_hall_trabado.txt)):

```text
URC → HOME
UCI → EV HOMED 4
UCI → ERR 12 trabado                  (el Hall de J1 no se apaga)
UCI → S IDLE 0 -602 0 0 300 9 16 0    (sin referencia, ni siquiera J4)
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
