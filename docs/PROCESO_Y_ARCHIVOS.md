# Entender el proyecto SCARA desde cero

Esta guía explica el trabajo realizado y conecta cada idea con los archivos que la implementan. Leela en orden la primera vez. Para ejecutar el robot, usá el [README](../README.md); para consultar resultados concretos, la [validación](VALIDACION_WEBOTS.md).

## 1. Qué estamos construyendo y qué pide la materia

El proyecto representa en Webots el diseño de un brazo robótico SCARA entregado por la cátedra. Webots es el programa que calcula y muestra su movimiento. El objetivo es poder enviarle órdenes desde una aplicación externa, observar su respuesta y ensayar fallas.

La [consigna](../CONSIGNA-TP-FINAL.pdf), páginas 1–2, pide un modelo físico en un mundo `.wbt`, un controlador y una aplicación visual externa conectada mediante mensajes de texto por TCP/IP. En la página 6 identifica al SCARA como no construido, con protocolo y programa externo sin desarrollar. El [plan](PLAN_GEMELO_DIGITAL.md) distingue esos requisitos escritos de las ampliaciones acordadas por el grupo.

El [documento maestro](../00-SCARA-Master.pdf) describe la mecánica prevista. Es una fuente de diseño: contiene datos incompletos y diferencias respecto de algunos planos. No acredita que se haya construido y medido ese robot.

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

La referencia inicial aproximada del extremo es `(250, 250, 34,67) mm`. Es una condición elegida para el ensayo. No es una posición inicial encontrada físicamente mediante sensores.

**Comprobación de comprensión:** si gira J1, se mueven todos sus descendientes. Si solo se mueve J4, bajan el pistón y el soporte; el brazo y el antebrazo conservan su configuración.

## 3. Qué recibimos y qué desarrollamos

| Material de partida | Función |
| --- | --- |
| Consigna y documento maestro | Requisitos y descripción del diseño. |
| `Modelos3D/` | Piezas SolidWorks, ensambles, dibujos técnicos, planos PDF y algunos archivos de fabricación. |
| `fotografias/` | Referencias visuales del montaje y de componentes. |

Una pieza `.SLDPRT` describe una forma. Un ensamble `.SLDASM` relaciona ocurrencias colocadas de piezas. Un dibujo `.SLDDRW` es un documento técnico nativo; sus PDF permiten consultar vistas y cotas. Un G-code describe instrucciones de fabricación y no sustituye al modelo del robot.

Lo desarrollado en este proyecto comprende la conversión y recuperación del CAD, el modelo articulado en Webots, los cálculos, el controlador, la aplicación web, los ensayos y su documentación. El diseño mecánico de partida proviene de la cátedra.

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

Una forma detallada puede tener física aproximada. Agregar una malla no incorpora automáticamente su masa.

La masa interviene en la respuesta a aceleraciones y gravedad. El centro de masa indica dónde se concentra, de forma equivalente, la distribución de masa. La inercia describe la resistencia a cambiar la rotación. Un kilogramo cerca de un eje y otro lejos del eje producen distinta inercia.

El banco utiliza masas y esfuerzos provisionales y propiedades de cajas equivalentes. El precálculo CAD ya obtiene volumen, centroide y distribución geométrica, pero esos datos todavía no sustituyen la física activa. Hace falta respaldar materiales, impresiones y componentes comerciales, y completar el montaje. En una pieza homogénea `masa = densidad × volumen`; en un motor o una impresión con relleno, esa simplificación necesita un modelo apropiado.

Los motores del simulador reciben posiciones con límites finitos de velocidad, aceleración y esfuerzo. Los esfuerzos se expresan en N·m para J1–J3 y N para J4. Todavía no se reproduce la electrónica de los motores paso a paso ni la transmisión completa. El [resumen de transmisión](TRANSMISION.md) explica la diferencia.

**Pregunta para defenderlo:** ¿un resultado visualmente convincente demuestra que puede levantar una carga real? No: la carga admisible depende de propiedades y esfuerzos que todavía requieren respaldo.

## 6. Qué pasa cuando pedís «ir a X,Y,Z»

```text
Navegador
  ↓ HTTP local: destino en mm y grados
client/app.py: convierte unidades y calcula la cinemática inversa
  ↓ TCP: posiciones articulares en metros y radianes
scara_bridge.py → Runtime: interpreta, valida y genera consignas
  ↓ posiciones para los motores
Webots: calcula el movimiento físico simulado
  ↑ estados y resultados por TCP y HTTP hacia la interfaz
```

La **cinemática directa** calcula dónde queda el extremo cuando conocemos J1–J4. La **inversa** calcula articulaciones posibles para un destino. Ambas están en `scara/kinematics.py`.

Para las dos barras horizontales:

```text
x = L1 cos(q1) + L2 cos(q1 + q2)
y = L1 sen(q1) + L2 sen(q1 + q2)
rumbo = q1 + q2 + q3
z = altura de referencia + desplazamiento fijo de herramienta − q4
```

`q2` se mide respecto del brazo; por eso el segundo tramo usa `q1+q2`. La inversa considera las dos configuraciones de codo, descarta candidatos fuera de límites y elige uno cercano al estado estimado. El origen horizontal se rechaza por su singularidad. Después se comprueba el recorrido; una solución de la inversa puede igualmente ser rechazada por colisión.

Si se omite orientación, J3 compensa los cambios de J1 y J2 para conservar el rumbo cuando los límites lo permiten. Dejar J3 fijo no lograría eso.

`Runtime` interpola las articulaciones con un perfil quíntico: arranque y final suaves, con velocidad y aceleración de referencia nulas en los extremos. El extremo puede seguir una curva; no se implementó movimiento cartesiano rectilíneo.

TCP transporta un flujo de bytes. Un mensaje puede llegar partido y varios pueden llegar juntos. `scara/transport.py` reconstruye mensajes completos. El banco usa JSON por línea y se identifica como **`scara-dev/1`**. Es un contrato de desarrollo; todavía falta el del profesor.

En esta versión, Python sirve la página en el puerto local 8765 y se conecta al controlador de Webots en el 9000. Son dos conexiones distintas. Pausar Webots pausa también la atención de órdenes de su controlador.

## 7. Estados, mediciones y fallas

| Estado | Significado |
| --- | --- |
| `STOPPED` | Movimiento deshabilitado; requiere habilitación explícita. |
| `IDLE` | Habilitado y disponible para una orden. |
| `MOVING` | Ejecutando una secuencia de consignas. |
| `FAULT` | Hay una falla registrada que impide mover. |

La interfaz separa **ordenado**, **estimado** y **simulador**. El estimado actual sigue la referencia ideal; no cuenta pasos perdidos. La posición física de Webots se observa para comprobar ensayos. El diseño documentado no tiene encoders, de modo que esa observación interna no puede presentarse como un sensor real disponible para controlarlo.

`completed` significa que terminó la secuencia de consignas. Para afirmar llegada y sostén, las pruebas observan después la posición simulada dentro de tolerancias. Precisamente se encontró una oscilación de J4 después de terminar las consignas: se redujo al refinar el paso físico de 16 a 2 ms. El [diagnóstico de J4](DIAGNOSTICO_TOPE_J4.md) conserva la comparación y sus límites.

El banco permite fijar una señal Hall, reducir esfuerzo, cortar la conexión y cambiar una carga de ensayo. La carga conocida puede generar un aviso de sobrecarga. La [especificación de fallas](FALLAS_Y_VALIDACION.md) distingue lo implementado de las propuestas.

Una falla notificada cancela la trayectoria. Reconectar o limpiar un aviso no repite movimientos. La pérdida de esfuerzo invalida la referencia y requiere reiniciar el ensayo. **Reiniciar recarga el mundo; no hace homing.** Homing sería buscar una referencia mediante un procedimiento de movimiento y sensores, todavía pendiente.

## 8. Qué protección contra choques existe

El programa comprueba antes de mover todo el recorrido nominal frente al pedestal y al piso, y el de herramienta/carga frente a la base fija. Usa cajas, un margen y cotas de movimiento. No basta con comprobar el destino: se encontró un recorrido con extremos libres y una zona intermedia invasiva.

Hay además auditorías CAD de poses seleccionadas y ensayos de contacto en Webots. Cumplen funciones diferentes. Todavía no existe comprobación continua general de todos los pares internos ni búsqueda automática de caminos alternativos. Las cajas pueden causar rechazos conservadores y los contactos internos generales están desactivados (`selfCollision FALSE`). Una falla puede separar el movimiento físico de la referencia previamente comprobada.

Detalles y evidencia: [colisiones y recorridos](COLISIONES_Y_RECORRIDOS.md) y [montaje](MONTAJE_Y_AUTOCOLISIONES.md).

## 9. Mapa de archivos para explorar

| Archivo o carpeta | Qué mirar y qué explica |
| --- | --- |
| `README.md` | Cómo abrir, operar y cerrar el banco. |
| `config/scara.json` | Dimensiones, límites, estado inicial, masas, esfuerzos y paso de simulación, con procedencia y unidades. |
| `config/cad_integration.json` | Pertenencia de piezas a cuerpos y convenciones de montaje. |
| `scara/kinematics.py` | Directa, inversa y perfil de movimiento. Empezá por `forward()`. |
| `scara/frames.py` | Posición y orientación de los cuerpos; relaciona coordenadas locales y del mundo. |
| `scara/runtime.py` | Estados, aceptación y rechazo, movimiento, fallas y rearme. No depende de Webots. |
| `scara/dynamics.py` | Cajas equivalentes y combinación de herramienta con carga. |
| `scara/collisions.py` | Comprobación conservadora del recorrido. |
| `scara/transport.py` | Recepción y envío TCP sin bloquear los pasos de Webots. |
| `client/index.html` | Pantalla, botones y presentación de estados. |
| `client/app.py` | Servidor HTTP, inversa y enlace TCP. |
| `webots/controllers/scara_bridge/scara_bridge.py` | Adaptación entre esas reglas y los motores, sensores e instrumentación de Webots. |
| `webots/protos/SCARA.proto` | Definición generada del robot: cuerpos, articulaciones, visuales y física. |
| `webots/worlds/scara.wbt` | Mundo dinámico generado: robot, banco y entorno. |
| `webots/worlds/scara_cad_inspeccion.wbt` | Vista fija del ensamble recuperado, sin motores ni física. |
| `cad/derivados/` | STEP, STL, informes de conversión y tratamiento separado de la torre. |
| `cad/ensambles/` | XML, vistas guardadas, ejes y colocaciones. `integracion_articulada.json` es el manifiesto efectivo del montaje. |
| `cad/propiedades/` | Propiedades geométricas en JSON y CSV, aún sin aplicar como física material. |
| `tools/` | Programas para convertir, extraer, integrar, generar y ensayar; véase la tabla siguiente. |
| `tests/` y `client/test_app.py` | Pruebas automáticas de matemática, estados, comunicación y coherencia del modelo. |
| `validation/` | Resultados de ejecuciones y capturas. Cada informe tiene alcance y versión propios. |
| `validation/historico/` | Etapas anteriores y respaldos. Se consultan para reproducir o contrastar una revisión. |
| `.agent-state/` | Coordinación temporal de trabajos de IA. No forma parte de la explicación técnica ni de la entrega. |

| Herramientas | Función |
| --- | --- |
| `convertir_cad.py`, `patches/` | Conversión, adaptadores y comprobaciones de regresión del conversor. Licencias y NOTICE se conservan. |
| `exportar_torre_cuerpos.py` | Tratamiento visual separado de los sólidos de la torre. |
| `extraer_ensamble.py`, `extraer_ejes_cad.py`, `registrar_subensambles.py` | Colocaciones, líneas de eje y relación entre conjuntos. |
| `integrate_cad.py`, `generate_world.py`, `generate_cad_preview.py` | Manifiesto móvil, mundo/PROTO y vista fija. |
| `calcular_propiedades_cad.py` | Volúmenes, centroides y tensores geométricos. |
| `check_cad_motion.py`, `check_simulation.py`, `check_joint_stops.py` | Ensayos nativos de montaje, comportamiento y sostén de J4. |
| `check_collisions.py`, `check_self_collisions.py`, `check_collisions_native.py` | Auditorías CAD y ensayos de contacto/rechazo en Webots. |
| `check_wrist_bearings.py`, `check_pulley_mounts.py`, `check_pulley_geometry.py`, `check_remaining_mounts.py` | Diagnósticos específicos de montaje y geometría. |

Los archivos `__init__.py` permiten reconocer paquetes Python. Las carpetas `__pycache__` son cachés automáticas. No contienen una parte adicional del algoritmo que tengas que estudiar.

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

La [validación](VALIDACION_WEBOTS.md) es el índice para saber qué revisión está respaldada. Un informe antiguo no aprueba automáticamente los archivos que hoy hay en la carpeta.

## 11. Cómo prepararlo para explicarlo y defenderlo

Podés organizar una presentación en este orden:

1. Problema y requisitos: simular el diseño y conectarlo con una aplicación externa.
2. Material recibido y recuperación: formas, colocaciones y ejes.
3. Modelo: cuatro articulaciones; separar apariencia, contacto y física.
4. Orden completa: destino → inversa → TCP → controlador → motores → estado.
5. Evidencia: mostrar un movimiento, un rechazo y una falla, indicando la versión ensayada.
6. Límites: física provisional, protocolo pendiente, montaje incompleto y validación sin hardware.

Usá estas preguntas para verificar tu comprensión; cada una tiene respuesta en los bloques anteriores:

- ¿Qué desarrollamos nosotros y qué recibimos de la cátedra?
- ¿Qué cambia al mover una articulación? ¿Por qué J3 debe compensar para conservar rumbo?
- ¿Qué diferencia hay entre convertir una pieza y recuperar el ensamble?
- ¿Por qué una malla detallada no demuestra fidelidad dinámica?
- ¿Qué calcula la inversa y por qué puede rechazarse un destino alcanzable?
- ¿Qué significa `completed`? ¿Qué prueba adicional acredita llegada?
- ¿Por qué la posición interna de Webots no es un encoder del robot real?
- ¿Qué fallas están implementadas y cuáles son propuestas?
- ¿Qué confirma un ensayo aprobado y qué no permite concluir?

Las preguntas que necesitan una decisión externa están en [Consultas para el profesor](DATOS_PARA_EL_PROFESOR.md). Las dudas de comprensión las podemos resolver recorriendo estos bloques y sus archivos, sin estudiar todos los informes a la vez.

## Documentación para profundizar por tema

| Cuando necesites… | Leer |
| --- | --- |
| Operar el robot | [README](../README.md). |
| Entender alcance, acuerdos y pendientes | [Plan](PLAN_GEMELO_DIGITAL.md) y [decisión de simular sin hardware](adr/0001-simulacion-del-diseno-sin-hardware.md). |
| Resolver un término | [Glosario](../GLOSSARY.md). |
| Justificar conversiones y recuperaciones | [Conversión CAD](EVALUACION_CONVERSION_CAD.md), [tres geometrías recuperadas](RECUPERACION_GEOMETRIAS.md) y [torre por cuerpos](../cad/derivados/torre_por_cuerpos/README.md). |
| Explicar posiciones, ejes y cuerpos | [Ensamble](ENSAMBLE_CAD.md) y [criterios de integración](INTEGRACION_CAD_CRITERIOS.md). |
| Revisar montaje y transmisión | [Montaje](MONTAJE_Y_AUTOCOLISIONES.md) y [transmisión](TRANSMISION.md). |
| Justificar física y materiales | [Propiedades geométricas](PROPIEDADES_GEOMETRICAS_CAD.md). |
| Explicar rechazos y choques | [Colisiones y recorridos](COLISIONES_Y_RECORRIDOS.md). |
| Revisar pruebas, fallas y referencia | [Validación](VALIDACION_WEBOTS.md), [fallas](FALLAS_Y_VALIDACION.md) y [diagnóstico de J4](DIAGNOSTICO_TOPE_J4.md). |
| Preparar consultas externas | [Datos para el profesor](DATOS_PARA_EL_PROFESOR.md). |
| Consultar fuentes técnicas | [Referencias](FUENTES_CAD_WEBOTS.md). |

Los documentos especializados se abren cuando aparece esa duda. No hace falta leerlos todos antes de explorar el robot.
