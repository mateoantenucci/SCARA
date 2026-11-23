# Guion de la presentación (borrador)

12 minutos de exposición y después preguntas. Sin diapositivas: se muestra en vivo el gemelo en Webots y la página de la URC con el panel **Demo de la presentación**.

Las acciones van en negrita entre corchetes; lo que se dice, en párrafos con sangría. Los números entre corchetes con «leer» se leen de la pantalla en el momento, porque pueden cambiar un poco.

## Reparto

Cada uno toma una letra y reemplaza A, B, C o D por su nombre. El **piloto** maneja la compu toda la presentación: es C, que además hace el teach con el teclado. Cuando habla otro, el piloto hace los clics que marca el guion.

| Persona | Nombre | Bloques | Habla | Preguntas que conviene que conteste |
| --- | --- | --- | --- | --- |
| A | | 1. Qué es · 2. No sabe dónde está · 7. Conclusión | ~2:50 | Gemelo digital y alcance (sección 1 del banco), y uso de IA |
| B | | 3. Homing y sensores Hall · 4. Arquitectura y protocolo | ~2:50 | Sensores Hall, firmware y protocolo (secciones 3 y 4) |
| C (piloto) | | 5. Teach & play, y todos los clics | ~1:25 | Programa externo, cinemática y planificación (sección 5) |
| D | | 6. Fallas | ~2:40 | Modelo en Webots y fallas (secciones 2 y 6) |

Las preguntas las puede contestar cualquiera; la última columna dice quién debería estudiar cada tema más a fondo.

## Antes de empezar

1. En la compu de la presentación, **compilar el controlador** desde Webots (clic derecho en el robot → *Edit Controller* → **Build**) y *Reload World*.
2. Levantar la URC (`python3 -m urc.app`) y abrir **http://127.0.0.1:8766/#demo**.
3. Webots en **Real-time**, con una vista que muestre el brazo entero y el lugar de la maceta (X 375, Y −217 mm desde la torre).
4. Pantalla partida: Webots a la izquierda, el navegador a la derecha. La página, arriba de todo: tienen que verse la tabla de posiciones, el panel Demo y el tráfico sin desplazarse.
5. Si ensayaron antes: **Para ensayar → Recargar el mundo**, así arranca como recién abierto (desviado y sin referencia).
6. Notificaciones apagadas y nada más abierto.

## Tiempos

| Bloque | Quién | Desde | Hasta | Habla | Máquina |
| --- | --- | --- | --- | --- | --- |
| 1. Qué es | A | 0:00 | 0:55 | ~50 s | — |
| 2. No sabe dónde está | A | 0:55 | 1:35 | ~35 s | arranca el homing |
| 3. Homing y sensores Hall | B | 1:35 | 3:05 | ~1:25 | homing: 62 s + vuelta al reposo, mientras habla |
| 4. Arquitectura y protocolo | B | 3:05 | 4:30 | ~1:25 | — |
| 5. Teach & play | C | 4:30 | 6:35 | ~1:25 | jog ~15 s, grabada ~6 s, cuadrado 13 s |
| 6. Fallas | D | 6:35 | 10:00 | ~2:40 | ~20 s, más pausas para mirar |
| 7. Conclusión | A | 10:00 | 11:25 | ~1:25 | — |
| Margen | | 11:25 | 12:00 | | |

Quedan ~35 s de margen. Si en el ensayo se pasan, los párrafos marcados **[recortable]** ahorran ~40 s más.

«Habla» es el texto leído a unas 130 palabras por minuto.

---

## 1. Qué es (A · 0:00–0:55)

**Habla: A** · clics: C

**En pantalla:** Webots, con el robot quieto.

> Buenas. Somos el equipo Alan Turing: [nombres]. Nos tocó el SCARA, un brazo de cuatro ejes donde el hombro, el codo y la muñeca giran —son J1, J2 y J3— y el cuarto eje, J4, sube y baja la herramienta. Lo mueven cuatro motores paso a paso y este es un diseño sin encoders (es decir que el robot no sabe su posicion exacta en cada momento)
>
> Como el robot no está construido diseñamos un gemelo digital en Webots a partir de las piezas modeladas, el firmware del Arduino que lo controlaria, el programa externo para manejarlo —que es esta página— y el protocolo de texto que los conecta.

## 2. No sabe dónde está (A · 0:55–1:35)

**Habla: A** · clics: C

**En pantalla:** la tabla «Posición estimada por pasos».

> «Estimada» es lo que sabe el firmware: Arranca en cero tomando como referencia la posicion de reposo y cuenta los pasos que le mandó a cada motor. «Simulado» es dónde está de verdad, según el simulador. Como ven no coinciden: el mundo arranca con el brazo desviado hasta diez grados, como un robot que nadie dejó exacto. Por eso para que el robot descubra su posicion lo primero que hay que hacer es el homing.

**[PILOTO: Arranque → «Habilitar y homing»]**

## 3. Homing y sensores Hall (B · 1:35–3:05)

**Habla: B** · clics: C

**En pantalla:** Webots, con el robot buscando sus sensores. Abajo, el tráfico del panel. El homing va en orden J4 (hasta ~18 s), J1 (~32 s), J2 (~45 s) y J3 (~58 s), y después vuelve al reposo: este bloque dura lo mismo.

**[señalar el tráfico, antes de que aparezca el primer EV HOMED]**

> Abajo ven la conversación real con el firmware. Al conectarse, la URC saludó con HELLO y el firmware contestó BOOT y HI. Recién mandamos ENABLE y HOME, y ahora el firmware busca solo el sensor Hall de cada eje: J4, J1, J2 y J3.

**[señalar el pistón en Webots: J4 está subiendo]**

> El documento maestro preveía sensores Hall con imanes en los cuatro ejes, pero no decía dónde. La ubicación la propusimos nosotros: un sensor KY-003 en la parte fija y dos imanes en la parte que se mueve, uno en cada extremo del recorrido. Uno es la referencia del homing y el otro, el fin de carrera.
>
> En J4, que es el que busca ahora, los imanes van por dentro del pistón de aluminio y el sensor los lee a través de la pared.

**[señalar el sensor de J1, sobre la torre, cuando empieza a girar el brazo]**

> En los otros tres ejes, los imanes están pegados al carretel de la polea y el sensor los mira desde una escuadra. Quedan cinco grados antes del tope mecánico, así el homing nunca choca.
>
> Para fijar el cero, va rápido hasta el imán, retrocede y vuelve despacio al mismo borde. Cada vez que lo encuentra, avisa: EV HOMED y el número del eje.

## 4. Arquitectura y protocolo (B · 3:05–4:30)

**Habla: B** · clics: C

**[cuando termina el homing y vuelve al reposo]**

> Listo: estimada y simulada coinciden, y en la columna Hall está activo el de J4: en reposo, el pistón descansa sobre su imán de abajo.
>
> Cómo está armado: esta página es la URC, el programa externo, en Python. Webots corre el controlador del robot, y adentro corre el firmware: el mismo código C++ que compila para el Arduino UNO del robot real. Solo cambia la capa que toca el hardware.
>
> Entre los dos va el protocolo scara/1, por TCP: texto, una línea por mensaje y solo números enteros. La URC decide los movimientos; el firmware los ejecuta, pero si deja de escuchar a la URC por un segundo, frena solo.
>
**[señalar «Último S», arriba del tráfico]**

> Lo que no aparece en el tráfico es el estado, la línea S, que llega veinte veces por segundo. Es esta: «S IDLE 15 0 0 0 12000 8 16» y un número más. IDLE, quieto; 15, los cuatro ejes con referencia; las cuatro posiciones en centésimas —12000 son 120 mm—; 8, el Hall de J4 activo, y 16 lugares libres en la cola. La tabla de arriba es esa línea decodificada.

## 5. Teach & play (C · 4:30–6:35)

**Habla: C**

**En pantalla:** Webots y el panel.

**[PILOTO: Teach & play → «Trayectoria nueva»]**

> Movemos el robot con el teclado: cada tecla mueve un eje.

**[R unos 3 s: sube J4 · S unos 3 s: dobla el codo · Espacio]**

> Con la barra espaciadora guardamos el punto. Con Tab pasamos a cartesiano: las mismas teclas ahora mueven la punta en X, Y y Z, en línea recta. Para eso la URC resuelve la cinemática inversa en cada paso.

**[Tab · A unos 3 s · Espacio · F unos 2 s · Espacio]**

> Y lo reproducimos.

**[PILOTO: «▶ Grabada»]**

**[recortable: la segunda mitad, desde «Después la parte…»]**

> Antes de mover, la URC planificó la trayectoria entera y la verificó: los límites de cada eje, el alcance, la velocidad de los motores, que el codo no cambie de lado y que no choque con la torre ni con la base. Si algo no pasa, no manda nada y explica por qué. Después la parte en segmentos de 20 milisegundos y se los manda al firmware: cada uno es un SEG con el destino, y espera el OK antes de mandar el siguiente. El firmware los encola —entran 16— y los ejecuta con su propio reloj.
>
> Hay dos tipos de tramo. En el PTP cada eje va directo a su destino y la punta hace una curva. En el LIN la punta sigue una recta. Este cuadrado es todo LIN.

**[PILOTO: «▶ Cuadrado LIN»]**

## 6. Fallas (D · 6:35–10:00)

**Habla: D** · clics: C

> Ahora, como es un gemelo digital queremos ver como se comportaria el robot real ante distintas fallas. Para eso armamos en la simulación un banco de ensayo que provoca estas situaciones. Va por un canal aparte, con otro protcolo, ya que el robot real no lo tendría. Vamos a mostrar tres fallas:

### Maceta (~1:40)

**[PILOTO: Falla 1 → «1 · Poner la maceta e ir»]**

> Ponemos una maceta en el camino de un barrido y llevamos el brazo al principio. La URC no sabe que está: el robot real no tiene cámara ni sensores del entorno.

**[PILOTO: «2 · Barrer» · todos miran Webots]**

> Choca. El motor no tiene fuerza para empujarla y pierde pasos, y el firmware sigue contando como si nada. Miren la tabla: la URC cree que el codo está en −60 grados; el simulador dice [leer: unos −98]. No hubo ningún error ni aviso.

**[PILOTO: «3 · Sacar la maceta»]**

### F1: pasos perdidos que el robot sí detecta (~1:20)

> ¿Hay algo que el robot pueda detectar? Sí: los imanes.

**[PILOTO: Falla 2 → «1 · J4 a 60 mm, 5 kg, M4 50 %»]**

> Le ponemos cinco kilos a la herramienta y le bajamos a la mitad la corriente al motor de J4: tiene menos fuerza.

**[PILOTO: «2 · Subir J4»]**

> Le pedimos que suba hasta 10 milímetros. La URC dice 10; el pistón no se movió de 60.

**[PILOTO: «3 · M4 100 % y estacionar» · señalar el tráfico]**

> Volvemos al reposo. Al bajar, el imán de abajo aparece antes de lo que esperaba la cuenta de pasos, y el firmware avisa: EV LOST, eje 4, [leer: unos 1250] pasos. La URC marca la referencia como dudosa y no deja reproducir hasta hacer homing de nuevo.
>
> Y fíjense en Webots: el codo sigue doblado por la maceta. Ese no lo detectó nadie, porque los imanes del codo están en los extremos de su recorrido y no pasó por ahí.

### F5: se reinicia la placa (~0:45)

> La última: la placa se reinicia, como un corte de alimentación.

**[PILOTO: Falla 3 → «Subir J4 y reiniciar la UCI»]**

> Sin corriente, J4 cae por su peso. Por el protocolo llega un BOOT en plena sesión. Para la URC, todo BOOT significa robot sin corriente y sin referencia, y no supone nada más. Con el Arduino real es igual: abrir el puerto USB lo reinicia.

**[recortable: se puede dejar para las preguntas]**

> El banco tiene más: un sensor Hall trabado, el enlace cortado con el watchdog, un empujón en la punta, J4 contra una mesa y mover el brazo a mano. Si quieren, después las mostramos.

## 7. Conclusión: para qué sirve el gemelo (A · 10:00–11:25)

**Habla: A** · clics: C

**En pantalla:** Webots.

> Para cerrar, qué nos deja un gemelo digital como este.
>
> El SCARA todavía no existe, pero ya tiene su programa, su protocolo y su firmware funcionando. Eso nos permite decidir cosas del diseño antes de construirlo —dónde van los sensores, cuánta fuerza necesitan los motores— y ver qué pasa cuando algo falla, sin romper nada.
>
> Cuando se construya, el firmware se carga en el Arduino y Webots se reemplaza por el robot, sin tocar el programa externo. Y el gemelo no se descarta: se calibra con mediciones del robot real para que se le parezca cada vez más.
>
> Ahí se vuelve un banco de pruebas sin riesgo. Como el simulador sabe la verdad y puede provocar fallas, se pueden generar miles de corridas y situaciones automáticas con la respuesta correcta y tal vez usarlas para optimizar trayectorias antes de probarlas en la máquina o quien sabe para entrenar un modelo de aprendizaje automático.
>
> Esa es la idea: tener una versión lo más cercana posible a la realidad antes de construir el robot, y seguir usándola después. Gracias.

---

## Si algo se tranca

| Qué pasa | Qué hacer |
| --- | --- |
| El homing no termina (pasó una vez en la campaña) | Seguir hablando; Para ensayar → Recargar el mundo y otra vez «Habilitar y homing» |
| Frena solo con `ERR 4 watchdog` | Webots no está a 1×: ponerlo en Real-time |
| Un atajo se pone en rojo | El mensaje dice por qué; Esc frena todo y los botones normales siguen más abajo en la página |
| La reproducción de lo grabado se rechaza | Leer el porqué en voz alta (es la validación previa, también sirve) y seguir con «▶ Cuadrado LIN» |

## Pendiente

- Ensayar el teach con el teclado: cuánto mantener cada tecla para que los tres puntos queden lindos y la reproducción pase la validación.
- Ensayar el encuadre de Webots para que se vean los sensores, la maceta y la caída de J4. Los KY-003 son chicos: probar si se ven en el proyector o si conviene acercar la cámara a J1 durante el homing.
- Ensayar los tiempos de cada bloque con cronómetro, hablando en voz alta.

---

# Banco de preguntas para la defensa

Respuestas cortas, para decir en 20 o 30 segundos. Si el profesor pide más detalle, cada una dice dónde está en el informe. Las marcadas con **(a mano)** se pueden mostrar en vivo.

## 1. Gemelo digital y alcance (A)

**¿Qué es un gemelo digital, si el robot no existe?**

Es una simulación que se comporta como la máquina, al punto de que el programa que la controla no nota la diferencia. Como el SCARA no está construido, simulamos el *diseño*: la geometría sale del CAD de la cátedra y cada parámetro declara de dónde sale. Cuando exista, se calibra con mediciones y pasa a ser gemelo del robot real. (Informe, introducción y 1.2.)

**¿Qué es dato real y qué es supuesto?**

Del CAD: la geometría, las piezas y las distancias entre ejes (250 mm). Del maestro v1: motores, poleas, recorridos y el Arduino. Provisional: las masas de cada cuerpo (0,30; 0,50; 0,35 y 0,15 kg) y el par de los motores, que sale del catálogo de la familia más parecida porque no aparecieron las hojas de datos exactas. Propuestas nuestras: la ubicación de los sensores Hall y el microstepping 1/8. (1.2, 1.4, 6.2.)

**¿Cómo saben que el gemelo está bien?**

No hay robot para comparar, así que validamos que se comporte como dice el diseño: 208 pruebas automáticas y una campaña de ensayos en Webots con tolerancias (homing, teach & play, fallas F1–F5 y pruebas físicas C1–C4). Por ejemplo, los pasos que perdió la planta coinciden con los que informó el firmware con EV LOST. (`validation/campana/`.)

**¿Qué quedó afuera?**

El electroimán de la punta (no está en el CAD), las correas dibujadas (la transmisión la hace la planta), el modelo eléctrico de los motores y los choques entre piezas del mismo robot (esos los verifica la URC antes de mover). (1.2, 6.2.)

**¿Para qué sirve a futuro?**

Para decidir cosas del diseño antes de construir, para probar el programa y el firmware sin el robot, y después, calibrado, como banco de pruebas: generar corridas con fallas y la respuesta correcta al lado, entrenar un modelo que las reconozca u optimizar trayectorias. El aprendizaje automático es una posibilidad, no algo que hicimos.

**¿Qué hizo la IA y qué hicieron ustedes?**

Usamos Claude Code como asistente en la implementación y la documentación. Las decisiones de diseño fueron nuestras, y lo que dependía del profesor lo consultamos en clase. Nada se aceptó sin verificarlo con las pruebas y la campaña de ensayos. Los commits asistidos están marcados. (5.5.) *Cada uno tiene que poder explicar su bloque con sus palabras: es lo más probable que pregunten.*

**¿Qué fue lo más difícil?**

*Respuesta personal: piénsenla entre los cuatro.* Candidatos: convertir el CAD sin SolidWorks, reproducir el acople M1/M2 en la física de Webots, y que el motor pierda pasos de forma realista sin que el firmware se entere.

## 2. Modelo en Webots (D)

**¿Cómo pasaron del CAD a Webots?**

Las piezas de SolidWorks se convirtieron a STEP con sldprt2step, sin SolidWorks, y con OpenCascade a STL. Las posiciones salen de los ensambles. Son 43 piezas repartidas en cinco cuerpos rígidos, unidos por tres articulaciones de giro (HingeJoint) y una de deslizamiento (SliderJoint) para J4. (1.2, 5.4.)

**¿Cómo se simula un motor paso a paso?**

Cada motor es un rotor que sigue a los pasos que cuenta la planta, con el par que le da su curva par–velocidad. Si la carga o la aceleración piden más par del que tiene, el rotor cae al equilibrio siguiente y pierde cuatro pasos completos, sin que el firmware se entere. Los motores de Webots se comandan en velocidad para seguir a esos rotores. (1.4, 1.5.)

**¿Por qué se pierden de a cuatro pasos?**

Porque el rotor de un paso a paso tiene equilibrios cada cuatro pasos completos (un ciclo eléctrico): cuando lo vence la carga, salta al siguiente.

**¿Por qué J2 = (θM2 − θM1) / 4?**

Los motores de J1 y J2 están en la base. M2 mueve el antebrazo con una correa a lo largo del brazo, así que fija su ángulo *absoluto*, no el relativo. Si gira solo M1, el brazo gira y el antebrazo conserva su orientación: cambia J2. Por eso, para mover solo J1, el firmware da los mismos pasos a M1 y a M2. (1.2.) **(a mano: jog por motor de M1)**

**¿Qué es la columna «Simulado»? ¿El firmware la usa?**

Es la posición que da el `PositionSensor` de Webots: la verdad del simulador. El firmware nunca la lee, porque el robot no tiene encoders; solo la usan la planta y el canal de instrumentación. Si difiere de la estimada, el motor perdió pasos. (1.2.)

**¿Cómo se simula un sensor Hall?**

Cada KY-003 es un `Receiver` y cada imán un `Emitter`. La planta mide la distancia entre los dos en el modelo 3D y activa el sensor cuando el imán está dentro de su alcance. La activación sale de la geometría, no de leer la posición perfecta del simulador. (1.3.)

**¿Por qué Webots tiene que correr en tiempo real?**

El watchdog del firmware cuenta tiempo simulado y la URC manda PING en tiempo real. Si Webots va acelerado, el watchdog se adelanta y frena el robot con ERR 4. (2.3.)

**¿Por qué un paso de simulación de 2 ms?**

Con 16 ms, J4 mostraba un salto entre el motor y su tope. El rotor además se integra en 10 subpasos de 0,2 ms. (1.2.)

## 3. Sensores Hall y homing (B)

**¿Dónde están los sensores y por qué ahí?**

Un KY-003 por eje en la parte fija y dos imanes en la parte móvil, uno en cada extremo del recorrido. Uno es la referencia del homing y el otro, el fin de carrera. El maestro decía que había sensores Hall con imanes en los cuatro ejes, pero no dónde: la ubicación es una propuesta nuestra para revisar con el profesor. (1.3.)

**¿Cómo están montados?**

En J1, J2 y J3, dos imanes de 8 × 3 mm pegados por fuera del carretel que gira con la pieza, y el sensor en una escuadra de PLA a 1,5 mm. En J4, los imanes van por dentro del pistón de aluminio, que no es magnético, y el sensor cuelga del buje con una abrazadera y los lee a unos 4 mm. Escuadras, abrazadera e imanes los agregamos nosotros: no están en el CAD. Verificamos con las mallas que no choquen con nada en todo el recorrido. (1.3.)

**¿Cómo es el homing?**

En orden J4, J1, J2 y J3. Por eje: busca rápido (15 °/s; J4 a 10 mm/s), retrocede hasta que el sensor se apaga y 3° más, y vuelve a 1 °/s al mismo borde, que fija la referencia. Termina con J1 y J2 en −130°, J3 en −145° y J4 a 3 mm de arriba, y la URC lo lleva al reposo. Tarda un minuto. (3.4.)

**¿Por qué el homing no choca contra el tope?**

El borde de cada imán está 5° antes del tope mecánico (3 mm en J4).

**¿Qué pasa si un sensor falla?**

Es la falla F3. Si queda trabado activo, el homing aborta con ERR 12; si queda trabado inactivo, recorre todo sin encontrarlo y aborta con ERR 11. En los dos casos el robot queda sin referencia. **(a mano, tarda)**

**¿Qué es la referencia manual (ZERO)?**

Declarar que el robot está en la pose de reposo sin buscar los sensores. Es menos precisa: si el robot no estaba exactamente ahí, la trayectoria queda corrida sin aviso.

## 4. Firmware y protocolo (B)

**¿Cómo es posible que sea el mismo firmware en el Arduino y en Webots?**

Está en capas. El núcleo (protocolo, cola, jog, homing, watchdog) no toca el hardware: usa seis operaciones de una interfaz (HAL): `millis`, `step`, `enableDrivers`, `readHall`, `readByte` y `write`. Cambia solo la implementación: una para el UNO, otra para Webots y otra falsa para las pruebas. (1.5.)

**¿Lo probaron en un Arduino real?**

No hay placa. Compila para el UNO (16 148 bytes de flash, el 50 %, y 1297 de RAM, el 63 %) y el camino serie se probó con un puerto virtual y socat.

**¿Por qué sin números con coma ni memoria dinámica?**

Por el UNO: no tiene unidad de punto flotante y tiene 2 KB de RAM. Todo va en enteros; por ejemplo, la transmisión de J1 se guarda como la fracción 8/45 de paso por centésima de grado.

**¿Cómo genera los pulsos en el Arduino?**

Con una interrupción del Timer1 a 20 kHz: hasta 10 000 pasos por segundo por motor, con el ancho del pulso independiente de lo que haga el programa. El que más pide es M4: 8000 pulsos/s a 40 mm/s.

**¿Por qué 1/8 de paso?**

Con 400 pulsos por vuelta, un pulso de M1 mueve el extremo casi 2 mm con el brazo estirado y una recta se vería escalonada; con 1/8 (1600 pulsos por vuelta), medio milímetro. Es una propuesta nuestra y un solo parámetro del firmware.

**¿Por qué el protocolo es de texto?**

La consigna pide texto claro, y se puede depurar a mano con `nc` o con el monitor serie de Arduino. Alcanza: a 50 segmentos por segundo son unos 2 KB/s, contra unos 11 KB/s del serie a 115 200 baudios. **(a mano: hablarle con nc)**

**¿Quién es servidor y quién cliente? ¿Por qué?**

La URC es el servidor (puerto 9000) y la UCI el cliente, que reintenta cada segundo. Así el robot se puede reiniciar o reconectar sin tocar la URC, y el mismo esquema sirve para Webots, para socat y para un UNO con Ethernet. Es otro plano que maestro/esclavo: la URC decide los movimientos aunque sea la que espera la conexión. (3.2.)

**Si la URC es el maestro, ¿la UCI no decide nada?**
Decide la seguridad: frena sola si la URC deja de hablar (watchdog), si el jog toca un sensor de fin de carrera o si un segmento pide más velocidad que la del motor. Ninguna orden puede saltear eso. Y el homing lo ejecuta sola.

**¿Cómo es el control de flujo?**

La URC manda un SEG y espera su OK antes del siguiente. Entran 16 en la cola; con la cola llena, el firmware demora el OK hasta que termina el que ejecuta. Si la URC mandara de más, sería ERR 9. El reloj lo pone el firmware: una demora del enlace no se nota mientras quede cola (320 ms). (3.7.)

**¿Qué pasa si se corta la comunicación?**

Si la URC deja de hablar más de un segundo con el robot en movimiento, el firmware frena solo (ERR 4) y conserva la referencia. Por eso la URC manda PING cada 250 ms. Al reconectarse, Webots vuelve sin BOOT; y todo BOOT significa robot sin referencia. **(a mano: F4)**

**¿Qué es la línea S?**

El estado, 20 veces por segundo: `S modo ref J1 J2 J3 J4 hall libres último`. Por ejemplo, `S RUN 15 45 0 0 12000 8 13 180`: ejecutando, los cuatro ejes referenciados, J1 en 0,45°, J4 en 120 mm, el Hall de J4 activo, 3 segmentos en cola y el último terminado, el 180. `ref` y `hall` son máscaras de bits: cada eje suma 1, 2, 4 u 8. (3.5.)

**¿Por qué unidades en centésimas?**

Para usar solo enteros: 9000 son 90,00° y 12000 son 120,00 mm. La URC nunca habla en pasos ni en motores: eso lo resuelve el firmware.

**¿Por qué hay un segundo protocolo, scara-sim/1?**

Para separar lo que el robot real no tendría: la posición verdadera, las fallas, la carga. Si eso viajara por scara/1, la URC podría terminar dependiendo de ello y no funcionaría con el robot real. Va por otro puerto (9001) y sin él la URC funciona igual. (3.10.)

**¿Cómo saben que la URC y el firmware entienden lo mismo?**

Con 24 conversaciones de conformidad que definen el protocolo y se corren contra los dos: contra el firmware C++ compilado para la PC y contra la URC en Python con una UCI falsa. (3.12.)

**¿Qué pasa con una línea mal formada?**

Ninguno de los dos se cuelga: la UCI responde ERR 1, 2 o 3 y sigue, y la URC la registra como no entendida. Las líneas tienen hasta 64 bytes, por la RAM del UNO.

**¿Diferencia entre STOP y HALT?**

STOP frena con rampa, todos los motores a la vez, y conserva la referencia. HALT corta en seco: es el freno de emergencia, y si el robot se movía da la referencia por perdida, porque frenar en seco puede perder pasos.

## 5. Programa externo y planificación (C)

**¿Qué hace la URC y qué el firmware?**

La URC planifica y el firmware ejecuta, como en GRBL o Klipper: la URC tiene la cinemática, los tramos, la validación y las trayectorias; el firmware convierte a pasos, encola y ejecuta con su reloj. (2.2.)

**¿Cómo se calcula la cinemática inversa?**

J2 sale de la ley de los cosenos del triángulo brazo–antebrazo; J1, de la dirección del punto; J3, de que el rumbo es J1 + J2 + J3; y J4, de la altura. Hay dos soluciones (codo a un lado o al otro): la URC elige la más cercana a la pose actual. (2.2.)

**¿Qué es la singularidad?**

El brazo estirado (J2 = 0°). Ahí no se puede seguir una recta, y por eso un tramo LIN no puede cambiar de lado el codo; un PTP sí.

**¿Diferencia entre PTP y LIN?**

En PTP cada eje va directo a su destino y todos llegan a la vez: la punta hace una curva. En LIN la punta sigue una recta, resolviendo la inversa a lo largo del tramo.

**¿Qué es el perfil trapezoidal?**

Acelera con la aceleración máxima, va a velocidad constante y frena igual. Si el tramo es corto, el perfil queda triangular. Lo limita el eje o motor más exigido.

**¿Qué verifica antes de mover?**

Planifica el tramo entero y revisa cada segmento de 20 ms: alcance, límites de cada eje, que el codo no cambie de lado, velocidades y aceleraciones de ejes y motores, y choques contra la torre, el pedestal y el suelo (cada pieza como una caja, a más de 1 mm). Si algo falla no manda nada y explica qué cambiar. **(a mano: pedir un punto fuera de alcance)**

**¿Cómo es el jog?**

Con referencia, la URC calcula cada paso de 20 ms, lo verifica y lo manda como SEG (articular a 10 °/s, o cartesiano). Sin referencia no puede verificar nada: usa la orden JOG del firmware, limitada a 5 °/s, y frenan los sensores de fin de carrera.

**¿Cómo se guardan las trayectorias?**

En JSON, con la punta en X, Y, Z y rumbo, el tipo de tramo, la velocidad y la espera de cada punto. Se capturan con el jog, se editan, se reordenan y se reproducen con loop, pausa y stop.

**¿Qué son los botones del panel Demo?**

Atajos para la presentación: encadenan las mismas órdenes de la página (los controles normales están más abajo) y esperan a que el robot termine, para no tipear poses durante la defensa. Sin `#demo` en la dirección no aparecen.

## 6. Fallas (D)

**¿Por qué la URC no esquivó la maceta?**

Porque no sabe que está. El robot real no tiene cámara ni sensores del entorno, y la URC solo conoce el robot, la torre, el pedestal y el suelo. El obstáculo existe solo en la planta simulada, a propósito.

**¿Por qué la maceta no dio EV LOST y F1 sí?**

EV LOST solo aparece al entrar en un imán, y los imanes están en los extremos del recorrido. Después de la maceta, el codo no pasó por su imán; en F1, J4 vuelve al reposo y pasa por el imán de abajo.

**¿Cómo detecta el firmware los pasos perdidos?**

Cuando un eje referenciado entra en un imán, compara su cuenta de pasos con la que tenía ese borde. Si difieren en dos pasos completos o más, manda EV LOST con la diferencia.

**¿Por qué EV LOST dijo 1254 y la planta perdió 1252?**

El sensor se lee cada 2 ms y J4 lo cruza a 40 mm/s: entre dos lecturas avanza 0,08 mm, que son dos pasos completos de M4. (3.8.)

**¿El firmware corrige la posición?**

No: informa. La URC marca la referencia como dudosa, avisa y no deja reproducir hasta un homing. Corregir sin saber cuánto se corrió el resto sería peor.

**¿Cómo se podría detectar lo de la maceta?**

Con encoders o algún sensor por motor. Hoy un paso perdido se descubre recién al cruzar un imán; es una de las mejoras propuestas si se construye el robot. (6.3.)

**¿Qué otras fallas tiene el banco?**

F2: el driver de M4 sin corriente, J4 cae y la estimada no cambia. F3: un sensor Hall trabado. F4: el enlace cortado, actúa el watchdog. C2: J4 contra una mesa. C3: un empujón en la punta (con 5 N vuelve solo; con 12 N pierde pasos y queda corrido unos 72°). C4: mover el brazo a mano sin corriente. **(a mano: F2, F4 y el empujón son de un clic en el banco de ensayo)**

**¿Qué pasa si se corta la luz en el robot real?**

Es F5: el firmware arranca de nuevo sin corriente y sin referencia, y J4 cae por su peso. La URC ve el BOOT, frena la reproducción y no deja seguir hasta un homing.
