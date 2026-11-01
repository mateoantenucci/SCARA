# Entender el proyecto SCARA desde cero

Esta guía explica el trabajo realizado y conecta cada idea con los archivos que la implementan. Leela en orden la primera vez. Para ejecutar el robot, usá el [README](../README.md). El diseño completo, con cada decisión, está en el [documento maestro v2](maestro/SCARA-Master-v2.md); los resultados, en la [campaña de validación](../validation/campana/INFORME.md).

## 1. Qué estamos construyendo y qué pide la materia

El proyecto representa en Webots el diseño de un brazo robótico SCARA entregado por la cátedra. Webots es el programa que calcula y muestra su movimiento. El objetivo es moverlo desde una aplicación externa, grabar y reproducir trayectorias (teach & play) y ensayar fallas.

La [consigna](../CONSIGNA-TP-FINAL.pdf), páginas 1–2, pide un modelo físico en un mundo `.wbt`, un controlador y una aplicación visual externa conectada mediante mensajes de texto por TCP/IP. En la página 6 identifica al SCARA como no construido, con protocolo y programa externo sin desarrollar. El [plan](PLAN_GEMELO_DIGITAL.md) distingue esos requisitos escritos de las ampliaciones acordadas por el grupo.

El [documento maestro v1](../00-SCARA-Master.pdf) describe la mecánica prevista; el [maestro v2](maestro/SCARA-Master-v2.md) lo actualiza con el CAD como fuente de verdad. Es una fuente de diseño: contiene datos incompletos y diferencias respecto de algunos planos. No acredita que se haya construido y medido ese robot.

Por eso, aunque la materia habla de «gemelos digitales», nuestro resultado actual es una **simulación del diseño con aproximaciones declaradas**. Podemos comprobar su coherencia con los archivos y con cálculos. La precisión o capacidad de un robot futuro requiere evidencia adicional.

**Al terminar este bloque deberías poder explicar:** qué pide la materia, qué aportó la cátedra y por qué todavía no podemos comparar contra hardware.

## 2. Cómo se mueve este robot

Imaginá una torre fija, un brazo que gira en horizontal, un antebrazo que gira respecto del brazo y un mecanismo en su extremo que puede girar y deslizarse verticalmente.

| Articulación | Movimiento | Efecto |
| --- | --- | --- |
| J1 | Giro del brazo respecto de la torre | Arrastra también al antebrazo y a todo lo que cuelga de él. |
| J2 | Giro del antebrazo respecto del brazo | Cambia el plegado del codo y mueve el conjunto del extremo. |
| J3 | Giro del conjunto vertical respecto del antebrazo | Cambia el rumbo del soporte final. |
| J4 | Deslizamiento del pistón | Baja o sube el soporte final. |

Esta cadena se llama **R-R-R-P**: tres articulaciones rotacionales y una prismática. Tiene cuatro grados de libertad, es decir, cuatro coordenadas articulares independientes en el modelo. No puede inclinar libremente la herramienta como un robot de seis ejes.

```text
Base fija → J1 → brazo → J2 → antebrazo → J3 → conjunto Z → J4 → pistón y soporte
```

Cada tramo rígido conserva la posición relativa de sus piezas. Las piezas situadas después de una articulación acompañan su movimiento. Una articulación es la unión que permite movimiento; el motor es el actuador que lo produce a través de una transmisión. **Motor y articulación no son sinónimos.**

Las distancias entre J1–J2 y J2–J3 son de 250 mm en el CAD analizado. Eso da una extensión horizontal nominal de 500 mm. No significa que todos los puntos de ese círculo sean admisibles: también influyen límites y choques.

Usamos X,Y en horizontal y Z hacia arriba. La interfaz muestra milímetros y grados; internamente se usan metros y radianes. J4 positivo baja el soporte, por lo que aumentar J4 disminuye Z.

El robot arranca cerca de la **pose de reposo** (J1 = J2 = J3 = 0°, brazo estirado, J4 abajo) y sin referencia. La referencia se obtiene con el **homing**, que busca un sensor Hall por eje (D11, D30).

**Comprobación de comprensión:** si gira J1, se mueven todos sus descendientes. Si solo se mueve J4, bajan el pistón y el soporte; el brazo y el antebrazo conservan su configuración.

## 3. Qué recibimos y qué desarrollamos

| Material de partida | Función |
| --- | --- |
| Consigna y documento maestro | Requisitos y descripción del diseño. |
| `Modelos3D/` | Piezas SolidWorks, ensambles, dibujos técnicos, planos PDF y algunos archivos de fabricación. |
| `fotografias/` | Referencias visuales del montaje y de componentes. |

Una pieza `.SLDPRT` describe una forma. Un ensamble `.SLDASM` relaciona ocurrencias colocadas de piezas. Un dibujo `.SLDDRW` es un documento técnico nativo; sus PDF permiten consultar vistas y cotas. Un G-code describe instrucciones de fabricación y no sustituye al modelo del robot.

Lo desarrollado en este proyecto comprende la conversión y recuperación del CAD, el modelo articulado en Webots, la URC, el firmware, el protocolo `scara/1`, los ensayos y su documentación. El diseño mecánico de partida proviene de la cátedra.

Una **instancia** es una aparición colocada de una pieza. El mismo modelo de motor puede aparecer dos veces. Por eso no hay que confundir cantidad de archivos de piezas, cantidad de instancias montadas y cantidad de cuerpos móviles.

## 4. Cómo pasamos del CAD a un robot articulado

El proceso tuvo estos pasos, que resolvieron problemas diferentes:

1. **Convertir formas.** `tools/convertir_cad.py` usa el conversor local `sldprt2step` para obtener STEP y OpenCascade/OCP para revisar sólidos y exportar mallas STL. STEP conserva una representación geométrica que permite cálculos; STL aproxima la superficie con triángulos para mostrarla.
2. **Resolver conversiones defectuosas.** Se añadió lectura de bloques pequeños del contenedor de SolidWorks y se ajustó la precisión del conversor para recuperar tres piezas. La torre se exportó por sus tres sólidos; en uno se eliminaron exclusivamente ocho triángulos de área cero. Los rechazos restantes se identifican en los informes.
3. **Recuperar posiciones.** `tools/extraer_ensamble.py` lee información XML comprimida guardada en los ensambles. Recuperó 106 ocurrencias en diez conjuntos. Son colocaciones guardadas; no una reconstrucción de todas las restricciones mecánicas con la revisión actual.
4. **Localizar los ejes.** `tools/extraer_ejes_cad.py` contrasta cilindros, agujeros y alojamientos entre piezas. Así se sustentan las distancias de 250 mm entre ejes; el tubo del antebrazo de 237 mm no es su longitud cinemática.
5. **Reunir conjuntos compatibles.** `tools/registrar_subensambles.py` usa piezas compartidas para relacionar coordenadas. Conserva ambigüedades: los diez ensambles no forman un maestro único y no se pueden superponer sin revisar duplicados y revisiones.
6. **Elegir cuerpos y referencias.** `config/cad_integration.json` declara qué piezas acompañan a cada cuerpo y qué colocaciones se adoptan. `tools/integrate_cad.py` calcula sus posiciones locales, conservando la geometría de las mallas.
7. **Generar Webots.** `tools/generate_world.py` construye el robot y el mundo a partir de esos datos y de `config/scara.json`.

Los detalles para justificar este proceso están en [conversión](EVALUACION_CONVERSION_CAD.md), [recuperación de geometrías](RECUPERACION_GEOMETRIAS.md), [ensambles](ENSAMBLE_CAD.md) y [criterios de integración](INTEGRACION_CAD_CRITERIOS.md). No hace falta dominar el formato binario de SolidWorks para explicar qué resolvió cada paso.

**Pregunta para defenderlo:** ¿por qué convertir todas las piezas no arma automáticamente el robot? Porque la forma de cada pieza no determina su colocación, su cuerpo rígido, sus articulaciones ni sus propiedades físicas.

## 5. Qué significa que el modelo tenga física

En Webots hay tres representaciones distintas:

| Capa | Qué aporta | Ejemplo |
| --- | --- | --- |
| Visual: `Shape` y `Mesh` | Lo que se dibuja | La malla del brazo, incluidos sus agujeros. |
| Contacto: `boundingObject` | Volúmenes usados para resolver choques | Cajas que envuelven piezas y pueden ocupar también sus huecos. |
| Física: `Physics` | Respuesta a fuerzas y gravedad | Masa, centro de masa y tensor de inercia de un cuerpo móvil. |

Una forma detallada puede tener física aproximada. Agregar una malla no incorpora automáticamente su masa. Las masas y esfuerzos siguen siendo provisionales; el precálculo CAD obtiene volumen, centroide y distribución geométrica, pero falta respaldar materiales, impresiones y componentes comerciales.

Los motores no se mueven por consignas ideales: la **planta** del controlador de Webots reemplaza a drivers, motores, correas y sensores. Las articulaciones avanzan en pasos discretos con la transmisión y el acople M1/M2 (modelo N1), y cada rotor sigue a los pulsos con el par de su curva par–velocidad: si la carga o la aceleración piden más, pierde pasos y el firmware no se entera (modelo N2, D64, [ADR 0006](adr/0006-modelo-de-motores-pasos-y-perdida-de-pasos.md)). El [resumen de transmisión](TRANSMISION.md) da las relaciones y los pares supuestos.

**Pregunta para defenderlo:** ¿un resultado visualmente convincente demuestra que puede levantar una carga real? No: la carga admisible depende de propiedades y esfuerzos que todavía requieren respaldo.

## 6. Qué pasa cuando pedís «ir a X,Y,Z»

```text
Navegador
  ↓ HTTP 8766: jog, puntos, trayectorias
URC (urc/): cinemática inversa, planificador PTP/LIN, verificación de colisiones
  ↓ TCP 9000, scara/1: segmentos SEG con duración, en unidades articulares
UCI (firmware/): encola, convierte a pasos y resuelve el acople M1/M2
  ↓ pulsos STEP/DIR (en Webots, a la planta simulada)
Webots: calcula el movimiento físico simulado
  ↑ estado S a 20 Hz con la posición estimada por pasos
```

La **cinemática directa** calcula dónde queda el extremo cuando conocemos J1–J4. La **inversa** calcula articulaciones posibles para un destino. Ambas están en `scara/kinematics.py`, que usa la URC.

Para las dos barras horizontales:

```text
x = L1 cos(q1) + L2 cos(q1 + q2)
y = L1 sen(q1) + L2 sen(q1 + q2)
rumbo = q1 + q2 + q3
z = altura de referencia + desplazamiento fijo de herramienta − q4
```

`q2` se mide respecto del brazo; por eso el segundo tramo usa `q1+q2`. La inversa considera las dos configuraciones de codo y descarta candidatos fuera de límites. Después se comprueba el recorrido; una solución de la inversa puede igualmente ser rechazada por colisión.

La URC planifica y el firmware ejecuta, como GRBL y Klipper (D6, [ADR 0005](adr/0005-la-urc-planifica-el-firmware-ejecuta.md)): un tramo **PTP** interpola las articulaciones y un tramo **LIN** sigue una recta del extremo; los dos se parten en segmentos de 20 ms que la URC verifica antes de mandar. El firmware responde `OK n` cuando el segmento entró en su cola (control de flujo). El protocolo completo está en [`scara/1`](PROTOCOLO_SCARA_1.md).

La URC escucha y la UCI se conecta (D1): el controlador de Webots, o socat con el Arduino por USB. Así el día del robot real se cambia Webots por el UNO sin tocar la URC ([UCI en el Arduino UNO](ARDUINO_UNO.md)).

## 7. Estados, referencia y fallas

La UCI arranca sin corriente y sin referencia, y anuncia `BOOT`. Sin referencia solo se puede mover con jog lento (5 °/s o 5 mm/s), y el Hall hace de fin de carrera; capturar y reproducir quedan bloqueados (D21, D58). El **homing** busca J4, J1, J2 y J3 en su Hall y fija la referencia en el flanco; después la URC vuelve sola a la pose de reposo (D11, D56, D72).

La interfaz separa la posición **estimada por pasos**, la única que conoce el robot real, de la **simulada**, que solo muestra el banco de ensayo por el canal de instrumentación. El diseño no tiene encoders: la posición física de Webots no puede presentarse como un sensor disponible para controlarlo, y una prueba verifica que la URC no la usa para capturar ni planificar ([ADR 0004](adr/0004-canal-de-instrumentacion-separado.md)).

`STOP` frena y conserva la referencia; `HALT` para en seco y la pierde si había movimiento; deshabilitar los motores corta la corriente y la pierde (D40, D41). Si la UCI pasa 1 s sin mensajes de la URC, frena sola (watchdog).

| Falla | Qué es | Cómo se detecta sin encoders |
| --- | --- | --- |
| F1 | Pérdida de pasos por sobrecarga o aceleración | `EV LOST` al cruzar un Hall |
| F2 | Driver sin corriente | J4 cae; la posición estimada ya no vale |
| F3 | Hall trabado | El homing aborta (`ERR 11` o `ERR 12`) |
| F4 | Enlace cortado | Watchdog |
| F5 | Reinicio inesperado de la UCI | `BOOT`: referencia perdida |

Las fallas se inyectan desde el panel «Banco de ensayo (solo simulación)». El detalle está en las secciones 7 y 9 del [maestro v2](maestro/SCARA-Master-v2.md).

## 8. Qué protección contra choques existe

El planificador de la URC comprueba cada segmento, también los del jog verificado, frente al pedestal, el piso y la torre, y el de herramienta/carga frente a la base fija: el jog frena antes de un choque (D28, D75). Usa cajas, un margen y cotas de movimiento. No basta con comprobar el destino: se encontró un recorrido con extremos libres y una zona intermedia invasiva.

Hay además auditorías CAD de poses seleccionadas y ensayos de contacto en Webots. Cumplen funciones diferentes. Todavía no existe comprobación continua general de todos los pares internos ni búsqueda automática de caminos alternativos. Las cajas pueden causar rechazos conservadores y los contactos internos generales están desactivados (`selfCollision FALSE`). Una falla (por ejemplo, pasos perdidos) puede separar el movimiento físico de la referencia previamente comprobada.

Detalles y evidencia: [colisiones y recorridos](COLISIONES_Y_RECORRIDOS.md) y [montaje](MONTAJE_Y_AUTOCOLISIONES.md).

## 9. Mapa de archivos para explorar

| Archivo o carpeta | Qué mirar y qué explica |
| --- | --- |
| `README.md` | Cómo abrir y operar el sistema. |
| `config/scara.json` | Dimensiones, límites, masas, esfuerzos y paso de simulación, con procedencia y unidades. |
| `config/cad_integration.json` | Pertenencia de piezas a cuerpos y convenciones de montaje. |
| `scara/kinematics.py`, `scara/frames.py` | Directa, inversa y posición de los cuerpos. |
| `scara/collisions.py`, `scara/dynamics.py` | Comprobación conservadora del recorrido; cajas equivalentes y carga. |
| `urc/app.py`, `urc/index.html` | Servidor HTTP de la página y la página. |
| `urc/session.py`, `urc/protocol.py` | Sesión `scara/1` con la UCI: conexión, estado, `BOOT`, referencia. |
| `urc/planner.py`, `urc/jog.py`, `urc/validation.py` | Tramos PTP y LIN, jog verificado y validación previa. |
| `urc/trajectories.py`, `urc/playback.py` | Gestor de trayectorias y reproducción. |
| `urc/instrumentation.py`, `urc/banco.js` | Canal de instrumentación y banco de ensayo (solo simulación). |
| `firmware/firmware.cpp`, `firmware/hal.h`, `firmware/transmission.h`, `firmware/config.h` | Núcleo C++ único: protocolo, cola, homing, pasos y acople M1/M2; la capa de hardware cambia entre UNO y Webots. |
| `firmware/arduino/` | Sketch para el Arduino UNO. |
| `firmware/pc/`, `firmware/test/` | Firmware compilado en la PC y conversaciones de conformidad. |
| `webots/controllers/scara_uci/` | Controlador de Webots: firmware más la planta simulada (`stepper.h`). |
| `webots/protos/SCARA.proto`, `webots/worlds/` | Robot generado y mundos. |
| `trayectorias/` | Trayectorias de demostración (D74). |
| `cad/` | Derivados, ensambles y propiedades geométricas del CAD. |
| `tools/` | Conversión, extracción, integración y generación del modelo; diagnósticos CAD; `exportar_maestro.py` y `verificar_enlaces.py`. |
| `tests/` | Pruebas automáticas: conformidad, planificador, URC, planta, Hall, UNO, demos y documentación. |
| `validation/` | Evidencia de cada ensayo; la vigente del sistema es la [campaña](../validation/campana/INFORME.md). |
| `validation/historico/`, `docs/historico/` | Etapas anteriores y el banco `scara-dev/1`. Se consultan para contrastar, no como prueba. |

| Herramientas | Función |
| --- | --- |
| `convertir_cad.py`, `patches/` | Conversión, adaptadores y comprobaciones de regresión del conversor. Licencias y NOTICE se conservan. |
| `exportar_torre_cuerpos.py` | Tratamiento visual separado de los sólidos de la torre. |
| `extraer_ensamble.py`, `extraer_ejes_cad.py`, `registrar_subensambles.py` | Colocaciones, líneas de eje y relación entre conjuntos. |
| `integrate_cad.py`, `generate_world.py`, `generate_cad_preview.py` | Manifiesto móvil, mundo/PROTO y vista fija. |
| `calcular_propiedades_cad.py` | Volúmenes, centroides y tensores geométricos. |
| `check_collisions.py`, `check_self_collisions.py` | Auditorías CAD de colisiones. |
| `check_wrist_bearings.py`, `check_pulley_mounts.py`, `check_pulley_geometry.py`, `check_remaining_mounts.py` | Diagnósticos específicos de montaje y geometría. |

## 10. Cómo distinguir fuentes, generados e informes

Los originales recibidos se conservan. Los programas y configuraciones son fuentes que se editan deliberadamente. Los mundos, mallas y manifiestos generados se obtienen de esas fuentes. Los informes registran lo ejecutado y observado.

Editar a mano un generado puede producir un arreglo que desaparezca al regenerarlo. Para cambiar el montaje se modifica su configuración, se integra y se genera; para cambiar la física se modifican parámetros fundamentados y se genera. Después se repiten los controles afectados. Los comandos están en los documentos técnicos correspondientes.

Un JSON es texto estructurado con nombres y valores. Para leer un informe, buscá:

| Campo | Qué significa |
| --- | --- |
| `source`, `sources`, `provenance` | De dónde salió el dato. |
| `sha256` | Huella del archivo: permite reconocer exactamente qué entrada se usó. No prueba su corrección. |
| `status`, `checks` | Resultado y comprobaciones a las que se refiere. |
| `warnings`, `limitations` | Advertencias y límites que también cuentan si el resultado fue aprobado. |
| `null` | Valor no asignado o no disponible; no significa cero. |
| Versión, build y fecha | Identidad y momento de la ejecución. |

La [campaña de validación](../validation/campana/INFORME.md) identifica la versión respaldada por commit y SHA-256. Un informe antiguo no aprueba automáticamente los archivos que hoy hay en la carpeta.

## 11. Cómo prepararlo para explicarlo y defenderlo

El [maestro v2](maestro/SCARA-Master-v2.md) ordena la presentación. Un recorrido posible:

1. Problema y requisitos: simular el diseño, moverlo desde una aplicación externa y grabar y reproducir trayectorias.
2. Material recibido y recuperación: formas, colocaciones y ejes.
3. Arquitectura: URC, firmware único y `scara/1`; por qué la URC planifica y el firmware ejecuta.
4. Referencia: pose de reposo, homing con Hall y qué se puede hacer sin referencia.
5. Evidencia: teach & play y una falla, indicando la versión ensayada.
6. Límites: física provisional, propuestas P1 y P2 sin revisar, sin placa real ni hardware.

Preguntas para verificar tu comprensión:

- ¿Qué desarrollamos nosotros y qué recibimos de la cátedra?
- ¿Por qué el protocolo usa unidades articulares y no pasos ni coordenadas cartesianas?
- ¿Qué cambia entre el firmware en Webots y en el UNO?
- ¿Por qué la posición simulada de Webots no es un encoder del robot real?
- ¿Cómo se detecta una pérdida de pasos sin encoders?
- ¿Qué confirma un ensayo aprobado y qué no permite concluir?

## Documentación para profundizar por tema

| Cuando necesites… | Leer |
| --- | --- |
| Operar el robot | [README](../README.md) y [UCI en Webots](UCI_WEBOTS.md). |
| El diseño completo y cada decisión | [Maestro v2](maestro/SCARA-Master-v2.md), [registro de decisiones](REGISTRO_DE_DECISIONES.md) y [ADR](adr/). |
| Alcance y pendientes | [Plan](PLAN_GEMELO_DIGITAL.md) y [decisión de simular sin hardware](adr/0001-simulacion-del-diseno-sin-hardware.md). |
| Resolver un término | [Glosario](../GLOSSARY.md). |
| El protocolo | [`scara/1`](PROTOCOLO_SCARA_1.md). |
| El robot real | [UCI en el Arduino UNO](ARDUINO_UNO.md). |
| Justificar conversiones y recuperaciones | [Conversión CAD](EVALUACION_CONVERSION_CAD.md), [tres geometrías recuperadas](RECUPERACION_GEOMETRIAS.md) y [torre por cuerpos](../cad/derivados/torre_por_cuerpos/README.md). |
| Explicar posiciones, ejes y cuerpos | [Ensamble](ENSAMBLE_CAD.md) y [criterios de integración](INTEGRACION_CAD_CRITERIOS.md). |
| Montaje, transmisión y motores | [Montaje](MONTAJE_Y_AUTOCOLISIONES.md) y [transmisión](TRANSMISION.md). |
| Física y materiales | [Propiedades geométricas](PROPIEDADES_GEOMETRICAS_CAD.md). |
| Rechazos y choques | [Colisiones y recorridos](COLISIONES_Y_RECORRIDOS.md). |
| Pruebas, homing y fallas | [Campaña de validación](../validation/campana/INFORME.md) y sección 10 del maestro. |
| Fuentes técnicas | [Referencias](FUENTES_CAD_WEBOTS.md). |
| El banco anterior `scara-dev/1` | [Documentación histórica](historico/README.md). |
