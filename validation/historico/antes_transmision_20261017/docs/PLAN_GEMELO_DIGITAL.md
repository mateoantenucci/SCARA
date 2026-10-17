# Plan del gemelo digital SCARA

**Avance 17/10:** los dos rodamientos de muñeca ya están incorporados como visuales provisionales; 36 instancias. El desfase de 3 mm se explicó por una tapa invertida en el global y se resolvió usando su pose guardada en el subensamble coherente. [Resumen breve y siguientes pasos](MONTAJE_Y_AUTOCOLISIONES.md). La revisión oficial y las propiedades físicas siguen pendientes.

**Avance de montaje:** 34 instancias, cuatro rodamientos añadidos y rechazo de recorridos de herramienta/carga contra base fija. La revisión de 41 poses encontró cuatro invasiones de la torre, ya rechazadas por el control. Siguen pendientes el montaje de muñeca con desfase de 3 mm y los demás contactos internos. [Resumen breve](MONTAJE_Y_AUTOCOLISIONES.md).

Actualización de decisiones: 14 de octubre de 2026. **Estado: Q1–Q5 aceptadas; CAD visual articulado parcial integrado y ensayado, con física y protocolo provisionales. El [checkpoint](CHECKPOINT_CONTINUAR.md) registra la continuación; el [README](../README.md) explica cómo usar el proyecto y sus límites.**

Avance 15/10/2026: **punto 1 del próximo hito completado como precálculo geométrico**, sin aplicar propiedades incompletas a la física. Procedimiento, resultados y datos pendientes en [Propiedades geométricas del CAD](PROPIEDADES_GEOMETRICAS_CAD.md). Todo desarrollo debe conservar método, evidencia, archivos y limitaciones para que el grupo pueda explorarlo y documentar lo realizado.

Continuación del 15/10: **punto 2 resuelto para pedestal/piso y recorridos nominales del banco**, con diagnóstico CAD, cajas por pieza, rechazo conservador previo y validación propia. Alcance y límites en [Colisiones y recorridos](COLISIONES_Y_RECORRIDOS.md); no equivale a planificación general ni autocolisión completa.

Continuación del16/10: el [diagnóstico del tope J4](DIAGNOSTICO_TOPE_J4.md) reprodujo la oscilación y ajustó el paso numérico de16 a2ms. Conserva carrera, geometría, masas y esfuerzos; quince escenarios de sostén cumplen error/amplitud<0,5mm con medición en cada paso. La amplitud residual máxima medida es0,174mm. No convierte esos criterios en prestaciones de hardware; en aquella revisión el punto3 seguía pendiente; se completó después, como se registra a continuación.

**Continuación posterior del 16/10: punto 3 completado.** Se [recuperaron las tres geometrías](RECUPERACION_GEOMETRIAS.md), se integraron las 30 instancias con malla y se regeneraron propiedades: 49 tipos/51 sólidos/30 instancias. Pasaron 30 pruebas Python, 15 controles de recuperación y las regresiones CAD/colisiones. El próximo paso es revisar montaje y autocolisiones internas; después, física fundamentada y comportamiento/entrega según los datos docentes. La exportación alternativa de esas tres piezas queda como contraste opcional de fidelidad.

La primera guía trataba modelo y movimiento como alcance inicial. La actualización del grupo agrega comunicación TCP/IP, interpretación de comandos y respuestas, fallas, masas y fuerza/torque. La finalidad es una entrega reutilizable por otros alumnos. Este documento pasa a ser la referencia de planificación; la [guía anterior](GUIA_PROYECTO_SCARA_WEBOTS.md) conserva utilidad para convertir CAD.

## Hechos y fuentes

- [Consigna revisada el 13/10/2026](../CONSIGNA-TP-FINAL.pdf), páginas 1–2: modelo físico en `.wbt`, controlador `.cpp`, `.java` o `.py`, conexión con programa externo visual de escritorio o web y mensajes de texto por TCP/IP. Los roles cliente/servidor dependen del programa externo; no están fijados universalmente.
- Misma consigna, página 6: SCARA no construido, no disponible, no operativo; protocolo no redactado y programa externo no desarrollado. No hay allí objetivos específicos completados ni fecha de entrega. Por lo tanto, hoy no se puede prometer validación experimental contra un SCARA disponible.
- [Documento maestro](../00-SCARA-Master.pdf), páginas 5–14: cadena R-R-R-P; longitudes y recorridos nominales; transmisiones; sensores Hall y ausencia de encoders. Hay valores faltantes y documentos con medidas distintas.
- Actualización del grupo del 14/10: el profesor elaborará el protocolo y quiere un intérprete en Webots; solicita fallas y dinámica. Se confirmó en Onshape la medida de `A-Brazo.SLDPRT` indicada en la guía. La conversión local posterior produjo 50 STEP y 44 STL aceptados, con seis rechazos documentados; no reconstruye el ensamble.
- Inventario original: 50 SLDPRT, 10 SLDASM, 44 SLDDRW, 46 PDF, 3 STL, 1 G-code. El mundo dinámico actual incorpora **30 instancias, todas con geometría**, con base fija y cuatro articulaciones. La integración combina 20 instancias del snapshot global y diez montajes/carcasas registrados entre subconjuntos. No representa todas las piezas ni todos los mecanismos del diseño.
- Pasaron **16 pruebas Python**, once capturas nativas con 30 instancias cada una —330 colocaciones— y seis llegadas articulares en [validation/cad_motion.json](../validation/cad_motion.json). También se repitieron y aprobaron **nueve ensayos nativos de movimiento/fallas sobre CAD** en [validation/simulation.json](../validation/simulation.json). No certifican precisión real ni colisiones seguras.
- El banco de cajas anterior, sus fuentes e informes se conservaron en [validation/historico/banco_cajas](../validation/historico/banco_cajas). La interfaz también se comprobó contra el **modelo CAD actual**, con habilitación, movimiento a (240, 250, 35) mm, regreso a (250, 250, 34,67) mm y reinicio a STOPPED con nueva identificación de ensayo, carga cero y referencia válida; evidencia en [validation/client_native.json](../validation/client_native.json). El contrato sigue siendo `scara-dev/1`, provisional; el protocolo del profesor no fue entregado.

El grupo confirmó que no existe robot físico ni hardware. El objetivo es una simulación fiel al diseño, que pueda servir de base a una construcción futura o a trabajos posteriores, por ejemplo aprendizaje automático. No se exigirán mediciones contra hardware inexistente para completar la entrega actual. La fidelidad se sustentará en geometría, cálculos, propiedades con procedencia y ensayos reproducibles.

El integrante que coordina este chat comienza sin conocimientos de modelado, controladores o hardware. El agente explicará desde cero las decisiones relevantes, resolverá las técnicas rutinarias y solo pedirá intervención humana cuando falte acceso, información de cátedra o una preferencia que cambie el resultado. Las instrucciones de uso deberán poder seguirse sin conocimientos previos del proyecto.

## Árbol de decisiones

La entrevista sigue `grill-with-docs`: cada ronda pregunta únicamente decisiones cuyos antecedentes ya se conocen. Las respuestas se registrarán antes de cerrar el plan o implementar decisiones dependientes.

```text
Hechos: consigna + CAD disponible + objetivos del grupo
├── Q1. Alcance de fidelidad y evidencia [aceptado]
│   ├── Revisión CAD de referencia y propiedades físicas
│   ├── Magnitudes a validar y tolerancias
│   └── Catálogo de fallas y nivel de actuador/transmisión
├── Q2. Responsabilidad sobre el programa externo [aceptado]
│   ├── Interfaz mínima y escenarios docentes
│   └── Frontera de cinemática/planificación
│       └── Depende también del protocolo del profesor
└── Q3. Fecha [resuelto: no hay fecha; avanzar diariamente]
    └── Priorización de hitos y validaciones
Q4. Movimiento punto a punto, XYZ, velocidad y orientación opcional [aceptado]
Q5. Rechazo previo, detención y rearme explícito, sin repetición [aceptado]
```

Hay antecedentes externos que resolver con el profesor: protocolo, revisión mecánica y prestaciones. No convertir su ausencia en decisiones ficticias del grupo. Los valores que permitan avanzar se marcarán como provisionales y reemplazables.

## Primera ronda resuelta

| ID | Decisión | Respuesta confirmada |
| --- | --- | --- |
| Q1 | Qué comprende una primera entrega fiel | Aceptado: CAD y cadena articulada; cinemática; masa, centro de masa e inercia; límites de esfuerzo; TCP/IP; fallas reproducibles; trazabilidad. No hay hardware y no forma parte de esta entrega calibrarlo contra uno. |
| Q2 | Si el grupo implementa programa externo | Sí: incluir interfaz visual mínima de referencia, reemplazable por otra compatible. |
| Q3 | Plazo | No hay fecha de entrega. Avanzar lo posible cada día, por hitos funcionales; no implica una automatización programada. |

El protocolo definitivo y la revisión mecánica siguen siendo consultas externas. La frecuencia de consulta al profesor no impide preparar el modelo ni los componentes independientes del contrato.

## Segunda ronda resuelta: comportamiento observable

Las decisiones técnicas rutinarias y reversibles las resolverá el agente. El usuario aceptó Q4 y Q5; no queda pendiente repetir esa consulta.

| ID | Decisión aceptada | Ejemplo concreto |
| --- | --- | --- |
| Q4 | Movimiento suave punto a punto del soporte, objetivo XYZ y orientación opcional; conservar orientación si se omite. No añadir pinza en la primera demostración. | Cambiar X,Y sin pedir giro debe mantener la dirección de la herramienta cuando los límites lo permitan; no mantener simplemente el valor de J3. El camino inicial puede ser curvo. |
| Q5 | Rechazar objetivos inválidos antes de mover; ante falla o desconexión solicitar detención y exigir rearme explícito. Primera batería: conexión interrumpida, Hall atascado y esfuerzo de motor reducido. Carga ajustable para ensayos. | Reconectar no debe repetir un movimiento anterior sin decisión explícita. Un motor sin esfuerzo no puede garantizar sostener el eje: la física sigue activa. |

La política de rearme y los eventos se adaptarán al protocolo que entregue el profesor. El banco actual está rotulado como provisional y no representa sus mensajes. No se promete detección de fallas con sensores inexistentes. Tras pérdida de esfuerzo se invalida la referencia: limpiar fallas no restaura fuerza ni referencia; hay que reiniciar el ensayo y habilitar explícitamente. Ese reinicio recarga la simulación, no es homing físico.

El banco también compara el peso conocido del soporte y carga con los 8 N provisionales de J4. Si lo supera, conserva el esfuerzo nominal, aplica la masa y avisa sobrecarga con referencia inválida. Después no permite cambiar la masa hasta reiniciar el ensayo, para evitar recuperar movimiento con una referencia incierta. Es un aviso del banco por carga conocida, no diagnóstico basado en sensores inexistentes ni una capacidad certificada del diseño.

## Herramientas CAD: comparación y prueba

La propuesta aportada por el grupo fue `sldprt2step → CadQuery → Blender`. La [evaluación y ejecución local](EVALUACION_CONVERSION_CAD.md) permitió usar `sldprt2step` y el kernel OpenCascade mediante OCP, sin instalar CadQuery completo ni Blender. Hay conversión reproducible y seis rechazos por resolver. Blender sigue condicionado a una necesidad concreta de tratamiento de malla.

Convertir piezas individuales y recuperar las instancias/posiciones de los ensambles son tareas distintas. Convertir las 50 piezas no habría resuelto por sí solo su colocación. Se mantienen separados geometría visual, colisión y propiedades materiales para no asignar fidelidad física automáticamente por incorporar CAD.

Se recuperó posteriormente el XML guardado con 106 instancias de los 10 ensambles y sus transformaciones. Es información de caché con procedencia, no reconstrucción de restricciones o CAD actualizado. Su vista estática no sustituye la clasificación de cuerpos móviles ni la incorporación al mundo dinámico.

La integración móvil actual asigna las 30 instancias a base, brazo, antebrazo, conjunto Z exterior y pistón/soporte. [config/cad_integration.json](../config/cad_integration.json) declara las decisiones y [integracion_articulada.json](../cad/ensambles/integracion_articulada.json) conserva marcos y colocaciones efectivas. Los [criterios de integración](INTEGRACION_CAD_CRITERIOS.md) justifican las convenciones reversibles: ejes horizontales de 250 mm, torre orientada hacia abajo, hombro a 0,2913625 m y punto de herramienta provisional. No son ceros de motor, homing ni TCP oficiales. Los carreteles tienen pertenencia visual propuesta y fase angular no certificada; los NEMA23 se muestran sin animar sus rotores internos.

## Recorrido acordado y criterios de avance

| Hito | Resultado concreto | Criterio de avance |
| --- | --- | --- |
| H0. Referencia y datos | Consigna trazada, revisión CAD elegida, tabla de parámetros y consultas al profesor | Cada dato esencial tiene valor con unidad, fuente y estado: confirmado, calculado, estimado o pendiente. |
| H1. Planta articulada | Modelo parametrizado con base fija y cuatro ejes; CAD incorporado progresivamente | Ejes y descendientes correctos, referencias adoptadas documentadas y dimensiones controladas. No confundir referencias de simulación con ceros físicos oficiales. |
| H2. Conversación completa | Programa externo de prueba y controlador intercambian una orden y un resultado | El bucle de simulación continúa con o sin datos de red; mensajes completos/fragmentados/concatenados se interpretan según contrato. Protocolo definitivo depende del profesor. |
| H3. Movimiento cartesiano | Objetivo de posición/pose convertido en movimiento articular | Directa e inversa concuerdan; límites, codo alternativo, singularidades y punto inalcanzable tienen resultados definidos. |
| H4. Fidelidad física | Mallas CAD, masas, centros de masa, inercias y esfuerzo disponible | Las propiedades pertenecen al cuerpo correcto; carga y esfuerzo finito afectan el movimiento de forma explicable. No hay dobles masas. |
| H5. Fallas y recuperación | Escenarios reproducibles con condición inicial y resultado esperado | Cada falla modifica el mecanismo, sensor o canal correspondiente; se observa su efecto y se puede restablecer el ensayo. |
| H6. Entrega docente | Proyecto portable, interfaz de referencia, ensayos e instrucciones | Un compañero abre una copia limpia y reproduce los escenarios; quedan explícitos límites de fidelidad y datos pendientes. |

H1 y H4 incorporan CAD progresivamente. H2 debe comenzar pronto para detectar incompatibilidades del protocolo; no conviene dejar toda la integración TCP para el final. Hasta recibir el contrato oficial se pueden verificar transporte y componentes mediante un banco de pruebas identificado como provisional, sin presentarlo como protocolo del profesor.

### Progreso efectivo de los hitos

- **H0–H1:** inventario, conversiones, XML, líneas de eje y cadena CAD parcial disponibles. Cada eje se movió por separado en Webots y se comprobaron los descendientes correspondientes; faltan revisión mecánica coherente y componentes/transmisiones pendientes.
- **H2–H3:** cliente, cinemática y TCP provisional implementados; ensayos directos contra el mundo CAD y recorrido navegador→Webots aprobados. Se comprobaron dos destinos y reinicio, con respuesta final visible en la interfaz; esto no acredita todos los controles ni todos los destinos. El protocolo definitivo depende del profesor.
- **H4–H5:** masa/centro/inercia de cajas equivalentes y esfuerzo finito implementados, con nueve ensayos nativos CAD aprobados. Las masas siguen exploratorias y las envolventes no son colisión precisa. Homing, pasos perdidos, bloqueo mecánico, desprendimiento y planificación anticolisión siguen sin implementar.
- **H6:** existen [guía de proceso y archivos](PROCESO_Y_ARCHIVOS.md), README y evidencias reproducibles. Faltan completar fidelidad y criterios docentes, adaptar protocolo y repetir ejecución nativa en Windows/Linux; no se declara cerrada la entrega final.

## Próximo hito y dependencias — 15/10/2026

El proyecto permite cerrar la sesión en el checkpoint actual y retomarla sin rehacer conversiones ni montaje. **No hay un bloqueo general.** La integración CAD parcial tiene evidencia propia; el siguiente hito es mejorar la base física y geométrica conservando las referencias provisionales identificadas.

| Orden | Trabajo autónomo | Resultado concreto para revisar |
| --- | --- | --- |
| 1 — completado el 15/10 | Propiedades geométricas de 46 tipos de pieza / 48 sólidos válidos; cuatro exclusiones explícitas. Unidades, hashes de revisión y colocaciones de 27/30 instancias conservados. | [Guía reproducible](PROPIEDADES_GEOMETRICAS_CAD.md), [CSV](../cad/propiedades/propiedades_geometricas.csv) y [JSON](../cad/propiedades/propiedades_geometricas.json). Sumas por grupo solo de referencia; no se activó física ni se asignó material homogéneo a componentes comerciales. |
| 2 — realizado para el banco | Once poses CAD, invasión intermedia con extremos libres, 30 cajas por pieza y rechazo continuo nominal frente a pedestal/piso. | [Proceso y verificación](COLISIONES_Y_RECORRIDOS.md), diagnóstico BREP y regresiones reproducibles. Pendientes autocolisiones, geometría completa y planificación de desvíos si se requiere. |
| 3, en paralelo cuando convenga | Diagnosticar las tres geometrías visibles rechazadas y revisar candidatos adicionales de montaje con evidencia suficiente. | Recuperación validada o diagnóstico concreto para pedir una exportación alternativa. Agregar piezas solo con colocación y cuerpo sustentados; no prometer que todo nativo podrá recuperarse con el conversor actual. |

No hace falta esperar que el usuario termine de leer para realizar esos trabajos, ni pedir que mida de nuevo las distancias entre ejes. Los datos externos impiden cerrar afirmaciones concretas de fidelidad, pero no todos los cálculos o implementaciones:

- **Referencia mecánica:** revisión vigente, fijaciones/fases y transmisión. Mientras tanto se conservan las convenciones reversibles y discrepancias documentadas.
- **Física y referencias oficiales:** materiales e impresión, componentes comerciales, motores/drivers, Hall/homing y punto de herramienta. Sin ellos se pueden precalcular propiedades geométricas y comparar supuestos; no fijar prestaciones fieles.
- **Contrato docente:** protocolo TCP/IP y criterios de aceptación/fallas. El transporte y la interfaz de desarrollo siguen siendo útiles; su compatibilidad definitiva requiere esa especificación.

Después se incorporarán las respuestas, se repetirán los ensayos afectados y se comprobará la ejecución en los sistemas del grupo. Homing, conteo/pérdida de pasos, bloqueo mecánico y desprendimiento requieren definir su alcance y validar cada escenario; no se declaran terminados por aprobar los ensayos actuales. El listado de consultas está en [DATOS_PARA_EL_PROFESOR.md](DATOS_PARA_EL_PROFESOR.md).

## Fronteras que hay que definir

### Cinemática y controlador intérprete

Una orden cartesiana exige conocer referencia, unidades, punto de herramienta y orientación deseada. X,Y,Z no determina por sí solo la orientación de J3. También hay dos configuraciones de codo posibles para muchos objetivos, y llegar al mismo destino no garantiza recorrer una línea recta.

La matemática de cinemática y planificación está separada de las APIs de Webots, para probarla y reutilizarla. El banco provisional resuelve XYZ en el programa externo y envía consignas articulares. **La ubicación definitiva depende del protocolo:** si recibe consignas articulares puede conservarse esa frontera; si recibe objetivos cartesianos habrá que acordar si el intérprete debe resolverlos.

El controlador de Webots seguirá interpretando comandos, aplicando consignas y devolviendo el estado acordado. El formato de mensajes, unidades, roles de red y vocabulario definitivo serán los del profesor.

### Dinámica y motores

Masa, centro de masa e inercia son propiedades diferentes. Calcularlas con CAD/materiales y registrar incertidumbre es más fiel que adoptar la inercia automática de una caja de colisión. PLA con relleno 30% no equivale necesariamente al 30% de la masa maciza.

En la integración actual se conservaron las masas exploratorias y se recalcularon envolventes equivalentes por grupo CAD. Sus centros e inercias corresponden a esas cajas, no a materiales verificados. La incorporación de 27 geometrías y las pruebas de caída no convierten esas estimaciones en propiedades reales del diseño.

El precálculo posterior ya permite convertir las integrales geométricas mediante `m = rho V` e `I = rho Jc` para piezas homogéneas, y conserva sólidos separados para materiales diferentes. Los 50 originales muestran la etiqueta de material sin especificar. Para grupos multimaterial se debe recalcular el COM ponderado por masas y aplicar ejes paralelos; las sumas a densidad común no pueden copiarse directamente al banco. La [guía nueva](PROPIEDADES_GEOMETRICAS_CAD.md#7-datos-que-faltan-para-reemplazar-la-física-provisional) detalla la transición.

Se puede usar control de posición con límites finitos de velocidad, aceleración y esfuerzo. No hace falta un control por torque desde el primer hito. Los motores genéricos de Webots no reproducen por sí solos la electrónica y la pérdida de pasos de un stepper: si se exige ese comportamiento, hay que modelarlo explícitamente y declarar sus supuestos.

La conversión de torque motor a esfuerzo articular requiere transmisión, eficiencia y, donde corresponda, acoplamiento. En particular M2 está en la base y transmite movimiento por un brazo que también gira; no asumir directamente `q2 = ángulo M2 / 4`.

### Estado observable y fallas

El robot documentado no tiene encoders. Mantener distintos la posición ordenada, la estimada por pasos y la física simulada permite representar descalibración o pérdida de pasos. La instrumentación interna de ensayos puede conocer la posición física simulada sin presentarla como sensor existente en el robot.

El esfuerzo indicado por el feedback de motor de Webots es una aproximación del esfuerzo del actuador en su grado de libertad; no equivale a un sensor de carga externa. Tampoco devuelve el esfuerzo aplicado directamente mediante `setTorque`/`setForce`.

El banco implementa inyecciones de esfuerzo reducido, Hall atascado, cierre de conexión y carga ajustable. Los nueve ensayos previos sobre CAD aprobaron pose inicial, llegada nominal y rumbo, rechazo previo, Hall/rearme, masa/COM/inercia/fuerza efectiva, caída por pérdida de esfuerzo, sobrecarga, desconexión y reset. Con 0,4 kg móviles el sostén fue aproximadamente 3,924 N; J4 cayó unos 60 mm en los escenarios de falta de esfuerzo y de sobrecarga, manteniendo en el segundo el límite de 8 N. La actualización de colisiones agrega rechazo de recorridos nominales contra pedestal/piso; no hay planificador de desvíos ni autocolisión (`selfCollision FALSE`). Una falla puede apartar la posición física de esa referencia. El [catálogo de fallas](FALLAS_Y_VALIDACION.md) conserva criterios de ensayo y escenarios posteriores. Bloqueo mecánico y desprendimiento no están implementados. Una orden inválida o un objetivo inalcanzable son casos de validación; no sustituyen una falla física simulada.

### Comunicación

TCP es un flujo; hay que respetar la delimitación de mensajes acordada. Recibido, aceptado y movimiento terminado son eventos distintos, aunque el protocolo elija cómo representarlos. Definir comandos durante movimiento, cancelación, desconexión y repetición antes de implementar esas políticas.

Las operaciones de red no deben impedir los pasos de simulación. El tiempo simulado rige el movimiento; el reloj de pared rige la comunicación. El banco actual atiende TCP en cada paso: pausar Webots también pausa el procesamiento de nuevas órdenes, aunque la interfaz permanezca abierta. Su servidor local usa JSON por línea; son decisiones provisionales que se adaptarán al protocolo oficial.

## Autonomía y colaboración humana

El agente puede preparar modelos y exportaciones cuando tenga acceso al CAD, desarrollar cliente/controlador, cálculos, pruebas y documentación. Puede localizar incompatibilidades y proponer valores provisionales respaldados. No se necesita que un humano haga manualmente esas tareas si están disponibles los archivos y herramientas.

La ayuda humana se reserva para información que no esté en los archivos: decisiones de cátedra, protocolo, identificación de revisión oficial, acceso autenticado que lo requiera y mediciones/ensayos físicos cuando exista el equipo. La lista concreta está en [DATOS_PARA_EL_PROFESOR.md](DATOS_PARA_EL_PROFESOR.md); es un borrador de consulta, no un mensaje enviado.

## Documentación que debe quedar al cerrar la entrevista

- Este plan con decisiones, hitos y criterios acordados.
- [Glosario](../GLOSSARY.md) con vocabulario coherente.
- Tabla de parámetros con unidades, fuente, revisión, incertidumbre y transformación de coordenadas cuando corresponda.
- Contrato de comunicación oficial y ejemplos de conversaciones.
- Escenarios de validación y fallas reproducibles.
- ADR solo para decisiones con alternativas y consecuencias duraderas. Se aceptó [simular el diseño sin hardware](adr/0001-simulacion-del-diseno-sin-hardware.md), preservando el grado de evidencia de los parámetros.

## Fuentes técnicas verificadas

- [Webots R2025a: programación del controlador](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/controller-programming.md): intercambio con simulación y `step`.
- [Webots R2025a: integración TCP/IP](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/interfacing-webots-to-third-party-software-with-tcp-ip.md): ejemplo oficial de puente hacia una aplicación externa.
- [Python: Socket Programming HOWTO](https://docs.python.org/3/howto/sockets.html): flujo, buffers y sockets no bloqueantes.
- [Webots R2025a: Physics](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/physics.md): masa, centro de masa, tensor y propiedades derivadas de colisiones.
- [Webots R2025a: Motor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/motor.md): control de posición, esfuerzo disponible, control por torque y límites del feedback.
- [Webots R2025a: PositionSensor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/positionsensor.md): observación de posición en el simulador.
- [Webots R2025a: Robot](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/robot.md): tiempo simulado y ejecución.

Para conversión de formatos y alternativas CAD, ver [fuentes anteriores](FUENTES_CAD_WEBOTS.md), consultadas el 29/09/2026. No se revisaron nuevamente todos sus planes comerciales.
