# Cómo llega el movimiento de los motores a las articulaciones

El maestro identifica transmisiones nominales. En el camino nuevo (UCI en Webots), la planta simulada las implementa a nivel N1: el firmware da pasos a los motores y la planta los convierte en movimiento de las articulaciones ([abajo](#transmisión-n1-en-el-firmware-y-en-la-planta)). A nivel N2, cada motor tiene el par que le da su curva par–velocidad y pierde pasos si la carga o la aceleración lo superan ([N2](#par-de-los-motores-y-pérdida-de-pasos-n2)). En el banco viejo (`scara.wbt`), Webots todavía acciona directamente las cuatro articulaciones. Las poleas visuales no implementan por sí solas la transmisión ni cambian masas o esfuerzos.

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

**Límites (D45, valores de D76).** Se fijan por motor, en grados de su eje, con el margen de par de N2 ([abajo](#los-límites-con-n2)). Se derivan a las articulaciones por la transmisión:

| Motor | Velocidad | Aceleración | Qué limita |
| --- | --- | --- | --- |
| M1 | 360 °/s | 560 °/s² | \|ω_J1\| ≤ 90 °/s, \|α_J1\| ≤ 140 °/s² |
| M2 | 360 °/s | 560 °/s² | \|ω_J1 + ω_J2\| ≤ 90 °/s: el ángulo absoluto del antebrazo |
| M3 | 720 °/s | 1440 °/s² | \|ω_J3\| ≤ 180 °/s, \|α_J3\| ≤ 360 °/s² |
| M4 | 1800 °/s | 5400 °/s² | \|v_J4\| ≤ 40 mm/s, \|a_J4\| ≤ 120 mm/s² |

Con 1/8, la velocidad de M4 son 8000 pulsos/s (el Timer1 del UNO da hasta 10 000), la de M3, 3200, y la de M1 y M2, 1600. Por el acople, J2 no tiene un límite propio: si J1 gira a 90 °/s, J2 puede ir de 0 a −180 °/s. El jog (hasta 10 °/s o 10 mm/s, sin rampa) queda dentro de todos; el firmware lo verifica al compilar. El planificador PTP de la URC (#9) planifica dentro de estos límites por motor y de los de cada articulación (D53), y el firmware rechaza un segmento que los supere (`ERR 8`, D51); el LIN (#10) no planifica dentro de ellos: los verifica en cada segmento y rechaza el tramo antes de enviarlo (D54, D55). Las articulaciones de Webots tienen sus propios límites (`maxVelocity` en `SCARA.proto`, de `config/scara.json`), algo por encima de los que permiten los motores (J2, hasta el doble): así limitan los motores y Webots no satura una articulación, que atrasaría la física como si se perdieran pasos (D76).

**La planta simulada** ([`scara_uci.cpp`](../webots/controllers/scara_uci/scara_uci.cpp)) cuenta los pasos de cada motor, los convierte en ángulos con su propia copia de la mecánica y el microstepping de `config.h`, y lleva las articulaciones de Webots adonde están los rotores. Desde N2, cada rotor sigue a sus pasos con el par que tiene ([abajo](#par-de-los-motores-y-pérdida-de-pasos-n2)).

**Pruebas y evidencia.**

- [`firmware/test/transmision.cpp`](../firmware/test/transmision.cpp), compilada con los seis microsteppings del TB6600: una vuelta, ida y vuelta sin acumular redondeo, acople y pose de reposo exacta.
- Conversaciones [`jog_j1.txt`](../firmware/test/conversaciones/jog_j1.txt), [`jog_ejes.txt`](../firmware/test/conversaciones/jog_ejes.txt) y [`jog_motor.txt`](../firmware/test/conversaciones/jog_motor.txt): pasos emitidos por motor y posición estimada.
- [Ensayo en Webots](../validation/transmision/INFORME.md): la posición física simulada contra la estimada en el jog de J1–J4 y de M1, y la resolución de un paso.

## Par de los motores y pérdida de pasos (N2)

Issue #15, decisiones D64–D67 y [ADR 0006](adr/0006-modelo-de-motores-pasos-y-perdida-de-pasos.md). El modelo está en [`stepper.h`](../webots/controllers/scara_uci/stepper.h), sin Webots, y tiene sus pruebas en la PC ([`test/stepper.cpp`](../webots/controllers/scara_uci/test/stepper.cpp), `tests/test_planta.py`).

**Cómo funciona.** Cada pulso del firmware adelanta el campo del estator un micropaso. El rotor es una inercia (la suya más la de la carga, reflejada por la transmisión) que sigue al campo con la curva par–ángulo del motor híbrido:

```text
T = T(ω) · sen(π/2 · e / paso completo) + amortiguamiento
```

con `e` el atraso del rotor. El par máximo, con un paso completo de atraso, es el de la curva par–velocidad `T(ω)`. Si la carga o la aceleración piden más, el atraso crece; a dos pasos completos (medio ciclo eléctrico) el equilibrio se vuelve inestable y el rotor cae al siguiente, **cuatro pasos completos** más atrás. Así pierde pasos un paso a paso real, y el firmware no se entera: sigue contando los pulsos que emitió. La planta mueve las articulaciones con los rotores, así que «Simulado» se aparta de lo estimado en múltiplos de cuatro pasos completos.

- **Curva par–velocidad.** Plana hasta la velocidad de esquina, `V / (2 L I)` pasos completos por segundo, donde el driver todavía lleva la corriente a su valor en cada paso; más rápido, la inductancia la recorta y el par cae como `1/ω`. A baja velocidad, con micropasos, el par es 0,7 del de retención (corrientes senoidales: alrededor de 1/√2).
- **Carga.** M1 mueve el brazo y todo lo que cuelga del codo; M2, el ángulo absoluto del antebrazo con la muñeca; M3, la muñeca; M4, la herramienta. Las inercias se toman con el brazo estirado, la pose más exigente, sin los términos cruzados entre M1 y M2. La masa de la herramienta es `toolMass`: 0,15 kg del pistón y su soporte más la carga del banco de ensayo, hasta 5 kg en total (D85). J1–J3 giran en el plano y el peso no les hace par; en J4 el peso pasa por el ACME: pesa 1/η al subir y η' al bajar o quieto.
- **Topes.** Un tope mecánico frena el eje y el rotor. Si el firmware sigue dando pulsos, el motor pierde pasos contra el tope.
- **Sin modelo eléctrico (N3).** Corrientes, inductancia y resonancias quedan resumidas en la curva y en un amortiguamiento fijo (ζ = 0,6). El rotor se integra en 10 subpasos de 0,2 ms dentro de cada paso de 2 ms de Webots: el paso de la simulación no cambia.
- **En Webots.** Cada articulación va hacia la posición de los rotores con control de velocidad: la velocidad del rotor más la mitad de lo que le falta por paso, sin el límite de aceleración del proto (la dinámica ya la puso el rotor), y quedándose a 1/8 de paso completo de sus topes, porque un motor de ODE que empuja contra su tope vibra. Al volver la corriente, su fuerza sube en rampa durante 0,1 s: con J4 apoyado en su tope, ODE le aplica de más en el primer paso que el motor lo saca de ahí, y lo haría saltar milímetros. El par de las articulaciones de Webots se sube en el mundo de la UCI (campos `j1MaxTorque`… de `SCARA.proto`) para que no sea Webots el que limita; el mundo viejo conserva sus valores (D64).

**Parámetros y su fuente.** El maestro nombra los modelos, pero sus hojas de datos exactas no aparecieron, ni en esta búsqueda (31/10/2026) ni en la de la sesión 3 ([fuentes físicas](../validation/physics_sources.json)). Cada número es de la familia más cercana o un supuesto típico declarado:

| Parámetro | M1, M2 | M3 | M4 | Fuente o supuesto |
| --- | --- | --- | --- | --- |
| Modelo | Minebea 23KM-K381-P1 | Shinano Kenshi STP-42D221-03 | 42D265 | Maestro, p. 14 |
| Par de retención | 0,80 N·m | 0,31 N·m | 0,20 N·m | M1/M2: familia 23KM-K3 (cuerpo de 50 mm), bipolar 23KM-K349B, [catálogo Minebea 23KM-K](https://hallaweb.jlab.org/tech/Detectors/public_html/manuals/data_sheets-manuals/M-N/M/minebea/23km-k.shtml). M3: el STP-42D201-37 de la misma serie, 3200 g·cm ([Jameco](https://www.jameco.com/z/STP-42D201-37-Shinano-Kenshi-12-Volt-1-8-Step-Angle-Bipolar-Stepper-Motor_2158531.html)). M4: supuesto, NEMA 17 corto a 0,7 A |
| Inercia del rotor | 180 g·cm² | 54 g·cm² | 35 g·cm² | M1/M2: 23KM-K349B. M3 y M4: supuestos típicos de NEMA 17 de 40 y 34 mm |
| Inductancia por fase | 11,8 mH | 8 mH | 4 mH | M1/M2: 23KM-K349B. M3 y M4: supuestos |
| Corriente por fase | 1,4 A | 0,8 A | 0,7 A | M1/M2: 23KM-K349B. M3: supuesto. M4: maestro (1,9 V, 0,7 A) |
| Velocidad de esquina | 1308 °/s | 3375 °/s | 7714 °/s | Calculada con 24 V en los TB6600. Supuesto: el maestro da una fuente de 36 V; 24 V es más conservador |
| Par a baja velocidad | 0,7 × retención | ← | ← | Supuesto: micropasos con corrientes senoidales |
| Correa 2GT 4:1 | η = 0,95 | ← | — | Supuesto típico de correa dentada |
| ACME de 8 mm por vuelta | — | — | η = 0,67 al subir, 0,55 al bajar | Supuesto: ~7 mm de diámetro medio (hélice de 20°), tuerca de bronce, fricción 0,15. Reversible: sin corriente, J4 cae (D60) |
| Fricción seca | 3 % del par de retención | ← | ← | Supuesto |
| Masas e inercias | Brazo 0,3 kg, antebrazo 0,5 kg, muñeca 0,35 kg, herramienta `toolMass` | ← | ← | `config/scara.json` y `SCARA.proto` (provisionales) |
| Amortiguamiento | ζ = 0,6 | ← | ← | Supuesto del modelo, en lugar de N3 |

### Los límites con N2

Con la corriente nominal, el par que piden los límites (aceleración máxima a velocidad máxima, más el peso al subir y la fricción) queda por debajo del disponible. La tabla sale de `test/stepper.cpp --tabla`:

| Motor | Disponible a velocidad máxima | Pedido, herramienta sola (0,15 kg) | Margen | Pedido con 5 kg | Margen |
| --- | --- | --- | --- | --- | --- |
| M1 | 0,560 N·m | 0,069 N·m | 8,1× | 0,264 N·m | 2,1× |
| M2 | 0,560 N·m | 0,052 N·m | 10,7× | 0,247 N·m | 2,3× |
| M3 | 0,217 N·m | 0,010 N·m | 21× | 0,014 N·m | 16× |
| M4 | 0,140 N·m | 0,009 N·m | 15× | 0,100 N·m | 1,4× |

**Criterio (D76).** Al menos 2 veces de margen con 5 kg, lo usual al dimensionar un paso a paso en lazo abierto: cubre lo que el modelo no tiene (resonancias, N3) y la dispersión de los supuestos de la tabla de parámetros. M1 y M2 lo fijan; M3 tiene de sobra y lo limita la vista, no el par. M4 conserva su 1,4: lo pone el peso que sube por el ACME, no la aceleración, y su velocidad la limitan los pulsos del UNO. Todas las velocidades quedan por debajo de la de esquina, donde el par todavía no cae.

Las pruebas simulan además cada motor en sus límites y en el jog más rápido arrancando sin rampa, con 0,15 y 5 kg: ninguno pierde pasos y el atraso no llega a un paso completo. Con la corriente nominal, entonces, el robot no pierde pasos dentro de lo que planifica la URC: para provocarlos hace falta la falla F1. Hasta D76 los límites eran 4,5 veces más bajos en J1–J2 (D45, D66), elegidos antes de tener N2.

### F1: pérdida de pasos y `EV LOST`

**Provocarla (D67).** El banco de ensayo baja la corriente de un driver (`F1 m porcentaje`, de 10 a 100 %): es lo que pasa con un TB6600 regulado de menos. Con menos corriente, el motor tiene menos par a baja velocidad:

- **Por carga:** con el driver de M4 al 50 %, 5 kg se sostienen pero no suben: el motor pierde pasos de a cuatro mientras el firmware cree que J4 sube.
- **Por aceleración:** con el driver de M1 al 20 % y 5 kg, el jog de J1, que arranca sin rampa, pierde pasos al arrancar; con una rampa suave (136 °/s² en el eje), a la misma velocidad, no. Con la rampa del planificador (560 °/s², D76) también los pierde: un driver regulado de menos no da el par que suponen los límites.

**Detectarla (D65).** Al entrar en un imán con el eje referenciado, el firmware compara los pasos contados con los del flanco y envía `EV LOST j pasos` ([protocolo](PROTOCOLO_SCARA_1.md#pérdida-de-pasos)). La URC marca la referencia como dudosa hasta un homing. El banco muestra, además, los pasos que perdió cada motor según la planta desde el último homing de su eje o desde que recuperó la corriente: la verdad del simulador contra lo que el firmware descubrió (D86).

Evidencia: [ensayo de la pérdida de pasos en Webots](../validation/perdida_pasos/INFORME.md).

## Qué falta

Confirmar revisión, fijaciones, recorrido de correas, sentidos, ceros, códigos de motores, conexión y corriente de drivers, curvas torque–velocidad, fricción/eficiencia y sostén vertical. Con las hojas de datos exactas de los motores se reemplazan los supuestos de N2 (D64).

Respaldo: [fuentes de transmisión](../validation/transmission_sources.json), [montaje de salidas](../validation/pulley_mounts.json), [conteo geométrico](../validation/pulley_geometry.json), [montaje restante](../validation/remaining_mounts.json) y [nominales y fuentes físicas](../validation/physics_sources.json). Los ensayos del montaje están centralizados en [Validación](historico/VALIDACION_WEBOTS.md).
