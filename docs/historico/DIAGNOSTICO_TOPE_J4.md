# Diagnóstico del sostén de J4 en el tope superior de carrera

Registro del **16/10/2026**, continuación de [colisiones y recorridos](COLISIONES_Y_RECORRIDOS.md). Se observó un problema adicional al ordenar exactamente **J4=120 mm**: la referencia terminaba, pero la posición simulada seguía oscilando. Este documento conserva el problema reproducido, las pruebas de una variable por vez, las fuentes examinadas y el criterio para elegir el paso numérico actual.

La conclusión corresponde al banco provisional y a una build concreta de Webots. No es una medición del diseño construido ni una declaración de error formal del simulador.

## 1. Qué significan consigna, llegada y tope

J4 es la articulación prismática: un valor positivo desplaza la herramienta hacia abajo. La carrera declarada sigue siendo de **0 a 120 mm**. El nombre «tope superior» se refiere aquí al valor máximo de la coordenada J4, aunque la herramienta descienda al aumentar esa coordenada.

El banco distingue tres valores:

| Dato | Procedencia | Significado |
|---|---|---|
| `commanded` | Perfil de trayectoria del controlador. | Posición que se pide al motor. |
| `estimated` | Referencia ideal del banco. | Sigue la consigna; no es un encoder ni una medición física. |
| `simulated` | Instrumentación interna de Webots. | Posición que resolvió el motor físico del simulador. |

El evento `completed` indica que terminó el perfil de consignas. No demuestra por sí solo que la posición simulada haya llegado o permanezca quieta. La prueba debe seguir observándola después de ese evento.

Hay además dos tipos de límites en Webots:

- El `LinearMotor` tiene `minPosition` y `maxPosition`: límites de los objetivos ordenados.
- El `SliderJoint` tiene `minStop` y `maxStop`: restricciones mecánicas del modelo físico, implementadas mediante topes ODE.

En el modelo inicial, el objetivo máximo y el tope mecánico coincidían en **0,120 m**. Esa coincidencia es válida según la documentación de límites, pero activa un tratamiento específico del motor al llegar al tope. Referencias: [JointParameters](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/jointparameters.md#joint-limits) y [Motor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/motor.md#motor-limits).

## 2. Cómo se reprodujo antes de modificar el modelo

Se creó [tools/check_joint_stops.py](../tools/check_joint_stops.py), reutilizando `Bench` de [tools/check_simulation.py](../tools/check_simulation.py). Cada escenario recarga un mundo de ensayo, habilita movimiento, ordena J4, espera `completed`, deja **1 s simulado** de asentamiento y observa **2 s simulados** de sostén.

Las dos condiciones exigidas son:

```text
máximo |J4_simulada − J4_objetivo| < 0,5 mm
máximo J4_simulada − mínimo J4_simulada < 0,5 mm
```

El primer criterio detecta una llegada equivocada; el segundo detecta una oscilación aunque la media quede cerca del destino. Se guardan resultados incluso cuando fallan. El script devuelve un código de salida no nulo si no cumple el criterio.

La primera reproducción usó una pose plegada lateralmente fuera del pedestal: J1=−60°, J2=120°, J3=0°. A J4=120 mm falló; a **119 mm y 0 mm** quedó estable dentro de aproximadamente **1,472 µm** de error en las muestras observadas. Se redujo después el caso a mover solo J4 desde la pose inicial J1=0°, J2=90°, J3=−90°. También falló. Por tanto, la reproducción mínima no necesita el movimiento previo de los brazos ni una carga añadida.

| Evidencia inicial | Error máximo observado | Amplitud observada | Resultado |
|---|---:|---:|---|
| [Pose plegada, J4=120 mm](../validation/j4_stops_before.json) | 10,816480 mm | 10,858873 mm | No cumple. |
| [Solo J4 desde pose inicial](../validation/j4_stops_initial_before.json) | 10,816500 mm | 10,858607 mm | No cumple. |
| [Pose inicial, cada paso físico de 16 ms](../validation/j4_stops_before_every_step.json) | 10,904553 mm | 10,997025 mm | No cumple. |

En la última reproducción, la posición varió entre **109,095447 y 120,092472 mm**, con la consigna constante en 120 mm. El agregado incluyó **125 pasos físicos** en los 2 s de observación. La consulta de contactos al finalizar devolvió cero contactos externos en esa instantánea; no debe confundirse con una comprobación continua de todos los contactos.

### Por qué se amplió la instrumentación

La telemetría normal emite estados aproximadamente cada **128 ms**. Sirve para operar y observar el banco, pero puede perder máximos de una oscilación entre dos mensajes.

Se agregó la orden de ensayo `inspect_j4_window` en [scara_bridge.py](../webots/controllers/scara_bridge/scara_bridge.py). Durante una ventana acotada, agrega la posición del sensor simulado **en cada paso físico**, conservando mínimo, máximo, error máximo, cantidad de muestras y si cambió la consigna. Al terminar envía un solo resumen `j4_window`; no necesita emitir un paquete TCP por paso.

Esta orden es instrumentación de lectura. No modifica consignas, fuerza, topes o referencia, ni utiliza la posición perfecta del simulador como realimentación del control. Las muestras periódicas de `state` también se guardan para contexto; el veredicto del ensayo definitivo utiliza el resumen de todos los pasos físicos.

La revisión de la instrumentación encontró dos riesgos y se corrigieron antes de guardar los resultados finales: las ventanas descartan la aprobación si hay lecturas no finitas (`invalid_samples`), y las muestras TCP se seleccionan desde el inicio de la petición y se contrastan con su `trial_id`. El tiempo simulado vuelve a cero al recargar: filtrar solo por tiempo podía mezclar muestras de ensayos anteriores. Las métricas de la ventana física no dependían de esa selección TCP, pero sus datos adjuntos también deben ser correctos.

## 3. Hipótesis y lectura de fuentes primarias

Después de obtener la reproducción fallida se consideraron tres hipótesis: tratamiento numérico del tope, parámetros del control PID y resolución temporal de 16 ms. Se ensayó una variable por vez en copias temporales; no se modificó el mundo activo del usuario para probarlas.

Se leyó el código público de **la misma revisión que identifica el ejecutable instalado**: `a459c02c7292d23ae437101c76111ec1668198c8`. Los enlaces siguientes fijan esa revisión del código para que la explicación sea reproducible.

La cadena relevante es:

1. [`WbMotor::setTargetPosition`](https://github.com/cyberbotics/webots/blob/a459c02c7292d23ae437101c76111ec1668198c8/src/webots/nodes/WbMotor.cpp#L352-L369) recorta un objetivo que excede los límites del motor. La igualdad con el límite está permitida.
2. [`WbMotor::computeCurrentDynamicVelocity`](https://github.com/cyberbotics/webots/blob/a459c02c7292d23ae437101c76111ec1668198c8/src/webots/nodes/WbMotor.cpp#L429-L465) calcula velocidad a partir del error PID, la limita por velocidad y aproxima esa velocidad según la aceleración disponible.
3. [`WbSliderJoint`](https://github.com/cyberbotics/webots/blob/a459c02c7292d23ae437101c76111ec1668198c8/src/webots/nodes/WbSliderJoint.cpp#L91-L103) transmite los topes a ODE, compensando el origen de posición. En [cada paso físico](https://github.com/cyberbotics/webots/blob/a459c02c7292d23ae437101c76111ec1668198c8/src/webots/nodes/WbSliderJoint.cpp#L228-L250), transmite también velocidad deseada y fuerza máxima disponible.
4. El [`SliderJoint` de ODE](https://github.com/cyberbotics/webots/blob/a459c02c7292d23ae437101c76111ec1668198c8/src/ode/ode/src/joints/slider.cpp#L119-L138) activa el límite cuando la posición es menor o igual al mínimo, o mayor o igual al máximo. La igualdad exacta ya pertenece a esa rama.
5. En [`dxJointLimitMotor::addLimot`](https://github.com/cyberbotics/webots/blob/a459c02c7292d23ae437101c76111ec1668198c8/src/ode/ode/src/joints/joint.cpp#L641-L727), un motor energizado situado en un límite recibe un tratamiento distinto del motor libre: se aplica directamente una fuerza de módulo `fmax`, con signo según el sentido ordenado, y la fila de restricción se utiliza para el tope. Al salir del tope se aplica un factor de aproximación, `fudge_factor`; su [valor inicial es 1](https://github.com/cyberbotics/webots/blob/a459c02c7292d23ae437101c76111ec1668198c8/src/ode/ode/src/joints/joint.cpp#L489-L501).

Esta rama introduce una discontinuidad concreta al activar el tope. La fuente y las pruebas apoyan que la interacción entre motor energizado, tope y paso temporal domina el problema observado. No bastan para declarar un defecto formal de Webots ni para trasladar el resultado a una máquina real.

El `bounce` inicial de este tope ODE es **cero**. El `bounce` de `ContactProperties` describe otra clase de contacto; cambiarlo no equivale a cambiar esta rama del límite articular. Los parámetros `stopERP` y `stopCFM` aparecen en `HingeJointParameters`, pero no se exponen en el `JointParameters` usado por este `SliderJoint`. En el [código ODE de esta revisión](https://github.com/cyberbotics/webots/blob/a459c02c7292d23ae437101c76111ec1668198c8/src/ode/ode/src/joints/joint.cpp#L489-L501), ERP y CFM del tope se inicializan desde los del mundo.

## 4. Experimentos controlados

Cada archivo `validation/j4_experiment_*.json` identifica la copia ejecutada, hashes de sus fuentes, script y `Bench`, versión de Webots, parámetros de observación, solicitudes y eventos. Las entradas verificadas permanecieron sin cambios durante sus respectivas corridas.

Los experimentos de esta tabla se midieron inicialmente con la telemetría periódica de aproximadamente **128 ms**. Sus valores son máximos y amplitudes de esas muestras; no se presentan como máximos de todos los pasos físicos. La verificación final repite la alternativa elegida con el agregado por paso.

| Única variable respecto del caso de 16 ms | Error observado | Amplitud observada | Evidencia |
|---|---:|---:|---|
| ERP global 0,05 | 10,808517 mm | 10,843243 mm | [No cumple](../validation/j4_experiment_world_erp005.json). |
| Ganancia P de J4 = 1 | 2,789625 mm | 2,406015 mm | [No cumple](../validation/j4_experiment_j4_pid1.json). |
| Ganancia P de J4 = 0,1 | 43,689381 mm | 7,721367 mm | [No cumple](../validation/j4_experiment_j4_pid01.json). |
| Aceleración interna de J4 sin límite | 10,432834 mm | 10,433025 mm | [No cumple](../validation/j4_experiment_j4_no_acceleration.json). |
| Sin amortiguamiento de J4 | 11,123474 mm | 11,340645 mm | [No cumple](../validation/j4_experiment_j4_no_damping.json). |
| Amortiguamiento de J4 = 2 | 8,945601 mm | 9,051792 mm | [No cumple](../validation/j4_experiment_j4_damping2.json). |
| Paso físico 8 ms | 2,715380 mm | 2,725553 mm | [No cumple](../validation/j4_experiment_step8.json). |
| Paso físico 4 ms | 0,400012 mm | 0,399988 mm | [Cumple en las muestras, cercano al umbral](../validation/j4_experiment_step4.json). |
| Paso físico 2 ms | 0,170369 mm | 0,170179 mm | [Cumple en las muestras](../validation/j4_experiment_step2.json). |
| Paso físico 1 ms | 0,035859 mm | 0,035756 mm | [Cumple en las muestras](../validation/j4_experiment_step1.json). |
| Solo `maxStop` = 121 mm; objetivo y límite motor = 120 mm | 0,0014715 mm | Menor que 0,000001 mm | [Cumple; prueba diagnóstica](../validation/j4_experiment_diagnostic_hard_stop121.json). |

Separar el objetivo del tope hizo que 120 mm fuera una posición interior y eliminó la oscilación grande en ese experimento. Esto refuerza la localización del problema en la activación del tope. **No se adoptó esa separación**: extender una restricción física solo para mejorar el cálculo cambiaría la carrera ante fallas, y falta evidencia mecánica que la justifique.

La serie 16/8/4/2/1 ms muestra una reducción marcada del residuo al refinar el paso. Se eligió **2 ms**: 4 ms quedaba cerca del criterio de 0,5 mm, mientras que 2 ms dejaba mayor margen en las muestras, sin llevar todo el banco a 1 ms. Es una elección numérica provisional sustentada por estas pruebas, no una frecuencia de hardware validada.

Se amplió después la comprobación de 2 ms a J4=120,119,0 y 60 mm, repitiendo 120 mm, en pose plegada y con carga de ensayo 0 y 0,25 kg. Los dos informes preliminares cumplen sus criterios: [sin carga](../validation/j4_experiment_step2_folded_full.json) y [con 0,25 kg](../validation/j4_experiment_step2_payload025.json). Conservan la limitación del muestreo periódico; no sustituyen la verificación final por paso físico.

## 5. Cambio adoptado y alcance

El paso pasó de **16 a 2 ms**. Se centralizó en `simulation.basic_time_step_ms` de [config/scara.json](../config/scara.json), y [tools/generate_world.py](../tools/generate_world.py) lo inserta en `WorldInfo.basicTimeStep` del mundo generado.

No se modificaron carrera, límites software ni topes mecánicos. Se conservaron masas, fuerzas máximas, geometría de colisión y los parámetros de control del modelo anterior. La instrumentación `inspect_j4_window` y el script de regresión dejan una forma de volver a medir el síntoma con futuras revisiones.

Pasar de 16 a 2 ms significa **ocho veces más pasos físicos por segundo simulado**. No permite afirmar que la ejecución tarde ocho veces más: el tiempo de pared depende también del motor físico, gráficos, comunicación y equipo. Tampoco implica que el modelo sea ocho veces más exacto.

La oscilación numérica residual no desaparece por definición. Se acepta únicamente si error y amplitud se mantienen por debajo del criterio declarado en el escenario ensayado. El margen geométrico de colisiones y esta tolerancia de llegada tienen funciones distintas; no constituyen una garantía conjunta de seguridad física.

### Verificación definitiva por paso físico

La reproducción de referencia con 16 ms y agregación en cada paso está guardada en [j4_stops_before_every_step.json](../validation/j4_stops_before_every_step.json). La verificación de la configuración adoptada debe guardar la misma medición a **cada paso de 2 ms**, incluir los escenarios y carga indicados, confirmar `command_changed=false` y comprobar hashes de la copia ejecutada.

La evidencia definitiva se organiza en tres informes, cada uno con destinos `[.12, .119, 0, .06, .12]` y ventanas de 2 s que incluyen al menos 1000 pasos de 2 ms:

- [Pose inicial, sin carga](../validation/j4_stops_after_initial.json).
- [Pose plegada, sin carga](../validation/j4_stops_after_folded.json).
- [Pose plegada, carga de 0,25 kg](../validation/j4_stops_after_payload025.json).

**Resultado final: 15/15 escenarios aprobados.** Cada ventana contiene exactamente **1000 pasos físicos**, ninguna lectura inválida y ninguna modificación de consigna. Se verificó la pertenencia de las muestras TCP a un único ensayo; cada informe confirma entradas sin cambios y restauración inicial.

| Escenario | Mayor error de posición | Mayor amplitud | Muestras físicas |
| --- | ---: | ---: | ---: |
| Pose inicial, sin carga | 0,173982 mm | 0,174011 mm | 5×1000 |
| Pose plegada, sin carga | 0,174002 mm | 0,174032 mm | 5×1000 |
| Pose plegada, carga 0,25 kg | 0,040870 mm | 0,040892 mm | 5×1000 |

La amplitud máxima pasó de **10,997025 a 0,174032 mm**, una reducción aproximada del **98,4 %** en las ventanas medidas. El error máximo pasó de **10,904553 a 0,174002 mm**. No se presenta el residuo como cero ni como precisión de un robot construido.

También aprobaron las [30 pruebas Python](../validation/j4_tests.json), los [cinco casos nativos de colisiones](../validation/collisions_native_j4.json), los [nueve escenarios de movimiento/fallas](../validation/simulation_j4.json) y las [330 colocaciones CAD en once estados](../validation/cad_motion_j4.json), con seis llegadas articulares. El caso de colisión con extremos libres volvió a **J4=120 mm**, retirando el uso temporal de 119 mm que aislaba la oscilación anterior. Los hashes definitivos se verifican en [el resumen del diagnóstico](../validation/j4_diagnosis.json).

Los informes exploratorios de la sección anterior no acreditan por sí solos la aprobación por paso físico. Al revisar la evidencia, comprobar `status`, `checks`, `per_physics_step_window`, `executed_inputs_unchanged` y `restored_initial_trial`; un `status=failed` o un error de limpieza no debe ocultarse.

### Costo de ejecución observado

La [sonda local de costo](../validation/j4_timestep_cost.json) midió tres ventanas de sostén de 5 s simulados por variante, en modo Fast. La mediana de tiempo de pared fue aproximadamente **0,069 s con 16 ms** y **0,692 s con 2 ms**, unas diez veces más en esa sonda. Con 2 ms las ventanas tardaron entre **0,523 y 0,856 s**: siguieron avanzando entre 5,8 y 9,6 veces más rápido que tiempo real en este equipo y condición. No es un benchmark general; hay variación por carga del equipo, gráficos y comunicación. No se garantizan esos valores en otros ordenadores.

## 6. Cómo repetir

Usar una copia recargable del proyecto, con Webots en reproducción y sin otros clientes TCP. Registrar el ejecutable y los hashes de esa copia. No hace falta conservar las rutas temporales ni los nombres de aplicación del diagnóstico original: los informes identifican lo que se ejecutó.

Desde la raíz, con el puerto del controlador de esa copia (9000 por defecto):

```sh
python3 tools/check_joint_stops.py --port 9000 --snapshot-root /ruta/copia-scara --webots-version "versión y build usadas" --pose initial --targets .12 --output /tmp/j4-minimo.json
python3 tools/check_joint_stops.py --port 9000 --snapshot-root /ruta/copia-scara --webots-version "versión y build usadas" --pose folded --targets .12 .119 0 .06 .12 --output /tmp/j4-sin-carga.json
python3 tools/check_joint_stops.py --port 9000 --snapshot-root /ruta/copia-scara --webots-version "versión y build usadas" --pose folded --targets .12 .119 0 .06 .12 --payload .25 --output /tmp/j4-carga025.json
```

Son ejecuciones consecutivas que recargan, habilitan y mueven. El script actual mide cada paso físico, intenta restaurar el ensayo y registra si pudo hacerlo. Después de un fallo de conexión o limpieza, revisar el estado antes de repetir.

Para reproducir el fallo a 16 ms, preparar otra copia con ese paso en configuración y regenerar el mundo antes de iniciarla, conservando la instrumentación actual. No regenerar una copia durante la medición. Para verificar la solución, usar el paso adoptado de 2 ms y los mismos criterios.

## 7. Preservación y límites del resultado

Se conservaron **29 archivos anteriores al cambio** en [validation/historico/antes_tope_j4_20261016](../validation/historico/antes_tope_j4_20261016/), con [snapshot.json](../validation/historico/antes_tope_j4_20261016/snapshot.json). Incluyen fuentes, configuración, mundo/PROTO, manifiesto, documentación e informes de la revisión de colisiones. Los resultados fallidos y los experimentos de este diagnóstico se conservan con nombres distintos.

Cambiar paso o instrumentación produce hashes distintos respecto de informes previos. Un informe aprobado anteriormente describe su versión; no valida automáticamente los nuevos archivos. La auditoría geométrica offline conserva su alcance, pero toda repetición nativa debe asociarse a las fuentes y build realmente ejecutadas.

Los informes guardan los hashes de las fuentes ejecutadas. Para probar una revisión nueva, recargar su mundo generado y comprobar su identidad; una copia temporal antigua no incorpora cambios automáticamente.

Quedan estos límites:

- **Caso específico.** Se diagnostica J4 cerca de su tope máximo, en las poses y cargas ensayadas. No se certifican todos los topes, fuerzas, cargas, trayectorias o plataformas.
- **Residuo numérico.** Refinar el paso reduce el error observado; no lo convierte en cero ni en una incertidumbre física conocida.
- **Ventana temporal finita.** La prueba mide 2 s tras 1 s de asentamiento; no demuestra estabilidad ilimitada ni un régimen de contacto distinto.
- **Contacto y control separados.** Cero contactos externos en una instantánea no desactiva las restricciones articulares internas de ODE.
- **Propiedades provisionales.** Masa, inercia, fuerza disponible, amortiguamiento y transmisión siguen sin validación material o de hardware.
- **Sin encoder real.** La instrumentación del simulador verifica el ensayo; no resuelve homing o pérdida de referencia del diseño.
- **Sin declaración de defecto externo.** La rama ODE leída y los experimentos explican una interacción reproducible del modelo. Un reporte formal a Webots requeriría un caso mínimo independiente y el análisis correspondiente.

Si una revisión futura modifica masas, esfuerzos, PID, topes, paso o build, repetir el caso mínimo y las regresiones pertinentes. Conservar tanto el resultado fallido anterior como la nueva evidencia permite distinguir una mejora medida de un cambio que solamente oculta el síntoma.
