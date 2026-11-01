# Fallas y validación del SCARA

Especificación del comportamiento esperado y de los ensayos de fallas. Los resultados ejecutados y sus versiones se consultan en [Validación](VALIDACION_WEBOTS.md); un escenario propuesto no se considera implementado por estar descrito aquí.

El alcance es una simulación del diseño: no existe un SCARA físico disponible. La validación compara geometría, cálculos y comportamiento reproducible. Los valores provisionales y los resultados simulados conservan esa condición; no se presentan como mediciones de hardware.

## Un motor que no funciona y un brazo retirado son casos diferentes

Un motor sin esfuerzo sigue teniendo masa y sigue conectado a su transmisión. El brazo puede permanecer, moverse por inercia o ceder bajo una carga. Una articulación trabada conserva las piezas, pero restringe su movimiento relativo. Retirar un motor cambia la distribución de masa; retirar o desprender un brazo también cambia las conexiones mecánicas. Ocultar una malla solo cambia la imagen.

La primera batería cubre fallas de actuador, sensor y comunicación con el mecanismo armado. La retirada y el desprendimiento se reservan para un ensayo estructural posterior; no hacen falta para demostrar que un motor dejó de actuar.

## Reglas comunes y observación

- El movimiento de referencia es suave, punto a punto, hacia XYZ. La orientación es opcional; al omitirla se conserva la orientación del extremo respecto del mundo cuando el movimiento sea admisible. No se exige trayectoria cartesiana recta.
- Un objetivo inválido se rechaza antes de iniciar movimiento. Es una validación de entrada, no una falla física.
- Una falla notificada o la pérdida de la conexión solicita detención con la física activa y bloquea nuevas órdenes de movimiento hasta un rearme explícito. Reconectar, quitar la inyección y rearmar son acciones distintas. Ninguna reanuda automáticamente la trayectoria interrumpida.
- Detener significa cancelar la trayectoria y solicitar una detención realizable con los actuadores disponibles. No significa fijar posiciones por software, poner a cero la velocidad física instantáneamente ni garantizar inmovilidad cuando falta esfuerzo para sostener un eje.
- Los nombres del catálogo son identificadores de ensayos internos, no comandos ni mensajes del protocolo del profesor. Su contrato definitivo sigue pendiente.

El banco registra por separado estas magnitudes:

| Magnitud | Procedencia y uso |
| --- | --- |
| Objetivo y referencia de trayectoria | Posición solicitada y consigna que corresponde al instante del ensayo. No prueban que se haya alcanzado. |
| Posición física simulada | Instrumentación de Webots para evaluar el ensayo. Debe identificarse como observación interna, no como encoder disponible en el robot. |
| Posición estimada por pasos | Estimación del diseño físico, cuando se implemente. No sustituirla silenciosamente por la posición física simulada. |
| Hall nominal y Hall entregado al controlador | Estado que correspondería a la posición y geometría del imán/sensor, y estado luego de aplicar una posible falla. Las regiones de activación reales siguen pendientes. |
| Esfuerzo disponible y esfuerzo del actuador | Límite impuesto y feedback aproximado del motor simulado, con sus unidades. No equivalen a masa de carga, fuerza de contacto ni torque de placa del motor físico. |
| Falla inyectada y falla detectada | El banco sabe qué inyectó. Un controlador solo detecta aquello que permiten sus entradas y reglas implementadas. Registrar ambos eventos por separado. |

El diseño documentado no tiene encoders. No se promete detectar un atasco, una sobrecarga o pasos perdidos mediante un error de posición que el hardware no podría observar. Una inyección conocida por el sistema puede solicitar la detención, pero eso debe rotularse como aviso del banco de fallas. Si después se añade un detector basado en Hall, tiempos o corriente, se documentarán sus supuestos y limitaciones.

`Motor.getTorqueFeedback()` y `getForceFeedback()` estiman el esfuerzo que usa el actuador en su grado de libertad; no proporcionan todas las fuerzas externas ni el esfuerzo impuesto directamente con `setTorque`/`setForce`. Los sensores de posición usados para ensayos son instrumentación simulada. Fuentes: [Motor R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/motor.md), [PositionSensor R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/positionsensor.md).

## Preparación reproducible

Antes de cada escenario guardar la versión de Webots, revisión del proyecto, parámetros físicos y sus fuentes, configuración inicial de las cuatro articulaciones, carga y su posición, paso de simulación, límites de velocidad/aceleración/esfuerzo, orden de referencia y momento de inyección. Expresar valores en m, rad, kg, N y N·m; la interfaz puede mostrar otras unidades si la conversión es explícita.

Cada escenario empieza con una recarga limpia y una ejecución nominal de control con iguales parámetros. Se inyecta una sola falla a la vez. Elegir una pose inicial válida, alejada de topes y singularidades, sin penetraciones entre colisiones y con espacio para la caída de J4. Registrar el vector inicial concreto; una descripción como «brazo a mitad de recorrido» no basta para repetirlo.

Las inyecciones físicas se programan por tiempo de simulación o por un evento registrado. El reloj de pared se usa para observar conexiones y sus tiempos de espera. Una pausa de Webots no equivale a tiempo de movimiento transcurrido. Registrar semilla cuando se incorpore ruido. Fuentes: [Robot R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/robot.md), [controladores R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/controller-programming.md).

Las tolerancias de pose, detención y repetición pertenecen a la configuración del ensayo y deben escribirse antes de ejecutarlo. Aún no son prestaciones verificadas del robot. Registrar el resultado como aprobado, fallido o pendiente, acompañado por la evidencia; que el mundo abra sin errores no aprueba los ensayos dinámicos.

## Estado de implementación

| Escenario | Estado |
| --- | --- |
| F01: pérdida o reducción de esfuerzo | Implementado; reducción retenida y referencia invalidada. Para recuperarla el banco exige recargar el ensayo. |
| F02: articulación trabada | Propuesto; falta una restricción física y su prueba. |
| F03: Hall fijo | Implementado como inyección lógica; montaje real de imán/sensor y homing pendientes. |
| F04: cierre TCP reconocido | Implementado; cancela trayectoria y exige rearme. Interrupción silenciosa sin cierre reconocido pendiente. |
| F05: sobrecarga conocida | Implementado con masa conocida y esfuerzo provisional; no es un detector físico de carga. |
| Retirada o desprendimiento | Propuesto; no se implementó ruptura estructural. |

La restauración descrita en el catálogo es el criterio general. En el banco actual, pérdida de esfuerzo y sobrecarga requieren `reset_trial`: limpiar el aviso no recupera fuerza ni referencia. Hall puede limpiarse y luego rearmarse. El [README](../README.md) indica los pasos de operación.

## Catálogo inicial

### F01. Pérdida o reducción del esfuerzo de un actuador

- **Inicial:** mecanismo completo, parámetros nominales, pose segura y trayectoria o sostén de una carga registrados. Para observar una caída por gravedad elegir J4; para un eje horizontal, el efecto depende de la inercia y las cargas.
- **Inyección:** en un único eje multiplicar el esfuerzo nominal disponible por un factor registrado: `0` para pérdida total o, como caso de prueba, `0.5` para reducción al 50 %. Mantener el límite reducido durante la detención; no restaurarlo como efecto secundario de frenar.
- **Observables:** esfuerzo disponible antes/después, posición física y velocidad, error contra referencia, estado de detención y eventual referencia perdida. El Hall puede no cambiar; eso no descarta la falla. El banco conoce la inyección sin convertir ese conocimiento en diagnóstico por encoder.
- **Esperado:** la limitación realmente afecta al actuador. Con esfuerzo nulo el motor no sostiene ni impulsa; puede haber deriva o caída. Una reducción no garantiza que el eje falle en toda carga. La trayectoria se cancela al notificarse la falla y no se anuncia llegada por el solo transcurso del tiempo.
- **Restauración:** quitar la inyección, recuperar límites nominales y comprobar estabilidad. Si la estimación perdió su referencia, restablecerla con un procedimiento declarado; luego rearmar y enviar una orden nueva. Para repetir el ensayo, recargar su estado inicial.

La implementación actual usa `setAvailableTorque` en ejes rotacionales y `setAvailableForce` en J4, conservando el control de posición. Cambiar a control por torque no es necesario. Fuente: [Motor R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/motor.md).

### F02. Articulación trabada

- **Inicial:** una articulación identificada, pose de atasco concreta y cargas acotadas. Conservar masas y conexiones. La prueba de bloqueo mecánico requiere una restricción física validada.
- **Inyección:** introducir la restricción que impide movimiento relativo. Un aumento finito de fricción puede representar un atasco bajo una carga máxima declarada; si solo se añade amortiguamiento, identificarlo como articulación frenada, no bloqueo perfecto.
- **Observables:** desplazamiento residual, velocidad, esfuerzo del actuador y reacción de los demás ejes; estado informado por el controlador y origen de esa información.
- **Esperado:** el eje restringido no sigue la trayectoria, dentro de la tolerancia definida para el ensayo; los demás cuerpos reaccionan de acuerdo con las conexiones y la física. El sistema solicita detención al recibir aviso de falla. Sin sensores adecuados no se atribuye detección autónoma del atasco.
- **Restauración:** eliminar la restricción en reposo, restaurar fricción/topes originales y restablecer referencia si corresponde. Exigir rearme y orden nueva. Recargar el mundo para repetir y evitar energía o contactos residuales.

Este escenario queda pendiente de implementación mecánica. `Brake.setDampingConstant` añade resistencia proporcional a velocidad: no crea por sí solo un cierre rígido y puede permitir movimiento bajo carga. No usar un coeficiente arbitrariamente enorme para fingir un bloqueo. `Solid.locked` solo impide mover con el mouse. Los topes `minStop`/`maxStop` tienen reglas sobre el cero; ambos en cero los desactivan, por lo que no constituyen una receta general de bloqueo en cualquier pose. Fuentes: [Brake R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/brake.md), [JointParameters R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/jointparameters.md), [Solid R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/solid.md).

Si se requiere un cierre rígido, evaluar un vínculo explícito y probar que solo elimina el movimiento relativo buscado. `Connector.lock()` permite mantener distancia y orientación entre dos conectores compatibles y alineados; preparar ese mecanismo exige un ensayo propio, no una llamada genérica para trabar cualquier articulación. Fuente: [Connector R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/connector.md).

### F03. Hall atascado activo o inactivo

- **Inicial:** sensor y articulación identificados; dos configuraciones registradas en lados distintos de la región de activación nominal. Si esa región aún es provisional, indicarlo.
- **Inyección:** fijar la salida lógica entregada al controlador en activo y, en otra ejecución, en inactivo; no modificar la pose física para producir el fallo. Comprobar el mapeo nominal/inyección con muestras del banco, sin requerir que el robot continúe una trayectoria después de la detención.
- **Observables:** Hall nominal interno, Hall entregado, configuración física, estado de referencia y fuente del aviso de falla. No confundir la posición interna del simulador con un sensor añadido al diseño.
- **Esperado:** la salida permanece fija aunque la muestra física corresponda al estado contrario. Una falla notificada solicita detención. Cuando exista homing, la búsqueda debe estar acotada por recorrido y tiempo, contemplar sensor activo al inicio y no declarar referencia recuperada por una lectura fija.
- **Restauración:** volver a la salida nominal, verificar ambos estados y repetir el establecimiento de referencia cuando se implemente. Rearmar explícitamente antes de una nueva orden.

La generación de la señal Hall, su geometría y el homing deben declararse como implementados o pendientes por separado. Esta falla no consiste en desactivar un `PositionSensor` y llamarlo sensor Hall.

### F04. Corte de comunicación

- **Inicial:** cliente conectado y movimiento válido en curso, con secuencia y tiempos registrados.
- **Inyección:** cerrar la conexión desde el cliente; repetir durante reposo. Una interrupción silenciosa de la red es otro caso y requiere el mecanismo de vivacidad/tiempo de espera que admita el contrato definitivo.
- **Observables:** cierre o error de socket, momento de su reconocimiento, último comando aceptado, cola pendiente, referencia cancelada, movimiento físico posterior y bloqueo del rearme. Separar tiempos de pared y simulados.
- **Esperado:** al reconocer la pérdida se cancela la trayectoria y se solicita detención; el bucle de Webots continúa. No garantizar detección inmediata de un cable desconectado sin una política implementada de tiempo de espera. Al reconectar se informa el estado actual, se descartan fragmentos de mensajes de la sesión anterior y no se repiten movimientos pendientes. Reconectar no rearma.
- **Restauración:** restablecer la conexión, verificar estado y referencia y ejecutar rearme explícito. La siguiente trayectoria necesita una orden nueva.

TCP no conserva fronteras de mensajes. Los casos de fragmentación, concatenación y mensajes truncados se ensayan con la delimitación del profesor; no se prescribe aquí un protocolo alternativo. Fuente: [Python Socket HOWTO](https://docs.python.org/3/howto/sockets.html).

### F05. Sobrecarga

- **Inicial:** dos ejecuciones equivalentes con carga nominal y carga aumentada; definir masa, ubicación, centro de masa e inercia de cada carga, además de los límites del actuador. Comenzar con ambas cargas ya configuradas, evitando añadir masa instantáneamente a una pieza en movimiento.
- **Inyección:** aumentar una carga útil explícita en una ejecución separada; no reducir esfuerzo a la vez. El barrido debe incluir al menos un caso donde la gravedad o la aceleración solicitada exijan más que el esfuerzo disponible. Un eje que soporta poco peso puede completar el movimiento pese al aumento de masa.
- **Observables:** posición física, tiempo de movimiento, esfuerzo del actuador y error respecto de la referencia; parámetros y masa total para descartar conteo doble. La carga conocida por el banco no constituye un sensor de peso del robot.
- **Esperado:** una carga mayor cambia la dinámica de forma coherente. Al superar la capacidad puede producir retraso, no llegar o ceder durante sostén. Si el sistema conoce el exceso o recibe un aviso de falla solicita detención y exige rearme; no se afirma detección automática por un encoder inexistente.
- **Restauración:** recargar la condición nominal de carga y comprobar estabilidad/referencia; rearmar y emitir una orden nueva. No borrar masa real de una ejecución para que parezca que el motor se recuperó espontáneamente.

El cálculo de masa/inercia debe ser independiente de la malla visual simplificada. Un cambio de masa con igual distribución exige actualizar su inercia de forma consistente. Fuente: [Physics R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/physics.md).

## Retirada o desprendimiento: ensayo estructural posterior

Se debe elegir explícitamente entre «pieza ausente desde el inicio» y «pieza que se desprende durante la simulación». En el primer caso se recalculan las propiedades y conexiones del mecanismo restante. En el segundo, el cuerpo liberado conserva su masa, inercia, pose y velocidades iniciales correspondientes, colisiona con el entorno y responde a gravedad. Una pieza retirada no puede seguir aportando masa a su cuerpo anterior.

Antes de añadirlo se necesita definir qué unión se rompe, qué cuerpos quedan conectados, cómo se libera esa unión y qué sucede con cables, correas o restricciones que el modelo represente. Se ejecutará en un mundo de ensayo con contención y restauración por recarga. Ocultar o eliminar la geometría visual, fijar manualmente su pose o reducir el torque del motor no demuestra desprendimiento. Fuentes para las capacidades de vínculo y propiedades: [Joint R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/joint.md), [Connector R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/connector.md), [Physics R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/physics.md).

## Comprobaciones para aceptar una versión

| Área | Evidencia mínima |
| --- | --- |
| Modelo y cadena | Ejes y descendientes correctos; medidas contra CAD/planos; límites y ceros con fuente; colisiones sin penetraciones iniciales. |
| Movimiento | Directa/inversa coherentes; dos ramas de codo cuando correspondan; objetivo actual, límites, singularidades y punto inalcanzable definidos; orientación preservada en el mundo al omitirse. |
| Rechazo previo | Una entrada inválida deja el movimiento previo y el estado en la condición definida; no inicia una trayectoria parcial hacia el nuevo objetivo. |
| Física | Masas e inercias positivas y con procedencia; actuadores con esfuerzo finito; efecto de gravedad/carga observado; ninguna masa contabilizada dos veces. |
| Fallas | Inyección efectiva sobre la magnitud correspondiente; aviso de inyección separado de diagnóstico; detención física observada; rearme explícito y repetición desde estado conocido. |
| Comunicación | Recepción completa/fragmentada/concatenada según contrato, desconexión reconocida, bucle sin bloqueo y reconexión sin repetición de una orden. |
| Portabilidad | Una copia limpia permite abrir el proyecto y repetir los ensayos implementados con las instrucciones y dependencias declaradas. |

Si una comprobación usa instrumentación de verdad simulada, se declara en el resultado. Si el contrato TCP o un dato físico falta, se registra la prueba como pendiente o realizada con un banco provisional identificado. La entrega no queda validada contra hardware inexistente ni contra un protocolo aún no entregado.

## Referencia inicial y propuesta de homing

El banco arranca en `initial_positions` y asume esa referencia conocida. Recargar ese estado no reproduce cómo un robot sin encoders encuentra su posición.

Una propuesta de homing pendiente de implementación sería: bloquear movimiento ordinario → liberar Hall si comienza activo → buscar un flanco con recorrido/tiempo acotados → retirar hasta inactivo → aproximar lentamente al mismo flanco → asignar referencia del eje → repetir los demás ejes en orden validado → quedar detenido y exigir rearme explícito.

Cada etapa necesita límites de pasos y tiempo. Un Hall fijo, falta de flanco, stop, desconexión o falla debe abortar sin declarar referencia recuperada. La decisión usaría Hall entregado, pasos emitidos y relojes declarados; la posición perfecta del simulador quedaría solo para verificar el ensayo.

Faltan posición/polaridad de Hall e imanes, sentido, offset al cero, pasos por unidad, secuencia libre desde las posiciones iniciales permitidas y sostén de J4. Sin referencia no se puede asumir que la comprobación nominal actual garantice una búsqueda libre de choques. Estos datos y el criterio docente deben acordarse antes de convertir la propuesta en un procedimiento operativo.
