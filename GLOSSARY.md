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
