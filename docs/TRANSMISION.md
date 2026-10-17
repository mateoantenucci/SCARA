# Cómo llega el movimiento de los motores a las articulaciones

El maestro identifica transmisiones nominales. Webots todavía acciona directamente las cuatro articulaciones: las poleas visuales no implementan por sí solas esa transmisión ni cambian masas o esfuerzos.

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

## Qué falta

Confirmar revisión, fijaciones, recorrido de correas, sentidos, ceros, códigos de motores, conexión y corriente de drivers, curvas torque–velocidad, fricción/eficiencia y sostén vertical. Después se podrá calcular y ensayar la relación completa motor→articulación y, si lo exige la entrega, conteo y pérdida de pasos.

Respaldo: [fuentes de transmisión](../validation/transmission_sources.json), [montaje de salidas](../validation/pulley_mounts.json), [conteo geométrico](../validation/pulley_geometry.json), [montaje restante](../validation/remaining_mounts.json) y [nominales y fuentes físicas](../validation/physics_sources.json). Los ensayos del montaje están centralizados en [Validación](VALIDACION_WEBOTS.md).
