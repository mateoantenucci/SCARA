# Guía de estudio del protocolo `scara/1`

Para estudiar la defensa. La especificación es [`PROTOCOLO_SCARA_1.md`](PROTOCOLO_SCARA_1.md): si esta guía y la especificación no coinciden, manda la especificación. Esta guía agrega lo que allá no está: por qué es así, cómo leer cada línea y qué responder cuando lo cuestionan.

Usa el vocabulario del [glosario](../GLOSSARY.md). Las decisiones (D5, D6…) están en el [registro](REGISTRO_DE_DECISIONES.md).

## Contenido

1. La idea en un minuto
2. Cómo está definido el protocolo
3. Por dónde viajan los mensajes
4. Cómo se ve una línea
5. Por qué grados y no X, Y, Z, R
6. Todos los mensajes
7. Qué se acepta en cada estado
8. Los segmentos y el control de flujo
9. Conversaciones completas
10. Quién frena el robot
11. Dónde está en el código
12. Autoevaluación
13. Errores que no hay que cometer

## 1. La idea en un minuto

- La **URC** (programa de la PC) decide **qué** movimiento hacer: planifica, calcula la cinemática y valida.
- La **UCI** (el firmware, en Webots o en el Arduino) decide **cómo** dar los pasos: cuenta pasos, mide el tiempo y mira los Hall.
- Se hablan con **líneas de texto**, una por mensaje.
- El operador piensa en **X, Y, Z, R**. Por el enlace viajan **articulaciones**, en centésimas. El firmware las convierte a **pasos**.
- Un movimiento son muchos `SEG` de 20 ms. La URC envía uno, espera su `OK` y envía el siguiente.
- La UCI informa su estado con una línea `S` 20 veces por segundo.

## 2. Cómo está definido el protocolo

Un protocolo es un contrato. Para que dos programas se entiendan, tiene que fijar seis cosas:

| Qué fija | En `scara/1` |
| --- | --- |
| Transporte | TCP al puerto 9000. Con el Arduino, USB-serie a 115200 baudios, puenteado con socat. |
| Roles | La URC escucha y la UCI se conecta (D1). |
| Formato | Una línea ASCII de hasta 64 bytes, con campos separados por espacios y solo enteros (D4). |
| Vocabulario | 11 órdenes de la URC y 7 mensajes de la UCI (sección 6). |
| Comportamiento | Qué hace cada orden, según el estado del robot (sección 7). |
| Errores | 12 códigos estables, que no se renumeran. |

Y está escrito en cuatro lugares, que tienen que coincidir:

| Dónde | Qué aporta |
| --- | --- |
| [`docs/PROTOCOLO_SCARA_1.md`](PROTOCOLO_SCARA_1.md) | La especificación, para leer. |
| [`firmware/firmware.cpp`](../firmware/firmware.cpp) | Cómo lo interpreta la UCI. |
| [`urc/protocol.py`](../urc/protocol.py) | Cómo lo interpreta la URC. Antes de enviar revisa la orden, y rechaza con el mismo código que usaría el firmware. |
| [`firmware/test/conversaciones/`](../firmware/test/conversaciones/LEEME.md) | **La definición ejecutable.** Son diálogos que se corren contra los dos lados. |

Lo último es lo más fuerte para la defensa: si alguien cambia un lado y el otro no, las pruebas fallan. El firmware corre compilado en la PC con hardware falso, y la URC corre contra una UCI falsa por TCP (D42). Un archivo se ve así, donde `>` envía la URC, `<` responde la UCI y `+ 1000` avanza el reloj 1 s:

```text
< BOOT scara/1 1
> ENABLE
> JOG 1 + 450
+ 1000
= M1 80 M2 80 M3 0 M4 0
```

## 3. Por dónde viajan los mensajes

```text
navegador ──HTTP 8766──► URC ◄──TCP 9000, scara/1── UCI en Webots
                          ▲
                          ├──TCP 9001, scara-sim/1── Webots (solo simulación)
                          │
                          └──TCP 9000, scara/1── socat ◄──USB-serie 115200── Arduino UNO
```

- **El navegador no habla `scara/1`.** Le pide cosas a la URC por HTTP, y la URC las traduce en líneas.
- **La UCI es cliente TCP.** Así lo pidió el profesor, y con el robot real quien se conecta es socat, que abre el USB (D1). La URC queda esperando, y el robot puede reiniciarse sin tocarla.
- **El mismo protocolo sirve para los dos.** A `scara/1` no le importa si abajo hay un socket o un cable: los dos entregan bytes.
- **El 9001 es otro protocolo.** Lleva lo que un robot real no podría saber, como la posición física simulada o la inyección de fallas (ADR 0004). Así la URC no puede depender sin querer de algo que el hardware no da.

## 4. Cómo se ve una línea

TCP y la serie entregan un **chorro de bytes**, sin separación entre mensajes. Una línea puede llegar cortada en dos pedazos, o dos líneas pueden llegar pegadas. Por eso cada mensaje termina en un salto de línea (LF, byte `0A`), y el que recibe junta bytes hasta encontrarlo.

```text
P  I  N  G  \n
50 49 4E 47 0A      5 bytes
```

Reglas (D4):

| Regla | Qué pasa si no se cumple |
| --- | --- |
| Solo ASCII imprimible (bytes 32 a 126) | La línea se descarta: `ERR 1 comando`. |
| Hasta 64 bytes, contando el LF | La línea se descarta: `ERR 3 largo`. |
| Campos separados por uno o más espacios | — |
| El CR se ignora | Así funciona el `println` de Arduino. |
| Una línea vacía no es un mensaje | Se ignora. |
| Solo enteros | `JOG 1 + 10x` es `ERR 2 argumentos`. |

**Por qué texto.** Lo pide la consigna («mensajes de texto claro»). Además se lee a mano con `nc` o el monitor serie, y se procesa en los 2 KB de RAM del UNO. JSON se descartó por pesado.

**Por qué solo enteros.** Parsear e imprimir decimales es lento en el AVR del UNO (ADR 0003). Por eso los ángulos van en centésimas: `9000` son 90,00° y `12000` son 120,00 mm.

**Cuánto ocupa.** A 115200 baudios entran unos 11 500 bytes por segundo en cada sentido. Una reproducción usa unos 1800 hacia la UCI (50 `SEG` de unos 35 bytes, más 4 `PING`) y unos 1200 de vuelta (20 `S` de unos 40 bytes, más 50 `OK`). Es cerca del 15 % y del 10 %, según esta cuenta.

## 5. Por qué grados y no X, Y, Z, R

Es la pregunta central de la reunión del 03/11: el profesor propuso enviar `X Y Z R`, recibir `OK` al llegar o `ERR`, y que la Arduino resuelva la cinemática.

### 5.1 Hay tres idiomas posibles

| Nivel | Ejemplo | Quién lo entiende mejor |
| --- | --- | --- |
| Herramienta: X, Y, Z, R | `250 150 50 30` (mm y grados) | El operador |
| Articulaciones: J1–J4 | `8530 -10866 5337 4467` (centésimas) | **El enlace** |
| Motores: pasos | M1 1516, M2 −415, M3 949, M4 8934 | Los drivers |

Es una decisión con dos mitades:

- **Articulaciones y no pasos** (D5, ADR 0003): el microstepping, las poleas y el acople son hechos del robot. Cambiar un driver toca la configuración del firmware y no la URC, y la telemetría se puede leer.
- **Articulaciones y no X, Y, Z, R** (D6, ADR 0005): la cinemática y la planificación están en la URC.

### 5.2 Qué es cada cosa

```text
J1  giro del brazo respecto de la torre             ±135°
J2  giro del antebrazo respecto del brazo           ±135°
J3  giro de la muñeca respecto del antebrazo        ±150°
J4  bajada del pistón; positivo hacia abajo         0 a 120 mm
```

Con los dos eslabones de 250 mm, ir de articulaciones a herramienta es **cinemática directa** (`scara/kinematics.py`, `forward`):

```text
X = 250 · cos(J1) + 250 · cos(J1 + J2)
Y = 250 · sen(J1) + 250 · sen(J1 + J2)
Z = 94,67 − J4
R = J1 + J2 + J3
```

Ir al revés es **cinemática inversa** (`arm_angles` e `inverse`):

```text
cos(J2) = (X² + Y² − 250² − 250²) / (2 · 250 · 250)
J2 = ± acos(...)                                        ← acá aparecen dos soluciones
J1 = atan2(Y, X) − atan2(250 · sen(J2), 250 + 250 · cos(J2))
J3 = R − J1 − J2
J4 = 94,67 − Z
```

**R no es J3.** R es el rumbo de la herramienta en el mundo, y J3 es el giro de la muñeca respecto del antebrazo. Si se mueve el brazo con J3 quieto, R cambia. Para mantener R fijo durante un movimiento, J3 tiene que ir compensando todo el tiempo. Por ejemplo, un punto de la demo tiene J1 = −90°, J2 = −60° y J3 = 0°, y su rumbo es −150°, aunque J3 valga cero.

### 5.3 Las razones, de la más fuerte a la más discutible

**1. Las articulaciones definen una única pose; X, Y, Z, R no.** La directa da un solo resultado, y la inversa da dos:

```text
X=250 Y=150 Z=50 R=30, codo negativo → J1  85,30°  J2 −108,66°  J3  53,37°  J4 44,67
X=250 Y=150 Z=50 R=30, codo positivo → J1 −23,37°  J2  108,66°  J3 −55,30°  J4 44,67
```

La herramienta queda en el mismo lugar, pero el brazo está en otra posición: uno puede chocar y el otro no, y pasar de uno a otro exige estirar el brazo. Con `X Y Z R` hay que agregar un campo más para el codo o fijar una regla. Con articulaciones, la pregunta no existe. Por eso un punto de trayectoria guarda las articulaciones (D13, D62).

Los límites descartan otras soluciones por vueltas: J1 recorre 270° y J3 300°, los dos menos de una vuelta. La única ambigüedad en este robot es el codo.

**2. Es lo que el robot sabe de verdad.** El firmware cuenta pasos, y de pasos a articulaciones hay una cuenta exacta. No sabe dónde está la herramienta en el mundo: eso sale de un modelo con largos y parámetros provisionales (ADR 0001). La línea `S` informa algo que el firmware efectivamente conoce.

**3. Los límites físicos están en las articulaciones.** Los recorridos, los imanes de los Hall y las velocidades de los motores son por eje. El firmware verifica el segmento con cuentas simples (`segmentWithinMotorSpeed`, M2 sigue a J1 + J2), sin geometría.

**4. El firmware trabaja solo con enteros.** La conversión de articulaciones a pasos es una multiplicación y una división enteras (`firmware/transmission.h`):

```text
J1–J3: pasos = centésimas × 8 / 45        (900 → 160 pasos)
J4:    pasos = centésimas × 2             (12000 → 24000 pasos)
M2 sigue a J1 + J2:  M2 = (J1 + J2) × 8 / 45
```

Con `X Y Z R`, el firmware tendría que usar `acos`, `atan2`, `sen` y `cos`, es decir, flotantes. El generador de pulsos ya consume entre 9 % y 20 % del procesador ([conteo de ciclos](ARDUINO_UNO.md)).

**5. Una recta en X, Y, Z no es una recta en articulaciones.** Este es el motivo de que existan los segmentos. Para ir de (300, −100) a (300, 100), con Z = 50 y R = 0:

```text
Inicio:                     J1 32,33   J2 −101,54   J3 69,20
Fin:                        J1 69,20   J2 −101,54   J3 32,33
Promedio de los extremos:   J1 50,77   J2 −101,54   J3 50,77   → X = 316,22 mm
Punto correcto de la recta: J1 53,13   J2 −106,26   J3 53,13   → X = 300,00 mm
```

Si se interpolara solo entre los extremos, el centro del recorrido se iría **16 mm** de la recta. Además, J2 empieza y termina igual, pero en el medio se mueve. Por eso la URC parte la recta en trozos cortos y resuelve la inversa en cada uno: esa recta al 50 % son 159 segmentos de 20 ms. Dentro de cada segmento, tan corto, el firmware sí interpola lineal en articulaciones.

**6. La validación necesita la cinemática en la URC de todos modos.** Antes de mover, la URC comprueba el trayecto completo: alcance, codo, límites, velocidades y choques (D55). Ese chequeo de choques tarda unos 3 ms por segmento en una PC y usa cajas envolventes sacadas del CAD. Además, la página tiene que mostrar X, Y, Z, R. Si el firmware también resolviera la cinemática, estaría en los dos lados y habría que mantenerla igual.

**7. Un solo mensaje sirve para todo.** LIN, PTP, jog verificado y esperas son todos `SEG`. El firmware no necesita saber de qué tipo de tramo viene cada uno (ADR 0005). Es la división de trabajo de GRBL y Klipper.

**8. La capacidad del UNO (la más discutible).** El ADR 0005 dice que un UNO no puede calcular la inversa a la frecuencia que exige una recta. **Eso no está medido en el repo.** Hay firmwares que resuelven SCARA adentro, como [Marlin](https://github.com/ttsalo/Marlin-SCARA). No prueba que entre en este UNO, pero alcanza para que «es imposible» sea una respuesta débil. La memoria tampoco cierra el tema: [`DEFENSA.md`](DEFENSA.md) registra 50 % de flash y 63 % de RAM usadas. Conviene decir «elegimos ponerla en la PC por las razones anteriores, y no medimos cuánto costaría en el UNO».

### 5.4 El operador sí trabaja en X, Y, Z, R

El profesor dijo que el operador debe ver X, Y, Z, R y no grados. **Eso ya está cubierto**, porque son dos cosas distintas:

```text
Operador ── X Y Z R ──► URC ── articulaciones ──► UCI ── pasos ──► motores
         ◄── X Y Z R ──     ◄── articulaciones ──
```

- La URC calcula X, Y, Z y rumbo a partir de cada `S` para mostrarlos en la página (`Session._tool`).
- El jog cartesiano mueve en X, Y, Z y rumbo.
- «Ir a una pose» y la carga de puntos aceptan X, Y, Z y rumbo.
- Cada punto guardado incluye los dos: `"joints"` y `"tool"`. Mandan las articulaciones (D62).

### 5.5 Las dos propuestas, lado a lado

| | `X Y Z R` con `OK`/`ERR` | `scara/1` actual |
| --- | --- | --- |
| Para explicarlo | **Muy simple** | Más mensajes |
| Cinemática | En la Arduino | En la URC |
| Recta | La hace la Arduino | La hace la URC, en segmentos |
| Respuesta | `OK` al llegar | `OK` al entrar en la cola, y `S` continuo |
| Durante el movimiento | No se sabe nada hasta el `OK` | Posición, modo y Hall 20 veces por segundo |
| Validar antes de mover | Solo lo que entre en la Arduino | Todo el trayecto, con choques |
| Codo | Regla o campo extra | Implícito en J2 |
| Protección local | **Mayor**: el firmware conoce el plan | Parcial (sección 10) |
| Cortes y demoras del enlace | **No afectan** el tramo en curso | La cola absorbe hasta 320 ms |
| Costo en el UNO | Mayor, sin medir | Conocido: compila para el UNO, sin probar en placa |
| Homing | Valor especial (`9999`) | Orden propia, `HOME` |

Su propuesta tiene ventajas reales: es más simple y protege más en la propia UCI. Cambiar a esa forma contradice los ADR 0003 y 0005, así que primero habría que reabrirlos.

**Una forma de responder:** «Separamos los dos idiomas: el operador usa X, Y, Z, R y el enlace usa articulaciones. La posición articular es única y es lo que el robot realmente conoce. La URC resuelve la inversa porque también tiene que validar el trayecto completo y los choques antes de mover. El costo es que durante la reproducción dependemos más de la URC, y eso lo tenemos identificado».

## 6. Todos los mensajes

### URC → UCI

Si una orden sale bien, no responde: el efecto se ve en el próximo `S` (D35). Las excepciones son `HELLO`, `STATUS` y `SEG`.

| Línea | Qué hace | Responde |
| --- | --- | --- |
| `HELLO` | Saludo, al aceptar cada conexión | `HI` |
| `PING` | «Sigo vivo», cada 250 ms | — |
| `STATUS` | Pide el estado ya | `S` |
| `ENABLE` | Da corriente a los cuatro drivers | — |
| `DISABLE` | Frena, corta la corriente y **pierde la referencia** | — |
| `JOG 1 + 450` | Mueve J1 a 4,50 °/s, hasta `JOG STOP`. Velocidad de 1 a 1000 | — |
| `JOG M1 + 450` | Mueve solo el motor M1, sin compensar el acople | — |
| `JOG STOP` | Frena el jog | — |
| `STOP` | Frena con rampa los segmentos, y **conserva la referencia** | — |
| `HALT` | Para en seco. Si había movimiento, **pierde la referencia** | — |
| `ZERO` | «Estoy en la pose de reposo»: referencia manual | — |
| `HOME` o `HOME 3` | Homing de todos, o de un eje | `EV HOMED j` por eje |
| `SEG n ms q1 q2 q3 q4` | Encola «llegar a esta pose en `ms`» | `OK n` |

### UCI → URC

| Línea | Cuándo |
| --- | --- |
| `BOOT scara/1 1` | Al arrancar. Sin corriente y **sin referencia** |
| `HI scara/1 1` | En respuesta a `HELLO` |
| `S ...` | 20 veces por segundo, y ante `STATUS` |
| `OK n` | El segmento `n` **entró en la cola** |
| `ERR código palabra` | Orden rechazada o evento que frena |
| `EV HOMED j` | Eje `j` referenciado |
| `EV LOST j pasos` | Al entrar en un imán, la cuenta no coincide: pasos perdidos |

### Cómo leer un `SEG`

```text
SEG  1234  20  8530  -10866  5337  4467
│    │     │   │     │       │     └ J4 = 44,67 mm
│    │     │   │     │       └ J3 = 53,37°
│    │     │   │     └ J2 = −108,66°
│    │     │   └ J1 = 85,30°
│    │     └ duración: 20 ms (de 1 a 1000)
│    └ número de segmento: no se repite en la sesión
└ comando
```

Dice **adónde llegar** y **en cuánto tiempo**. La velocidad sale de ahí: el firmware la calcula y la verifica.

### Cómo leer un `S`

Tiene nueve campos después de la `S`, siempre en el mismo orden:

```text
S  RUN  15  900  0  0  12000  8  15  1
   │    │   │    │  │  │      │  │   └ último: segmento terminado (0 = ninguno)
   │    │   │    │  │  │      │  └ libres: lugares en la cola, de 16
   │    │   │    │  │  │      └ hall: bits de los sensores
   │    │   └────┴──┴──┘
   │    │   J1 J2 J3 J4: posición estimada por pasos
   │    └ ref: bits de los ejes referenciados
   └ modo
```

| Modo | Significa |
| --- | --- |
| `OFF` | Drivers sin corriente |
| `IDLE` | Quieto, con corriente |
| `JOG` | Jog del firmware en curso |
| `RUN` | Ejecutando segmentos, o frenando con la rampa de `STOP` |
| `HOMING` | Homing en curso |

Los campos `ref` y `hall` son **máscaras de bits**, donde cada bit es un eje:

```text
bit:    3   2   1   0
eje:   J4  J3  J2  J1      valor = J1·1 + J2·2 + J3·4 + J4·8

15 = 1111 → los cuatro
 8 = 1000 → solo J4
 5 = 0101 → J1 y J3
```

En la pose de reposo, `hall` vale 8: J4 descansa abajo, sobre su imán. En los ejemplos de las pruebas suele aparecer 0, porque sin el renglón `! iman` los Hall nunca se activan.

La posición es **estimada por pasos**: lo que el firmware cree. Si el motor perdió pasos, sigue diciendo lo mismo (F1).

### Códigos de `ERR`

| Código | Palabra | Causa |
| --- | --- | --- |
| 1 | `comando` | Comando desconocido, o bytes no imprimibles |
| 2 | `argumentos` | Faltan, sobran o están fuera de rango |
| 3 | `largo` | Más de 64 bytes |
| 4 | `watchdog` | Más de 1 s sin mensajes con el robot en movimiento |
| 5 | `ocupado` | No se acepta con movimiento en curso |
| 6 | `deshabilitado` | No se acepta sin corriente |
| 7 | `referencia` | `SEG` sin los cuatro ejes referenciados |
| 8 | `velocidad` | El segmento supera el límite de un motor |
| 9 | `cola` | `SEG` antes del `OK` del anterior, con la cola llena |
| 10 | `fin` | El jog frenó porque se activó un Hall |
| 11 | `ausente` | Homing: el Hall no apareció |
| 12 | `trabado` | Homing: el Hall no se apagó |

El código es lo que usa el programa, porque comparar números es más robusto que comparar textos. La palabra es para leerla a simple vista, y no lleva espacios para no complicar el parser.

### Números para tener a mano

| Dato | Valor |
| --- | --- |
| Estado `S` | Cada 50 ms (20 por segundo) |
| `PING` | Cada 250 ms |
| Watchdog | 1 s sin líneas completas |
| Segmento | 20 ms |
| Cola | 16 lugares, hasta 320 ms de movimiento |
| Jog de la URC | 3 segmentos en cola, unos 60 ms |
| Jog del firmware | Hasta 10 °/s; sin referencia, hasta 5 °/s |
| Renovación del jog | La página cada 150 ms; la URC frena tras 500 ms sin renovar |
| Línea | 64 bytes con el LF |
| Un paso de J1–J3 (1/8) | 0,05625°: unos 0,49 mm con el brazo estirado |
| Un paso de J4 (1/8) | 0,005 mm |

## 7. Qué se acepta en cada estado

Primero se revisa la **forma** de la línea, y después el **estado** del robot. Por eso `JOG 1 + 99999` sin corriente es `ERR 2`, no `ERR 6`.

| Orden | `OFF` | `IDLE` sin ref. | `IDLE` con ref. | `JOG` | `RUN` | `HOMING` |
| --- | --- | --- | --- | --- | --- | --- |
| `ENABLE` | Sí | Sin efecto | Sin efecto | Sin efecto | Sin efecto | Sin efecto |
| `JOG j` | `ERR 6` | Sí, hasta 5 °/s | Sí | Reemplaza | `ERR 5` | `ERR 5` |
| `ZERO` | `ERR 6` | Sí | Sí | `ERR 5` | `ERR 5` | `ERR 5` |
| `HOME` | `ERR 6` | Sí | Sí | `ERR 5` | `ERR 5` | `ERR 5` |
| `SEG` | `ERR 6` | `ERR 7` | Sí | `ERR 7` o `ERR 5` | Sí, se encola | `ERR 7` o `ERR 5` |
| `STOP` | Sin efecto | Sin efecto | Sin efecto | Frena | Rampa | Aborta |
| `HALT` | Sin efecto | Sin efecto | Sin efecto | Frena y pierde ref. | Frena y pierde ref. | Aborta y pierde ref. |

En `SEG`, `ERR 7` es sin los cuatro ejes referenciados y `ERR 5` es con ellos.

Dos detalles que se suelen preguntar:

- **Con segmentos en ejecución, todo `ERR` frena con rampa.** Un `JOG` en pleno `RUN` no solo se rechaza: también detiene el movimiento. Mientras frena, `S` sigue en `RUN` con 16 libres, y un `SEG` nuevo da `ERR 5`.
- **Cualquier línea completa renueva el watchdog**, no solo `PING`. Incluso una línea inválida cuenta, porque demuestra que el enlace funciona.

## 8. Los segmentos y el control de flujo

### Por qué hay una cola

Si el firmware recibiera posiciones para ejecutarlas al llegar, cualquier demora de la red o de la PC se convertiría en un tirón. Con cola, el reloj lo pone el firmware: cada segmento empieza cuando **termina el anterior**, no cuando llega. Una demora no se nota mientras quede algo en la cola (ADR 0005).

### Por qué se espera el `OK`

La URC puede generar líneas mucho más rápido de lo que el robot las ejecuta. Sin regulación, la cola se desbordaría. La regla (D50):

1. La URC envía un `SEG` y **no envía otro hasta recibir su `OK`**.
2. Si hay lugar, el firmware lo encola y responde `OK` enseguida.
3. Si la cola está llena, retiene ese segmento y **demora su `OK`** hasta que termine el que se está ejecutando.

Es decir, el `OK` es la forma en que el firmware regula el ritmo. Si la URC envía otro `SEG` mientras uno está retenido, es un error de la URC: `ERR 9 cola`.

```text
URC → SEG 16 20 0 0 0 11840
UCI → OK 16                        (16 en la cola: llena)
URC → SEG 17 20 0 0 0 11830
           … sin OK: el 17 espera lugar y la URC no envía el 18 …
UCI → OK 17                        (a los 20 ms terminó el 1)
```

### `OK` no significa «llegué»

`OK n` significa «lo recibí y entró en la cola». Puede faltar casi un tercio de segundo para que se ejecute. Lo que dice hasta dónde se llegó es el campo `último` de `S`. Con `OK` regula el ritmo y con `S` sigue el avance.

### Qué valida cada lado

| Lo valida | Qué | Cuándo |
| --- | --- | --- |
| URC | Alcance, codo, límites articulares, velocidades, aceleraciones y choques | Antes de mover, todo el trayecto |
| Firmware | Corriente, referencia, modo y velocidad de cada motor | Cada `SEG`, al recibirlo |
| Firmware | **No** valida límites articulares, aceleraciones ni choques | — |

La frase corta: **el firmware defiende a los motores, la URC defiende al robot**.

## 9. Conversaciones completas

Salvo que se indique otra cosa, están tomadas de la especificación o de las conversaciones de conformidad.

### Arranque

```text
UCI → BOOT scara/1 1          arrancó: sin corriente y sin referencia
URC → HELLO                   lo envía la URC al aceptar la conexión
UCI → HI scara/1 1
UCI → S OFF 0 0 0 0 0 8 16 0  sin referencia: la posición cuenta desde el arranque
URC → ENABLE                  da corriente
UCI → S IDLE 0 0 0 0 0 8 16 0
```

Con el Arduino real, abrir el puerto lo reinicia y ese `HELLO` se pierde en el bootloader. No hace falta, porque `BOOT` ya trae el protocolo y la versión.

### Jog sin referencia: lo ejecuta el firmware

```text
URC → JOG 1 + 450             J1 a 4,5 °/s; M1 y M2 juntos
UCI → S JOG 0 225 0 0 0 0 16 0
URC → PING
URC → JOG STOP                al soltar la tecla
UCI → S IDLE 0 450 0 0 0 0 16 0
```

Si activa un Hall, el firmware frena solo y envía `ERR 10 fin`.

### Jog con referencia: lo planifica la URC

**Con el robot referenciado, el jog articular y el cartesiano no usan `JOG`**, sino `SEG` verificados de a uno (D75). Por eso, en el panel de tráfico se ve esto (ilustrativo):

```text
URC → SEG 30 20 20 0 0 12000      10 °/s son 20 centésimas cada 20 ms
UCI → OK 30
URC → SEG 31 20 40 0 0 12000
UCI → OK 31
URC → SEG 32 20 60 0 0 12000
UCI → OK 32
                                  al soltar la tecla no se envía nada: termina lo encolado
```

### Referencia manual y primer movimiento

Los `SEG` son reales, generados por `plan_ptp` para llevar J1 a 9° y J2 a −9° al 25 %. Los `S` son ilustrativos.

```text
URC → ZERO                    «estoy en reposo»
UCI → S IDLE 15 0 0 0 12000 8 16 0
URC → SEG 1 20 3 -3 0 12000
UCI → OK 1
URC → SEG 2 20 10 -10 0 12000
UCI → OK 2
URC → SEG 3 20 24 -24 0 12000
UCI → OK 3
      … hasta el SEG 29 …
URC → SEG 29 20 900 -900 0 12000
UCI → OK 29
UCI → S IDLE 15 900 -900 0 12000 8 16 29
```

Los segmentos empiezan chicos y crecen: es la aceleración del perfil trapezoidal, escrita como una distancia cada vez mayor en el mismo tiempo. Y como J1 + J2 siempre da 0, **M2 no se mueve**: solo gira M1.

### Homing

```text
URC → HOME
UCI → S HOMING 0 0 0 0 0 8 16 0       J4 abajo, sobre su imán
UCI → EV HOMED 4                      J4 primero: aleja la herramienta de la mesa
UCI → EV HOMED 1                      M1 y M2 juntos: J2 no cambia
UCI → EV HOMED 2                      M2 solo
UCI → EV HOMED 3
UCI → S IDLE 15 -12999 -12999 -14501 300 15 16 0
```

En cada eje: si el Hall ya está activo, sale del imán; busca rápido; retrocede hasta que se apaga y 3° más; vuelve lento al mismo flanco. Ese flanco es la referencia. Da `-12999` y no `-13000` porque −130° no es un número entero de pasos.

Después, la URC vuelve sola a la pose de reposo con un PTP.

### `STOP` con rampa

```text
URC → SEG 1 1000 1800 0 0 12000
UCI → OK 1
URC → STOP                            a los 500 ms, con J1 en 9°
UCI → S RUN 15 990 0 0 12000 0 16 0   frenando, cola vacía
UCI → S IDLE 15 1018 0 0 12000 0 16 0   quieto: se pasó 1,2° frenando
```

La pausa de la reproducción es este mismo `STOP`. Al reanudar, la URC recalcula lo que falta desde donde frenó, con números de segmento nuevos.

### Corte del enlace (F4)

```text
URC → JOG 1 + 450
           … más de 1 s sin mensajes …
UCI → ERR 4 watchdog
UCI → S IDLE 0 900 0 0 0 0 16 0
```

Los drivers siguen con corriente y la referencia se conserva.

### Reinicio de la UCI (F5)

```text
UCI → S JOG 15 450 0 0 12000 0 16 0
           … la UCI se reinicia sin cortar el enlace …
UCI → BOOT scara/1 1                  la URC avisa «BOOT inesperado»
URC → STATUS
UCI → S OFF 0 0 0 0 0 0 16 0
```

Para la URC, todo `BOOT` significa robot sin referencia: descarta el estado y las órdenes pendientes.

### Pasos perdidos (F1)

```text
UCI → EV LOST 4 -48          al entrar en el imán de J4, la cuenta difiere (ilustrativo)
```

El número son los pasos reales menos los contados, en pasos completos. El firmware **no corrige ni frena**. La URC marca la referencia como dudosa, detiene la reproducción con `STOP` y la bloquea hasta un homing.

## 10. Quién frena el robot

Es el punto que el profesor cuestionó: si una demora del enlace hace que el motor siga de largo al llegar al sensor. La respuesta honesta depende del caso.

| Situación | Quién reacciona | ¿Depende del enlace? |
| --- | --- | --- |
| Jog del firmware que activa un Hall | Firmware: `ERR 10 fin` | **No** |
| Homing que busca el Hall | Firmware, con búsqueda acotada en recorrido y a 60 s | **No** |
| Se corta el enlace durante un jog del firmware o un homing | Firmware: watchdog a 1 s | **No** |
| Se corta el enlace durante una reproducción | Nadie: la cola se agota y el robot queda en el último destino, **sin rampa** | **No** |
| La página deja de renovar el jog | URC, a los 500 ms | Sí |
| Reproducción con pasos perdidos | Firmware avisa `EV LOST`; la URC envía `STOP` | **Sí** |
| Reproducción fuera de recorrido | Solo la validación previa de la URC | **Sí** |
| Choque con algo que el modelo no conoce | Nadie, en ese momento | No aplica |

**Lo que hay que admitir:**

- En modo `RUN`, el Hall no frena: `checkJogHall` solo corre con `JOG`. Con segmentos, entrar en un imán puede ser legítimo: el flanco de J1 está en ±130° y su recorrido llega a ±135°.
- **El firmware no verifica el recorrido de un `SEG`.** Se comprobó el 04/11 con el arnés de conformidad: con la referencia manual, aceptó `SEG` hasta J1 = 220°, cuando el límite es ±135°. Solo controló que la velocidad del motor no se pasara.
- Una URC con un error de programación podría, entonces, mandar el brazo contra el tope.

- Con segmentos de 20 ms, **el watchdog no llega a actuar** si se corta el enlace. La cola se agota en unos 320 ms y el firmware pasa a quieto, sin rampa, y quieto el watchdog no avisa. Se comprobó el 04/11 con el arnés: a 10 °/s, sin `ERR 4` después de 1,5 s de silencio. A plena velocidad, frenar así podría perder pasos, y el firmware seguiría con su referencia. La campaña no lo ensaya: F4 se demuestra con el jog sin referencia.

**Lo que limita el problema:** si se corta el enlace, el robot deja de moverse en unos 320 ms, porque el firmware no recibe más. Y toda trayectoria se valida completa antes de moverse.

**Una mejora posible, sin cambiar la arquitectura:** que el firmware rechace un `SEG` fuera del recorrido, con los mismos límites de la URC. Es comparar enteros, y hoy no se hace.

**Paradas, para no confundirlas:**

| | Rampa | Cola | Referencia | Corriente |
| --- | --- | --- | --- | --- |
| `JOG STOP` | No, en seco | No aplica | Se conserva | Sigue |
| `STOP` | Sí en segmentos; el jog, en seco | Se vacía | Se conserva | Sigue |
| Watchdog | Igual que `STOP` | Se vacía | Se conserva | Sigue |
| `HALT` | No, en seco | Se descarta | **Se pierde** si había movimiento | Sigue |
| `DISABLE` | No, en seco | Se descarta | **Se pierde** | **Se corta** |

## 11. Dónde está en el código

**Ida: la URC envía un `SEG`, la UCI responde `OK`.**

| Paso | Dónde |
| --- | --- |
| La URC arma la línea y la revisa | `segment_line` y `check_order`, en `urc/protocol.py` |
| Sale un solo `SEG` sin confirmar | `Session._send_pending`, en `urc/session.py` |
| El firmware lee los bytes | `Firmware::poll`, en `firmware/firmware.cpp` |
| Junta bytes hasta el LF | `Firmware::receive` |
| Identifica el comando | `Firmware::handle` y `nextField` |
| Valida y encola | `Firmware::handleSegment` |
| Responde | `Firmware::sendOk` |

**Vuelta: la URC recibe.**

| Paso | Dónde |
| --- | --- |
| Lee del socket y corta por LF | `Session._run` |
| Procesa la línea | `Session._receive` |
| Interpreta el mensaje | `parse_message`, en `urc/protocol.py` |
| Libera el próximo `SEG` | `in_flight = None` en la rama `OK` |

**Qué hace el firmware en cada vuelta de `poll`, en este orden:**

1. Lee los Hall.
2. Compara con la cuenta de pasos (`checkLostSteps`, salvo en homing).
3. Frena el jog si hace falta (`checkJogHall`) y avanza el homing.
4. Avanza el movimiento: jog, segmentos o rampa.
5. Lee los bytes nuevos y atiende las órdenes completas.
6. Revisa el watchdog.
7. Envía `S` si pasaron 50 ms.

**Las capas de hardware** están detrás de `firmware/hal.h`, con seis funciones: `millis`, `step`, `enableDrivers`, `readHall`, `readByte` y `write`. Por eso el mismo núcleo corre en el Arduino, en Webots y en las pruebas (ADR 0002).

## 12. Autoevaluación

Tratá de responder antes de abrir cada respuesta.

<details><summary>1. ¿Por qué el protocolo usa articulaciones y no X, Y, Z, R?</summary>

Porque la posición articular es única, mientras que X, Y, Z, R admite dos configuraciones del codo. También es lo que el firmware conoce por sus pasos, y es donde están los límites físicos. La inversa queda en la URC, que además tiene que validar el trayecto y los choques. El operador igual trabaja en X, Y, Z, R.
</details>

<details><summary>2. ¿Qué significa <code>S HOMING 8 0 0 0 300 8 16 0</code>?</summary>

Homing en curso, solo J4 referenciado. J1–J3 valen 0 porque cuentan desde el arranque. J4 está a 3 mm. El Hall de J4 está activo. La cola está vacía (16 libres) y no terminó ningún segmento.
</details>

<details><summary>3. ¿Qué son <code>12000</code> en J4 y <code>9000</code> en J1?</summary>

120,00 mm (J4 abajo del todo, con Z = −25,33 mm) y 90,00°.
</details>

<details><summary>4. ¿Por qué R no es lo mismo que J3?</summary>

R es el rumbo en el mundo: R = J1 + J2 + J3. J3 es el giro relativo al antebrazo. Con J3 = 0, R puede valer cualquier cosa según J1 y J2.
</details>

<details><summary>5. ¿Por qué 159 segmentos para una recta de 200 mm? ¿Por qué no enviar solo el destino?</summary>

Porque una recta en X, Y, Z no es una recta en articulaciones. Interpolando solo entre extremos, el centro se desvía 16 mm. Son 159 porque a esa velocidad la recta tarda 3,17 s, y cada segmento dura 20 ms.
</details>

<details><summary>6. ¿<code>OK 5</code> quiere decir que el robot llegó al segmento 5?</summary>

No. Quiere decir que entró en la cola. Lo que indica lo terminado es el campo `último` de `S`.
</details>

<details><summary>7. ¿Qué pasa si la URC envía el <code>SEG 18</code> sin esperar el <code>OK 17</code>?</summary>

Si el 17 entró en la cola y hay lugar, se acepta. Si el 17 quedó retenido porque la cola está llena, responde `ERR 9 cola` y frena con rampa. La URC correcta nunca lo hace.
</details>

<details><summary>8. ¿Qué responde <code>JOG 1 + 99999</code> sin corriente? ¿Por qué?</summary>

`ERR 2 argumentos`. Primero se revisa la forma de la línea y después el estado.
</details>

<details><summary>9. Si se corta el cable en plena recta, ¿actúa el watchdog?</summary>

El robot sigue con lo que tiene en la cola, como máximo unos 320 ms, y queda en el último destino, sin rampa. El watchdog no llega a actuar, porque a esa altura el firmware ya está quieto. La referencia se conserva, aunque a plena velocidad esa parada podría perder pasos. La URC ve que deja de llegar `S`: a 0,5 s lo muestra como enlace demorado y a 1 s como cortado.
</details>

<details><summary>10. ¿Diferencia entre <code>STOP</code> y <code>HALT</code>?</summary>

`STOP` frena con rampa los segmentos y conserva la referencia. `HALT` para en seco y, si había movimiento, la pierde, porque frenar de golpe puede perder pasos.
</details>

<details><summary>11. ¿Cómo sabe el firmware que un motor perdió pasos?</summary>

No lo sabe al perderlos: no hay encoders. Al entrar en un imán, compara su cuenta con la posición conocida del flanco. Si difieren en 2 pasos completos o más, envía `EV LOST`. Hasta cruzar un Hall, la falla es invisible.
</details>

<details><summary>12. El profesor dice: «si la comunicación se demora al llegar al sensor, el motor sigue y se rompe». ¿Qué responden?</summary>

Separar casos. En jog y homing, el firmware frena solo con el Hall, sin depender del enlace. En reproducción, el Hall no frena: el camino se valida antes de mover y, si hay pasos perdidos, la URC envía `STOP`. Ahí dependemos más de la URC, y una mejora concreta es que el firmware rechace los `SEG` fuera de recorrido.
</details>

<details><summary>13. ¿Por qué un <code>SEG</code> de J1 a 90° en 20 ms da error?</summary>

`ERR 8 velocidad`: J1 tiene un máximo de 90 °/s (M1 gira 360 °/s, poleas 4:1), y eso sería 4500 °/s. El firmware calcula la velocidad de cada motor a partir de la distancia y el tiempo.
</details>

<details><summary>14. ¿Por qué J1 mueve dos motores?</summary>

Por el acople: M2 fija el ángulo absoluto del antebrazo, J1 + J2. Por eso J2 = (θM2 − θM1)/4. Para que J2 no cambie al mover J1, M1 y M2 dan los mismos pasos. La URC no se entera: lo resuelve el firmware.
</details>

## 13. Errores que no hay que cometer

| No digas | Decí |
| --- | --- |
| «Enviamos `S RUN` con los joints» | `S` lo **informa** la UCI. La orden es `SEG`. |
| «El sensor HALT» | El sensor es el **Hall**. `HALT` es una orden de parada. |
| «El heartbeat es cada medio segundo» | `PING` cada 250 ms; watchdog a 1 s. Los 500 ms son del jog en la URC. |
| «`OK` es que llegó» | `OK` es que entró en la cola. |
| «El Arduino no puede calcular la inversa» | «Elegimos la URC porque tiene que validar el trayecto; no medimos el costo en el UNO». |
| «El robot sabe dónde está» | Sabe dónde **cree** estar: la posición es estimada por pasos. |
| «Si se corta el enlace, siempre frena el watchdog» | El watchdog actúa con jog u homing. Con segmentos de 20 ms, antes se agota la cola. |
| «El firmware valida los límites» | Valida corriente, referencia y velocidad. Los límites y los choques los valida la URC. |
| «El jog siempre usa `JOG`» | Con referencia, el articular y el cartesiano usan `SEG`. |
| «Servidor» y «cliente» como nombres | URC y UCI. La URC escucha en TCP, pero no la define eso. |
| «Controlador», a secas | UCI, firmware o controlador de Webots, según corresponda. |

**Pendiente, sin desarrollar acá:** simular el choque con un objeto como una maceta. Un objeto cargado en `environment` (`config/scara.json`) debería rechazarse antes de mover; uno que el modelo no conoce no lo detecta ningún sensor, y lo esperable es que se note como pasos perdidos al cruzar un Hall. Falta comprobarlo en Webots.
