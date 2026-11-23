# Guion de la presentación (borrador)

12 minutos de exposición y después preguntas. Sin diapositivas: se muestra en vivo el gemelo en Webots y la página de la URC con el panel **Demo de la presentación**.

Las acciones van en negrita entre corchetes; lo que se dice, en párrafos con sangría. Los números entre corchetes con «leer» se leen de la pantalla en el momento, porque pueden cambiar un poco.

## Reparto

Cada uno toma una letra y reemplaza A, B, C o D por su nombre. El **piloto** maneja la compu toda la presentación: es C, que además hace el teach con el teclado. Cuando habla otro, el piloto hace los clics que marca el guion.

| Persona | Nombre | Bloques | Habla | Preguntas que conviene que conteste |
| --- | --- | --- | --- | --- |
| A | | 1. Qué es · 3. No sabe dónde está · 8. Conclusión | ~2:30 | Gemelo digital y alcance (sección 1 del banco), y uso de IA |
| B | | 4. Homing y sensores Hall · 5. Arquitectura y protocolo | ~2:55 | Sensores Hall, firmware y protocolo (secciones 4 y 5) |
| C (piloto) | | 2. Cómo lo modelamos · 6. Teach & play, y todos los clics | ~2:15 | Del CAD a Webots, controlador y planificación (secciones 2, 3 y 6) |
| D | | 7. Fallas | ~2:30 | Fallas, motores y transmisión (secciones 7 y 8) |

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
| 2. Cómo lo modelamos | C | 0:55 | 2:05 | ~70 s | — |
| 3. No sabe dónde está | A | 2:05 | 2:45 | ~35 s | arranca el homing |
| 4. Homing y sensores Hall | B | 2:45 | 4:15 | ~1:25 | homing: 62 s + vuelta al reposo, mientras habla |
| 5. Arquitectura y protocolo | B | 4:15 | 5:45 | ~1:30 | — |
| 6. Teach & play | C | 5:45 | 7:25 | ~1:05 | jog ~15 s, grabada ~6 s, cuadrado 13 s |
| 7. Fallas | D | 7:25 | 10:25 | ~2:25 | ~20 s, más pausas para mirar |
| 8. Conclusión | A | 10:25 | 11:40 | ~1:15 | — |
| Margen | | 11:40 | 12:00 | | |

Quedan ~20 s de margen: hay que ensayarlo con cronómetro. Si se pasan, lo primero para acortar es la conclusión.

«Habla» es el texto leído a unas 130 palabras por minuto.

---

## 1. Qué es (A · 0:00–0:55)

**Habla: A** · clics: C

**En pantalla:** Webots, con el robot quieto.

> Buenas. Somos el equipo Alan Turing: [nombres]. Nos tocó el SCARA, un brazo de cuatro ejes donde el hombro, el codo y la muñeca giran —son J1, J2 y J3— y el cuarto eje, J4, sube y baja la herramienta. Lo mueven cuatro motores paso a paso y este es un diseño sin encoders (es decir que el robot no sabe su posicion exacta en cada momento)
>
> Como el robot no está construido diseñamos un gemelo digital en Webots a partir de las piezas modeladas, el firmware del Arduino que lo controlaria, el programa externo para manejarlo —que es esta página— y el protocolo de texto que los conecta.

## 2. Cómo lo modelamos (C · 0:55–2:05)

**Habla: C** · mientras habla, gira la cámara de Webots alrededor del robot

**En pantalla:** Webots.

> Partimos del CAD de SolidWorks de la cátedra. Webots no abre SolidWorks, así que convertimos cada pieza a STEP y de ahí a mallas STL, y de los ensambles sacamos dónde va cada una. El CAD dice cómo son las piezas, pero no cómo se mueven: eso lo agregamos nosotros. Repartimos las piezas en cinco cuerpos rígidos y los unimos con cuatro articulaciones de Webots: tres de giro, HingeJoint, y una de deslizamiento para J4, SliderJoint, cada una con su motor. Los sensores Hall son receptores y los imanes, emisores.
>
> Lo importante: los motores de Webots no son los del robot, porque son ideales y nunca pierden un paso. Los paso a paso, las poleas y el acople están modelados dentro del controlador, y las articulaciones de Webots siguen a esos motores simulados. Por eso, más adelante, el robot va a poder fallar como uno real.

## 3. No sabe dónde está (A · 2:05–2:45)

**Habla: A** · clics: C

**En pantalla:** la tabla «Posición estimada por pasos».

> «Estimada» es lo que sabe el firmware: Arranca en cero tomando como referencia la posicion de reposo y cuenta los pasos que le mandó a cada motor. «Simulado» es dónde está de verdad, según el simulador. Como ven no coinciden: el mundo arranca con el brazo desviado hasta diez grados, como un robot que nadie dejó exacto. Por eso para que el robot descubra su posicion lo primero que hay que hacer es el homing.

**[PILOTO: Arranque → «Habilitar y homing»]**

## 4. Homing y sensores Hall (B · 2:45–4:15)

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

## 5. Arquitectura y protocolo (B · 4:15–5:45)

**Habla: B** · clics: C

**[cuando termina el homing y vuelve al reposo]**

> Listo: estimada y simulada coinciden, y en la columna Hall está activo el de J4: en reposo, el pistón descansa sobre su imán de abajo.
>
> Cómo está armado: esta página es la URC, el programa externo, en Python. Webots corre el controlador del robot, y adentro corre el firmware: el mismo código C++ que compila para el Arduino UNO del robot real. Solo cambia la capa que toca el hardware.
>
> Cada 2 milisegundos el controlador hace siempre lo mismo: recibe lo que mandó la URC, mide los Hall, corre el firmware, le responde a la URC y mueve la planta: los motores simulados siguen a los pasos y Webots resuelve la física.
>
> Entre los dos va el protocolo scara/1, por TCP: texto, una línea por mensaje y solo números enteros. La URC decide los movimientos; el firmware los ejecuta, pero si deja de escuchar a la URC por un segundo, frena solo.

**[señalar «Último S», arriba del tráfico]**

> Lo que no aparece en el tráfico es el estado, la línea S, que llega veinte veces por segundo: el modo, si tiene referencia, las cuatro posiciones en centésimas y los sensores. La tabla de arriba es esa línea decodificada.

## 6. Teach & play (C · 5:45–7:25)

**Habla: C**

**En pantalla:** Webots y el panel.

**[PILOTO: Teach & play → «Trayectoria nueva»]**

> Movemos el robot con el teclado: cada tecla mueve un eje.

**[R unos 3 s: sube J4 · S unos 3 s: dobla el codo · Espacio]**

> Con la barra espaciadora guardamos el punto. Con Tab pasamos a cartesiano: las mismas teclas ahora mueven la punta en X, Y y Z, en línea recta. Para eso la URC resuelve la cinemática inversa en cada paso.

**[Tab · A unos 3 s · Espacio · F unos 2 s · Espacio]**

> Y lo reproducimos.

**[PILOTO: «▶ Grabada»]**

> Antes de mover, la URC planificó la trayectoria entera y la verificó: los límites de cada eje, el alcance, la velocidad de los motores, que el codo no cambie de lado y que no choque con la torre ni con la base. Si algo no pasa, no manda nada y explica por qué.
>
> Hay dos tipos de tramo. En el PTP cada eje va directo a su destino y la punta hace una curva. En el LIN la punta sigue una recta. Este cuadrado es todo LIN.

**[PILOTO: «▶ Cuadrado LIN»]**

## 7. Fallas (D · 7:25–10:25)

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

## 8. Conclusión: para qué sirve el gemelo (A · 10:25–11:40)

**Habla: A** · clics: C

**En pantalla:** Webots.

> Para cerrar, qué nos deja un gemelo digital como este.
>
> El SCARA todavía no existe, pero ya tiene su programa, su protocolo y su firmware funcionando, y pudimos ver qué pasa cuando algo falla sin romper nada. Cuando se construya, el firmware se carga en el Arduino, Webots se reemplaza por el robot sin tocar el programa, y el gemelo se calibra con mediciones reales para parecerse cada vez más.
>
> Ahí se vuelve un banco de pruebas sin riesgo. Como el simulador sabe la verdad y puede provocar fallas, se pueden generar miles de corridas y situaciones automáticas con la respuesta correcta y tal vez usarlas para optimizar trayectorias antes de probarlas en la máquina o quien sabe para entrenar un modelo de aprendizaje automático.
>
> Esa es la idea: que no sea una animación, sino que se comporte como la máquina, también cuando falla. Una versión lo más cercana posible a la realidad antes de construir el robot, y que se siga usando después. Gracias.

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

Un solo banco: respuestas cortas para decir en 20 o 30 segundos y, donde hace falta, el detalle para estudiar. Entre paréntesis, la sección del informe. Las marcadas **(a mano)** se pueden mostrar en vivo.

## 1. Gemelo digital y alcance (A)

**¿Qué es un gemelo digital, si el robot no existe?**

Una simulación que se comporta como la máquina, al punto de que el programa que la controla no nota la diferencia. Como el SCARA no está construido, simulamos el *diseño*: la geometría sale del CAD de la cátedra y cada parámetro declara de dónde sale. Cuando exista, se calibra con mediciones. (Introducción, 1.2.)

**¿Qué es dato real y qué es supuesto?**

Del CAD: piezas, geometría y distancias entre ejes. Del maestro v1: motores, poleas, recorridos, drivers y el Arduino. Provisional: las masas de cada cuerpo (0,30; 0,50; 0,35 y 0,15 kg, porque los planos mezclan materiales) y el par de los motores, que sale del catálogo de la familia más parecida. Propuestas nuestras: la ubicación de los sensores Hall y el micropaso 1/8. (1.2, 1.4, 6.2.)

**¿Cómo saben que el gemelo está bien?**

No hay robot para comparar, así que validamos que se comporte como dice el diseño: 208 pruebas automáticas y una campaña de diez ensayos en Webots con tolerancias (homing, teach & play, fallas F1–F5 y pruebas físicas C1–C4). Por ejemplo, los pasos que pierde la planta coinciden con los que informa el firmware con EV LOST. (`validation/campana/`.)

**¿Qué quedó afuera?**

El electroimán (no está en el CAD), las correas dibujadas, el modelo eléctrico de los motores y los choques entre piezas del mismo robot, que verifica la URC antes de mover. (1.2, 6.2.)

**¿Qué hacía el programa externo original?**

No existía: la consigna marca el protocolo como no redactado y el programa externo como no desarrollado. La idea de grabar y reproducir puntos viene de AGSA-BOT y CARTESIANA, pero la implementación es nuestra.

**¿Cuál es el equivalente a «la batería de Mate»?** (lo que el modelo tuvo que resolver aparte)

Tres cosas que Webots no trae: los sensores Hall (por distancia entre nodos), la pérdida de pasos (el rotor simulado) y la posición verdadera, que solo existe en la simulación y va por un canal aparte, el 9001.

**¿Cómo llega el robot real a este mismo programa?**

El firmware se carga en el UNO y socat conecta su puerto USB al TCP 9000, el mismo que hoy usa Webots: la URC no cambia. Se probó con un puerto serie virtual, no con una placa.

**¿Qué hizo la IA y qué hicieron ustedes?**

Usamos Claude Code como asistente en código, documentación e investigación. Las decisiones de diseño fueron nuestras y lo que dependía del profesor lo consultamos en clase. Nada se aceptó sin verificarlo con las pruebas y la campaña. Está declarado en el informe y los commits asistidos están marcados. (5.5.) *Cada uno tiene que poder explicar su bloque con sus palabras.*

**¿Qué fue lo más difícil?**

*Respuesta personal: piénsenla entre los cuatro.* Candidatos: convertir el CAD sin SolidWorks, reproducir el acople M1/M2 en la física de Webots y que el motor pierda pasos de forma realista sin que el firmware se entere.

## 2. Del CAD a Webots (C)

**¿De dónde sale el modelo?**

Del CAD que entregó la cátedra, la carpeta `Modelos3D/`: 152 archivos, entre ellos 50 piezas (`.SLDPRT`) y 10 ensambles (`.SLDASM`) de SolidWorks. Nosotros no dibujamos el robot.

**¿Qué son STEP y STL, y por qué se pasa de uno al otro?**

- **SLDPRT / SLDASM:** formatos cerrados de SolidWorks, una pieza y un ensamble. No teníamos SolidWorks y Webots no los abre.
- **STEP:** formato estándar para intercambiar CAD. Guarda la geometría *exacta*: caras, aristas y sólidos, en milímetros.
- **STL:** una *malla*, la superficie aproximada con triángulos (un círculo pasa a ser un polígono de muchos lados). No tiene unidades, colores ni ensamble. Es lo que Webots dibuja y usa.

Se pasa primero a STEP porque es lo único a lo que se puede llegar desde un SLDPRT sin SolidWorks, y porque la geometría exacta sirve para medir: ejes, agujeros, volúmenes, centros de masa. Recién después se generan los triángulos para Webots.

**¿Cómo se hizo la conversión?**

SLDPRT → **sldprt2step** → STEP → **OpenCascade** → STL → Webots. sldprt2step es un programa libre que lee una pieza de SolidWorks y escribe un STEP (no convierte ensambles). OpenCascade es una biblioteca libre de geometría 3D, un motor de CAD sin interfaz: desde Python lee el STEP, valida que el sólido sea correcto, lo mide y genera la malla con una tolerancia de 0,05 mm, en metros, que es lo que usa Webots. Salieron 50 STEP y 47 STL: la torre se exportó por cuerpos, B-ExtensorM3 tenía la geometría inválida y Z-BujeInterior no dio una malla cerrada. Las posiciones de cada pieza salen de los ensambles. (`tools/convertir_cad.py`, `docs/DEL_CAD_A_WEBOTS.md`.)

**¿Por qué 250 mm entre ejes y no el largo de los caños?**

Para el movimiento, el largo de un eslabón es la distancia entre dos ejes de giro, no el largo del caño. El caño del brazo mide 300 mm, con J1 en un agujero a 30 mm y J2 a 280 mm: 250 mm. El del antebrazo mide 237 mm, pero J3 pasa por el buje de la muñeca, fuera del caño: entre J2 y J3 también hay 250. Con 237, la punta quedaría mal calculada.

**¿Cómo se armó el robot en Webots?**

El CAD dice cómo son las piezas, no cómo se mueven. Las repartimos en cinco cuerpos rígidos (base, brazo, antebrazo, conjunto Z y pistón) y los unimos con cuatro articulaciones. Todo el robot es una plantilla, el PROTO `webots/protos/SCARA.proto`, que genera `tools/generate_world.py`. Para los choques, cada pieza tiene una caja envolvente simplificada. (1.2.)

**¿Qué son HingeJoint, SliderJoint y RotationalMotor? ¿Son funciones?**

No: son *nodos*, elementos del árbol de la escena de Webots, que se ven en el panel izquierdo. Las funciones son las del programa que los maneja.

| Nodo | Qué representa |
| --- | --- |
| HingeJoint | Bisagra: une dos cuerpos y deja solo el giro sobre un eje (J1, J2, J3) |
| SliderJoint | Corredera: deja solo el desplazamiento sobre un eje (J4) |
| RotationalMotor / LinearMotor | Mueve la bisagra o la corredera: le decimos velocidad y par (o fuerza) disponible |
| PositionSensor | Mide la posición de una articulación |
| Emitter / Receiver | Emisor y receptor de radio: acá, el imán y el sensor Hall |

Funciones que usa el controlador: `getMotor()`, `setVelocity()`, `setAvailableTorque()` y `getPositionSensor()`.

**¿Qué es la columna «Simulado»? ¿El firmware la usa?**

Es lo que mide el `PositionSensor`: una regla perfecta pegada a la articulación, la verdad del simulador. Parece un encoder, pero el robot no tiene encoders, así que el firmware nunca la lee. La usan la planta (para llevar la articulación hacia el rotor y girar las poleas) y el canal de instrumentación, que la muestra al lado de la estimada.

**¿Por qué Webots tiene que correr en tiempo real?**

El watchdog del firmware cuenta tiempo simulado y la URC manda PING en tiempo real. Si Webots va acelerado, el watchdog se adelanta y frena el robot con ERR 4. El paso de simulación es de 2 ms. (2.3.)

## 3. El controlador y los motores simulados (C)

**¿Qué hace el controlador?**

Es el programa en C++ que Webots ejecuta junto con el robot (`webots/controllers/scara_uci/scara_uci.cpp`, y el modelo del motor en `stepper.h`). Tiene tres partes: el firmware, que es el mismo código del Arduino; la capa de hardware, que le hace creer que está en la placa; y la planta simulada, que hace de drivers, motores, transmisión y sensores. Su bucle, cada 2 ms (línea 1013, resumido):

```text
link.service();                  // recibe lo que mandó la URC
plant.sense();                   // mide imanes y sensores Hall
firmware->poll();                // corre el firmware
link.flush();                    // responde a la URC
plant.apply(timestep / 1000.0);  // mueve rotores y articulaciones
```

El archivo real tiene además el giro de las poleas visuales y el reinicio de F5.

**¿Por qué no usar directamente los motores de Webots? ¿No tiene motores más fieles?**

El motor de Webots es un actuador genérico e ideal: se le pide una posición o una velocidad y empuja con hasta un par máximo para llegar. No sabe de pasos. Si la carga lo frena, va más lento o se queda; cuando la carga se va, **sigue persiguiendo el destino y lo alcanza**. Un paso a paso real no: pierde los pasos para siempre y se queda corrido sin enterarse. Esa es justo la falla que queríamos mostrar, y Webots no trae un motor paso a paso con ese comportamiento.

Por eso los motores se modelan en el controlador, cada 2 ms (en 10 subpasos de 0,2 ms):

1. El firmware da pasos y un contador los suma por motor.
2. Cada rotor simulado persigue su contador con el par que tiene a esa velocidad (la curva par–velocidad).
3. Las fórmulas de la transmisión pasan de ángulos de motor a ángulos de articulación.
4. Al motor de Webots se le ordena esa velocidad, con ese par como máximo (cero si no hay corriente).
5. Webots calcula la física y mueve la articulación.

Los motores M1–M4 no son piezas que empujan a otras: son variables y cuentas dentro del controlador. Las carcasas y las poleas se ven, pero no transmiten fuerza.

**¿Por qué se pierden pasos de a cuatro?**

El par del rotor depende de cuánto se atrasa respecto de los pasos que le mandaron: `T = T(ω) · sen(π/2 · atraso / paso completo)`. Aguanta hasta dos pasos completos de atraso; más allá salta al siguiente equilibrio, que está cuatro pasos completos más allá (un ciclo eléctrico). Nadie avisa. (`stepper.h`.)

**¿Qué falta modelar para que se parezca más a la realidad? ¿Se podría hacer?**

Falta el comportamiento eléctrico de los motores (corrientes, inductancia, resonancias a media velocidad: hoy lo resume la curva par–velocidad), las correas (que se estiran, patinan o tienen juego), fricciones más finas, el ruido de los sensores y, sobre todo, **los parámetros medidos**: masas y par reales. Parte se podría simular, y el informe lo deja como mejora (6.2), pero sin el robot los valores serían inventados: más detalle sin datos para calibrarlo no hace al gemelo más fiel. Por eso queda para cuando se construya.

**¿Cómo se reproduce el acople M1/M2 en Webots?**

En el robot, M2 está en la base y mueve el antebrazo por una correa; en Webots, el motor de J2 está entre el brazo y el antebrazo. La planta cancela sobre el brazo la reacción de ese motor, para que la correa quede referida a la base, como en el robot. (1.2.)

## 4. Sensores Hall y homing (B)

**¿Dónde están los sensores y por qué ahí?**

Un KY-003 por eje en la parte fija y dos imanes en la parte móvil, uno en cada extremo del recorrido: uno es la referencia del homing y el otro, el fin de carrera. Con un solo sensor por eje alcanzan los pines del UNO. El maestro pedía sensores Hall con imanes en los cuatro ejes pero no decía dónde: la ubicación es una propuesta nuestra para revisar con el profesor. (1.3.)

**¿Cómo están montados?**

En J1, J2 y J3, dos imanes de 8 × 3 mm pegados por fuera del carretel que gira con la pieza, y el sensor en una escuadra de PLA a 1,5 mm. En J4, los imanes van por dentro del pistón de aluminio, que no es magnético, y el sensor cuelga del buje con una abrazadera y los lee a unos 4 mm. Escuadras, abrazadera e imanes los agregamos nosotros: no están en el CAD. Verificamos con las mallas que no choquen en todo el recorrido.

**¿Cómo se simula un sensor Hall?**

Cada sensor es un `Receiver` y cada imán un `Emitter`. La planta mide la distancia entre los dos en el modelo 3D y activa el sensor cuando el imán está dentro de su alcance. En J1–J3 el sensor está a 40,5 mm del eje y el imán a 36,5: el alcance que da ±5° es d = √(40,5² + 36,5² − 2·40,5·36,5·cos 5°) ≈ 5,22 mm.

**¿Cómo es el homing?**

En orden J4, J1, J2 y J3: primero se aleja la herramienta de la mesa. Por eje: busca el imán rápido (15 °/s; J4 a 10 mm/s), retrocede hasta que el sensor se apaga y 3° más, y vuelve a 1 °/s al mismo borde. Llegar lento y siempre del mismo lado da una referencia repetible. Tarda un minuto, y al final la URC lo lleva al reposo. (3.4.)

| Eje | Tope | Borde de referencia | Separación |
| --- | --- | --- | --- |
| J1 y J2 | −135° | −130° | 5° |
| J3 | −150° | −145° | 5° |
| J4 | 0 mm (arriba) | 3 mm | 3 mm |

La separación hace que el homing nunca choque contra el tope. J1 y J2 se referencian los dos en el extremo negativo porque, con J2 en el positivo y J1 en −135°, el soporte Z chocaría con la torre.

**¿Por qué el reposo es con el brazo estirado?**

Plegado (J2 = ±135°) toca la torre incluso quieto. Estirado queda libre.

**¿Qué pasa si un sensor falla?**

Es la falla F3. Trabado activo: el homing aborta con ERR 12. Trabado inactivo: recorre todo sin encontrarlo y aborta con ERR 11. En los dos casos queda sin referencia.

**¿Qué es la referencia manual (ZERO)?**

Declarar que el robot está en el reposo sin buscar los sensores. Es menos precisa: si no estaba exactamente ahí, todo queda corrido sin aviso.

## 5. Firmware y protocolo (B)

**¿Cómo puede ser el mismo firmware en el Arduino y en Webots?**

Está en capas. El núcleo (protocolo, cola, jog, homing, watchdog) no toca el hardware: usa seis operaciones de una interfaz (HAL): `millis`, `step`, `enableDrivers`, `readHall`, `readByte` y `write`. Cambia solo la implementación: una para el UNO, otra para Webots y una falsa para las pruebas. (1.5.)

**¿Lo probaron en un Arduino real?**

No hay placa. Compila para el UNO (50 % de la flash, 63 % de la RAM) y el camino serie se probó con un puerto virtual y socat. El UNO no lo elegimos nosotros: lo indica el maestro. Usa 13 pines más los dos del serie.

**¿Por qué sin números con coma ni memoria dinámica?**

El UNO no tiene unidad de punto flotante y tiene 2 KB de RAM: interpretar e imprimir decimales es lento. Todo va en enteros; por ejemplo, la transmisión de J1 se guarda como la fracción 8/45 de paso por centésima de grado.

**¿Cómo genera los pulsos?**

Con una interrupción del Timer1 a 20 kHz; cada pulso ocupa dos interrupciones: hasta 10 000 pulsos por segundo por motor, con el ancho del pulso independiente de lo que haga el programa.

**¿Por qué el protocolo es de texto?**

La consigna pide texto claro, y se depura a mano con `nc` o el monitor serie de Arduino. Alcanza: a 50 segmentos por segundo son unos 2 KB/s, contra unos 11 KB/s del serie a 115 200 baudios. **(a mano: hablarle con nc)**

**¿Por qué el protocolo habla en ángulos y no en coordenadas ni en pasos?**

| Opción | Qué implicaría | Decisión |
| --- | --- | --- |
| Coordenadas X, Y, Z | El firmware tendría que calcular la cinemática inversa y las rectas | Descartada: el UNO no llega al ritmo que pide una recta |
| Pasos de motor | La URC tendría que conocer poleas, micropaso y acople | Descartada: cambiar un driver obligaría a tocar la URC, y el estado sería ilegible |
| Ángulos J1–J4 | La URC resuelve la geometría y el firmware, la mecánica | Elegida, en centésimas de grado y de mm |

**¿Quién es servidor y quién cliente? Si la URC es el maestro, ¿la UCI no decide nada?**

La URC es el servidor (puerto 9000) y la UCI el cliente, que reintenta cada segundo: así el robot se puede reiniciar sin tocar la URC, y sirve igual para Webots, socat o un UNO con Ethernet. Maestro y esclavo es otro plano: la URC decide los movimientos, pero la UCI se queda con la seguridad (frena sola si la URC deja de hablar, si el jog toca un fin de carrera o si un segmento pide más velocidad que la del motor) y ejecuta el homing sola. (3.2.)

**¿Cómo se leen las líneas de scara/1?**

| Línea | Qué dice |
| --- | --- |
| `HELLO` → `HI scara/1 1` | Saludo y versión del protocolo |
| `HOME` / `EV HOMED 4` | Hacé el homing / J4 quedó referenciado |
| `JOG M1 + 1000` | Mover solo M1, sentido +, a 1000 centésimas por segundo (10 °/s) |
| `SEG 293 20 2607 -3311 705 9732` | Segmento 293, de 20 ms, hasta 26,07°, −33,11°, 7,05° y 97,32 mm |
| `OK 293` | El segmento entró en la cola |
| `S RUN 15 3015 -3831 816 9377 0 0 301` | Ejecutando; referencia 15 (los cuatro); posición estimada; ningún Hall; 0 lugares libres; último segmento terminado, el 301 |
| `EV LOST 4 1254` | Al entrar en un imán de J4, la cuenta difiere en 1254 pasos completos |
| `ERR 4 watchdog` | Frenó solo: más de 1 s sin noticias de la URC |

`ref` y `hall` son máscaras de bits: cada eje suma 1, 2, 4 u 8. Las líneas tienen hasta 64 bytes, por la RAM del UNO; una mal formada recibe ERR 1, 2 o 3 y ninguno de los dos se cuelga. (3.3–3.5.)

**¿Cómo es el control de flujo y por qué segmentos de 20 ms?**

La URC manda un SEG y espera su OK antes del siguiente. Entran 16 en la cola; con la cola llena, el firmware demora el OK. El reloj lo pone el firmware: una demora del enlace no se nota mientras quede cola (16 × 20 ms = 320 ms). Los 20 ms son un equilibrio: 50 segmentos por segundo entran con holgura en el enlace, y dentro de un segmento la recta se aparta como mucho 0,13 mm. (3.7.)

**¿Qué pasa si se corta la comunicación?**

Si la URC deja de hablar más de un segundo con el robot en movimiento, el firmware frena solo (ERR 4) y conserva la referencia; por eso la URC manda PING cada 250 ms. Al reconectarse, Webots vuelve sin BOOT; y todo BOOT significa robot sin referencia. **(a mano: F4)**

**¿Por qué un segundo protocolo, scara-sim/1?**

Para separar lo que el robot real no tendría: la posición verdadera, las fallas, la carga. Si eso viajara por scara/1, la URC podría terminar dependiendo de ello y no funcionaría con el robot real. Va por el puerto 9001; sin él, la URC funciona igual. (3.10.)

**¿Cómo saben que la URC y el firmware entienden lo mismo?**

Con 24 conversaciones de conformidad que definen el protocolo y se corren contra los dos: el firmware en C++ y la URC en Python. (3.12.)

**¿Diferencia entre STOP y HALT?**

STOP frena con rampa, todos los motores a la vez, y conserva la referencia. HALT corta en seco: es la emergencia, y si el robot se movía da la referencia por perdida.

## 6. Programa externo y planificación (C)

**¿Qué hace la URC y qué el firmware?**

La URC planifica y el firmware ejecuta, como en GRBL o Klipper: la URC tiene la cinemática, los tramos, la validación y las trayectorias; el firmware convierte a pasos, encola y ejecuta con su reloj. (2.2.)

**¿Cómo se calcula la cinemática?**

Directa, de ángulos a punta (L1 = L2 = 250 mm):

```text
x = L1·cos J1 + L2·cos(J1 + J2)
y = L1·sen J1 + L2·sen(J1 + J2)
z = 94,67 − J4 (mm)            rumbo = J1 + J2 + J3
```

Inversa, de punta a ángulos (`scara/kinematics.py`):

```text
cos J2 = (x² + y² − L1² − L2²) / (2·L1·L2)      J2 = ± acos(…)
J1 = atan2(y, x) − atan2(L2·sen J2, L1 + L2·cos J2)
J3 = rumbo − J1 − J2            J4 = 94,67 − z
```

Ejemplo, X 350, Y 150, Z 30, rumbo 0, codo negativo: cos J2 = 0,16, J2 = −80,79°, J1 = 63,60°, J3 = 17,20°, J4 = 64,67 mm. Si el coseno da más de 1 o menos de −1, el punto está fuera de alcance. **(a mano: «Ir a una pose» con esos valores)**

**¿Dos soluciones? ¿Qué es la singularidad?**

El mismo punto se alcanza con el codo a un lado o al otro; la URC elige la más cercana a la pose actual (la preferida es J2 negativo). Con el brazo estirado (J2 = 0) está la singularidad: ninguna recta puede cambiar de codo, hace falta un PTP.

**¿Diferencia entre PTP y LIN?**

En PTP cada eje va directo a su destino y todos llegan a la vez, con perfil trapezoidal (acelera, velocidad constante, frena; triangular si el tramo es corto): la punta hace una curva. En LIN la punta sigue una recta, resolviendo la inversa cada 20 ms. No hay un modo «círculo»: en el barrido, solo gira J1 con el codo fijo y la punta hace un arco alrededor de la torre.

**¿Qué verifica antes de mover?**

Planifica el tramo entero y revisa cada segmento: alcance, límites de cada eje, que el codo no cambie de lado, velocidades y aceleraciones de ejes y motores, y choques contra la torre, el pedestal y el suelo (cada pieza como una caja, a más de 1 mm). Si algo falla no manda nada y explica qué cambiar. **(a mano: pasar a LIN el segundo punto del barrido: se rechaza porque pasaría por la torre)**

**¿Cómo es el jog?**

Con referencia, la URC calcula cada paso de 20 ms, lo verifica y lo manda como SEG (articular a 10 °/s, o cartesiano). Sin referencia no puede verificar nada: usa la orden JOG del firmware, limitada a 5 °/s, y frenan los fines de carrera.

**¿Qué son los botones del panel Demo?**

Atajos para la presentación: encadenan las mismas órdenes de la página (los controles normales están más abajo) y esperan a que el robot termine, para no tipear poses durante la defensa. Sin `#demo` en la dirección no aparecen.

## 7. Fallas (D)

**¿Por qué la URC no esquivó la maceta?**

Porque no sabe que está, igual que no sabría de un objeto real: el robot no tiene cámara ni sensores del entorno, y la URC solo conoce el robot, la torre, el pedestal y el suelo. El obstáculo (un cilindro de 120 × 150 mm) existe solo en la planta, a propósito.

**¿Por qué la maceta no dio EV LOST y F1 sí?**

EV LOST solo aparece al entrar en un imán, y los imanes están en los extremos del recorrido. Después de la maceta el codo no pasó por su imán; en F1, J4 vuelve al reposo y pasa por el de abajo.

**¿Cómo detecta el firmware los pasos perdidos? ¿Por qué 1254 y no 1252?**

Cuando un eje referenciado entra en un imán, compara su cuenta con la que tenía ese borde; si difieren dos pasos completos o más, manda EV LOST. La planta perdió 1252 y el firmware informó 1254 porque el sensor se lee cada 2 ms y J4 lo cruza a 40 mm/s: entre lecturas avanza 0,08 mm, dos pasos completos. (3.8.)

**¿El firmware corrige la posición?**

No: informa. La URC marca la referencia como dudosa y no deja reproducir hasta un homing. Corregir sin saber cuánto se corrió el resto sería peor.

**¿Qué pasa si se piden más pasos de los que el motor puede?**

Dos casos. Si se pide más *velocidad* que el límite, la URC no lo planifica y, si llegara, el firmware rechaza el segmento con ERR 8. Si al motor le falta *par*, el pulso se da y se cuenta, pero el rotor se atrasa y pierde pasos de a cuatro, sin aviso.

**¿Cómo se podría detectar lo de la maceta?**

Con encoders o un sensor por motor. Hoy un paso perdido se descubre recién al cruzar un imán. (6.3.)

**¿Qué otras fallas tiene el banco?**

F2: el driver de M4 sin corriente, J4 cae y la estimada no cambia. F3: un sensor Hall trabado. F4: el enlace cortado, actúa el watchdog. C2: J4 contra una mesa. C3: un empujón en la punta (con 5 N vuelve solo; con 12 N pierde pasos y queda corrido unos 72°). C4: mover el brazo a mano sin corriente: la estimada no cambia y no hay pasos perdidos, porque no se perdieron pasos sino que se movió sin corriente; al deshabilitar ya se había perdido la referencia. **(a mano: F2, F4 y el empujón son de un clic en el banco)**

**¿Qué pasa si se corta la luz en el robot real?**

Es F5: el firmware arranca sin corriente y sin referencia, y J4 cae por su peso. La URC ve el BOOT, frena la reproducción y no deja seguir hasta un homing.

## 8. Motores y transmisión (D)

**¿Por qué J2 = (θM2 − θM1) / 4?**

θ es cuánto giró cada motor; las poleas 20→80 reducen 4 veces. M2 está en la base y, por la correa del eje interior (60→60, 1 a 1), fija el ángulo del antebrazo respecto del mundo, no del brazo:

```text
Brazo:      J1      = θM1 / 4
Antebrazo:  J1 + J2 = θM2 / 4
Restando:   J2      = (θM2 − θM1) / 4
```

| Qué se hace | θM1 | θM2 | J1 | J2 |
| --- | --- | --- | --- | --- |
| Solo M1 | 160° | 0° | +40° | −40° |
| M1 y M2 iguales | 160° | 160° | +40° | 0° |
| Solo M2 | 0° | 160° | 0° | +40° |

Por eso, para mover solo J1, el firmware da los mismos pasos a M1 y M2. J3 = θM3 / 4 y J4 = 8 mm por vuelta de M4. **(a mano: jog por motor de M1: gira el brazo y el antebrazo sigue apuntando igual)**

**¿Qué es el TB6600?**

El driver: la etapa de potencia entre el Arduino y el motor. Recibe STEP (un pulso, un paso), DIR (el sentido) y ENABLE, y regula la corriente de las bobinas; con sus llaves se elige el micropaso y la corriente. Lo indica el maestro.

**¿Por qué 1/8 de paso?**

| Micropaso | Pulsos/vuelta | Punta, brazo estirado | J4 a 40 mm/s |
| --- | --- | --- | --- |
| 1/2 (maestro) | 400 | 1,96 mm | 2000 pulsos/s |
| 1/4 | 800 | 0,98 mm | 4000 pulsos/s |
| **1/8 (elegido)** | 1600 | 0,49 mm | 8000 pulsos/s: entra |
| 1/16 | 3200 | 0,25 mm | 16 000 pulsos/s: no entra |

Con 400, cada pulso movía la punta casi 2 mm y las rectas saldrían a saltos. 1/8 es el más fino que permite J4 a 40 mm/s con los 10 000 pulsos del UNO. Más pulsos dan más *resolución*, no más *precisión*: sigue sin encoder.

**¿Cómo se eligieron las velocidades y cuánto margen tienen los motores?**

Por los pulsos del UNO y el par de cada motor: J1 a 90 °/s (M1 a una vuelta por segundo), J3 a 180 °/s y J4 a 40 mm/s (M4 a 5 vueltas por segundo). Márgenes con 5 kg en la punta:

| Motor | Disponible a vel. máx. | Pedido con 5 kg | Margen |
| --- | --- | --- | --- |
| M1 | 0,560 N·m | 0,264 N·m | 2,1× |
| M2 | 0,560 N·m | 0,247 N·m | 2,3× |
| M3 | 0,217 N·m | 0,014 N·m | 16× |
| M4 | 0,140 N·m | 0,100 N·m | 1,4× |

Ojo: el informe dice «al menos 2×», pero **M4 queda en 1,4×**, porque lo limita el peso que sube por el husillo. Si lo preguntan, decirlo así. Los datos son de la familia de motor más cercana. (`docs/TRANSMISION.md`.)

**¿Por qué 5 kg?**

No sale del maestro, que no da un valor de carga. Lo fijamos como máximo del banco y verificamos los motores con ese peso: 0,15 kg de la herramienta y hasta 4,85 kg agregados. El caso más exigente es M4: 49 N por el husillo de 8 mm con rendimiento 0,67 dan 0,093 N·m, unos 0,100 con la fricción, contra 0,140 disponibles.
