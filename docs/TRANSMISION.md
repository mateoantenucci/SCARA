# Cómo llega el movimiento de los motores a las articulaciones

El maestro identifica transmisiones nominales. En el camino nuevo (UCI en Webots), la planta simulada las implementa a nivel N1: el firmware da pasos a los motores y la planta los convierte en movimiento de las articulaciones ([abajo](#transmisión-n1-en-el-firmware-y-en-la-planta)). En el banco viejo (`scara.wbt`), Webots todavía acciona directamente las cuatro articulaciones. Las poleas visuales no implementan por sí solas la transmisión ni cambian masas o esfuerzos.

| Motor | Qué mueve | Transmisión indicada en el maestro |
| --- | --- | --- |
| M1 | Brazo | 20→80 dientes: cuatro vueltas de motor por una de salida. |
| M2 | Antebrazo, desde la base | 20→80 y una etapa 60→60 hacia el codo; interviene además el giro del brazo. |
| M3 | Giro de muñeca | 20→80 dientes: reducción 4:1. |
| M4 | Desplazamiento vertical | Tornillo ACME con avance de 8 mm por vuelta. |

Fuente: [maestro, pp. 10–14](../00-SCARA-Master.pdf#page=10). Los datos son de diseño y no certifican rendimiento bajo carga ni revisión vigente de los controladores.

## Qué se comprobó en el CAD

Se incorporaron como visuales las salidas de brazo y codo y la polea de muñeca, con colocaciones sustentadas. La elección entre las poses R y B de muñeca y las incompatibilidades pendientes están en [Montaje](MONTAJE_Y_AUTOCOLISIONES.md).

La polea grande de muñeca tiene **80 dientes contados en la geometría**, coincidentes con el maestro. El plano suelto la describe como de 60: falta confirmar revisión. Las otras siete geometrías de polea son lisas y no permiten contar dientes; sus nombres y el maestro son referencias documentales.

M1 y M2 están en la base y utilizan ejes concéntricos. El codo gira respecto de un brazo que también gira. Por eso no alcanza con dividir el giro de M2 por cuatro para obtener J2: hay que derivar el acoplamiento, los signos y los ceros desde el montaje confirmado.

Los seis carreteles de canal anular son piezas diferentes de las poleas dentadas 2GT. Su posible función de guiar cables se infiere de su forma; no se presenta como una función explícitamente confirmada por el maestro.

## Cálculos nominales y qué permiten concluir

El maestro indica 400 impulsos por vuelta de motor. Son valores de configuración nominal, sin modelado de impulsos en el banco actual.

| Caso | Resultado nominal |
| --- | --- |
| Motor de 400 impulsos/vuelta con reducción 4:1 | 1600 impulsos/vuelta de salida: 0,225°/impulso o 4,444… impulsos/°. |
| Recorrido de 270° en esa etapa | 1200 impulsos. |
| Recorrido de 300° | 1333⅓ impulsos teóricos; 1333 producen 299,925° y 1334, 300,150°. No se ordena una fracción de impulso. |
| ACME de 8 mm/vuelta a 400 impulsos/vuelta | 0,020 mm/impulso; 50 impulsos/mm; 6000 impulsos para 120 mm. |
| Hipótesis de motor a 1000 rpm y reducción 4:1 | 250 rpm de salida = 1500°/s, idealmente y sin acreditar movimiento bajo carga. |
| Hipótesis de M4 a 1000 rpm | 133,333… mm/s nominales. |

Para M2, los números de salida de la etapa aislada no resuelven su movimiento articular general. Incremento de orden tampoco significa precisión o repetibilidad.

La tabla de velocidad del maestro p. 8 mezcla 4,44°/s y 266 rpm: no son equivalentes. 4,44°/s son 0,74 rpm; 266 rpm son 1596°/s. El valor 4,444… sí aparece al calcular impulsos por grado. No se copió esa celda como velocidad máxima del simulador.

Para una etapa aislada, `T_salida = 4 η T_motor`. Para el tornillo, con avance de 0,008 m/vuelta, `F = 2π η T_tornillo / 0,008`. La eficiencia η y los torques reales están por fundamentar; estas relaciones no producen por sí solas una fuerza disponible ni prueban autobloqueo sin alimentación. En M2 tampoco justifican esfuerzos articulares independientes sin resolver el acoplamiento.

## Transmisión N1 en el firmware y en la planta

Issue #7, decisiones D44–D46. Ecuaciones, con θ el ángulo del eje de cada motor y los ceros en la pose de reposo:

```text
J1 = θM1 / 4        J2 = (θM2 − θM1) / 4        J3 = θM3 / 4        J4 = 8 mm · vueltas de M4
```

**Un solo microstepping.** [`firmware/config.h`](../firmware/config.h) fija `SCARA_MICROSTEPS` (8 por defecto, D9) y los 200 pasos por vuelta de los motores. Lo incluyen el núcleo, la capa del Arduino UNO y la planta de Webots (D44). Cambiarlo ahí, y en las llaves DIP de los TB6600, es todo lo que hace falta: el protocolo habla en unidades articulares (ADR 0003).

**El firmware** ([`firmware/transmission.h`](../firmware/transmission.h)) convierte unidades del protocolo a pasos con una fracción entera reducida, calculada al compilar:

| Microstepping | Pasos por vuelta de motor | J1–J3: pasos por centésima de grado | J4: pasos por centésima de mm | Un paso en J1–J3 | Un paso en J4 |
| --- | --- | --- | --- | --- | --- |
| 1/2 | 400 | 2/45 | 1/2 | 0,225° | 0,02 mm |
| **1/8** | **1600** | **8/45** | **2/1** | **0,05625°** | **0,005 mm** |
| 1/16 | 3200 | 16/45 | 4/1 | 0,028125° | 0,0025 mm |

- **Acople.** Para mover solo J1, el firmware da los mismos pasos a M1 y a M2. M2 sigue al ángulo absoluto del antebrazo, J1 + J2. La posición estimada sale de J2 = (θM2 − θM1)/4.
- **Jog por motor (D46).** `JOG M1 + vel` mueve solo M1: el brazo gira, el antebrazo conserva su orientación, J2 cambia al revés que J1 y el rumbo J1 + J2 + J3 no cambia.
- **J4 es más fino que el protocolo.** Desde 1/8, un paso de M4 (0,005 mm) es menor que la centésima de mm: dos pasos seguidos pueden informarse con el mismo valor en `S`.

**Límites (D45).** Se fijan por motor, en grados de su eje, como parámetro provisional hasta tener las curvas de par (N2, #15). Se derivan a las articulaciones por la transmisión:

| Motor | Velocidad | Aceleración | Qué limita |
| --- | --- | --- | --- |
| M1 | 80 °/s | 136 °/s² | \|ω_J1\| ≤ 20 °/s, \|α_J1\| ≤ 34 °/s² |
| M2 | 80 °/s | 136 °/s² | \|ω_J1 + ω_J2\| ≤ 20 °/s: el ángulo absoluto del antebrazo |
| M3 | 112 °/s | 204 °/s² | \|ω_J3\| ≤ 28 °/s, \|α_J3\| ≤ 51 °/s² |
| M4 | 1350 °/s | 2700 °/s² | \|v_J4\| ≤ 30 mm/s, \|a_J4\| ≤ 60 mm/s² |

Con 1/8, la velocidad de M4 son 6000 pulsos/s y la de M1 y M2, 356 pulsos/s. Por el acople, J2 no tiene un límite propio: si J1 gira a 20 °/s, J2 puede ir de 0 a −40 °/s. El jog (hasta 10 °/s o 10 mm/s, sin rampa) queda dentro de todos; el firmware lo verifica al compilar. El planificador PTP de la URC (#9) planifica dentro de estos límites por motor y de los de cada articulación (D53), y el firmware rechaza un segmento que los supere (`ERR 8`, D51); el LIN (#10) tiene que hacer lo mismo. **Ojo:** las articulaciones de Webots tienen sus propios límites (`maxVelocity` en `SCARA.proto`, de `config/scara.json`: 0,35 rad/s en J2). Si un tramo pide J2 por encima de 20 °/s, aunque M2 lo permita, Webots lo satura y la física se atrasa como si se perdieran pasos. Hasta ajustar el modelo, los tramos respetan también esos límites por articulación.

**La planta simulada** ([`scara_uci.cpp`](../webots/controllers/scara_uci/scara_uci.cpp)) cuenta los pasos de cada motor, los convierte en ángulos con su propia copia de la mecánica y el microstepping de `config.h`, y ordena esas posiciones a las articulaciones de Webots. Todavía no pierde pasos (N2, #15). Webots lleva cada articulación a esa posición con un control de posición de velocidad, aceleración y par limitados: durante el movimiento la posición física simulada va unas centésimas detrás de la estimada, y se asienta en una fracción de segundo al frenar.

**Pruebas y evidencia.**

- [`firmware/test/transmision.cpp`](../firmware/test/transmision.cpp), compilada con los seis microsteppings del TB6600: una vuelta, ida y vuelta sin acumular redondeo, acople y pose de reposo exacta.
- Conversaciones [`jog_j1.txt`](../firmware/test/conversaciones/jog_j1.txt), [`jog_ejes.txt`](../firmware/test/conversaciones/jog_ejes.txt) y [`jog_motor.txt`](../firmware/test/conversaciones/jog_motor.txt): pasos emitidos por motor y posición estimada.
- [Ensayo en Webots](../validation/transmision/INFORME.md): la posición física simulada contra la estimada en el jog de J1–J4 y de M1, y la resolución de un paso.

## Qué falta

Confirmar revisión, fijaciones, recorrido de correas, sentidos, ceros, códigos de motores, conexión y corriente de drivers, curvas torque–velocidad, fricción/eficiencia y sostén vertical. Con las curvas se reemplazan los límites provisionales de D45 y se modela la pérdida de pasos (N2, #15).

Respaldo: [fuentes de transmisión](../validation/transmission_sources.json), [montaje de salidas](../validation/pulley_mounts.json), [conteo geométrico](../validation/pulley_geometry.json), [montaje restante](../validation/remaining_mounts.json) y [nominales y fuentes físicas](../validation/physics_sources.json). Los ensayos del montaje están centralizados en [Validación](VALIDACION_WEBOTS.md).
