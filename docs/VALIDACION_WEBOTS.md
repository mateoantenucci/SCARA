# Evidencia y alcance de las pruebas

Esta es la referencia para distinguir resultados comprobados, informes históricos y cambios todavía sin validación consolidada. La [guía de comprensión](PROCESO_Y_ARCHIVOS.md) explica los conceptos y el [README](../README.md) permite operar el banco.

## Revisión consolidada del 17/10/2026

El [consolidado de la ronda A, sesiones 7–9](../validation/sesion9/consolidado.json) centraliza la observación de la demo y el precálculo actualizado, sus identidades, revisión y límites. El [registro anterior de las seis sesiones](../validation/sesion6/consolidado.json) conserva la evidencia histórica y las fuentes reutilizadas. El montaje visual tiene **39 instancias**, seis rodamientos simplificados y tres poleas de salida, incluida la de muñeca desde el ensamble R. La física y el protocolo `scara-dev/1` siguen provisionales; el montaje no representa todavía todo el diseño.

| Comprobación vigente | Resultado y evidencia |
| --- | --- |
| Software con entorno CAD | **36/36 aprobadas, sin omisiones**, macOS 27.0.1 arm64, Python 3.12.14 con OCP. [Sesión 2](../validation/sesion2/execution.json). El pase de 35 de sesión 1 corresponde a su suite anterior. |
| Colocaciones en Webots | 11 instantáneas, 429 comparaciones y seis llegadas articulares aprobadas sobre 39 instancias. [Sesión 1](../validation/cad_motion_remaining.json). |
| Contactos y rechazo | Seis comprobaciones nativas sobre 39 cajas, una por instancia; [informe](../validation/collisions_native_remaining.json). Sesión 2 reutilizó esa evidencia tras comprobar identidad de sus 13 fuentes, sin repetirla. |
| Interferencias CAD entre cuerpos | **95 muestras / 78 poses**, 741 pares registrados: 583 evaluados entre cuerpos y 158 excluidos dentro del mismo cuerpo. Ocho registros representan cuatro poses invasivas conocidas, todas rechazadas; no aparecieron pares invasivos nuevos. 23 solapes iniciales de cajas sin volumen CAD positivo. [Auditoría y límites](../validation/sesion2/INFORME.md). |
| Comportamiento final | **16 controles nativos aprobados** sobre la copia mínima de 39 instancias, Python 3.9.6 estándar: nueve de movimiento/fallas, seis de detención/transporte/Hall/esfuerzo y uno para la demo de rechazo soporte/torre. [Ejecución final](../validation/sesion4/final39_execution.json). No fue QA visual nueva del navegador. |
| Reproducción de software | En macOS 27.0.1 arm64 con Python **3.9.6 y 3.15.0**, y Linux arm64 en contenedor con Python **3.12.15**: cada entorno descubrió 36 pruebas, aprobó 33 y omitió tres por falta de OCP; además aprobó cinco controles HTTP sin Webots. [Registro de portabilidad](../validation/sesion5/portability.json). El [ZIP ejecutable](../validation/sesion5/SCARA-ejecucion.zip) contiene 52 archivos y 35 mallas, con LEEME; no incluye originales CAD, tests ni scripts de validación. |
| Demo renderizada del paquete final | Ocho pasos observados en Chrome 155 y Webots R2025b nightly del 14/10/2026, macOS 27.0.1 arm64, sobre extracción limpia del ZIP. Conexión/habilitación, movimiento/llegada separada de `completed`, rechazo local antes de TCP sin mover, Hall/bloqueo, limpieza sin rearme, rearme explícito y final `STOPPED`, carga 0 kg. [Informe y capturas](../validation/sesion7/INFORME.md), [revisión independiente](../validation/sesion9/review7.json). No hubo cambios de producto ni reconstrucción del ZIP. |
| Entornos aún no ejecutados | **Windows y Webots en Linux pendientes**. El contenedor Linux prueba software sin escritorio ni simulador. Las comprobaciones HTTP no equivalen a observar el navegador. |
| Montaje y fuentes físicas | [Diagnóstico mecánico](../validation/remaining_mounts.json) y [fuentes físicas](../validation/physics_sources.json). Se recuperaron nominales de materiales/impresión y se calcularon relaciones; **no se modificaron masa, inercia ni esfuerzo activos**. |

El auditor CAD usa muestras finitas; no barre continuamente todos los pares ni prueba todo el espacio. El guard continuo conserva la cobertura de entorno y herramienta/carga frente a base fija. `selfCollision` permanece desactivado: las envolventes ocupan huecos y producirían contactos internos falsos. Volumen CAD cero no acredita una holgura positiva.

El [precálculo geométrico actual](../cad/propiedades/propiedades_geometricas_39.json) cubre **39/39 instancias**, 49 tipos y 51 sólidos. La única alta respecto de las 38 es la polea de muñeca: delta aditivo de 9,166651648 cm³; las 38 ocurrencias y los cuatro grupos no afectados se conservaron. [Contraste y suma BREP de muñeca](../validation/sesion8/INFORME.md), [revisión independiente](../validation/sesion9/review8.json). El [informe de 38](../cad/propiedades/propiedades_geometricas.json) sigue intacto como histórico. Ninguna corrida se aplicó como física material. La revisión mecánica, los datos físicos y el alcance docente pendientes están en [Consultas](DATOS_PARA_EL_PROFESOR.md).

La identidad del manifiesto CAD, PROTO, configuración y demás fuentes está registrada por SHA-256 en el [consolidado de ronda A](../validation/sesion9/consolidado.json), su antecedente de seis sesiones y cada ejecución. Toda incorporación posterior exige revisar qué ensayos afecta.

## Ensayos anteriores que conservan valor técnico

| Revisión / informe | Qué comprobó | Cómo interpretarlo |
| --- | --- | --- |
| [transmission.json](../validation/transmission.json), 17/10 | Montaje previo de 38 instancias: 34 pruebas, 418 comparaciones y seis comprobaciones nativas. | Antecedente de las dos salidas de brazo/codo; no sustituye los ensayos de la adición de muñeca. |
| [simulation.json](../validation/simulation.json), 14/10 | Nueve casos con CAD parcial: pose, XYZ/rumbo, rechazo, Hall/rearme, masa/inercia/esfuerzo, pérdida de fuerza, sobrecarga, desconexión y recarga. | Es la ejecución de aquella versión. No se volvió a ejecutar toda esta batería al ampliar cada montaje posterior. |
| [client_native.json](../validation/client_native.json), 14/10 | Navegador→HTTP→Python→TCP→Webots: dos destinos, respuesta final visible y reinicio con nueva identidad de ensayo. | No acredita todos los botones ni su repetición en cada montaje posterior. |
| [j4_diagnosis.json](../validation/j4_diagnosis.json), 16/10 | Reproducción de oscilación y ajuste del paso físico de 16 a 2 ms; regresiones de esa revisión. | Razón del paso adoptado y caso que debe repetirse si cambian parámetros relevantes. |
| [j4_stops_after_initial.json](../validation/j4_stops_after_initial.json), [folded](../validation/j4_stops_after_folded.json), [payload025](../validation/j4_stops_after_payload025.json) | 15 escenarios de sostén; 1000 muestras por paso físico en cada ventana de 2 s. | Mayor error 0,174002 mm y amplitud 0,174032 mm, inferiores al criterio de 0,5 mm. No es precisión real del robot. |
| [cad_recovery.json](../validation/cad_recovery.json), 16/10 | Recuperación de dos carreteles B y soporte; regresiones geométricas y nativas de esa etapa. | Respalda esa corrección y sus derivados. El detalle está en [recuperación](RECUPERACION_GEOMETRIAS.md). |
| [wrist_bearings.json](../validation/wrist_bearings.json), 17/10 | Corrección de tapa e incorporación de rodamientos de muñeca. | Respaldo de la decisión mecánica del prototipo; ver [montaje](MONTAJE_Y_AUTOCOLISIONES.md). |

Ejemplos de coherencia de la batería del 14/10: con 0,40 kg móviles el sostén fue 3,924 N, coherente con `m·g`. Con esfuerzo nulo J4 cayó unos 60 mm. Con sobrecarga añadida de 1 kg también cedió, conservando el límite provisional de 8 N. El error nominal del extremo fue de unos 0,025 mm **dentro del simulador**. Estos números no certifican carga, exactitud ni comportamiento de hardware.

## Qué significa aprobar una prueba

- **Colocación CAD:** las piezas siguen la pertenencia declarada al mover cada articulación. No verifica por sí sola mates, fijaciones, fases o materiales reales.
- **Llegada:** después de terminar las consignas se espera asentamiento y se compara la posición simulada con el objetivo. `completed` por sí solo no demuestra llegada.
- **Física:** se comprueba que Webots aplica masa, centro, inercia y esfuerzo configurados, y que carga/gravedad producen efectos coherentes. Si los parámetros son provisionales, el resultado conserva ese alcance.
- **Colisiones:** detectar y rechazar una pose invasiva es un resultado correcto. Un informe aprobado con intersecciones de ensayo no dice que todo el espacio de trabajo esté libre.
- **Fallas:** se comprueba la inyección y la reacción del banco. El conocimiento de lo inyectado no demuestra detección autónoma por sensores del robot.

Las ejecuciones nativas guardan versión de Webots, entradas y hashes, solicitudes, eventos, tolerancias y resultado. La compilación usada en los informes citados es Webots R2025b nightly, build identificada como `a459c02c7292d23ae437101c76111ec1668198c8`, en macOS Apple Silicon. Los encabezados R2025a de los mundos/PROTO identifican el formato de archivo, no el ejecutable ensayado.

Las tolerancias de referencia de las llegadas son 0,005 rad en giro, 0,0005 m en J4, 0,001 m en XYZ y 0,02 rad en rumbo; cada informe declara su criterio y su tiempo de asentamiento. Son criterios de prueba, no prestaciones mecánicas. La telemetría normal, aproximadamente cada 128 ms simulados, no mide máximos continuos; la sonda J4 agrega lecturas de cada paso físico.

## Cómo repetir sin reemplazar evidencia anterior

Las pruebas de software no requieren Webots. Usar el **proyecto fuente completo**: el paquete mínimo de ejecución no contiene tests ni herramientas de validación. Una ejecución con cero pruebas descubiertas no acredita la suite:

```sh
python3 -m unittest discover -v
```

Sin OCP se omiten tres pruebas de kernel CAD. Con el entorno definido en `tools/requirements-cad.txt` se ejecutan también esas tres. El total depende de los tests presentes en la revisión; registrar omisiones, errores y fallos.

Para ensayos nativos, usar una copia cuyo estado se pueda recargar, Webots en reproducción y un solo cliente TCP. Desconectar la interfaz antes: estos programas mueven, inyectan fallas y recargan el mundo. Desde la raíz del proyecto:

```sh
python3 tools/check_simulation.py --webots-version "versión y build usadas" --output /tmp/scara-simulation-repeticion.json
python3 tools/check_cad_motion.py --webots-version "versión y build usadas" --output /tmp/scara-cad-repeticion.json
python3 tools/check_collisions_native.py --webots-version "versión y build usadas" --output /tmp/scara-contactos-repeticion.json
```

Ejecutarlos consecutivamente. En Windows usar `python`; con puertos alternativos, consultar `--help`. Para comprobar identidad de una copia, los ensayos que lo admiten usan `--snapshot-root`. Los predeterminados pueden sobrescribir informes de `validation/`; por eso los ejemplos eligen otras salidas. Para J4 ver el [procedimiento específico](DIAGNOSTICO_TOPE_J4.md).

Para repetir el recorrido del navegador, seguir la primera prueba del [README](../README.md), comparando también la posición simulada después del fin de consignas. Fast modifica la relación con el tiempo de pared, sin cambiar el paso físico configurado. Pausar Webots detiene también el procesamiento TCP.

## Límites abiertos

Faltan revisión mecánica oficial, montaje/transmisión completos, física material, protocolo definitivo, homing, conteo y pérdida de pasos, atasco, desprendimiento y otros pares de autocolisión. J1 no ofrece feedback de torque con esta base fija: se publica `null`. Los Hall usan regiones lógicas provisionales. No hay detección de corte silencioso de red por un mecanismo de vivacidad propio.

La ejecución nativa Windows/Linux y otras compilaciones requiere ensayos propios. No se declara validación contra hardware inexistente. Cambiar código, CAD, configuración o ejecutable exige revisar qué pruebas se deben repetir.

## Compatibilidad del ejecutable

En los ensayos guardados se usó R2025b nightly por un problema de arranque de R2025a en macOS 27, conservado como antecedente en el [issue 6976](https://github.com/cyberbotics/webots/issues/6976) y [cambio 7032](https://github.com/cyberbotics/webots/pull/7032). Es información del entorno ensayado: no identifica automáticamente la aplicación instalada ni establece cuál es la última versión disponible. Para repetir, registrar la versión real del ejecutable utilizado y revisar sus propios resultados.
