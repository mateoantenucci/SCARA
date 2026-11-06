---
status: accepted
---

# Modelo de motores: pasos y pérdida de pasos, sin modelo eléctrico

La planta simulada representa los motores en dos niveles. Primero, pasos discretos con microstepping y transmisión, incluido el acople M1/M2. Segundo, par limitado según la velocidad: una carga o aceleración excesiva produce pérdida de pasos que el firmware no advierte. Se deja fuera el modelo eléctrico (corrientes, inductancia, resonancias): exige datos que el maestro no trae y pasos de simulación mucho más chicos, y no cambia lo que se quiere mostrar. Decidido el 29/10/2026.


## Contacto del entorno (spec #45, D89–D90)

Cuando un obstáculo de ensayo toca un cuerpo móvil, el esfuerzo de reacción entra al rotor como una carga externa. Se refleja por trabajo virtual: M1 recibe (Q1−Q2)/(4η), M2 recibe Q2/(4η), M3 recibe Q3/(4η), y M4 recibe F4·avance/(2πη). La posición y velocidad físicas atan el rotor al mecanismo durante el contacto, conservando los ciclos eléctricos perdidos. Quitar el objeto no reinicia el rotor: los pulsos nuevos siguen desde su posición corrida.

El esfuerzo disponible de las articulaciones viene de la curva par–velocidad, la corriente del driver y la transmisión. Con la corriente nominal y en reposo, M4 dispone de aproximadamente 73,7 N por el ACME de 8 mm y η=0,67. Los máximos del PROTO son techos de implementación de Webots, no la resistencia del motor.

La reacción es una aproximación: el [feedback de Motor de Webots](https://github.com/cyberbotics/webots/blob/master/docs/reference/motor.md) mide el esfuerzo que aplica el accionamiento, no la fuerza directa de cada contacto. Se usa su opuesto únicamente mientras los puntos de contacto confirman que el cuerpo toca el obstáculo. El pico mostrado es por lo tanto el esfuerzo articular del accionamiento, no el impulso de impacto ni una predicción de rotura. El límite provisional compara con el uso normal de D76 a 5 kg; faltan materiales y ensayos para calcular rotura.

El firmware y la planificación no reciben el contacto. El banco lo muestra sin frenar el robot; los Hall siguen siendo la única detección automática de la pérdida de pasos. La validación integrada de esta ampliación está pendiente.


Para medir J1, su articulación cuelga de un soporte numérico sin geometría bajo la base estática. Según la [semántica de Physics en Webots](https://github.com/cyberbotics/webots/blob/master/docs/reference/physics.md#how-to-use-physics-nodes), ese soporte se fija al entorno mediante una unión ODE fija. Su masa de 1 kg e inercia diagonal de 0,01 kg·m² solo hacen posible el feedback: no agregan una masa móvil ni cambian CAD o colisiones. La base permanece sin Physics. Sin ese soporte, Webots rechaza el feedback de J1 por no tener un cuerpo físico padre.


La capacidad de J1 no se implementa como una suma independiente de dos máximos. El accionamiento ODE de J1 se limita por M1 y el de J2 por M2; el esfuerzo de M2 sobre el brazo se suma cancelando la reacción del motor relativo de J2 sobre ARM. Esto representa a M2 fijo en la bancada y respeta Q1=4η(τ1+τ2), Q2=4ητ2. La cancelación usa el feedback del tick anterior (2 ms): es una aproximación numérica declarada, verificada con la campaña sin obstáculos. El banco muestra Q1 total, mientras el techo de cada accionamiento sigue perteneciendo a un solo motor.

Solo se reancla un rotor si el cuerpo tocado está en su cadena y el mecanismo se aparta de él más de un paso completo. Los ejes que siguen normalmente no reciben la reacción de otros ejes. En un eje retenido, el esfuerzo observado ya contiene la carga normal; se descuenta la contribución de gravedad y fricción del modelo antes de sumarlo como carga externa. Así un contacto horizontal del pistón no agrega una segunda vez el peso de J4.
