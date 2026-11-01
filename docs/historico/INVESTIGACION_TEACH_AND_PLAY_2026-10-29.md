# Investigación: grabar y reproducir trayectorias en el SCARA

**Estado: propuesta para discutir, 29/10/2026.** Nada de esto está decidido ni implementado. Reúne lo que pidió el profesor en la clase del 27/10, lo que aprendimos de AGSABOT, el estado actual del repositorio y una propuesta técnica. Cada decisión abierta tiene un código `D#` para resolverla en la sesión de preguntas (grill) y registrarla después como ADR.

## 1. Qué pidió el profesor y qué cambia

| Pedido | Qué implica respecto de lo que tenemos |
| --- | --- |
| Hacer algo como AGSABOT: mover articulaciones a mano, guardar puntos, formar una trayectoria, reproducirla. | Hoy solo hay "ir a un XYZ". Falta modo manual (jog), captura de puntos, gestor de trayectorias y reproducción. |
| En lugar de potenciómetros, teclas en Webots; una tecla guarda el punto. | Webots tiene que leer teclado y avisar al programa externo. |
| El protocolo informa la posición en todo momento; el programa externo acumula la lista y la reproduce respetando tiempos. | Telemetría periódica y envío de secuencias temporizadas. |
| Entre puntos: línea recta o el menor recorrido, ajustando las articulaciones. | Hoy se interpola en articulaciones; el extremo no sigue una recta. Hay que planificar en cartesiano. |
| Cadena cinemática híbrida: motores de hombro y codo en la base; mover el motor del hombro mueve hombro y codo. | Hoy Webots mueve las articulaciones directamente, como si cada una tuviera su motor. Mandar ángulos así puede diferir mucho del robot real. |
| Proponer nosotros el protocolo; lo de "comunicarnos por API" fue un error. | `scara-dev/1` (JSON) era provisional. Hay que diseñar un protocolo definitivo. |
| TCP/IP; en Linux `socat` hace de puente serie↔TCP; el robot real usaría Arduino por USB o con shield Ethernet. Webots es cliente TCP que recibe órdenes y debe operar **al nivel del Arduino** para que el reemplazo sea transparente. | Hoy Webots es **servidor** y habla JSON de 16 KB, imposible para un Arduino. Hay que invertir roles y bajar el protocolo a lo que un microcontrolador puede manejar. |
| Homing: el robot real no sabe dónde está al arrancar. Opción simulación: llevar a cero a mano y apretar Z. Opción real: sensores Hall, como una impresora 3D. Recomendado: Hall también en la simulación. | Hoy el ensayo arranca en una pose conocida y los "Hall" son una señal calculada a partir de la posición perfecta del simulador. |
| Los SolidWorks son la fuente de verdad; el PDF maestro está desactualizado. Motores: 2 NEMA 23 + 2 NEMA 17. | Cuando hay conflicto, gana el CAD. Hay que dejar documentado qué se tomó de dónde. |
| Simular movimiento y cinemática de los motores lo más real posible (drivers, transmisión, electrónica hasta donde se pueda). | Hay que modelar motores paso a paso, transmisión y pasos, no solo articulaciones ideales. |
| Documentar todo en una versión nueva del documento maestro, sin pisar la anterior. | Documento maestro v2 + ADRs por decisión. |

## 2. Qué es AGSABOT y qué conviene copiar

Fuente: informe de lectura de `~/Developer/AGSABOT` (PDFs y código completos).

**Arquitectura.** Dos partes, con los nombres de la cátedra:

- **UCI**: el Arduino. Lee 5 potenciómetros y mueve 5 servos en lazo abierto. Arranca en modo manual.
- **URC**: la aplicación de PC (Tauri: Rust + React). Monitorea, guarda trayectorias y las reproduce.

Se comunican por USB-serie a 115200 baudios con texto ASCII terminado en `;`. No hay TCP.

**Protocolo.**

| Sentido | Mensaje | Significado |
| --- | --- | --- |
| PC → UCI | `M;` | Modo manual: los servos siguen a las perillas. |
| PC → UCI | `S;` | Stop: quedan donde están. |
| PC → UCI | `T,86,3,132,97,0;` | Ir a esas 5 posiciones (enteros 0–180, "grados normalizados"). |
| UCI → PC | `M,89,90,92,95,91,89,90,92,95,91;` cada 100 ms | Modo, 5 perillas y 5 posiciones comandadas. |

**Teach-in.** Contra lo que suponíamos, **no hay botón físico**: el punto se guarda con el botón «Añadir Punto» de la aplicación, que toma la posición actual del brazo. La trayectoria se guarda como JSON con un diálogo de archivo.

**Reproducción.** La aplicación manda un `T` por punto y espera **1200 ms fijos**, sin confirmar llegada. No hay interpolación, ni tiempos por punto, ni pausa. Cada articulación va a su velocidad y llegan en momentos distintos.

**Interfaz.** Ventana principal con monitor de juntas (imagen y valor por articulación), conexión, botones de modo y gestor de trayectorias. El gestor tiene lista numerada de puntos, arrastrar para reordenar, clic derecho para borrar o sobrescribir, doble clic para ir al punto, guardar, cargar, nueva, ejecutar y añadir. Hay además una ventana de tráfico con los mensajes enviados y recibidos.

**Qué copiar:** separación UCI/URC; protocolo de texto corto; estado periódico; el punto se toma de la posición del robot, no de la entrada; arrancar en modo manual; la experiencia del gestor (lista, reordenar, sobrescribir, ir al punto, cambios sin guardar); ventana de tráfico.

**Qué no copiar** (bugs o carencias encontrados en el código):

- Reproducción a ciegas con un tiempo fijo.
- Stop que puede no enviarse y que no vacía la cola de puntos pendientes.
- Interfaz que muestra su propio modo y no el que informa el robot.
- Cola que reenvía órdenes viejas al reconectar.
- Sin homing, sin vigilancia de conexión (watchdog), sin parada de emergencia.
- Archivo con números como texto y sin versión ni unidades.

## 3. Estado actual del repositorio

```text
Navegador ⇄ HTTP ⇄ client/app.py (cliente TCP, cinemática inversa)
                         ⇄ TCP, JSON por línea, scara-dev/1
                   webots/controllers/scara_bridge (servidor TCP, scara/runtime.py)
                         → motores de Webots en cada ARTICULACIÓN
```

- **Sirve y se conserva:** `scara/kinematics.py` (directa e inversa), `scara/collisions.py` (rechazo de recorridos), modelo y mundo de Webots generados desde CAD, instrumentación del supervisor y documentación. Hay 37 pruebas y pasan.
- **Hay que rehacer:** roles TCP (hoy Webots es servidor); formato (JSON de hasta 16 KB); interpolación (articular quíntica, no recta); motores (accionan articulaciones directamente, sin transmisión ni pasos); Hall (calculados con la posición perfecta); el estado mezcla lo que sabría un Arduino con datos que solo tiene el simulador.

## 4. Arquitectura propuesta

```text
                         ┌──────────────────────────────────────────┐
                         │ URC · programa externo (PC)              │
                         │ servidor TCP :9000 · cinemática inversa  │
                         │ planificador (recta / articular, tiempos)│
                         │ trayectorias en disco · interfaz         │
                         └───────────────▲──────────────────────────┘
                                         │ protocolo scara/1 (texto por línea)
          ┌──────────────────────────────┼───────────────────────────────┐
          │                              │                               │
 ┌────────┴─────────┐        ┌───────────┴──────────┐        ┌───────────┴──────────┐
 │ Webots           │        │ socat (Linux)        │        │ Arduino + Ethernet   │
 │ "Arduino virtual"│        │ cliente TCP ⇄ USB    │        │ cliente TCP          │
 │ cliente TCP      │        └───────────┬──────────┘        └──────────────────────┘
 └────────┬─────────┘                    │ serie 115200
          │                     ┌────────┴─────────┐
          │                     │ Arduino real     │
          │                     └──────────────────┘
          │  canal de instrumentación :9001 (solo simulación)
          └──────────────► posición física real, fallas, carga, recarga
```

**Idea central: la frontera del firmware.** El protocolo solo transporta lo que un Arduino real podría saber: pasos emitidos, estado de los Hall, modo, botones. Todo lo que solo conoce el simulador (posición física real, inyección de fallas, carga, recargar el mundo) viaja por un canal separado de instrumentación. Así el programa externo no puede "hacer trampa": si funciona con Webots, funciona con el Arduino. Hoy `scara-dev/1` mezcla las dos cosas en el mismo mensaje `state`.

**Roles TCP.** El profesor dijo que Webots es cliente. Entonces el programa externo escucha y el robot se conecta:

- `socat TCP:<pc>:9000,forever,interval=1 /dev/ttyACM0,b115200,raw,echo=0`: socat abre el puerto serie del Arduino y se conecta como cliente al programa.
- Con shield Ethernet, el Arduino usa `EthernetClient` y se conecta igual.
- Webots hace lo mismo con un socket.

Para el programa externo los tres casos son idénticos: recibe una conexión y lee líneas.

**Detalle de transparencia.** Al abrir el puerto USB, la mayoría de los Arduino se reinician (señal DTR). Entonces conectar socat reinicia el firmware y **se pierde el homing**. Con Ethernet eso no pasa. Propuesta: el firmware siempre anuncia `BOOT` al arrancar, y el programa externo nunca supone que el robot sigue referenciado tras una reconexión. Webots puede emular las dos variantes con una opción.

**D1. Roles:** programa externo = servidor TCP, robot = cliente. *Recomendado: sí, es lo que pidió el profesor.*

**D2. Canal separado de instrumentación** para datos y acciones que solo existen en simulación. *Recomendado: sí.*

**D3. Cómo implementar el "Arduino virtual".**

- (A) **Núcleo de firmware en C++ compartido.** El mismo código corre en el Arduino y en el controlador de Webots. Solo cambia una capa fina de hardware (HAL): en el Arduino son pines, `Serial` y timers; en Webots son socket, teclado, receptores y el modelo de motores. El día del robot real se compila el mismo firmware: es literalmente "operar al nivel del Arduino". Costo: controlador de Webots en C++ (Webots lo soporta y la consigna admite `.cpp`), compilador en cada equipo y restricciones de microcontrolador (sin memoria dinámica, buffers fijos). En este Mac ya hay `clang`. La documentación de Webots indica compilar en Windows desde MSYS2: hay que probarlo en la PC Windows del grupo antes de comprometerse.
- (B) **Emulador en Python** que imita al firmware, y un sketch de Arduino escrito aparte más adelante. Más rápido hoy, pero el día del robot real hay que programar y depurar el firmware de cero. Es justo lo que el profesor quiere evitar.

*Recomendado: A.* Además permite probar el firmware con pruebas automáticas en la PC, sin Webots.

## 5. Protocolo propuesto `scara/1` (borrador)

**Principios.** Pensado para un Arduino (2–8 KB de RAM):

- Texto ASCII, un mensaje por línea terminada en LF; se ignora CR, así funciona el `println` de Arduino.
- Máximo 64 bytes por línea.
- Campos separados por espacio. Solo enteros: el Arduino AVR no imprime flotantes con `printf` y parsear flotantes es lento.
- Unidades enteras de punto fijo: J1–J3 en centésimas de grado (`9000` = 90,00°) y J4 en centésimas de mm (`6000` = 60,00 mm).
- Cada orden recibe `OK` o `ERR`.

Se puede leer y escribir a mano con `nc`, `socat` o el monitor serie del IDE de Arduino.

**PC → robot (UCI)**

| Mensaje | Qué hace |
| --- | --- |
| `HELLO` | Pide identificación. Respuesta: `HI SCARA fw=0.1 proto=1 axes=4`. |
| `PING` | Latido. Si el robot está en movimiento y pasa más de 1 s sin mensajes, se detiene solo (watchdog). |
| `ENABLE` / `DISABLE` | Habilita o corta los drivers. Sin corriente, J4 podría caer. |
| `HOME` / `HOME <j>` | Búsqueda de referencia con Hall, todos los ejes o uno. |
| `ZERO` | Referencia manual: declara que la pose actual es la de referencia (equivale a la tecla Z). |
| `JOG <j> <+\|-> <vel%>` / `JOG STOP` | Mover una articulación mientras dure la orden; sirve para jog desde la interfaz. |
| `SEG <n> <ms> <q1> <q2> <q3> <q4>` | Encolar el segmento `n`: llegar a esas posiciones absolutas en `ms` milisegundos, interpolando lineal en articulaciones. |
| `STOP` | Frena con rampa y vacía la cola. |
| `HALT` | Parada inmediata (emergencia). |
| `STATUS` | Pide un estado inmediato. |

**Robot (UCI) → PC**

| Mensaje | Cuándo |
| --- | --- |
| `BOOT fw=0.1 proto=1` | Al arrancar o reiniciarse. Significa "no estoy referenciado". |
| `S <modo> <ref> <q1> <q2> <q3> <q4> <hall> <libres> <seg>` | Cada 50–100 ms y ante `STATUS`. Incluye: modo (`IDLE`, `JOG`, `RUN`, `HOMING`, `FAULT`); máscara de ejes referenciados (`1111`); posición **estimada por pasos**; bits de Hall; lugares libres en la cola; último segmento terminado. |
| `OK <n>` / `ERR <código> <texto>` | Respuesta a cada orden. En `SEG`, `OK` sale recién cuando el segmento entró en la cola: eso es el control de flujo. |
| `EV CAPTURE <q1> <q2> <q3> <q4>` | Botonera local: se pidió guardar un punto (tecla Espacio en Webots). |
| `EV END` | Botonera local: terminar la trayectoria (Enter). |
| `EV UNDO` | Botonera local: borrar el último punto (Retroceso). |
| `EV HOMED <j>` / `EV LOST <j> <pasos>` | Eje referenciado, o diferencia detectada al cruzar un Hall: posible pérdida de pasos (ver §8). |

**Ejemplo: arranque y homing**

```text
UCI → BOOT fw=0.1 proto=1
URC → HELLO                 UCI → HI SCARA fw=0.1 proto=1 axes=4
URC → ENABLE                UCI → OK
URC → HOME                  UCI → OK
UCI → S HOMING 0000 ...     (busca J4, luego J1, J2 y J3; ver §8)
UCI → EV HOMED 4 ... EV HOMED 3
UCI → S IDLE 1111 0 9000 -9000 0 0000 16 0
```

**Ejemplo: reproducir un tramo recto.** El PC calcula la recta, la parte en segmentos de unos 20 ms y los manda; el robot responde `OK` mientras haya lugar en la cola:

```text
URC → SEG 1 20 4512 8990 -9001 6000    UCI → OK 1
URC → SEG 2 20 4525 8979 -9003 6000    UCI → OK 2
...                                     (si la cola se llena, el OK se demora)
UCI → S RUN 1111 4520 8984 -9002 6000 0000 3 1
```

Es la misma división de trabajo que GRBL (CNC con Arduino) y Klipper (impresoras 3D): la PC planifica y el microcontrolador ejecuta con su propio reloj. Así se "respetan los tiempos" aunque la red tenga demoras. A 50 segmentos por segundo son unos 2 KB/s, holgado para 115200 baudios (≈11 KB/s).

**D4. Formato.** Línea con LF, o `;` como AGSABOT. *Recomendado: LF* (más cómodo con socat y monitores); se puede aceptar `;` también.

**D5. Unidades del protocolo.** (A) Articulares en punto fijo; el firmware convierte a pasos y resuelve el acoplamiento M1/M2. (B) Pasos de motor; el PC sabe todo de la mecánica. *Recomendado: A.* La mecánica (poleas, microstepping) queda encapsulada en el firmware y la telemetría es legible. Igual el estado puede incluir pasos crudos para depurar.

**D6. Reparto de cálculo:** el PC hace cinemática inversa, recta y perfil de velocidad; el firmware interpola segmentos cortos y genera pasos. *Recomendado: sí.* Un Arduino no puede resolver la inversa a la frecuencia necesaria.

**D7. Nombre de las partes:** usar UCI/URC como AGSABOT. *Recomendado: sí,* por coherencia con la cátedra.

## 6. Cinemática híbrida: por qué importa

> Reconstruido de las listas de componentes de los `.SLDASM` y de los planos (`0-EnsambleBase`, `A-EnsambleBrazo`, `B-EnsambleAntebrazo`, `R-EnsambleRotacion`, `Z-EnsambleM4`). Los dientes se confirmaron por diámetro exterior: 20T = Ø12,2, 60T = Ø37,8, 80T = Ø50,4 mm. **Certeza alta** en la topología y las relaciones. **Media-alta** en qué motor físico es M1 y cuál M2 (se infiere del espaciador `0-ElevadorM2`). **Baja** en signos y cruces de correa: los fijamos nosotros como convención.

En un SCARA "serie" común, cada motor mueve una sola articulación. En este diseño, M1 y M2 están en la base, a 57 mm del eje central, y mueven dos ejes concéntricos:

- **M1** → polea 20T → correa → polea 80T sobre el **tubo exterior** `A-Eje`. Ese tubo gira en dos rodamientos 6203 y está abulonado al brazo (J1, reducción 4:1).
- **M2** → 20T → 80T sobre el **eje interior** `A-EjeInterior`, que pasa por dentro del tubo. Arriba, ese eje lleva una polea 60T. Una correa de unos 620 mm a lo largo del brazo la une con otra 60T sobre `B-Eje`, el eje del codo, que está **fijo al antebrazo**.
- **M3** va sobre el antebrazo, a 142 mm de J3: 20T → 80T en la muñeca, sobre rodamientos 6907. Sin acople.
- **M4** va sobre la columna Z y gira con ella: acople flexible → varilla ACME Ø8 de 4 hilos, 8 mm por vuelta. Sin acople con J3.

Consecuencia: **M2 fija el ángulo absoluto del antebrazo respecto del mundo, no el ángulo relativo J2.** Si gira M1 y M2 queda quieto, el brazo gira pero la correa mantiene la orientación del antebrazo en el mundo, y entonces J2 relativo cambia en sentido opuesto. Es lo que dijo el profesor: mover el motor del hombro mueve hombro y codo.

En ecuaciones, con θ el ángulo del eje de cada motor y ceros alineados:

```text
J1        = θM1 / 4
J1 + J2   = θM2 / 4        ⇒   J2 = (θM2 − θM1) / 4
J3        = θM3 / 4        (M3 en el antebrazo, si se confirma)
J4        = 8 mm · θM4 / 2π (tornillo ACME, 8 mm por vuelta)
```

Y al revés, para saber cuántos pasos dar: `θM1 = 4·J1`, `θM2 = 4·(J1 + J2)`. Es una matriz de 2×2 con enteros: el firmware la resuelve sin esfuerzo. Con 400 pasos por vuelta: `s1 = 4,444·J1[°]`, `s2 = 4,444·(J1 + J2)`, `s3 = 4,444·J3`, `s4 = 50·J4[mm]`.

**Tres consecuencias que conviene saber explicar en la defensa:**

1. **Mover solo M1 no cambia la orientación de la herramienta.** El rumbo absoluto es `ψ = J1 + J2 + J3 = (θM2 + θM3) / 4`: depende solo de M2 y M3. Al girar M1, el brazo gira pero el antebrazo y la muñeca conservan su orientación en el mundo, como un pantógrafo.
2. **Para mover solo J1, hay que mover M1 y M2 la misma cantidad de pasos.** Si no, J2 cambia en sentido contrario, 1:1.
3. **M2 recorre más de lo que dice el maestro.** Con J1 y J2 en ±135°, el ángulo absoluto del antebrazo cubre 540°: hasta 2400 pasos, no 1200. El maestro (p. 8) trata J2 como M2/4 e ignora el acople.

**Qué pasa si se ignora:** si Webots recibe ángulos y mueve J2 con su propio motor, el simulador mostrará movimientos que el robot real no hace. Por ejemplo, un jog de J1 con M2 quieto, en el robot real, cambia J2. Los esfuerzos también difieren: el par que sostiene al antebrazo lo aportan los dos motores combinados.

## 7. Simular los motores "lo más real posible"

Webots no tiene correas ni engranajes que vinculen dos articulaciones. La transmisión se modela en el controlador: el firmware emite pasos → el modelo de motor calcula el ángulo de cada rotor → la transmisión convierte a ángulos articulares → se ordenan las articulaciones de Webots.

| Nivel | Qué representa | Qué permite mostrar |
| --- | --- | --- |
| N0 (hoy) | Webots mueve cada articulación directamente. | Nada de motores. |
| N1 | Pasos y microstepping: resolución discreta. Acoplamiento M1/M2. Límites de velocidad y aceleración tomados de los motores. | El movimiento real del mecanismo, la resolución (cuánto mueve el extremo por paso) y que un jog de J1 cambia J2. |
| N2 | Par disponible según la velocidad (curva del motor y del driver) reflejado por la transmisión; **pérdida de pasos** cuando la carga supera ese par. | Fallas realistas: con sobrecarga o aceleración excesiva el robot "se corre" y el firmware no lo sabe; el Hall lo detecta al pasar. |
| N3 | Modelo electromecánico completo: par sinusoidal del rotor, resonancias, corriente del driver. | Detalle fino; riesgo numérico con paso de 2 ms. Probablemente excede el alcance. |

**D8. Nivel de modelado.** *Recomendado: N1 + N2.* N2 se puede hacer de forma estable: se sigue usando control de posición de Webots con par limitado. Si el error entre la posición pedida al rotor y la alcanzada supera medio ciclo eléctrico, el motor "salta" 4 pasos completos y el firmware no se entera. Eso es lo que hace un paso a paso real cuando se le pide más par del que tiene.

**Resolución, dato a decidir.** El maestro fija los TB6600 en 400 pasos por vuelta (medio paso). Con 4:1 son 0,225° por paso en la articulación. Un paso de J1 mueve el extremo **~1 mm a 250 mm del eje y ~2 mm con el brazo estirado**: una "recta" se vería escalonada. El TB6600 admite hasta 1/32 por llaves DIP. Con 1/8 (1600 pasos por vuelta) baja a ~0,5 mm en el peor caso. A cambio hacen falta más pasos por segundo: el UNO lo maneja con generación por interrupción de timer, como GRBL, pero no con la biblioteca AccelStepper. **D9: microstepping** (ver §11).

## 8. Sensores Hall y homing

**Sensor.** El CAD trae un `KY-003` que no está colocado en ningún ensamble: decidimos nosotros dónde va. Es un módulo digital (interruptor Hall): se activa cuando un imán se acerca a pocos milímetros.

**Cómo simularlo en Webots, sin trampa.** Webots no tiene sensor magnético, pero tiene **Emitter/Receiver de tipo radio con alcance esférico**: el receptor solo recibe si el emisor está dentro de un radio dado, y también informa la intensidad (1/distancia²) y la dirección. Modelo propuesto:

- Imán = `Emitter` radio con alcance de unos 5 mm y un canal por articulación, montado en la pieza que se mueve.
- KY-003 = `Receiver` en la pieza fija, con un umbral y un poco de histéresis.

La activación sale de la **geometría real** del modelo 3D, no de leer la posición perfecta. Alternativa: `DistanceSensor` de rayo corto apuntando a un "imán" sólido. Descartado: `TouchSensor`, que genera choques físicos.

**Qué dicen las fuentes.** El maestro (p. 14) prevé *«sensores de inicio y final de carrera en los cuatro ejes, con imanes de neodimio y sensores de efecto Hall»*, sin encoders. No dice cuántos sensores hay, dónde van ni su polaridad; la sección 8.4 «Sensor Hall» está vacía. El KY-003 no figura en ningún ensamble y no hay pieza de imán. **La ubicación la definimos nosotros.**

**Ubicación propuesta (D10).** Un sensor por articulación, como sugiere el maestro, entre las dos piezas de esa articulación. Hay dos imanes por sensor: uno en el **inicio** de carrera (referencia de homing) y otro en el **fin** (protección por sobrerrecorrido). Con un solo sensor por eje, el firmware distingue el extremo por el sentido de giro. Ahorra entradas del Arduino (ver §11).

| Sensor | Fijo en | Imanes en | Mide |
| --- | --- | --- | --- |
| H1 | Torre | Brazo, cerca de J1 = −135° y +135° | J1 |
| H2 | Brazo, en el codo | Antebrazo, cerca de los dos extremos de J2 | J2 **relativo** |
| H3 | Antebrazo | Polea de muñeca, cerca de los dos extremos de J3 | J3 |
| H4 | Cuerpo Z | Pistón, arriba y abajo | J4 |

*Alternativa para H2:* ponerlo en la base, sobre la polea 80T de M2. Mediría el ángulo absoluto del antebrazo y permitiría referenciar M2 sin depender de M1. **No lo recomiendo**: los topes que importan (cables en los carreteles, choque brazo–antebrazo) son del J2 relativo, y los cables de M3 y M4 ya pasan por el brazo, así que llevar uno más al codo no agrega dificultad.

**Secuencia de homing (D11):**

1. **J4 sube hasta su sensor**, para alejar la herramienta de la mesa.
2. **J1, moviendo M1 y M2 juntos** la misma cantidad de pasos, así J2 no cambia mientras se busca J1.
3. **J2 con M2 solo**: con M1 quieto, M2 cambia únicamente J2.
4. **J3 con M3.**

En cada eje: avance rápido hasta el flanco del Hall; retroceso hasta que se apague; aproximación lenta al mismo flanco, siempre desde el mismo lado para ser repetible; se fija el cero más un offset configurado. La búsqueda está acotada por pasos y tiempo. Si el Hall está activo al inicio, primero se sale de él. Un Hall trabado aborta sin declarar referencia.

**Riesgo de choque durante el homing.** Mientras no hay referencia, no se puede verificar colisiones. Con el codo muy plegado (|J2| cerca de 135°), el soporte Z queda a unos 190 mm del eje J1. El banco actual ya detecta ahí contacto con la torre. Propuesta: exigir una **pose de arranque segura** (codo con |J2| < 90°, que el operador verifica o alcanza con jog) y buscar a velocidad baja. En la simulación, la pose aleatoria inicial se sortea dentro de esa zona. *Alternativa más elegante, si sobra tiempo:* un imán largo en sector, que cubra medio recorrido de J2. Así el estado del sensor dice de qué lado del cero está el codo y no hace falta ir a un extremo plegado.

**Arranque en Webots:** el mundo arranca en una pose **arbitraria** (aleatoria dentro de una zona segura) y el firmware arranca "no referenciado": no acepta `SEG` hasta hacer `HOME` o `ZERO`, pero sí permite jog. Así se demuestra el ciclo real.

**Opción manual (tecla Z):** el operador lleva el robot con jog hasta unas marcas visuales de cero y aprieta Z (o manda `ZERO`). El firmware fija esa pose como referencia. Las dos opciones conviven.

**Diagnóstico gratis:** cada vez que un eje cruza su Hall durante el trabajo normal, el firmware compara los pasos contados con los esperados. Si difieren, informa `EV LOST`. Es una forma realista de detectar pasos perdidos **sin encoders**, con la limitación de que solo se detecta al pasar por el sensor.

## 9. Teach con teclado y captura de puntos

**Concepto.** El teclado de Webots representa una **botonera local** conectada al Arduino, el equivalente de las perillas de AGSABOT. En el firmware compartido es una función de la capa de hardware: en Webots lee teclas y en el robot real leería pulsadores. Además, la interfaz puede hacer jog por protocolo (`JOG`), que funciona igual con el robot real sin botonera.

**Mapeo propuesto (D12).** Sigue el ejemplo del profesor, pares en la fila del medio:

| Tecla | Acción |
| --- | --- |
| A / S | J1 − / + |
| D / F | J2 − / + |
| G / H | J3 − / + |
| J / K | J4 sube / baja |
| Mayús + tecla | Jog lento (ajuste fino) |
| Espacio | Guardar punto (`EV CAPTURE` con la posición estimada) |
| Retroceso | Borrar el último punto |
| Enter | Terminar la trayectoria: la interfaz pide nombre y la guarda |
| Z | Referencia manual (`ZERO`) |
| Esc | Stop |

Detalles de Webots: hay que hacer clic en la vista 3D para que reciba el teclado; detecta hasta 7 teclas simultáneas mientras están apretadas.

**Jog articular o por motor.** Si la tecla de J1 moviera solo M1, el antebrazo conservaría su orientación y J2 cambiaría. Propuesta: el jog es **articular**; el firmware mueve M1 y M2 juntos para que solo cambie J1. Opcionalmente, un modo "jog por motor" para mostrar el acoplamiento en la defensa.

**Dónde vive la trayectoria (D13).** En el programa externo, como en AGSABOT: el robot solo avisa "capturar"; la lista, el nombre y el archivo son del PC. Formato propuesto:

```json
{
  "formato": "scara-trayectoria/1",
  "nombre": "pick-and-place-1",
  "creada": "2026-10-29T18:30:00-03:00",
  "unidades": {"J1-J3": "grados", "J4": "mm", "xyz": "mm"},
  "puntos": [
    {"q": [45.12, 89.90, -90.01, 60.00],
     "xyz": [240.1, 250.3, 34.7], "yaw": 45.0,
     "movimiento": "LIN", "velocidad": 0.5, "espera_ms": 0}
  ]
}
```

Se guarda `q`, la verdad capturada, porque incluye la configuración del codo. `xyz` se recalcula para mostrar.

## 10. Reproducción: recta o menor recorrido

**Dos tipos de movimiento por tramo (D14):**

- **LIN (recta):** el extremo va en línea recta de un punto al siguiente; la orientación (yaw) se interpola. El PC muestrea la recta, resuelve la inversa en cada muestra y manda segmentos.
- **PTP (punto a punto sincronizado):** se interpola en articulaciones y todas llegan a la vez. Es el "menor recorrido" para los motores y siempre es posible si el punto lo es.

**Cuándo una recta es imposible** y hay que avisar o pasar a PTP:

- La recta sale del área alcanzable, por ejemplo al pasar cerca de la torre.
- Los dos puntos tienen el codo en configuraciones distintas (izquierda/derecha): para cambiar de configuración el brazo tiene que estirarse por completo, lo cual es una singularidad.
- Alguna muestra viola límites articulares, velocidades de motor o el chequeo de colisiones.

El planificador verifica todo antes de mandar el primer segmento. Si algo falla, rechaza o propone PTP; nunca arranca y se frena a mitad de camino.

**Tiempos.** Cada punto puede tener velocidad y espera. El PC arma un perfil trapezoidal sobre la longitud del camino y lo respeta con el reloj del firmware. Hay play, pausa (frena y conserva el punto actual), stop (vacía la cola), loop y "ejecutar desde el punto seleccionado". Mientras se reproduce, la interfaz resalta el punto en ejecución usando el número de segmento que informa el estado.

**Error de cuerda:** dentro de cada segmento corto el firmware interpola lineal en articulaciones, así que el extremo se aparta de la recta unas micras. Se puede calcular y mostrar.

## 11. Datos mecánicos y electrónicos

Fuente: maestro v1 (02/05/2026) y planos. Los datos sin observación los da el maestro y no contradicen al CAD.

| Tema | Dato | Observación |
| --- | --- | --- |
| Controlador | **Arduino UNO**, gabinete separado del brazo (p. 14) | 2 KB de RAM, 32 KB de flash, 20 pines de E/S. |
| Drivers | Un **TB6600** por motor, todos a **400 pasos/vuelta** (p. 14) | El TB6600 permite 1/1 a 1/32 por llaves DIP. |
| Alimentación | 36 V 10 A para los drivers; 12 V 2 A para Arduino y ventiladores | |
| M1, M2 | Minebea 23KM-K381-P1, NEMA 23, 1,8°, 6 cables | Corriente y resistencia: «??» en el maestro. |
| M3 | Shinano Kenshi STP-42D221-03, NEMA 17 | Corriente: «??». |
| M4 | 42D265, NEMA 17, 1,9 V, 0,7 A, 4 cables | |
| Transmisión | M1–M3 con 20T→80T (4:1); codo 60T→60T; J4 con ACME de 8 mm/vuelta, 4 hilos | ACME de 4 hilos y paso largo: probablemente **no autobloqueante**. Sin corriente, J4 cae. |
| Excursiones | J1 y J2 270°, J3 300°, J4 120 mm | M2 recorre hasta 540° de salida (§6). |
| Velocidad | «1000 rpm» por motor, sin carga; aceleraciones «??» | A 400 pasos/vuelta son 6,7 kHz por motor. Hay que acotar velocidades. |
| Sensores | Hall de inicio y fin en los cuatro ejes; sin encoders | Ubicación no definida (§8). |
| Sin dato | Diagrama de conexión; capítulos de software y protocolo; ficha del sensor Hall | Páginas con título y sin contenido. |

**Presupuesto de pines del UNO (D18).** Es un hallazgo que condiciona el diseño:

| Uso | Pines |
| --- | --- |
| STEP + DIR × 4 motores | 8 |
| ENABLE común a los 4 drivers | 1 |
| Hall: 1 entrada por eje, con los dos imanes leídos por el mismo sensor | 4 |
| **Subtotal** | **13** |
| Serie por USB (D0, D1) | 2 |
| Shield Ethernet (SPI D10–D13 + D4) | 5 |

- **Con USB + socat:** 13 + 2 = 15 de 20. Entra.
- **Con shield Ethernet:** 13 + 5 + 2 = 20 de 20. Entra justo, sin margen para una botonera física.
- **Con 8 sensores separados** (inicio y fin con entradas propias) no entra con Ethernet.

Conclusión: un sensor por eje, o dos en paralelo como en GRBL. Una botonera física en el UNO requeriría una escalera de resistencias en una entrada analógica, o pasar a un Arduino Mega.

**Microstepping (D9).** Mantener 400 pasos/vuelta como el maestro (~2 mm por paso en el extremo con el brazo estirado), o subir a 1/8 (~0,5 mm). *Recomendado: 1/8,* justificado por la calidad de las rectas, con velocidades acotadas para no superar la frecuencia de pasos que soporta el UNO. Es configurable: el simulador lo toma de la configuración.

**Firmware en el UNO.** Con 2 KB de RAM entra una cola de unos 16 segmentos de 4 enteros más el tiempo (≈350 bytes), el buffer de línea (64 bytes) y el estado. Hay que prohibir memoria dinámica y `String`, y no usar flotantes en la interrupción de pasos. Es una restricción buena: obliga a un firmware simple y explicable.

**Pendiente de datos.** Faltan curvas de par de los motores y corrientes de los drivers para el nivel N2 de §7. Se pueden buscar las hojas de datos de los modelos que nombra el maestro; si no aparecen, se usan valores típicos de NEMA 23 y NEMA 17 declarados como supuestos.

## 12. Interfaz

Se mantiene la interfaz web local servida por Python: funciona en los tres sistemas y no requiere instalar nada. Contenido propuesto, tomando lo bueno de AGSABOT:

1. **Conexión:** robot conectado, `BOOT`, versión, referenciado sí/no y botón Homing.
2. **Monitor:** las 4 articulaciones (estimadas por pasos) y el XYZ calculado; estado de Hall; modo informado por el robot, nunca uno local.
3. **Jog:** botones por articulación, como alternativa al teclado.
4. **Gestor de trayectorias:** lista de puntos con XYZ y q, tipo de movimiento, velocidad y espera; reordenar, sobrescribir con la pose actual, borrar, ir al punto, guardar con nombre, cargar, nueva; play, pausa, stop, loop; punto en ejecución resaltado; "cambios sin guardar".
5. **Tráfico:** mensajes crudos enviados y recibidos, con hora real.
6. **Banco de ensayo (solo simulación):** verdad del simulador (posición física y error contra la estimada), fallas, carga y recarga. Va por el canal de instrumentación, visualmente separado.

**D15. Interfaz web local vs aplicación de escritorio.** *Recomendado: web local.* Ya existe, no agrega dependencias y la consigna admite expresamente *«una aplicación visual de escritorio, o una página web»*. La consigna también deja libre quién es servidor y quién cliente, y pide *«mensajes de texto claro, regulados por un protocolo de comunicación»*: `scara/1` cumple.

**Aclaración «API».** El navegador habla HTTP con el programa Python. Eso es interno de la URC, no la comunicación con el robot, que es solo TCP con `scara/1`. Hay que confirmar qué fue exactamente lo que el profesor marcó como error.

## 13. Qué pasa con el código actual (D16)

| Archivo | Destino propuesto |
| --- | --- |
| `scara/kinematics.py`, `scara/collisions.py` | Pasan a ser parte del planificador de la URC. Se agregan recta, perfil y verificación por muestras. |
| `scara/runtime.py`, `scara/transport.py`, `scara_bridge.py` | Reemplazados por el firmware (C++) y el controlador de Webots cliente. `scara-dev/1` queda como histórico. |
| Fallas, carga, recarga, inspecciones | Se mudan al canal de instrumentación (supervisor). |
| `client/app.py` + `index.html` | Se reescriben como servidor TCP, sesión con la UCI, planificador y gestor de trayectorias. |
| Modelo y mundo de Webots | Se agregan imanes/sensores Hall y la pose inicial aleatoria. Los motores pasan a recibir lo que calcula el modelo de transmisión. |

## 14. Documento maestro v2 (D17)

Propuesta: `docs/maestro/SCARA-Master-v2.md`, exportado a PDF. El PDF original no se toca. Estructura:

1. Cambios respecto de la v1 (02/05/2026) y fuentes: el CAD manda.
2. Mecánica vigente: datos tomados del CAD, con discrepancias resueltas y su justificación.
3. Transmisión y cinemática híbrida.
4. Electrónica: Arduino, drivers, microstepping, Hall y pines.
5. Protocolo `scara/1`.
6. Homing y seguridad.
7. Teach y reproducción.
8. Simulación: qué se modela y qué no.
9. Registro de decisiones: un ADR por decisión `D#`, con fecha, alternativas y motivo.

## 15. Decisiones a resolver

Las decisiones, su estado y su justificación se mantienen en el [registro de decisiones](REGISTRO_DE_DECISIONES.md). Algunas cambiaron respecto de esta propuesta. Por ejemplo, el jog pasó de la ventana de Webots al teclado de la URC ([ADR 0007](adr/0007-jog-desde-la-urc.md)). Ante una diferencia, vale el registro.

## 16. Posibles consultas al profesor

No queda ninguna consulta bloqueante. Las tres candidatas se resolvieron el 29/10/2026:

- **Tercer NEMA 23:** el ensamble guarda el nombre `NEMA23-2`, pero solo `NEMA23-1` y `NEMA23-3` tienen ubicación recuperable y aparecen en los planos. Es una instancia suprimida o residual. Recomendación: 2 NEMA 23 + 2 NEMA 17, como dicen el profesor y el maestro (D20).
- **Botonera física:** no; alcanza con jog desde la URC.
- **Pasos crudos vs unidades articulares:** unidades articulares ([ADR 0003](adr/0003-protocolo-en-unidades-articulares.md)).

Para revisar en la próxima clase, como propuestas ya implementadas: microstepping 1/8 (D9) y ubicación de los Hall (D10).

## 17. Plan de trabajo tentativo

Se ajusta después del grill. Primero una **bala trazadora**: el camino más delgado que atraviesa todas las capas y demuestra la arquitectura. Después se ensancha en paralelo.

| Ticket | Entrega | Bloqueado por |
| --- | --- | --- |
| T1 Bala trazadora | Webots (C++) se conecta como cliente a la URC. Con A/D en la página de la URC (jog articular) se mueve J1, moviendo M1 y M2 por el acople. La posición llega a la interfaz. Espacio captura un punto, que aparece en la lista. Play lo reproduce con un movimiento PTP. | Decisiones D1–D7 |
| T2 Protocolo `scara/1` completo | Especificación, vectores de prueba de conformidad, `HELLO`/`PING`/watchdog, `BOOT`, `STOP`/`HALT`. | T1 |
| T3 Transmisión N1 | Pasos y microstepping, acople M1/M2, M3, ACME, límites de motor; la planta de Webots mueve las articulaciones desde los motores. | T1 |
| T4 Hall y homing | Imanes y KY-003 en el modelo, Emitter/Receiver, `HOME`, `ZERO`, arranque cerca de la pose de reposo y no referenciado. | T3 |
| T5 Planificador | LIN y PTP, perfil temporal, verificación previa (alcance, codo, límites, colisiones), envío por segmentos con control de flujo. | T1 |
| T6 Gestor de trayectorias | Archivo con nombre, edición, play/pausa/stop/loop, punto en ejecución, ventana de tráfico. | T5 |
| T7 Canal de instrumentación | Verdad del simulador separada; mudar fallas, carga y recarga. | T1 |
| T8 Pérdida de pasos (N2) | Par según velocidad, saltos de paso y detección `EV LOST` al cruzar un Hall. | T3, T4 |
| T9 Camino al robot real | Receta de socat, prueba con puerto serie virtual y sketch Arduino con la capa de pines; compila sin hardware. | T2 |
| T10 Maestro v2 + ADR | Documento nuevo con todas las decisiones y su justificación. | Grill |
| T11 Defensa | Guion, demostraciones y material de estudio (`/teach`). | Casi todo |

## Fuentes

- Consigna del TP final (6 p., rev. 13/10/2026) y documento maestro v1 (27 p., 02/05/2026). Planos de `Modelos3D/`; listas de componentes de los `.SLDASM`.
- Informe de lectura de AGSABOT: `docs_AGSABOT/*.pdf` y `soft_AGSABOT/**`.
- Código actual: `scara/`, `client/`, `webots/` y [PROTOCOLO_SCARA_DEV_1.md](PROTOCOLO_SCARA_DEV_1.md).
- Webots R2025b: [Emitter](https://github.com/cyberbotics/webots/blob/master/docs/reference/emitter.md), [Receiver](https://github.com/cyberbotics/webots/blob/master/docs/reference/receiver.md) y [Keyboard](https://github.com/cyberbotics/webots/blob/master/docs/reference/keyboard.md).
- Arquitecturas de referencia: GRBL (control CNC sobre Arduino) y Klipper (planificación en el host y ejecución temporizada en el microcontrolador).
