# Guía del código y de las pruebas (para el grupo)

**Complemento interno del informe principal · Cómo está armado el código, qué herramientas usa cada parte y cómo funcionan las pruebas**

Esta guía está pensada para nosotros, como complemento del informe que entregamos. En el informe principal contamos qué hace el gemelo digital, cómo es el protocolo `scara/1` y qué resultados dio, pero dejamos afuera la explicación interna del código y de los tests para no recargar el documento del profesor.

La idea de estas páginas es explicar **con nuestras palabras** cómo está construido cada bloque, qué tecnologías o librerías usa (y cuáles no usa a propósito), cómo viaja una orden desde que apretás una tecla hasta que se mueve el brazo en Webots, y cómo hicimos para probar todo sin tener el robot físico.

> [!IDEA] **Cuatro preguntas que tenés que poder responder con tus palabras después de leer esta guía:**
> 1. ¿Cómo se reparten el trabajo la aplicación en Python (URC) y el programa en C++ del robot (firmware)?
> 2. ¿Cómo logra el mismo código en C++ correr tanto en un Arduino UNO real como adentro de Webots?
> 3. ¿Dónde y para qué se usan la cinemática directa y la cinemática inversa?
> 4. ¿Cómo se prueban el firmware y la URC automáticamente en un minuto sin tener la placa ni abrir Webots?

---

## 1. El panorama general: qué hay en el proyecto y qué usa cada parte

Si abrís el repositorio, vas a ver varias carpetas, pero cuando el sistema está funcionando en vivo solo intervienen **tres programas** que hablan entre sí: el **navegador**, la **URC** (en Python) y el **controlador de Webots** (en C++, que adentro lleva el firmware del robot y la planta simulada). Todo el resto de las carpetas son la matemática en la que se apoya la URC, las pruebas automáticas y las herramientas que se usaron una vez para preparar el modelo 3D a partir de los archivos de SolidWorks.

<!-- FIGURA: mapa_codigo | Figura 1. Mapa general del código: qué carpetas corren en vivo (azul y naranja), cuáles sólo asisten en simulación (verde) y cuáles son pruebas o herramientas de armado (gris). -->

### Qué tecnologías y librerías se usan en cada bloque (y por qué)

Una decisión importante del proyecto fue **no sumar librerías ni frameworks pesados** donde no hacían falta. Eso hace que el código sea fácil de leer, que arranque en cualquier computadora sin instalar paquetes raros y que la parte del robot entre en un microcontrolador chico:

| Parte del sistema | Carpeta | Qué tecnologías o librerías usa | Por qué se eligió así |
| --- | --- | --- | --- |
| **Página web de operación** | `urc/index.html` y `urc/*.js` | HTML, CSS y JavaScript puro del navegador (`fetch` para hablar con la URC). Sin React, Vue ni librerías externas. | Alcanza para dibujar el estado 5 veces por segundo, capturar el teclado y armar la tabla de puntos sin depender de `npm` ni compiladores web. |
| **Aplicación externa (URC)** | `urc/` | Python 3 usando **solo su biblioteca estándar**: `http.server` (servidor web), `socket` (TCP), `threading` (hilos), `json` (archivos de trayectorias). | Corre directo con `python3 -m urc.app` en Windows o Mac sin instalar nada con `pip`. |
| **Cinemática y choques** | `scara/` | Python 3 con `math` (`cos`, `sin`, `acos`, `atan2`, `hypot`) y `dataclasses`. | Toda la geometría son triángulos y cajas 3D: no hace falta NumPy ni motores externos para calcular un tramo en milisegundos. |
| **Firmware del robot (UCI)** | `firmware/` | C++ estándar escrito para microcontrolador (`stdint.h`, `stddef.h`): **sin decimales (`float`) y sin memoria dinámica (`new`/`malloc`)**. | Tiene que entrar y correr igual en los **2 KB de RAM** del Arduino UNO y adentro de Webots (D3, ADR 0002). |
| **Controlador y planta en Webots** | `webots/` | C++ con la librería propia de Webots (`libCppController`: `Supervisor`, `Motor`, `PositionSensor`, `Emitter`, `Receiver`) y sockets TCP del sistema operativo. | Es el puente entre nuestro firmware portable y el mundo 3D de Webots. |
| **Pruebas automáticas** | `tests/` y `firmware/test/` | `unittest` (que ya viene con Python), `subprocess` y sockets locales. | Permite correr más de 200 pruebas en ~1 minuto desde la terminal con un solo comando (`python3 -m unittest discover`). |
| **Conversión del CAD (hecha una vez)** | `cad/` y `tools/` | Conversor local `sldprt2step` y Python con OpenCascade (`OCP`) para leer sólidos 3D y exportar mallas STL. | Solo se usa si algún día se quiere regenerar el robot desde SolidWorks. **Para usar o probar el sistema no hace falta tenerlo instalado.** |

### Las cuatro reglas de oro que ordenan el código

Antes de mirar archivo por archivo, conviene tener presentes cuatro ideas que explican por qué el código está dividido así:

1. **La URC piensa el camino y el firmware solo lo ejecuta con su reloj (D6, ADR 0005).** Hacer una línea recta con un brazo articulado exige calcular trigonometría (cinemática inversa) cincuenta veces por segundo y chequear que el brazo no choque contra la torre. A un Arduino UNO no le da ni la velocidad ni la memoria para hacer eso. Por eso toda la matemática pesada vive en Python (`urc/` y `scara/`), que corta el movimiento en **segmentos chiquitos de 20 ms** y se los manda al firmware en una cola. El firmware solo los recibe y mueve los motores a tiempo con su propio reloj.
2. **Un solo firmware con un «enchufe» intercambiable (`firmware/hal.h`, D3, ADR 0002).** El corazón del firmware (`firmware.cpp`) no tiene ni una sola línea que nombre a Webots ni a los registros del Arduino. Cuando necesita leer un byte, saber qué hora es, dar un paso de motor o leer un sensor Hall, llama a una interfaz chiquita de seis funciones (`hal.h`). En el Arduino, esas seis funciones tocan pines y timers reales; en Webots, mueven la planta simulada; y en las pruebas, tocan contadores en memoria.
3. **Lo que cree el robot está separado de la verdad del simulador (ADR 0004).** Como el SCARA real tiene motores paso a paso **sin encoders**, el firmware no puede medir dónde está el brazo: solo cuenta cuántos pulsos mandó desde el último homing (la **posición estimada por pasos**). Webots sí sabe dónde está físicamente cada pieza (por ejemplo, si el eje vertical se cayó o perdió pasos por exceso de peso), pero esa verdad **solo** viaja por un segundo canal separado (`scara-sim/1`, puerto 9001) hacia el cartel del «Banco de ensayo». Ni el planificador ni la sesión de la URC leen jamás ese canal.
4. **Doble barrera de seguridad: la URC cuida al robot y el firmware cuida a los motores (D51, D55).** Antes de empezar a moverse, la URC revisa el camino entero para asegurarse de que no se salga del alcance, no invierta el codo de golpe ni choque contra el pedestal o la torre. Y del otro lado, el firmware revisa por su cuenta cada orden que le llega: si no hay corriente en los drivers, si falta hacer homing o si un segmento pide girar un motor más rápido de lo permitido, lo rechaza aunque la URC se haya equivocado.

---

## 2. El viaje de una orden: qué pasa cuando mantenés apretada una tecla

La forma más fácil de entender cómo se conectan todos los archivos es seguir una orden real de punta a punta. Imaginemos que el robot ya hizo su homing, está quieto en la pose de reposo y mantenés apretada la tecla **D** en la página para girar el hombro (`J1`) hacia el lado positivo.

<!-- FIGURA: viaje_jog | Figura 2. El recorrido completo cuando mantenés apretada la tecla D con el robot referenciado: del navegador a la URC (HTTP), de la URC al firmware (segmentos de 20 ms por TCP) y del firmware a la planta simulada de Webots. -->

### Paso 1: En el navegador (`urc/index.html`)
La página web detecta que apretaste la `D`. Como el operador puede soltar la tecla en cualquier momento —o se le puede cerrar la pestaña—, la página no manda una orden de «movete para siempre»: manda un pedido `POST /api/jog` diciendo «quiero seguir moviendo J1 hacia +» **y lo repite cada 150 milisegundos** mientras tengas el dedo apoyado. En cuanto soltás la tecla (o cambiás de ventana), deja de repetir y avisa `/api/jog/stop`.

### Paso 2: En la URC (`urc/app.py`, `urc/session.py` y `urc/jog.py`)
El servidor web de Python (`app.py`) recibe ese pedido y se lo pasa a la sesión (`session.py`). Acá pasa algo muy importante: como el robot **ya está referenciado**, la URC sabe exactamente dónde está el brazo y no manda un comando `JOG` crudo, sino que usa el **jog verificado**.
- Cada vez que necesita alimentar al robot, le pide a `jog.py` que calcule dónde quedaría el brazo **20 milisegundos más adelante**.
- `jog.py` chequea dos cosas antes de dar el visto bueno: que ese pasito no se pase del límite de grados de la articulación y que en esa nueva pose el brazo no invada la zona de seguridad del pedestal, el piso ni la torre (usando `scara/collisions.py`).
- Si está todo libre, la URC arma una línea de texto del protocolo: `SEG 1 20 20 0 0 12000` («segmento número 1, dura 20 ms, llevá J1 a 0,20° y dejá el resto igual»).
- Para que el movimiento sea continuo pero frene al instante cuando sueltes la tecla, la URC mantiene siempre **hasta 3 segmentos** (60 ms en total) adelantados en la cola del firmware.

### Paso 3: En el firmware (`firmware/firmware.cpp` y `firmware/transmission.h`)
El texto `SEG 1 20 20 0 0 12000` entra por el enchufe TCP al firmware que corre dentro del controlador de Webots:
- El firmware revisa que los motores estén habilitados, que los cuatro ejes tengan referencia y que la velocidad pedida no supere el tope de ningún motor.
- Después llama a `transmission.h` para traducir esos `0,20°` de `J1` a pasos de motor. Y acá entra en juego el **acople mecánico de las correas**: como el motor `M2` mueve el antebrazo respecto del mundo por adentro del brazo, si solo girara `M1` el antebrazo se doblaría solo. Entonces `transmission.h` calcula que para mover `J1` sin doblar el codo hay que dar **4 pasos en `M1` y también 4 pasos en `M2`**.
- Guarda ese segmento en su cola, le contesta `OK 1` a la URC («recibido, mandame el que sigue cuando quieras») y en cada vuelta de su reloj va emitiendo los pulsos `step()` hacia la capa de hardware.

### Paso 4: En la planta simulada y en la ventana 3D (`webots/controllers/scara_uci/`)
Cada pulso que emite el firmware lo recibe la **planta simulada** (`scara_uci.cpp` y `stepper.h`):
- La planta suma ese pulso al campo magnético del motor `M1` y del motor `M2`.
- En cada paso de simulación de Webots (cada 2 milisegundos), el modelo físico del motor (**N2**) calcula cuánta fuerza hace el rotor para seguir a esos pulsos según el peso que tenga cargado el brazo.
- Finalmente, le pasa la nueva posición a las articulaciones de Webots y ves moverse el brazo en 3D. Al mismo tiempo, 20 veces por segundo, el firmware manda una línea `S RUN ...` hacia la URC con los pasos que lleva contados, y la página web actualiza los numeritos en pantalla.

> [!IDEA] **¿Y qué cambia si apretás la misma tecla `D` apenas prendés el robot, antes de hacer homing?**
> Sin referencia, la URC todavía no sabe en qué ángulo real arrancó el brazo, así que no puede calcular geometría ni choques. En ese caso, en vez de mandar segmentos `SEG`, manda una sola orden `JOG 1 + 500` (mover a velocidad fija y bajita, 5 °/s). El que cuida al robot ahí es el propio firmware: si mientras te movés a ciegas el brazo pisa cualquiera de los sensores Hall de los extremos, el firmware frena solo como si fuera un fin de carrera (D21, D58).

### Los tres frenos por si algo falla en el medio (D37)
¿Qué pasa si estás moviendo el robot con jog y se tilda el navegador, o se corta la conexión entre la URC y Webots? Hay tres paracaídas independientes, uno en cada capa:
1. **En la página:** apenas soltás la tecla o cambiás de pestaña, manda la orden de parar.
2. **En la URC:** si pasan **0,5 segundos** sin que la página renueve el pedido de jog, la URC corta el movimiento por su cuenta.
3. **En el firmware (el watchdog):** la URC le manda un `PING` cada 250 ms. Si pasa **1 segundo** entero sin recibir noticias de la URC, el firmware frena los motores por su cuenta y avisa `ERR 4 watchdog`.

---

## 3. La URC por dentro (`urc/`): cómo trabaja la aplicación en Python

La carpeta `urc/` contiene todo el programa que corre del lado de la computadora del operador. Para que sea ordenado y fácil de probar, está separado en archivos chicos donde cada uno tiene una responsabilidad clara:

| Archivo | Qué papel cumple (explicado simple) |
| --- | --- |
| `urc/app.py` | **El mostrador web.** Levanta el servidor en `http://127.0.0.1:8766`, entrega la página y recibe los clics y teclas del navegador para derivarlos al módulo que corresponda. |
| `urc/session.py` | **El telefonista con el robot.** Mantiene abierta la conexión TCP (puerto 9000) con el firmware en un hilo propio, manda los `PING` cada 250 ms, recibe los estados `S` 20 veces por segundo y administra el envío de los segmentos. |
| `urc/protocol.py` | **El traductor del protocolo.** Sabe armar las líneas de texto que salen hacia el firmware (`SEG`, `JOG`, `HOME`, etc.) y sabe leer las respuestas que vuelven (`BOOT`, `HI`, `S`, `OK`, `ERR`, `EV LOST`). |
| `urc/planner.py` | **El calculador de caminos.** Toma un punto de inicio y uno de destino y fabrica la lista de segmentos de 20 ms, tanto para movimientos articulados (**PTP**) como para rectas (**LIN**), aplicando la rampa suave de aceleración y frenado. |
| `urc/validation.py` | **El inspector antes de salir.** Revisa todos los tramos de una trayectoria completa antes de que el robot se mueva un milímetro; si encuentra un problema, arma un mensaje claro diciendo en qué tramo está y cómo arreglarlo. |
| `urc/jog.py` | **El paso a paso del teclado.** Calcula cada pasito de 20 ms cuando mantenés apretada una tecla en modo referenciado (tanto en grados como en X, Y, Z) y frena antes de tocar un límite o un obstáculo. |
| `urc/trajectories.py` | **El cuaderno de trayectorias.** Permite capturar puntos con la barra espaciadora, agregarlos a mano escribiendo coordenadas, cambiarles la velocidad o el tipo (`LIN`/`PTP`) y guardarlos en archivos `.json` dentro de la carpeta `trayectorias/`. |
| `urc/playback.py` | **El director de reproducción.** Cuando le das a «Play», pide validar toda la trayectoria, calcula el tramo lento de acercamiento hasta el primer punto (al 25 % de velocidad), va alimentando los tramos sin pausas entre uno y otro, y maneja la **Pausa** (que frena suave y al reanudar retoma por la misma recta) y el **Stop**. |
| `urc/instrumentation.py` | **El canal del banco de ensayo.** Escucha en otro puerto distinto (el 9001) los datos exclusivos de la simulación de Webots (posición física real, corriente de los motores, fallas inyectadas) para mostrarlos en el panel inferior de la página. |
| `urc/events.py` | **La bitácora.** Guarda la lista de todo lo que fue pasando (conexiones, homings, errores, fallas aplicadas) que se ve en la columna derecha de la página. |

### Cómo piensa un movimiento `planner.py`: la diferencia entre PTP y LIN

Cuando el robot tiene que ir de un punto A a un punto B, la URC puede armar el movimiento de dos maneras:

- **En un tramo PTP (*point to point*):** lo que importa es llegar de la pose A a la pose B de la forma más directa para los motores. El planificador mira cuántos grados tiene que recorrer cada articulación, calcula cuánto tarda la más exigida (teniendo en cuenta que el motor `M2` tiene que recorrer `J1 + J2` por el acople) y mueve las cuatro articulaciones juntas con una misma rampa de aceleración y frenado (**perfil trapezoidal**). Todas arrancan juntas y terminan en el mismo instante, aunque la punta del brazo dibuje una curva en el aire. **No usa cinemática inversa.**
- **En un tramo LIN (línea recta):** queremos que la punta de la herramienta dibuje una recta perfecta en el espacio X, Y, Z. Entonces el planificador corta esa recta en pedacitos de 20 milisegundos y, **en cada pedacito, calcula la cinemática inversa** para averiguar qué ángulos tienen que poner `J1`, `J2`, `J3` y `J4` en ese instante. Además, exige que el codo se mantenga doblado del mismo lado durante toda la recta, porque cambiar el codo de lado obligaría a estirar el brazo del todo en el medio.

> [!PREGUNTA] **Preguntas probables del profesor sobre la URC**
> - **«¿Por qué hicieron la interfaz como una página web y no con una ventana de escritorio (como Tkinter o Qt)?»**
>   Porque el navegador ya viene en cualquier computadora, no hay que instalar librerías gráficas que suelen dar problemas entre Windows y Mac, y la separación entre la pantalla (HTML/JS) y la lógica (Python) queda limpísima por HTTP.
> - **«¿Por qué la URC tiene un hilo aparte en `session.py`?»**
>   Porque mientras el operador hace clic en la página web, la URC tiene que seguir escuchando los mensajes `S` del robot 20 veces por segundo y mandándole `PING` cada 250 ms sin atrasarse. Si todo corriera en el mismo lugar, un pedido lento de la página congelaría la comunicación con el robot y haría saltar el watchdog.
> - **«¿Qué guarda adentro un archivo `.json` de una trayectoria?»**
>   Guarda la lista de puntos, y en cada punto guarda **los ángulos de las articulaciones** (`J1` a `J4`) como dato principal, además del X, Y, Z para que sea fácil de leer, el tipo de tramo (`LIN` o `PTP`), la velocidad (en %) y el tiempo de espera. No guarda los segmentos de 20 ms: los segmentos se calculan recién en el momento de darle Play, según dónde esté parado el robot y a qué velocidad global quieras reproducir (D13).

---

## 4. La matemática del robot (`scara/`): cinemática y choques

Toda la geometría del brazo vive en la carpeta `scara/`, separada del servidor web y de la red para poder probarla sola.

### ¿Usamos solo la cinemática inversa o también la directa? (`scara/kinematics.py`)

Usamos **las dos**, todo el tiempo, pero cada una para cosas distintas:

1. **La cinemática directa (`forward`):** recibe los ángulos de las articulaciones (`J1` a `J4`) y calcula dónde queda la punta de la herramienta en milímetros (`X, Y, Z`) y con qué rumbo apunta. Se usa para:
   - Mostrar en vivo las coordenadas `X, Y, Z` en la página web cada vez que llega un estado `S` del robot (que viene en grados y milímetros articulares).
   - Anotar las coordenadas `X, Y, Z` cuando capturás un punto durante el teach, y verificar que coincidan cuando cargás un archivo `.json` del disco.
   - Conocer el punto exacto de partida y de llegada cuando hay que trazar una recta `LIN`, y comprobar en los ensayos que el camino ejecutado no se haya desviado de la recta.
2. **La cinemática inversa (`inverse` y `arm_angles`):** hace el camino al revés: le das el `X, Y, Z` y el rumbo al que querés llevar la punta, y te devuelve qué ángulos tienen que poner `J1, J2, J3, J4`. Se usa en tres lugares:
   - En cada muestra de 20 ms de un **tramo LIN**.
   - En cada pasito de 20 ms del **jog cartesiano** (cuando movés con el teclado en X o en Y).
   - Cuando escribís un punto a mano en coordenadas `X, Y, Z` o usás el botón «Ir a una pose» en modo cartesiano.

### Cómo resuelve la inversa sin misterio
Como el brazo SCARA se mueve en el plano horizontal y sube y baja verticalmente con el vástago `J4`, el problema se desarma fácil:
- La altura `Z` sale directo de `J4` (`Z = 94,67 mm − J4`, porque cuando `J4` avanza hacia abajo, la altura respecto de la mesa disminuye).
- Visto desde arriba, el brazo (`L1 = 250 mm`), el antebrazo (`L2 = 250 mm`) y la distancia hasta el punto `(X, Y)` forman un triángulo. Con el **teorema del coseno** sale el ángulo del codo (`J2`).
- Como el coseno da igual para un ángulo positivo o negativo, siempre hay **dos formas de llegar al mismo punto**: con el codo doblado hacia un lado (`J2` negativo, que es el que prefiere el sistema por defecto) o hacia el otro (`J2` positivo).
- Con `J2` elegido, sale el ángulo del hombro (`J1`) con `atan2`, y por último la muñeca (`J3`) simplemente compensa lo que giraron `J1` y `J2` para que la herramienta quede apuntando con el rumbo pedido (`J3 = rumbo − J1 − J2`).

### Cómo se chequean los choques (`scara/collisions.py` y `scara/frames.py`)
En Webots desactivamos los choques internos entre piezas vecinas del propio robot (`selfCollision FALSE`) porque las cajas envolventes simplificadas se rozan en las uniones. En cambio, quien impide que el robot se lleve puesto algo es **`scara/collisions.py`** en la URC:
- Representa la torre, el piso, el pedestal de ensayo y las piezas móviles del brazo como **cajas 3D con un margen de seguridad** (15 mm en general y 8 mm entre el brazo y la torre).
- Antes de aprobar cualquier segmento (sea de una trayectoria o del jog verificado), ubica esas cajas según los ángulos `J1..J4` y comprueba que ninguna se superponga.
- **Un detalle inteligente del código (D71):** si por algún motivo el brazo ya quedó estacionado *adentro* de la zona de margen de seguridad, no te deja bloqueado para siempre: te permite moverte con un PTP siempre y cuando ese movimiento **aleje** al brazo del obstáculo.

> [!PREGUNTA] **Preguntas probables del profesor sobre cinemática y choques**
> - **«¿Por qué un tramo LIN no puede cambiar la configuración del codo a mitad de camino?»**
>   Porque para pasar de codo negativo a codo positivo el brazo tendría que pasar por `J2 = 0°` (totalmente estirado), que es una singularidad, o dar un latigazo enorme con las articulaciones mientras la punta intenta seguir una recta. Por eso `validation.py` lo detecta antes de arrancar y te pide cambiar ese punto a `PTP`.
> - **«¿Alcanza con verificar que el punto inicial y el punto final de un tramo no choquen?»**
>   No: dos puntos pueden estar libres de obstáculos y que el camino entre ellos atraviese la torre o el pedestal. Por eso el código verifica **todos los segmentos intermedios de 20 ms** de punta a punta.

---

## 5. El firmware (`firmware/`): cómo un mismo programa corre en el UNO y en Webots

La carpeta `firmware/` es el corazón de la **UCI** (la Unidad de Control Incorporada). Lo más lindo de su diseño es que **es exactamente el mismo código C++** cuando compila para el Arduino UNO real, cuando corre adentro del controlador de Webots y cuando corre en las pruebas automáticas en la PC.

<!-- FIGURA: costura_hal | Figura 3. La «costura» de hardware (firmware/hal.h): el núcleo del firmware es uno solo y habla con seis funciones simples; cambiando qué hay del otro lado de ese enchufe, el mismo programa corre en el Arduino UNO, en Webots o en las pruebas de la PC. -->

### Cómo está organizado por dentro
- **`firmware/hal.h` (el enchufe al hardware):** define una clase abstracta mínima con solo **seis operaciones**: saber cuántos milisegundos pasaron (`millis`), leer o escribir texto por el canal de comunicación (`readByte` y `writeLine`), prender o apagar la corriente de los drivers (`setDriversEnabled`), emitir un paso a un motor en una dirección (`step`) y leer si el sensor Hall de un eje está viendo un imán (`hallActive`).
- **`firmware/config.h` (los números de la máquina):** guarda en un solo lugar el microstepping (`1/8`, es decir 1600 pasos por vuelta de motor), las velocidades máximas de cada motor y las posiciones donde están los imanes Hall. Lo leen tanto el firmware como la planta simulada de Webots para que nunca tengan números distintos (D44).
- **`firmware/transmission.h` (de grados y milímetros a pasos, con el acople):** hace todas las cuentas con fracciones de números enteros (sin `float`). Por ejemplo, con reducción 4:1 y 1600 pasos por vuelta, girar 1° la articulación son `1600 × 4 / 360 = 17,78` pasos (exactamente `8 pasos cada 0,45°`). Y acá se resuelve el **acople entre M1 y M2**:
  - `pasos de M1 = pasos que pide J1`
  - `pasos de M2 = pasos que pide J1 + pasos que pide J2`
  Así, cuando la URC pide mover solo `J1`, el firmware mueve `M1` y `M2` juntos y el antebrazo mantiene su ángulo relativo.
- **`firmware/firmware.cpp` (el cerebro del controlador):** contiene la máquina de estados del robot (`OFF` sin corriente, `IDLE` quieto con corriente, `JOG` moviendo continuo, `HOMING` buscando los imanes y `RUN` ejecutando la cola de segmentos).
- **`firmware/arduino/scara_uci/` (la versión para la placa real):** implementa `hal.h` para el chip ATmega328P del Arduino UNO. Usa el puerto serie a 115200 baudios y el **Timer1 por interrupciones cada 50 microsegundos** (`StepPulser`) para generar los pulsos `STEP/DIR` hacia los drivers TB6600 sin que se atrasen aunque el programa esté leyendo texto. Cuando se compila con `arduino-cli`, ocupa **la mitad de la memoria flash (50 %)** y el **63 % de los 2 KB de RAM**.

### Cómo funcionan las tres tareas clave del firmware
1. **La cola de segmentos (`RUN`):** el firmware tiene una cola circular de **16 lugares**. A medida que la URC le manda líneas `SEG`, las guarda ahí. En cada vuelta de su lazo principal, mira cuántos milisegundos van del segmento actual y calcula por regla de tres cuántos pasos tendría que haber dado cada motor hasta ese instante, emitiendo los pasos que falten. Cuando termina un segmento, engancha el siguiente sin frenar. Si la cola está llena (los 16 lugares ocupados), recibe el segmento nuevo pero **se guarda el `OK` sin enviarlo** hasta que se desocupe un lugar: así frena a la URC de forma natural sin perder ningún mensaje (D50).
2. **El homing en 5 fases (`HOMING`):** como al prender el robot no sabemos dónde está pero puede haber arrancado cerca o encima de un imán, cada eje busca su referencia haciendo una coreografía de cinco pasos: si ya estaba pisando el imán, primero sale; después avanza a velocidad media (15 °/s, o 10 mm/s en J4) hasta tocar el imán; se mete un poquito más adentro para asegurarse de no estar en el borde; retrocede lento para salir; y vuelve a entrar **despacito (2 °/s)** para detectar el borde exacto del imán siempre desde el mismo lado. Lo hace en orden seguro: primero sube la herramienta (`J4`), después el hombro (`J1` moviendo M1 y M2 juntos), después el codo (`J2`) y por último la muñeca (`J3`).
3. **La detección de pérdida de pasos sin encoders (`checkLostSteps`):** una vez que un eje hizo homing, el firmware sabe en qué número exacto de paso empieza el imán de cada extremo. Si durante el trabajo normal el brazo vuelve a cruzar cualquiera de sus imanes, el firmware compara los pasos que lleva contados en memoria contra el lugar donde debería estar ese imán. Si la diferencia es de **2 pasos completos o más**, se da cuenta de que el motor patinó y manda el aviso `EV LOST <eje> <pasos>` a la URC (sin corregir la cuenta a las apuradas en movimiento, para obligar a hacer un homing limpio).

> [!PREGUNTA] **Preguntas probables del profesor sobre el firmware**
> - **«¿Por qué hay dos órdenes para frenar: `STOP` y `HALT`?»**
>   Porque hacen lo mismo que el *feed hold* y el *reset* de un CNC (como GRBL): **`STOP`** frena con una rampa suave de desaceleración (en hasta 250 ms) para que los motores no pierdan pasos por inercia y **conserva la referencia** (es lo que usa el botón Pausa). **`HALT`**, en cambio, clava los motores en seco en el acto ante una emergencia; como frenar de golpe puede hacer patinar el rotor, si el robot se estaba moviendo `HALT` da por **perdida la referencia** por seguridad (D41).
> - **«¿Por qué el protocolo habla en centésimas de grado y centésimas de milímetro en vez de mandar directamente pasos de motor desde la URC?»**
>   Para que la URC no tenga que saber qué poleas, qué tornillo ni qué microstepping tiene puesto el robot (D5, ADR 0003). Si mañana en el laboratorio cambiamos un driver de `1/8` a `1/16`, solo se cambia un número en `firmware/config.h` y la URC sigue andando sin tocar una línea de Python.

---

## 6. Webots por dentro (`webots/` y `cad/`): planta simulada, fallas y modelo 3D

Cuando corrés la simulación en Webots, el programa que maneja al robot es `webots/controllers/scara_uci/scara_uci.cpp`. Adentro de ese programa conviven tres cosas: **el firmware** (el mismo que acabamos de ver), **la planta simulada** (que hace el papel de los drivers, los motores, las correas y los sensores Hall) y **el banco de ensayo** (que maneja el segundo canal TCP para inyectar fallas).

<!-- FIGURA: planta_webots | Figura 4. Qué pasa dentro del controlador de Webots en cada paso de 2 milisegundos: el firmware emite pulsos como si hablara con un driver real; la planta simulada calcula la física del rotor paso a paso (N1 + N2) y mueve el modelo 3D. -->

### Cómo simula los motores la planta: niveles N1 y N2 (`stepper.h`)
Si en Webots simplemente le dijéramos a la articulación «ponete en 30 grados», el brazo se movería como un servomotor ideal y nunca podríamos ver qué pasa cuando un motor paso a paso hace demasiada fuerza y pierde pasos. Por eso el controlador modela los motores en dos capas (ADR 0006):

- **Nivel N1 (la transmisión y los escalones discretos):** cada pulso que emite el firmware mueve el ángulo del campo magnético del motor en un escalón fijo (`0,05625°` en los ejes rotacionales con microstepping 1/8, o `0,005 mm` en el eje vertical `J4`) aplicando la reducción de las poleas y el acople entre `M1` y `M2`.
- **Nivel N2 (la física del rotor paso a paso en `stepper.h`):** el rotor del motor no salta mágicamente a donde dice el pulso, sino que tiene inercia y es «tironeado» magnéticamente hacia el pulso según la curva de par del motor (`T = T_max · sen(π/2 · atraso / paso_completo)`).
  - En uso normal, el par que tienen los motores NEMA 23 y NEMA 17 alcanza con holgura y el rotor sigue a los pulsos casi pegado.
  - Pero si desde el banco de ensayo le ponés mucho peso en la punta y le bajás la corriente a un driver (**falla F1**), o si el brazo choca contra un obstáculo físico (**escenarios C1–C4**), el par magnético no alcanza: el rotor se atrasa más de dos pasos completos, «zafa» de diente magnético y **pierde de a 4 pasos completos** (un ciclo eléctrico entero). El firmware sigue contando sus pulsos como si nada, y en el panel del banco ves en vivo cómo se separan la posición que cree el robot y la posición física real.

### Cómo funcionan los sensores Hall en Webots (D57)
En el modelo 3D (`SCARA.proto`), cada articulación tiene un nodo para el sensor Hall (`Receiver`) en la parte fija y dos nodos para los imanes (`Emitter`, uno en cada extremo del recorrido) en la pieza móvil. Como Webots no entrega paquetes de radio entre un `Emitter` y un `Receiver` que pertenecen al mismo `Robot`, el controlador hace algo mucho más directo y fiel a la geometría: en cada paso mide la **distancia en 3D** entre la posición del sensor y la de los imanes de ese eje. Si el imán está más cerca que su alcance, unos 5 milímetros (salvo que la falla F3 lo haya dejado trabado), el Hall se activa. Dónde va cada sensor e imán, con sus escuadras, está en D93 y en `tools/generate_world.py`.

### Cómo se inyectan las fallas desde el banco (`scara-sim/1`, puerto 9001)
El bloque `Bench` del controlador se conecta al puerto 9001 de la URC y 20 veces por segundo le cuenta la verdad física del simulador. Cuando hacés clic en el panel «Banco de ensayo» de la página, le llegan órdenes por ese canal:
- **`F1` (bajar corriente de un driver):** achica el porcentaje de par disponible de ese motor en `stepper.h` para provocar pérdida de pasos bajo carga o aceleración.
- **`F2` (driver de M4 sin corriente):** deja sin fuerza de retención al motor vertical; por la gravedad de Webots, el vástago `J4` se cae solo mientras el firmware sigue creyendo que está arriba.
- **`F3` (sensor Hall pegado o muerto):** fuerza la lectura de ese sensor en siempre activo o siempre inactivo, para mostrar cómo el homing detecta la falla y aborta con error (`ERR 10` o `ERR 11`).
- **`F4` (cortar el cable de comunicación):** enmudece el enchufe TCP del puerto 9000 sin cerrar la conexión, como si alguien desenchufara el cable serie en pleno movimiento, para ver actuar al watchdog en menos de 1 segundo.
- **`F5` (reinicio inesperado del microcontrolador):** destruye y vuelve a crear el objeto `Firmware` adentro del controlador sin mover el brazo 3D. El firmware nuevo manda `BOOT` y la URC detecta al instante que el controlador se reinició y perdió la referencia.

### De dónde salió el archivo `SCARA.proto` (`cad/` y `tools/`)
El archivo `webots/protos/SCARA.proto` (que define todas las piezas, articulaciones, motores y sensores del robot en Webots) **no se escribió a mano**: lo generó el script `tools/generate_world.py` al final de una cadena de herramientas que procesó el material original de la cátedra:
1. Primero, `tools/convertir_cad.py` tomó las piezas nativas de SolidWorks (`Modelos3D/*.SLDPRT`), las pasó a formato geométrico STEP con el conversor `sldprt2step` y exportó las mallas de triángulos `.stl` en `cad/derivados/stl/` usando OpenCascade.
2. Después, `tools/extraer_ensamble.py` y `tools/extraer_ejes_cad.py` leyeron las posiciones guardadas adentro de los ensambles y midieron los cilindros de los ejes (de ahí se confirmaron los **250 mm** exactos entre el hombro y el codo y entre el codo y la muñeca).
3. Por último, `tools/integrate_cad.py` agrupó qué piezas se mueven juntas en cada eslabón (según `config/cad_integration.json`) y `tools/generate_world.py` escribió el `SCARA.proto` listo para abrir en Webots.

> [!PREGUNTA] **Preguntas probables del profesor sobre Webots y el CAD**
> - **«¿Por qué no bastaba con pasar todas las piezas de SolidWorks a STL y tirarlas en Webots?»**
>   Porque un archivo STL es solo una cáscara de triángulos: no sabe dónde va ubicada la pieza en el ensamble, ni qué piezas se mueven solidarias entre sí, ni dónde pasan los ejes de giro ni cuánto pesa cada cuerpo. Todo eso lo reconstruyen `integrate_cad.py` y `generate_world.py`.
> - **«¿El sensor Hall de Webots hace trampa leyendo el ángulo de la articulación?»**
>   No: mide la distancia en el espacio 3D entre el nodo del sensor y el nodo del imán montado en la pieza móvil. Si movés el imán en el modelo, cambia el lugar donde se activa el sensor.

---

## 7. Cómo están hechas las pruebas (`tests/`, `firmware/test/` y `validation/`)

Esta es una de las partes más interesantes para contar si el profesor pregunta *«¿cómo saben que todo esto anda bien?»* o *«¿cómo están desarrollados los tests?»*.

En vez de depender únicamente de abrir Webots y probar a ojo con el mouse (que lleva mucho tiempo y no sirve para repetir después de cada cambio en el código), armamos el sistema de pruebas en **tres capas**, usando la librería `unittest` que trae Python.

<!-- FIGURA: tres_costuras | Figura 5. Las tres capas de pruebas del proyecto: 1) el firmware en C++ probado en la PC con un hardware falso; 2) la URC en Python probada con un robot falso y pruebas de unidad; y 3) la campaña de 18 escenarios reales corriendo en Webots. -->

### Capa 1: Probar el firmware sin Arduino y sin Webots (`firmware/test/`)
Como el firmware se comunica con el hardware únicamente a través de las seis funciones de `hal.h`, en `firmware/test/conversacion.cpp` armamos una **capa de hardware falsa (`FakeHal`)** que corre directamente en la PC:
- Tiene un reloj de mentira que podemos adelantar la cantidad exacta de milisegundos que queramos (`+ 1000` avanza 1 segundo al instante, sin tener que esperar 1 segundo real).
- Tiene cuatro contadores para anotar cuántos pasos dio cada motor (`M1` a `M4`) y una geometría simple que prende o apaga los sensores Hall cuando esos pasos llegan a los extremos.
- Compilamos el `firmware.cpp` real junto con ese `FakeHal` en un programita de consola y le pasamos **guiones de conversación** (`firmware/test/conversaciones/*.txt`).

Mirá qué fácil se lee uno de esos archivos de conversación (`jog_j1.txt`):
```text
> ENABLE
> JOG 1 + 450
+ 1000
= M1 80 M2 80 M3 0 M4 0
< S JOG 0 450 0 0 0 0 16 0
```
*Traducción renglón por renglón:*
1. `> ENABLE` y `> JOG 1 + 450`: simulamos que la URC le manda habilitar motores y mover `J1` a 4,50 °/s.
2. `+ 1000`: adelantamos el reloj del firmware 1000 milisegundos (1 segundo).
3. `= M1 80 M2 80 M3 0 M4 0`: verificamos que en ese segundo el firmware haya emitido exactamente **80 pasos en M1 y 80 pasos en M2** (demostrando que el acople funciona).
4. `< S JOG ...`: verificamos que el mensaje de estado `S` que contestó el firmware diga que está en modo `JOG` y en la posición `450` (4,50°).

### Capa 2: La «conformidad simétrica» y las pruebas de la URC (`tests/`)
Acá viene el mejor truco de las pruebas (`tests/test_conformidad.py`, D42): ¿qué pasaría si probamos muy bien el firmware por su lado y la URC por el suyo, pero los dos entienden un mensaje del protocolo de forma apenas distinta?
Para que eso sea imposible, **usamos los mismos 24 archivos `.txt` de conversación de recién, pero dados vuelta**:
- En Python levantamos la **URC real** y le conectamos por TCP una **UCI falsa (`FakeUci`)** que hace de títere.
- Por cada renglón `>` del archivo, le pedimos a la URC que genere esa orden y comprobamos que mande exactamente ese texto.
- Por cada renglón `<` del archivo, la UCI falsa le manda esa respuesta a la URC y comprobamos que la URC actualice bien su estado, sus errores o sus alertas.
- Así, el archivo `.txt` funciona como un contrato vivo: **si alguien cambia algo del protocolo de un lado y se olvida del otro, el test salta enseguida.**

Además de esa prueba de conformidad, la carpeta `tests/` tiene archivos `test_*.py` para cada pieza de la URC y de la matemática:

| Qué queremos probar | Archivo de prueba | Cómo lo prueba sin abrir Webots |
| --- | --- | --- |
| **Cinemática directa e inversa** | `tests/test_kinematics.py` | Calcula la directa de varias poses y verifica que la inversa vuelva al mismo lugar, que elija el codo correcto y que rechace puntos fuera del alcance de 500 mm. |
| **Detección de choques** | `tests/test_collisions.py` | Pone el brazo en poses libres y en poses que tocan el pedestal, el piso o la torre y comprueba que las detecte (y que permita salir si ya estaba en el margen). |
| **Planificador PTP y LIN** | `tests/test_planner.py` y `tests/test_lin.py` | Verifica que todas las articulaciones lleguen juntas en un PTP, que la recta LIN no se desvíe más de la tolerancia y que se rechacen rectas que cambian el codo o chocan. |
| **Sesión, gestor y reproducción** | `tests/test_urc.py`, `test_trajectories.py`, `test_playback.py` | Levanta el servidor HTTP real de la URC en un puerto temporal, le hace pedidos HTTP como si fuera el navegador y le habla del otro lado con la `FakeUci`. |
| **Las tres demos de la defensa** | `tests/test_demos.py` | Carga los archivos reales de `trayectorias/` (el cuadrado LIN, el barrido PTP y el pick & place) y simula reproducirlos dos vueltas enteras para asegurar que ningún cambio los haya roto. |
| **Modelo físico del motor (N2)** | `tests/test_planta.py` | Compila `stepper.h` en la PC y verifica que con par normal siga los pulsos y que con sobrecarga pierda pasos de a 4 pasos completos. |
| **Aislamiento del canal de simulación** | `tests/test_instrumentation.py` | Además de probar el canal 9001, revisa el código de la URC para garantizar que ni `session.py`, ni `planner.py`, ni `validation.py` importen jamás el módulo del banco de ensayo. |

#### Cómo se corren y por qué algunas dicen «skipped» (omitidas)
Desde la raíz del repositorio corrés un solo comando:
```sh
python3 -m unittest discover -s tests -v
```
En más o menos **un minuto y cuarto** corren las **218 pruebas**. En una computadora normal vas a ver que unas 8 aparecen como *skipped* (omitidas): no es un error, sino que el test detecta si tenés instaladas ciertas herramientas opcionales que no hacen falta para usar el simulador (por ejemplo, si no tenés `arduino-cli` saltea la prueba que compila el sketch del UNO; si no tenés `socat` saltea el ensayo de puerto serie virtual; y si no tenés el entorno `OCP` de OpenCascade saltea la auditoría de volúmenes CAD).

### Capa 3: La campaña de validación con Webots abierto (`validation/campana/`)
Lo único que `unittest` no puede probar por sí solo es el motor físico de Webots moviendo el modelo 3D en tiempo real. Para eso está `validation/campana/campana.py`:
- Es un script que abre Webots y la URC automáticamente y corre los **18 escenarios de prueba** de punta a punta: homing normal y con desvío (**H1, H2**), teach & play y las tres demos (**T1 a T3**), las cinco fallas inyectadas desde el banco (**F1 a F5**), los ensayos de choque físico contra un bloque y sobrecarga (**C1 a C4**) y las pruebas de soporte (**P1 a P3**).
- Al terminar, deja guardado en `validation/campana/INFORME.md` el resultado de cada escenario junto con el hash `SHA-256` de los archivos para saber exactamente con qué versión se probó.

---

## 8. Cuidados prácticos para la demo y problemas conocidos

Hay tres detalles del funcionamiento real del sistema que sacamos de los pendientes del informe principal pero que **todos en el grupo tenemos que conocer** por si aparecen durante la defensa o si el profesor pregunta.

### 1. El homing intermitente que vimos una vez (y qué hacer si pasa en vivo)
Durante las corridas de la campaña de validación, en una corrida parcial uno de los escenarios quedó esperando más de 4 minutos a que terminara el homing sin que terminara, y cuando repetimos la campaña tres veces seguidas no volvió a pasar nunca más.

- **¿Por qué puede pasar?** En el código del firmware cada eje tiene un tiempo máximo de **60 segundos simulados** para encontrar su imán: si no lo encuentra, aborta solo con error (`ERR 11`). Para que un homing siga «en curso» durante 4 minutos de reloj real tienen que pasar una de dos cosas: o bien la computadora se puso muy lenta y Webots estuvo corriendo muy por debajo de `1×` (entonces 55 segundos del reloj de Webots tardaron varios minutos reales), o bien se trabó el envío de estados de Webots.
- **¿Qué hacemos si en plena demo el homing parece quedarse colgado?**

> [!ATENCION] **Receta paso a paso en vivo si el homing se demora o se traba:**
> 1. **Mirar la velocidad arriba en Webots y el brazo 3D:** si el brazo se sigue moviendo despacito, está todo bien: solo hay que esperar a que termine la secuencia (tarda unos 55 s de tiempo simulado más 14 s para volver al reposo).
> 2. **Si no se mueve o aparece el cartel amarillo de «Sin estado de la UCI»:** apretar **`Esc` o el botón «Stop»** en la página. Eso frena el homing limpiamente y deja al robot listo para recibir órdenes.
> 3. **Volver a tocar «Homing…»:** gracias a cómo está hecho el firmware (D72), repetir el homing después de un Stop funciona sin problema.
> 4. **Si Webots quedó mudo:** tocar **«Recargar el mundo…»** abajo en el panel del Banco de ensayo, volver a tocar «Habilitar motores» y hacer homing.
> 5. **Plan B rápido si estamos cortos de tiempo en la exposición:** con el robot quieto en la pose inicial, tocar **«Referencia manual…»** (envía el comando `ZERO`). Declara referenciado al robot en el acto sin esperar los 55 segundos del barrido por sensores Hall y ya habilita todo el teach & play.

### 2. Por qué Webots siempre tiene que estar en `Real-time` (cerca de `1×`)
El reloj interno del firmware dentro de Webots avanza con el **tiempo simulado** (2 ms por cada paso de simulación), mientras que la URC corre en Python con el **reloj real de la computadora** y manda un `PING` cada 250 ms reales.
- Si alguien pone Webots en modo **Fast** (por ejemplo, a `4×` o `10×` de velocidad), para el firmware pasa 1 segundo simulado en apenas una fracción de segundo real, antes de que la URC llegue a mandarle el siguiente `PING`.
- Entonces el firmware cree que la URC se desconectó y **hace saltar el watchdog (`ERR 4`)**.
- **Regla para la demo:** dejar siempre Webots en modo **Real-time** (`≤ 1×`). Si en una computadora corre un poquito más lento (por ejemplo a `0,7×`), no pasa nada: al revés, recibe más `PING` por cada segundo simulado y el watchdog nunca salta.

### 3. Machete de textos viejos por si alguien lee otros archivos del repo
El proyecto fue evolucionando en etapas (primero una bala trazadora, después transmisión N1, después planta N2 y banco de ensayo). Si alguno lee documentos anteriores del repositorio, ojo con estos detalles donde **manda lo que hace hoy el código**:
- En algún párrafo viejo de `docs/UCI_WEBOTS.md` quedó escrito que al apagar los motores (`DISABLE`) el eje vertical `J4` no se cae: **hoy sí se cae** (lo modela la planta N2 y es justamente lo que mostramos en la falla **F2**).
- También decía que el mundo arrancaba clavado en `0°`: **hoy arranca con un pequeño desvío al azar de hasta ±10°** (para que el homing tenga que buscar de verdad los imanes y no arranque siempre en el mismo milímetro).
- La campaña final y las capturas se validaron completas también en **macOS (Apple Silicon)** con Webots R2025a, además de Windows 11.

---

## 9. Resumen rápido: dónde mirar si el profesor pide abrir un archivo

Si durante la defensa el profesor dice *«muéstrenme en el código dónde está hecho tal cosa»*, este es el mapa directo para ir sin dudar:

| Si pregunta por… | Qué archivo abrir | Qué mostrarle ahí adentro |
| --- | --- | --- |
| **La cinemática directa e inversa** | `scara/kinematics.py` | Es un archivo cortito (~130 líneas): arriba está `forward()` (las ecuaciones con `cos` y `sin`) y abajo `arm_angles()` e `inverse()` (el teorema del coseno y la elección del codo). |
| **El acople de las correas M1/M2 y el pasaje a pasos** | `firmware/transmission.h` | Mostrar la función `jointsToMotors()`: ahí se ve clarito en tres renglones cómo `M1` recibe los pasos de `J1` y `M2` recibe la suma `J1 + J2`, todo en cuentas enteras. |
| **Cómo el mismo firmware sirve para Arduino y Webots** | `firmware/hal.h` y `firmware/firmware.cpp` | Abrir `hal.h` (son 35 líneas) y mostrar los 6 métodos virtuales (`millis`, `readByte`, `writeLine`, `setDriversEnabled`, `step`, `hallActive`). |
| **Cómo se planifica una recta LIN o un PTP** | `urc/planner.py` | Mostrar `_trapezoid()` (la rampa de velocidad), `plan_ptp()` (que interpola articulaciones directo) y `plan_lin()` (que muestrea la recta cada 20 ms y llama a la inversa). |
| **El chequeo de choques antes de mover** | `scara/collisions.py` | Mostrar cómo arma las cajas del pedestal, el piso y la torre con el margen de seguridad y revisa cada pose. |
| **El modelo del motor paso a paso y la pérdida de pasos** | `webots/controllers/scara_uci/stepper.h` | Mostrar `advance()`: ahí está la curva `sen(...)` entre el ángulo del rotor y los pulsos del estator que hace que, si falta par, se atrase y pierda de a 4 pasos completos. |
| **Las pruebas y las conversaciones de conformidad** | `firmware/test/conversaciones/` y `tests/test_conformidad.py` | Abrir cualquier `.txt` (por ejemplo `jog_j1.txt` o `seg_interpolacion.txt`) para mostrar cómo se lee a simple vista el diálogo entre URC y UCI. |
