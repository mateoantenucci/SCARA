# Sesión 2: choques y contactos internos

Revisión del 17/10/2026 sobre el modelo consolidado de **39 instancias**. Se amplió el auditor existente y se agregó una regresión de rechazos; no se cambiaron robot, contactos físicos, controlador ni propiedades.

## Qué quedó comprobado

La suite pasó **36/36 pruebas, sin omisiones**, con Python 3.12 y OCP en macOS. El auditor pasó sus 6 comprobaciones sobre **95 muestras nombradas y 78 poses distintas**: las repeticiones se conservan para seguir cada recorrido. Se registraron 741 pares: 583 entre cuerpos evaluados y 158 excluidos por pertenecer al mismo cuerpo rígido.

La tabla `pair_coverage` identifica cada par, grupos, exclusión, candidatos AABB y volúmenes positivos. Un par entre cuerpos con cero candidatos quedó separado por AABB en todas las muestras; no fue una exclusión. Los sólidos/STEP y transformaciones se verifican por hashes. La nueva polea de muñeca participa con su geometría válida.

Se hallaron **8 registros de intersección** en las muestras, correspondientes a estos pares: `0-Torre-1` / `Z-SoporteEfector-1`. Todas las poses con volumen positivo son rechazadas por el guard; no apareció un par interferente nuevo. Los registros repetidos no son nuevos choques independientes.

| Recorrido (9 muestras CAD por fila) | Intersecciones internas CAD (registros) | Extremos libres según guard sin carga | Guard continuo ida/vuelta, sin carga |
| --- | ---: | --- | --- |
| tower_positive | 2 | sí | rechaza / rechaza |
| tower_negative | 2 | sí | rechaza / rechaza |
| pedestal | 0 | sí | rechaza / rechaza |
| wrist_full_range | 0 | sí | acepta / acepta |
| vertical_full_range | 0 | sí | acepta / acepta |
| elbow_unfold | 0 | sí | acepta / acepta |

La columna CAD compara cuerpos del robot, no el pedestal ni el suelo: el cero de `pedestal` no significa ausencia de choque con el entorno. Su rechazo se conserva con el guard y con la prueba nativa de sesión 1.

Los cruces de torre de ambos signos de codo tienen extremos libres e interior invasivo. La nueva prueba llega por un desvío nominal libre a cada extremo, solicita el cruce en ambos sentidos y comprueba **cuatro rechazos Runtime que preservan posiciones, trayectoria, modo, fallas, carga, referencia y esfuerzo**. Es una prueba de software con referencia ideal; no una ejecución física.

Cada recorrido también registra el guard con cargas conocidas de 0 y 0,25 kg. La carga es el cubo reservado de 40 mm del modelo actual: no se agregó ni auditó un sólido CAD de carga. Los recorridos de muñeca cubren J3 de −150° a +150°; el vertical, J4 de 0 a 120 mm.

## Cajas y contactos físicos

En la pose inicial hay **23 pares de cajas con intersección y sin volumen CAD positivo**. Los tres pares añadidos por la nueva polea son:

| Par con la polea de muñeca | Volumen de intersección de cajas (cm³) | Volumen CAD (mm³) |
| --- | ---: | ---: |
| `R-Bancada-1` | 18.199648 | 0.000000 |
| `R-ContraBancada-1` | 18.199648 | 0.000000 |
| `Z-Piston-1` | 4.800000 | 0.000000 |

Estos volúmenes son de envolventes, no de material interferente. Volumen CAD cero tampoco prueba holgura positiva ni ausencia de contacto de superficie. No se activó `selfCollision`: las cajas de alojamientos y anillos siguen ocupando huecos. Un proxy anular aislado no habilitaría el resto del montaje y no cambia los contactos internos mientras esa opción está desactivada; no se introdujo una geometría más compleja sin beneficio demostrado.

Se reutilizan las [seis comprobaciones nativas de sesión 1](../collisions_native_remaining.json): todos los archivos `sources` del informe coinciden por SHA-256 con esta copia. No se repitieron en sesión 2; el código cambiado solo produce auditoría y pruebas. La regresión dinámica final pertenece a sesión 4.

## Límites y pendientes

El CAD se evaluó en muestras finitas, **sin barrido CAD continuo ni prueba de todo el espacio**. El guard sí acota continuamente la interpolación articular nominal, pero únicamente contra entorno y herramienta/carga frente a base fija: no se amplió su conjunto de pares. Usa margen de 1 mm y resolución de cota de 0,2 mm; la intersección BREP emplea umbral numérico de 0,001 mm³, que no es una holgura.

Quedan fuera las uniones dentro del mismo cuerpo, piezas omitidas, ejes/transmisión interior pendiente, correas, cables, pinza real y contactos físicos internos. La clasificación de montaje y exclusiones mecánicas corresponde a [sesión 1](../remaining_mounts.json); no se agregaron piezas ni se asumieron fijaciones. Cada incorporación futura exige repetir los pares y recorridos afectados. El profesor debe confirmar revisión mecánica, fijaciones y alcance de autocolisión/fallas exigidas.

## Evidencia y reproducción

- [Auditoría completa y fuentes](self_collisions.json).
- [Suite Python](python_tests.txt), [cajas de volumen conocido](known_solids_check.json) y [salida del auditor](audit.log).
- [Versión, entorno y reutilización nativa](execution.json).

Desde la raíz del proyecto, con el entorno OCP de `tools/requirements-cad.txt`, ejecutar `python tools/check_self_collisions.py --extended --output validation/sesion2/self_collisions.json`. Sin `--extended` conserva las 41 poses originales y añade la tabla de cobertura por par.
