# SCARA | Avances y puntos para revisión

**Reunión del 27 de octubre de 2026. Documento de trabajo para revisión docente.**

El objetivo es acordar cómo continuar la simulación del diseño recibido. Reunimos las diferencias entre fuentes y los datos que faltan para que puedan responderse también después de la clase. Cada hallazgo tiene un identificador; se puede responder por ese número, indicar el archivo correcto o marcarlo como pendiente.

## Cinco preguntas para conversar en clase

**1. Entrega.** Ya tenemos movimiento desde una aplicación externa y ensayos básicos de fallas y rechazo de recorridos. ¿Qué tarea, funcionalidades y pruebas considera indispensables para completar el trabajo?

**2. Comunicación.** Usamos un protocolo provisional documentado. ¿Debemos adaptarnos a otro protocolo de la cátedra o podemos acordar el actual como base? ¿Se deben intercambiar destinos XYZ o posiciones de las articulaciones?

**3. Diseño de referencia.** Encontramos diferencias entre el maestro, planos individuales y modelos CAD. ¿Qué ensamble o revisión debemos representar? En las páginas siguientes detallamos las diferencias para resolverlas con tiempo.

**4. Referencia inicial.** Hoy iniciamos el ensayo desde una posición conocida de la simulación. ¿Se espera implementar homing, es decir, buscar una referencia usando los sensores Hall? ¿Hay una secuencia prevista y ubicaciones definidas de sensores e imanes?

**5. Fidelidad física.** ¿Alcanza con fundamentar masas y límites de esfuerzo/velocidad de las articulaciones, o se espera además modelar motores paso a paso, transmisión y pérdida de pasos? ¿Qué carga y movimientos debemos usar como prueba?

## Qué podemos mostrar hoy

- Modelo articulado en Webots: giro de brazo, codo y muñeca, más desplazamiento vertical.
- Interfaz externa: recibe XYZ, calcula posiciones articulares y envía órdenes por TCP/IP.
- Movimiento a X=240, Y=250, Z=35 mm; comparación con la posición calculada por Webots.
- Rechazo de un punto fuera de alcance y de un recorrido con posible contacto con la torre.
- Ensayo de Hall fijo y rearme explícito; también hay pérdida de esfuerzo, desconexión y carga ajustable.

**Límites actuales.** Montaje parcial; masas y esfuerzos provisionales; homing pendiente. Las colisiones se comprueban con envolventes simplificadas y cubren ciertos pares, no todos los contactos internos. No hay robot físico disponible para contrastar prestaciones.

**Base escrita ya cubierta:** la consigna pide mundo físico Webots, controlador, aplicación visual externa y mensajes de texto por TCP/IP; entrega por SEO y defensa grupal. Lo que falta precisar son los objetivos particulares del SCARA y sus criterios de aceptación. Fuente: `CONSIGNA-TP-FINAL.pdf`, pp. 1-2 y 6.

<!-- SALTO DE PAGINA -->

## Hallazgos mecánicos | conjunto vertical

Son diferencias observadas entre archivos. Pueden corresponder a revisiones distintas. Se solicita elegir la referencia válida antes de modificar el modelo.

### H01. Cuerpo vertical: 200 mm o 190 mm

**Qué encontramos.** El maestro indica 200 mm de longitud para `Z-Cuerpo`. El plano individual indica 190 mm y otra disposición de perforaciones.

**Fuentes.** `00-SCARA-Master.pdf`, p. 20; `Modelos3D/Z-Cuerpo.PDF`, p. 1.

**Por qué importa.** Define geometría, posición de fijaciones y masa del conjunto vertical.

**Consulta.** ¿Qué versión de Z-Cuerpo debemos usar? Si corresponde otra, indicar el plano o modelo actualizado.

**Respuesta / archivo:** __________________________________________________

### H02. Pistón: 175 mm o 180 mm

**Qué encontramos.** El maestro indica 175 mm para `Z-Piston`; el plano individual indica 180 mm.

**Fuentes.** `00-SCARA-Master.pdf`, p. 21; `Modelos3D/Z-Piston.PDF`, p. 1.

**Por qué importa.** Cambia la longitud y masa de la pieza y puede afectar los extremos del desplazamiento según su montaje.

**Consulta.** ¿Qué longitud y versión de pistón corresponde al conjunto que debemos representar?

**Respuesta / archivo:** __________________________________________________

### H03. Tornillo ACME: tres referencias de longitud

**Qué encontramos.** El maestro describe 120 mm más encastres; el plano individual acota 200 mm; el modelo convertido disponible tiene unos 195 mm de longitud total. El avance nominal de 8 mm por vuelta está documentado.

**Fuentes.** Maestro, p. 12; `Modelos3D/Z-VarillaACME.PDF`, p. 1; dimensiones del sólido convertido en `cad/derivados/informe.json`, entrada Z-VarillaACME.

**Por qué importa.** Longitud total, longitud roscada y carrera útil son magnitudes diferentes; la carrera nominal de 120 mm no permite elegir una longitud total.

**Consulta.** ¿Qué tornillo corresponde al diseño final y qué parte de su longitud se destina al recorrido útil y a las fijaciones?

**Respuesta / archivo:** __________________________________________________

### H04. Buje exterior: dos formas diferentes

**Qué encontramos.** El maestro muestra un buje corto de exterior cuadrado; el plano individual muestra una pieza alargada con zonas cilíndricas para el conjunto de rotación. No es solo una diferencia de longitud.

**Fuentes.** `00-SCARA-Master.pdf`, p. 22; `Modelos3D/Z-BujeExterior.PDF`, p. 1.

**Consulta.** ¿Qué buje corresponde al conjunto vertical y de muñeca vigente? La respuesta debe ser coherente con sus rodamientos, polea y fijaciones.

**Respuesta / archivo:** __________________________________________________

<!-- SALTO DE PAGINA -->

## Hallazgos mecánicos | carreteles, poleas y ejes

### H05. Agujeros centrales de los carreteles A

**Qué encontramos.** El plano `A-Carreteles.PDF` muestra diámetros centrales de 35 y 40 mm. En las geometrías nativas actuales analizadas se obtienen 16 y 17 mm. La diferencia afecta el encastre con los ejes.

**Fuentes.** `Modelos3D/A-Carreteles.PDF`, p. 1; contraste CAD documentado en `docs/DATOS_PARA_EL_PROFESOR.md` y `docs/INTEGRACION_CAD_CRITERIOS.md`.

**Consulta.** ¿Qué versión de los carreteles A y de sus piezas de acople corresponde representar?

**Respuesta / archivo:** __________________________________________________

### H06. Polea de muñeca: CAD de 80 dientes, plano de 60

**Qué encontramos.** Se contaron 80 dientes en la geometría CAD de `2GT_80Teet_40Bore`; el maestro también describe 80. El texto del plano individual dice 60 dientes. El nombre del archivo no fue la única evidencia usada para el conteo.

**Fuentes.** Maestro, p. 12; `Modelos3D/2GT_80Teet40Bore.PDF`, p. 1; `validation/pulley_geometry.json`.

**Por qué importa.** Con un piñón de 20 dientes, 80 da reducción 4:1 y 60 daría 3:1. Cambian la relación de movimiento y el esfuerzo de salida.

**Consulta.** ¿Debemos mantener la polea de 80 dientes y considerar desactualizada la descripción del plano, o corresponde otra versión?

**Respuesta / archivo:** __________________________________________________

### H07. Transmisión M3: salida de 8 mm y agujero de 5 mm

**Qué encontramos.** El extensor de M3 tiene salida de diámetro 8 mm; el piñón analizado tiene agujero de 5 mm. En las posiciones guardadas se solapan axialmente unos 17 mm: esas piezas no encajan con esos diámetros y colocaciones.

**Fuentes.** `Modelos3D/B-ExtensorM3.PDF`, p. 1; `2GT_20Teet_5Bore.SLDPRT`; `validation/remaining_mounts.json`, apartado M3.

**Límite del hallazgo.** La geometría sólida convertida del extensor no supera las comprobaciones; sus superficies se usaron para diagnóstico, apoyado por el plano. Esto no demuestra que el archivo nativo esté dañado. No se usó ese sólido para calcular masa.

**Consulta.** ¿Qué combinación de motor, extensor y piñón es la prevista? ¿Hay que usar otro piñón, otro extensor o corregir el montaje? Si el extensor se conserva, sería útil un STEP exportado desde la revisión correcta.

**Respuesta / archivo:** __________________________________________________

### H08. Ejes de torre: diferencia de 30 mm

**Qué encontramos.** `A-Eje` mide 110 mm en el plano y 140 mm en el CAD actual; `A-EjeInterior`, 160 mm en el plano y 190 mm en el CAD. La información guardada en el ensamble de torre también corresponde a versiones más cortas.

**Fuentes.** `Modelos3D/A-Eje.PDF` y `A-EjeInterior.PDF`, p. 1; `validation/remaining_mounts.json`; `cad/ensambles/registro_subensambles.json`.

**Consulta.** ¿Qué longitudes y montaje de estos dos ejes corresponde usar? No se recortaron ni estiraron las piezas para forzar la coincidencia.

**Respuesta / archivo:** __________________________________________________

<!-- SALTO DE PAGINA -->

## Hallazgos y decisiones de montaje

### H09. Tapa y polea de muñeca: colocaciones distintas

**Qué encontramos.** La tapa `R-ContraBancada` aparece invertida entre el ensamble global y el subconjunto `R-EnsambleRotacion`. Sus apoyos son asimétricos; esa inversión explica un desfase de 3 mm entre alojamientos.

**Qué adoptamos.** En el prototipo usamos la colocación guardada en R: coinciden apoyos, agujeros y rodamientos. Para la polea de muñeca también usamos R: asienta con 12 mm de acople axial. La alternativa de `B-EnsambleAntebrazo` invade el escalón del buje en el análisis geométrico.

**Fuentes.** `validation/wrist_bearing_diagnosis.json`; `validation/remaining_mounts.json`; explicación en `docs/MONTAJE_Y_AUTOCOLISIONES.md`.

**Consulta.** ¿Es correcta la configuración del subconjunto R para la entrega? ¿Cómo se fijan los aros de los rodamientos y la polea a sus piezas? La coincidencia geométrica no demuestra por sí sola una fijación mecánica efectiva.

**Respuesta / archivo:** __________________________________________________

### H10. Velocidad rotacional: unidades incompatibles

**Qué encontramos.** El maestro, p. 8, pone en la misma celda 4,44 grados/s y 266 rpm. No son equivalentes: 4,44 grados/s son 0,74 rpm; 266 rpm son 1596 grados/s. La tabla también usa 4,44 como impulsos por grado.

**Qué ya sabemos.** El cálculo de 400 impulsos/vuelta y reducción 4:1 da 4,444... impulsos/grado. No adoptamos la celda contradictoria como límite de velocidad. La estimación de 1000 rpm de motor sin carga tampoco valida una velocidad de trabajo bajo carga.

**Consulta.** ¿Hay una velocidad y aceleración de trabajo previstas por eje? Si no están definidas, ¿podemos proponer límites fundamentados y declararlos como hipótesis de simulación?

**Respuesta:** ___________________________________________________________

### M01. Ensamble de referencia y piezas pendientes

Se recuperaron colocaciones de diez ensambles, pero no forman un único maestro enlazado. Hay revisiones y posiciones distintas de piezas compartidas, también en los subconjuntos verticales y en poleas/ejes interiores. Por ejemplo, `B-Eje` queda a distinta altura en A y B. El modelo de NEMA17 también difiere de algunas dimensiones guardadas en los ensambles.

**Consulta.** Si existe, facilitar el ensamble completo actualizado con sus dependencias (por ejemplo, Pack and Go), o un STEP del conjunto. Si no existe, indicar qué subconjunto manda en cada zona pendiente. Esto permitirá cerrar varias discrepancias a la vez; las posiciones ya recuperadas no necesitan medirse de nuevo una por una.

**Fuente:** `cad/ensambles/registro_subensambles.json` y `validation/remaining_mounts.json`.

### M02. Fijación de los seis carreteles

Son mitades con canales anulares, diferentes de las poleas dentadas. La asignación provisional es: A inferior a base y A superior a brazo; B superior a brazo y B inferior a antebrazo; R inferior a antebrazo y R superior al conjunto vertical que gira.

**Consulta.** ¿Qué función cumplen, a qué cuerpo queda fija cada mitad y con qué orientación angular se montan? Su posible uso para guiar cables es una inferencia de su forma. También necesitamos identificar fijaciones y recorrido de correas que no queden claros en el ensamble elegido. El grupo derivará después el acoplamiento entre los motores de base y el codo.

**Respuesta M01/M02 / archivo o croquis:** ___________________________________

<!-- SALTO DE PAGINA -->

## Física | datos disponibles y datos que faltan

### F01. Motores y electrónica: punto de partida documentado

Se toman como referencia los modelos que ya identifica el maestro. Solo sería necesario avisar si hubo un cambio posterior:

- **M1 y M2:** Minebea `23KM-K381-P1`, NEMA23, 1,8 grados, seis cables.
- **M3:** Shinano Kenshi `STP-42D221-03`, NEMA17, 1,8 grados, seis cables.
- **M4:** sin marca indicada, modelo `42D265`, NEMA17, 1,8 grados, cuatro cables; descripción de 1,9 V y 0,7 A.
- **Drivers:** compatibles con TB6600; 400 impulsos por vuelta en los cuatro motores.
- **Alimentación de potencia:** 36 V CC, 10 A. También se indica fuente auxiliar de 12 V CC, 2 A, y Arduino UNO.

**Fuente:** `00-SCARA-Master.pdf`, pp. 10 y 14. Los 0,7 A de la descripción de M4 no resuelven la corriente ajustada en cada driver. La tensión nominal del motor y la alimentación de su driver son datos diferentes.

**Consulta puntual.** ¿Dispone de fichas o curvas de torque frente a velocidad de esos motores y de la corriente ajustada y conexión de bobinas en cada driver? Ya hay una búsqueda documental registrada sin localizar fichas exactas en los catálogos consultados; eso no prueba que no existan. El grupo puede continuar la búsqueda; se solicita el material específico que la cátedra ya tenga.

### F02. Transmisión nominal ya identificada

El maestro indica reducción 20 a 80 dientes para M1-M3, etapa 60 a 60 hacia el codo y tornillo ACME de 8 mm de avance por vuelta para J4. El grupo realizará los cálculos motor-articulación a partir del montaje resuelto. Hoy Webots acciona directamente las articulaciones; las poleas visibles no implementan por sí mismas toda esa transmisión.

**Consulta de alcance.** ¿Se espera representar la transmisión mediante relaciones y límites equivalentes de esfuerzo/velocidad, o simular además pasos, pérdidas y fallas? ¿Hay datos conocidos de fricción, eficiencia o sostén vertical de J4 sin energía? Si no existen, se propondrán aproximaciones declaradas para revisión.

### F03. Materiales y masas

**Ya localizado:** acero para L0; tubos de aluminio para L1-L4; PLA con 30% de relleno en planos de piezas concretas, entre ellas B-SoporteRuleman, R-Bancada, R-ContraBancada, Z-BujeExterior, Z-BujeInterior y Z-SoporteEfector; ACME de acero y tuerca de bronce. No se pide nuevamente el material de todo el robot.

**También disponible:** un G-code conjunto de los dos carreteles A con tres perímetros, tres capas superiores/inferiores y relleno rectilíneo del 30%. No caracteriza todas las impresiones ni permite repartir su masa estimada por mitades. Fuentes: maestro p. 9 y 12, planos citados y `Modelos3D/A-CarretelInf.gcode`.

**Consulta puntual.** Para las piezas de la revisión elegida, ¿hay perfiles de impresión adicionales, materiales específicos, masas de catálogo o una lista de tornillos, correas, cables y accesorios con su ubicación? Si faltan datos, ¿qué aproximaciones considera aceptables para la entrega?

Ya calculamos volúmenes y distribución geométrica de las piezas admitidas. El grupo calculará masas y propiedades de cada conjunto; no se solicita al profesor calcular inercias. Una impresión al 30% no pesa necesariamente el 30% de la pieza maciza y el CAD de un motor no revela toda su estructura interna.

**Respuesta F01-F03 / datos disponibles:** ___________________________________

<!-- SALTO DE PAGINA -->

## Referencia, herramienta y comunicación

### R01. Sensores Hall y búsqueda de referencia

**Ya documentado.** El maestro, p. 14, prevé sensores Hall con imanes al inicio y final de carrera de los cuatro ejes y declara ausencia de encoders. En el banco actual las regiones de activación son provisionales; la posición interna de Webots se usa para observar ensayos.

**Consulta.** ¿Hay un plano, croquis o descripción de ubicación y orientación de sensores e imanes? ¿Qué lectura corresponde a activo? ¿Dónde queda el cero de cada eje respecto de la detección y cuáles son sus sentidos y topes? Las excursiones nominales del maestro no fijan por sí solas esos ceros.

Si se exige homing: ¿hay una secuencia prevista, un orden de ejes y posiciones permitidas de arranque? ¿Cómo debe sostenerse J4 durante la búsqueda? Con esos datos el grupo implementará y propondrá para revisión una búsqueda acotada, retirada del sensor, aproximación lenta y abortos ante una falla.

**Estado actual.** Recargar el ensayo establece una posición inicial definida; no busca sensores ni recupera físicamente una referencia. El grupo debe acordar cómo simular pérdida de referencia y su recuperación.

**Respuesta / croquis:** ___________________________________________________

### R02. Punto de herramienta y carga

**Convención actual.** Se usa como punto de destino el centro de la cara exterior de `Z-SoporteEfector`, sin pinza. La orientación es su rumbo en el plano horizontal.

**Consulta.** ¿Ese punto sirve para la entrega o debemos representar una herramienta concreta y otro punto de referencia? ¿Qué carga, ubicación de la carga y movimientos se deben ensayar? Por ejemplo, subir 1 kg con J4 y moverlo con el brazo extendido son condiciones distintas.

**Respuesta:** ___________________________________________________________

### C01. Protocolo entre la aplicación y Webots

**Qué existe.** `scara-dev/1` está implementado y explicado, con ejemplos, en `docs/PROTOCOLO_SCARA_DEV_1.md`. El programa externo actúa como cliente TCP y Webots como servidor. Usa mensajes de texto JSON, uno por línea. La aplicación calcula la inversa y envía posiciones articulares: J1-J3 en radianes y J4 en metros; la pantalla muestra grados y milímetros.

**Consulta.** Si hay otro protocolo, facilitar su especificación o ejemplos completos de órdenes y respuestas. Necesitamos saber quién conecta con quién, cómo se separan los mensajes, unidades, comandos, estados, errores, cancelación y reconexión. Si se conserva el actual, el documento existente puede servir de base de revisión.

**Decisiones que deben quedar claras:**

- ¿Se envían XYZ/orientación o articulaciones? Esto define dónde se calcula la inversa.
- ¿Qué respuesta significa orden recibida, orden aceptada y movimiento terminado? Hoy el fin de consignas no acredita llegada física.
- ¿Qué debe ocurrir al detener, perder la conexión o reconectar? ¿Se exige detectar una conexión que queda abierta pero deja de responder?
- ¿La aplicación web actual se entrega como aplicación externa o se integrará con otra que provea la cátedra?

**Aclaración de términos.** TCP/IP es la conexión de red. El punto de herramienta, a veces también llamado TCP por la sigla inglesa Tool Center Point, es un concepto geométrico diferente.

**Respuesta / protocolo o fecha prevista:** ___________________________________

<!-- SALTO DE PAGINA -->

## Evaluación y próximos pasos

### E01. Criterios particulares del SCARA

La consigna ya fija el formato general: mundo Webots, controlador, aplicación externa por TCP/IP, envío por SEO y defensa grupal. En su apartado SCARA no completa objetivos específicos ni fecha. Se propone precisar lo siguiente:

**Tarea y trayectoria.** ¿Qué operación debe demostrar el robot? Hoy mueve entre destinos mediante interpolación articular; el extremo puede seguir una curva. ¿Se requiere además una línea recta del extremo, una pinza o manipulación de objetos?

**Fallas.** Ya hay Hall fijo, reducción/pérdida de esfuerzo y cierre de conexión; también carga ajustable. ¿Cuáles son obligatorias? ¿Se agregan atasco, pérdida de pasos o desprendimiento de una pieza? Estas últimas requieren trabajo adicional. ¿Se evalúa la reacción a una falla que el ensayo informa o también su detección autónoma con los sensores del diseño?

**Precisión y sostén.** ¿Qué error de posición/orientación y tiempo de estabilización se aceptan, con qué carga? El simulador permite medirlo en el ensayo; esa instrumentación no equivale a agregar encoders al robot real.

**Colisiones.** La protección actual usa cajas y margen para ciertos contactos con base, pedestal y suelo. ¿Qué otros pares de piezas y obstáculos deben cubrirse? ¿Alcanza con rechazar el recorrido o se exige buscar automáticamente otro camino?

**Ejecución y documentación.** La demostración disponible se ejecuta en Mac. ¿En qué equipos/sistemas debe reproducirse la entrega? ¿Qué evidencia de pruebas espera y cuál es la fecha? El grupo preparará la copia y repetición correspondientes.

**Respuesta / prioridades:** ________________________________________________

_______________________________________________________________________

## Cómo usaremos las respuestas

Se registrará cada decisión con su identificador, fecha y fuente. El grupo actualizará montaje, parámetros y comportamiento, y repetirá las pruebas afectadas. Si un dato no está disponible, se propondrá una hipótesis explícita para acordarla; una consulta pendiente no se considerará aprobada.

Para responder después basta, por ejemplo: «H01: usar el plano de 190 mm» o «C01: envío protocolo el...». En una diferencia de geometría conviene indicar el archivo o revisión para poder reproducir la elección.

## Vocabulario breve para leer el documento

- **Articulación:** unión móvil. J1-J3 giran; J4 se desplaza verticalmente. **Motor:** actuador que la mueve mediante una transmisión.
- **Cinemática inversa:** calcula posiciones articulares para un destino. **Dinámica:** estudia fuerzas y movimiento considerando masas, gravedad y aceleraciones.
- **Envolvente:** forma simplificada que ocupa la pieza para comprobar posibles contactos.
- **Torque o par:** esfuerzo de giro. **Inercia:** resistencia de una distribución de masa a cambiar su movimiento de rotación.
- **Protocolo:** acuerdo sobre los mensajes intercambiados. **Homing:** procedimiento para encontrar una referencia mediante movimiento y sensores.

**Trazabilidad.** Las cotas de planos y los datos de electrónica se contrastaron con los PDF originales. Los resultados CAD citados remiten a los informes existentes; este documento no repite todas las conversiones ni convierte esos análisis en ensayos físicos. La evidencia general se reúne en `docs/VALIDACION_WEBOTS.md`.
