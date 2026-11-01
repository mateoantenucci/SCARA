# SCARA académico

Vocabulario del robot y de su representación digital. Las decisiones pendientes sobre alcance y comportamiento se registran en el plan, no en este glosario.

## Lenguaje

**Gemelo digital SCARA**:
Simulación del diseño de este robot para estudiar su geometría, movimiento, dinámica y fallas. En el alcance actual no existe hardware con el que sincronizar o calibrar experimentalmente el modelo.

**Parámetro provisional**:
Propiedad del robot cuyo valor se adopta con una fuente o hipótesis explícita mientras falta su confirmación. No equivale a una medición física.

**Articulación J1**:
Giro entre la torre fija y el brazo.

**Articulación J2**:
Giro del antebrazo respecto del brazo.

**Articulación J3**:
Giro del conjunto vertical respecto del antebrazo. En este proyecto J3 es rotacional.

**Articulación J4**:
Desplazamiento vertical del pistón respecto de su cuerpo. En este proyecto J4 es prismática.

**Motor M1–M4**:
Actuador físico identificado por su transmisión hacia la articulación correspondiente. Su movimiento no coincide necesariamente con el desplazamiento de esa articulación.
_Evitar_: Usar motor y articulación como sinónimos.

**Cuerpo rígido**:
Conjunto de piezas que conserva sus posiciones relativas durante el movimiento representado.

**Configuración articular**:
Conjunto de posiciones de J1, J2, J3 y J4 que determina la configuración del SCARA.
_Evitar_: Llamar coordenadas cartesianas a estos valores.

**Punto de herramienta**:
Punto de referencia del extremo del robot cuya posición se desea controlar. El soporte y una herramienta añadida pueden tener puntos de referencia diferentes.

**Pose de herramienta**:
Posición y orientación del punto de herramienta respecto de una referencia definida. Pedir únicamente X,Y,Z especifica posición, pero no toda la pose.

**Posición ordenada**:
Objetivo de movimiento solicitado para una articulación o para el punto de herramienta.

**Posición estimada por pasos**:
Posición inferida a partir del desplazamiento esperado de los motores desde una referencia conocida. Puede diferir de la posición alcanzada cuando se pierden pasos o la referencia es incorrecta.

**Posición física simulada**:
Posición que efectivamente alcanza el modelo durante una simulación. Permite evaluar el error respecto de la posición ordenada y de la estimada.
_Evitar_: Confundirla con una medición disponible en el robot físico.

**Esfuerzo articular**:
Torque alrededor de una articulación rotacional o fuerza en la dirección de una articulación prismática.
_Evitar_: Usar indistintamente torque del motor, esfuerzo articular y carga útil.

**Carga útil**:
Objeto o masa transportada por el extremo del robot, con ubicación y distribución propias. Se distingue de la masa permanente del mecanismo y de la herramienta.

**Falla simulada**:
Alteración deliberada del comportamiento nominal del robot, sus observaciones o su comunicación para estudiar sus efectos y la respuesta del sistema.
_Evitar_: Llamar falla física a todo comando inválido o punto inalcanzable.

## Comunicación y control

**URC (Unidad Remota de Coordinación)**:
Aplicación de PC desde la que se opera el robot: muestra su estado, guarda trayectorias y envía órdenes. Es el «programa externo» de la consigna y es la misma con el robot real y con la simulación.
_Evitar_: Back, backend, servidor (su rol de red no lo define).

**UCI (Unidad de Control Incorporada)**:
Unidad que ejecuta el firmware del robot: el Arduino en el robot real, el controlador de Webots en la simulación.
_Evitar_: Placa, controlador (a secas).

**Firmware**:
Programa de la unidad de control del robot que interpreta el protocolo y comanda motores y sensores. Es el mismo código en el Arduino y dentro de la simulación.
_Evitar_: Controlador (ambiguo con el controlador de Webots).

**Controlador de Webots**:
Programa que Webots ejecuta para animar el robot simulado. Aloja el firmware y la planta simulada.
_Evitar_: Llamarlo firmware o programa externo.

**Planta simulada**:
Parte del controlador de Webots que reemplaza al hardware que comanda el firmware: drivers, motores, transmisión, sensores Hall y botonera.
_Evitar_: Simulador (a secas), mundo.

**Protocolo de comunicación**:
Contrato de mensajes de texto entre la URC y el firmware de la UCI, transportado por TCP/IP o por un puerto serie puenteado a TCP.
_Evitar_: API.

**Canal de instrumentación**:
Conexión que solo existe en la simulación, por la que la URC lee la verdad del simulador y controla fallas, carga y recarga del mundo.
_Evitar_: Telemetría (el estado que informa la UCI es otra cosa).

**Conversación de conformidad**:
Archivo con un intercambio de ejemplo de `scara/1` (lo que envía la URC y lo que tiene que responder la UCI) que se ejecuta como prueba contra el firmware y contra la URC. Es la definición ejecutable del protocolo.
_Evitar_: Vector de prueba, caso de prueba (a secas).

**Banco de ensayo**:
Panel de la URC que solo aparece con la simulación: muestra la posición física simulada junto a la estimada por pasos y permite inyectar fallas, cambiar la carga y recargar el mundo. Lo alimenta el canal de instrumentación.
_Evitar_: Llamarlo panel de control del robot (el robot real no lo tiene).

**API de Webots**:
Funciones con las que el controlador de Webots lee sensores y ordena motores del mundo simulado. No comunica a la URC con el robot.
_Evitar_: Decir que la URC se comunica con Webots "por API".

## Operación

**Jog**:
Movimiento manual del robot mientras el operador mantiene apretada una tecla o un botón de la URC.
_Evitar_: PPM, perillas (no hay panel físico de posición).

**Jog cartesiano**:
Jog en el que el operador mueve el punto de herramienta en X, Y, Z o rumbo y la URC resuelve las articulaciones.

**Jog articular**:
Jog en el que el operador mueve una articulación por vez, sin que cambien las demás.

**Jog verificado**:
Jog con el robot referenciado, en segmentos que la URC planifica y verifica antes de enviarlos: recorrido, alcance, configuración del codo y choques. Frena antes de un límite en vez de llegar a él.

**Jog por motor**:
Modo de prueba del jog en el que cada tecla mueve un solo motor, sin compensar el acople. Mover M1 solo cambia J1 y J2, y no el rumbo de la herramienta.
_Evitar_: Jog articular (en el jog articular el firmware compensa el acople).

**Punto de trayectoria**:
Pose del robot capturada durante el jog. Registra dónde está el robot, no el camino por el que llegó.
_Evitar_: Waypoint, posición grabada.

**Trayectoria**:
Secuencia ordenada y con nombre de puntos de trayectoria, que la URC guarda y puede reproducir.
_Evitar_: Programa, rutina.

**Tramo**:
Movimiento entre dos puntos consecutivos de una trayectoria. Su camino lo calcula la URC según su tipo, LIN o PTP.

**Segmento**:
Porción de unos 20 ms de un tramo que la URC envía al firmware con `SEG`: una configuración articular de destino y su duración. El firmware los encola y los ejecuta con su reloj, interpolando lineal en articulaciones.
_Evitar_: Paso (es el pulso de un motor), punto (es de la trayectoria).

**Tramo de aproximación**:
Tramo PTP que la URC calcula al iniciar la reproducción, desde la pose actual del robot hasta el primer punto. No forma parte de la trayectoria guardada.

**Tramo LIN**:
Tramo en el que el punto de herramienta recorre una línea recta.
_Evitar_: Movimiento lineal (ambiguo con J4).

**Tramo PTP**:
Tramo en el que todas las articulaciones se interpolan en simultáneo y llegan a la vez. El camino del extremo no es recto.
_Evitar_: Movimiento libre.

**Homing**:
Búsqueda automática de la referencia de cada articulación con sus sensores Hall.
_Evitar_: Reset, reinicio de ensayo, recarga del mundo.

**Referencia manual**:
Declarar como referencia la pose actual, después de llevar el robot con jog hasta marcas conocidas.

**Robot referenciado**:
Robot cuyas articulaciones tienen una referencia válida desde el último homing o referencia manual, sin reinicio de la UCI desde entonces.

**Referencia dudosa**:
Referencia de una articulación después de que el firmware detectó, al cruzar su Hall, que la posición estimada por pasos no coincidía con la del sensor. El robot sigue referenciado, pero conviene volver a hacer homing.
_Evitar_: Referencia perdida (eso es sin referencia, después de un reinicio de la UCI o de cortar la corriente).

**Pose de reposo**:
Pose definida, con el brazo estirado, en la que se deja el robot al apagarlo y desde la que arranca el homing sin riesgo de choque.
_Evitar_: Home, cero, pose segura, parking (la referencia que encuentra el homing es otra pose).

**Configuración del codo**:
Lado hacia el que está doblado el codo; se nombra por el signo de J2. Una misma posición del extremo puede alcanzarse con las dos configuraciones.
_Evitar_: Codo arriba / codo abajo (es terminología de brazos verticales, aunque el maestro la usa).

**Pérdida de pasos**:
Diferencia entre los pasos que el firmware ordenó a un motor y los que el motor efectivamente dio, por falta de par.
_Evitar_: Desfase, error de encoder (no hay encoders).
