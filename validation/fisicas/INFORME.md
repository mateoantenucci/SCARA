# Ensayos físicos de contacto y perturbación (C1, C2 y C3)

El banco de ensayo inyecta en caliente dos obstáculos estáticos (`OBSTACULO maceta X Y`, cilindro de ⌀120 × 150 mm sobre Z=0, y `OBSTACULO mesa X Y altura`, prisma de 160 × 160 mm con cara superior en `altura` mm, además de `OBSTACULO ninguno`) y pulsos horizontales de fuerza sobre el efector (`EMPUJON fuerza_cN direccion_grados duracion_ms`) por el canal `scara-sim/1`. Capturar puntos, planificar y comprobar choques en la URC no reciben esos obstáculos ni perturbaciones (ADR 0004).

El contacto físico se confirma comparando los puntos que Webots informa para el obstáculo y los cuerpos del robot. La reacción se aproxima por el esfuerzo contrario al del accionamiento durante ese contacto y se refleja al eje del motor por las poleas y el ACME. En el empujón en la punta (`C3`), la fuerza horizontal se aplica con `addForce` sobre `TOOL` y su par equivalente ($J^T F$) se refleja a `M1` y `M2` respetando el acople diferencial. El rotor queda ligado al mecanismo frenado o empujado y pierde múltiplos de 4 pasos completos cuando se supera el diente magnético mientras el firmware continúa contando pulsos sin enterarse (no hay encoders ni sensores de par). Al retirar el objeto o cesar el empujón, el mecanismo no salta ni recupera el tramo perdido: un robot sin encoder solo nota la discrepancia cuando vuelve a cruzar un Hall (`EV LOST`) o recupera su cero con homing.

El esfuerzo de cada articulación se limita por el par disponible de los motores, su corriente y la transmisión. A baja velocidad y corriente nominal, J4 dispone de unos 73,67 N de empuje axial por el ACME de 8 mm y eficiencia directa 0,67. El feedback de Webots mide esfuerzo del accionamiento (y en `C3` se le suma el par externo equivalente del empujón); no entrega el impulso instantáneo de choque ni permite afirmar la carga de rotura.

Los límites provisionales son cotas calculadas con N2, las aceleraciones máximas de D76 y 5 kg totales en el extremo: J1 1,943 N·m, J2 0,939 N·m, J3 0,052 N·m y J4 52,783 N. Incluyen la inercia reflejada y del rotor, la gravedad de J4, la fricción y la transmisión; J1 incluye el acople M1/M2. No son límites de resistencia medidos. Superarlos significa cargar más la articulación que en el uso normal adoptado.

## Escenarios ensayados en `validation/fisicas/ensayo_webots.py`

1. **C1 — Maceta a medio recorrido (#46):** toma los primeros dos puntos de `demo-barrido-ptp.json` (versión 2) y coloca la maceta en la posición del punto de herramienta a medio barrido (`X=375, Y=-217 mm`). Repite al 25 y al 100 % de velocidad y aceleración, registra pico/límite y pasos perdidos, retira la maceta sin pulsos nuevos, verifica que no salta, continúa con un tramo de 10° de J1 comprobando que conserva el corrimiento, busca un Hall para recibir `EV LOST` y termina con homing.
2. **C2 — J4 contra la mesa (#47):** desde `[0°, 0°, 0°, 10 mm]`, coloca `OBSTACULO mesa 500 0 40` bajo el soporte del efector y ordena bajar J4 hasta `110 mm`. El soporte apoya contra la mesa a `~54,8 mm`, `M4` pierde pasos de a 4 mientras el firmware llega a `110 mm` y el pico axial alcanza la capacidad directa del husillo (`73,67 N > 52,78 N`). Al retirar la mesa sin pulsos nuevos no hay salto; al ordenar subir a `90 mm` conserva el desfasaje de `-55,20 mm` y el homing final recupera la referencia.
3. **C3 — Empujón en la punta (#48):** con el robot quieto y energizado en `[0°, 0°, 0°, 60 mm]`, aplica primero `EMPUJON 500 90 500` (`5 N` hacia `+Y` durante `0,5 s`), que está por debajo del límite de retención en la punta (~8,88 N): el brazo cede décimas de grado dentro del diente magnético y vuelve solo a `[0°, 0°, 0°, 60 mm]` con `0` pasos perdidos. Luego aplica `EMPUJON 1200 90 500` (`12 N` durante `0,5 s`), que vence la retención de `M1` y `M2`, hace saltar múltiplos de 4 pasos completos y deja el brazo corrido sin `ERR` ni `EV LOST`. Un tramo PTP posterior conserva ese corrimiento y el homing final restablece el cero.

La tolerancia de liberación y continuidad es menos de dos pasos completos por motor (J2 admite el acople); después de homing, menos de un paso completo con el robot quieto. Para repetir: `python3 validation/campana/campana.py fisicas`.

## Resultados verificados del 06/11/2026

### C1: Maceta a medio recorrido

| Límites D76 | Pasos perdidos M1, M2, M3, M4 | Picos J1, J2, J3 (N·m), J4 (N) | Movimiento al retirar (centésimas) |
| --- | --- | --- | --- |
| 25 % velocidad y aceleración | 0, −84, −12, 0 | 4,257; 2,137; 0,825; 2,012 | 0, −1, 0, 0 |
| 100 % | −20, −100, 0, 0 | 4,256; 2,138; 0,825; 2,589 | 3, 2, 0, 0 |

El contacto afectó a `TOOL`. A velocidad baja cedieron M2 y M3 mientras J1 completó su giro; a velocidad plena también perdió M1. Los picos horizontales llegan a la capacidad de los accionamientos porque el contacto permanece mientras siguen llegando pulsos: reducir la velocidad no evita ese esfuerzo sostenido. El Hall de J2 informó −84 pasos en la corrida lenta y −80 en la rápida (diferencia entre M2 = −100 y M1 = −20, D67).

### C2: J4 contra la mesa (`X=500, Y=0, altura=40 mm`)

| Magnitud | Valor medido |
| --- | --- |
| Posición estimada / física tras el bloqueo | `110,00 mm` / `54,80 mm` |
| Pasos perdidos M1, M2, M3, M4 | `0, 0, 0, −1380` |
| Pico axial J4 / límite provisional D76 | `73,670 N` / `52,783 N` |
| Movimiento al retirar la mesa | `0, 0, 0, 0` centésimas |
| Corrimiento conservado al subir a `90 mm` | `−55,20 mm` (`34,80 mm` físicos) |
| Error tras homing de recuperación | `[0, 0, 0, −1]` centésimas |

### C3: Empujón horizontal en la punta (`90°`, `500 ms`)

| Empujón | Pasos perdidos M1, M2, M3, M4 | Picos J1, J2 (N·m) | Desvío físico tras el pulso (centésimas) | Desvío tras PTP a `[10°, −10°, 0°, 60 mm]` |
| --- | --- | --- | --- | --- |
| Suave (`5 N`) | `0, 0, 0, 0` | `6,039; 2,961` | `[0, 0, 0, 0]` | — |
| Fuerte (`12 N`) | `160, 172, 0, 0` | `10,256; 5,128` | `[7200, 540, 0, 0]` (`+72,00°, +5,40°`) | `[7201, 539, 0, 0]` (sin `EV LOST`) |

El homing posterior a `C3` dejó las cuatro articulaciones en `[0, 0, 0, −1]` centésimas respecto del reposo. Registro: [fisicas.log](../campana/registros/fisicas.log).
