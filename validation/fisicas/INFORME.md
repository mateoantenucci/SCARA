# Contacto con obstáculos de ensayo (C1)

La maceta es un cilindro estático de ⌀120 × 150 mm, colocado en X,Y sobre Z=0. No tiene `Physics`: permanece fija. Se crea y retira en caliente mediante `OBSTACULO maceta X Y` y `OBSTACULO ninguno` del canal `scara-sim/1`. Capturar puntos, planificar y comprobar choques no reciben ese obstáculo (ADR 0004).

El contacto físico se confirma comparando los puntos que Webots informa para el obstáculo y los cuerpos del robot. La reacción se aproxima por el esfuerzo contrario al del accionamiento durante ese contacto; se refleja al eje del motor por las poleas y el ACME. El rotor queda ligado al mecanismo frenado y pierde ciclos eléctricos mientras el firmware continúa contando pulsos. Al retirar el objeto conserva los pasos perdidos. El banco muestra el contacto y el esfuerzo sin frenar: un robot sin encoder ni sensor de contacto solo puede notar la discrepancia cuando vuelve a cruzar un Hall.

El esfuerzo de cada articulación se limita por el par disponible de los motores, su corriente y la transmisión. A baja velocidad y corriente nominal, J4 dispone de unos 73,67 N por el ACME de 8 mm y eficiencia 0,67. El feedback de Webots mide esfuerzo del accionamiento; no entrega el impulso directo del contacto. No permite afirmar la carga de rotura.

Los límites provisionales son cotas calculadas con N2, las aceleraciones máximas de D76 y 5 kg totales en el extremo: J1 1,943 N·m, J2 0,939 N·m, J3 0,052 N·m y J4 52,783 N. Incluyen la inercia reflejada y del rotor, la gravedad de J4, la fricción y la transmisión; J1 incluye el acople M1/M2. No son límites de resistencia medidos. Superarlos significa cargar más la articulación que en el uso normal adoptado.

El escenario usa los primeros dos puntos de `demo-barrido-ptp.json`, en formato versión 2, y coloca la maceta en la posición del punto de herramienta a medio barrido. Repite al 25 y al 100 % de velocidad y aceleración (el ensayo reduce explícitamente ambas, porque el porcentaje de velocidad de la URC conserva la aceleración nominal), registra pico/límite y pasos perdidos, retira la maceta sin pulsos nuevos y continúa con un tramo de 10° de J1. Comprueba que no recupera el recorrido perdido, busca un Hall para recibir `EV LOST` y termina con homing. La tolerancia de liberación y continuidad es menos de dos pasos completos por motor (J2 admite el acople); después de homing, menos de un paso completo con el robot quieto. La tolerancia se contrasta durante la corrida y queda identificada junto a su registro.

Para repetir: `python3 validation/campana/campana.py fisicas`. La campaña completa guarda versión, huellas y registro en `validation/campana/`. La corrida individual del 06/11/2026 terminó con ENSAYO OK; la campaña completa vuelve a ejecutarla junto con la regresión y registra su versión.


## Resultado individual del 06/11/2026

| Límites D76 | Pasos perdidos M1, M2, M3, M4 | Picos J1, J2, J3 (N·m), J4 (N) | Movimiento al retirar (centésimas) |
| --- | --- | --- | --- |
| 25 % velocidad y aceleración | 0, −84, −12, 0 | 4,257; 2,137; 0,825; 2,012 | −1, 0, 0, 0 |
| 100 % | −20, −100, 0, 0 | 4,256; 2,138; 0,825; 2,589 | −2, −1, 0, 0 |

El contacto afectó a TOOL. A velocidad baja cedieron M2 y M3 mientras J1 completó su giro; a velocidad plena también perdió M1. Los picos horizontales llegan a la capacidad de los accionamientos porque el contacto permanece mientras siguen llegando pulsos: reducir la velocidad no evita ese esfuerzo sostenido. Se superó el límite provisional de uso normal, sin inferir rotura.

El Hall de J2 informó −84 pasos en la corrida lenta y −80 en la rápida. El segundo valor es la diferencia entre M2 (−100) y M1 (−20), porque el Hall de J2 mide el ángulo relativo y el otro motor todavía no cruzó su Hall (D67). El homing dejó las cuatro articulaciones dentro de un paso completo de la estimada en las dos corridas. Registro: [fisicas.log](../campana/registros/fisicas.log).
