# Cómo se está construyendo el SCARA y para qué sirve cada archivo

Esta guía explica el trabajo desde cero y puede usarse como base del informe de la materia. Para **abrir y probar** el proyecto, empezar por el [README](../README.md). Aquí se explica cómo llegamos a ese resultado, qué conserva cada carpeta y cómo reproducir una etapa sin confundirla con otra.

El objetivo es simular el **diseño** de un SCARA que todavía no existe físicamente. Podemos comprobar consistencia geométrica, cálculos, comunicación y comportamiento del modelo; no podemos asegurar que coincida con medidas de un robot que no se construyó. Los datos confirmados y los adoptados provisionalmente deben distinguirse en el informe.

**Estado actual:** hay conversiones CAD, colocaciones recuperadas, una vista estática y un robot articulado con **30 instancias CAD parciales**. En la integración del 14/10 pasaron 16 pruebas de software, las colocaciones y llegadas articulares CAD, nueve ensayos nativos de movimiento/fallas y una prueba de interfaz desde el navegador contra esta versión. La sección 10 explica esta integración y su alcance. Las pruebas del banco de cajas anterior se conservaron separadamente; no se trasladan automáticamente a esta versión.

**Actualización 15/10/2026:** se completó el [precálculo de propiedades geométricas](PROPIEDADES_GEOMETRICAS_CAD.md): 46 tipos de pieza, 48 sólidos y 27/30 instancias, con CSV/JSON, transformaciones y cinco pruebas nuevas. La suite completa con OCP aprobó **21/21** y un contraste independiente validó la composición de los cinco grupos; [evidencia](../validation/cad_properties.json). Este desarrollo está documentado para poder explorarlo y reutilizarlo en el informe; la física del banco sigue siendo provisional. El usuario confirmó Webots R2025b nightly por los problemas de R2025a en macOS 27.

**Continuación, punto 2:** la [revisión de colisiones y recorridos](COLISIONES_Y_RECORRIDOS.md) reproduce cuatro invasiones CAD, conserva el soporte efector faltante como envolvente y sustituye cinco cajas por grupo por 30 cajas de pieza. Ahora se rechazan antes de mover las consignas cuyos recorridos nominales no se separan del pedestal/piso con margen de 1 mm. Nueve regresiones nuevas completan **30/30 pruebas** con OCP. Los estados anteriores se conservan con sus hashes; los materiales y las inercias exploratorias siguen pendientes.

**Continuación 16/10, sostén de J4:** se reprodujo y aisló la oscilación en el tope exacto. El [diagnóstico](DIAGNOSTICO_TOPE_J4.md) explica por qué el paso físico cambió de16 a2 ms, conservando los límites y parámetros materiales. Aprobaron 15 casos de sostén con1000 lecturas físicas por ventana, y las regresiones de movimiento/colisiones/CAD. Se conservan el fallo anterior y experimentos distintos; la amplitud residual máxima observada es0,174mm, dentro del criterio0,5mm del banco.

## 1. Las cuatro cosas diferentes que había que resolver

Un archivo que muestra una pieza no contiene automáticamente todo lo necesario para simular el robot.

| Pregunta | Información que la responde | Ejemplo |
| --- | --- | --- |
| ¿Qué forma tiene? | Geometría de la pieza. | Tubo perforado `A-Brazo.SLDPRT`. |
| ¿Dónde está colocada? | Posición y orientación de cada instancia en un ensamble. | Dos motores pueden usar el mismo archivo NEMA17 y estar en lugares distintos. |
| ¿Qué se mueve junto? | Cuerpos rígidos, articulaciones y transmisiones. | Varias piezas del brazo acompañan J1; el antebrazo gira además con J2. |
| ¿Cómo responde a una fuerza? | Masa, centro de masa, inercia, límites de esfuerzo, gravedad y contactos. | J4 puede caer si el motor deja de sostener el peso. |

Una **pieza** es el modelo de un componente. Una **instancia** es una copia colocada de ese componente. Un **cuerpo rígido** agrupa las piezas que mantienen su posición relativa durante el movimiento estudiado. No se debe convertir cada archivo en un motor ni considerar rígido todo un ensamble solamente porque esté guardado en un `.SLDASM`.

La cadena de trabajo tiene dos ramas que después se reúnen:

```text
SLDPRT → STEP → comprobación del sólido → STL en metros → forma visible
SLDASM → XML guardado → instancias y colocaciones → ejes y grupos móviles
                                                    ↓
                      cuerpos articulados de Webots + propiedades físicas
                                                    ↓
                      cliente externo → comandos TCP → controlador
                                                    ↓
                        movimiento, fallas y evidencia de validación
```

## 2. Primero se conservaron y revisaron los originales

Los archivos del profesor permanecen como referencia. El inventario original tiene 50 piezas `.SLDPRT`, diez ensambles `.SLDASM`, dibujos `.SLDDRW`, planos PDF, algunos STL y otros archivos auxiliares. El [documento maestro](../00-SCARA-Master.pdf) describe mecánica y movimientos; la [consigna final](../CONSIGNA-TP-FINAL.pdf) pide simulación, controlador e interfaz externa por TCP/IP.

Los documentos no son totalmente coherentes entre sí. Hay diferencias de longitudes, revisiones y prestaciones. Se registraron en [DATOS_PARA_EL_PROFESOR.md](DATOS_PARA_EL_PROFESOR.md), sin modificar una pieza para hacerla coincidir con otra fuente. La comprobación inicial de distancia realizada en Onshape por el grupo se conserva como contraste independiente.

No fue necesario rehacer todas las piezas desde cero ni instalar SolidWorks en las cuatro computadoras. La conversión y extracción siguientes se hicieron localmente; no se subieron los CAD a otros servicios. Onshape sigue siendo una alternativa para contrastar o exportar casos que no se puedan resolver con esta ruta.

## 3. De SolidWorks a una geometría aprovechable

### Qué conserva cada formato

| Formato | Qué contiene o para qué se usa | Qué no debemos suponer |
| --- | --- | --- |
| `.SLDPRT` | Pieza nativa de SolidWorks. | Webots no la abre directamente. |
| `.SLDASM` | Referencias a componentes, configuraciones y datos del montaje. | Subir el archivo sin sus piezas no reconstruye necesariamente el conjunto. |
| `.STEP` o `.step` | Intercambio de superficies y sólidos: permite medir y analizar geometría. | No equivale a recuperar el historial de operaciones de SolidWorks ni todos sus materiales. |
| `.STL` o `.stl` | Superficie aproximada mediante triángulos; se usa para la apariencia en Webots. | Por sí solo no define unidades, articulaciones, materiales ni masa. |
| `.wbt` | Mundo de Webots: escena y referencias al robot. | Copiarlo sin sus dependencias no entrega todo el proyecto. |
| `.proto` | Definición reutilizable de un robot o componente de Webots. | No sustituye sus mallas ni el controlador. |

### La ruta elegida

Se usó el conversor libre `sldprt2step`, fijado a una revisión concreta, y después OpenCascade mediante las bibliotecas OCP del ecosistema CadQuery. **No hizo falta CadQuery completo, VTK ni Blender.** Blender se reservaría para una necesidad concreta que las herramientas actuales no resuelvan.

1. `tools/convertir_cad.py` entrega la pieza al conversor y conserva el STEP.
2. OpenCascade abre ese STEP y comprueba si hay sólidos con volumen positivo y geometría válida. Una colección de caras no se acepta como sólido por el solo hecho de verse parecida.
3. Se aproxima su superficie con triángulos, operación llamada **teselación**.
4. Se exporta el STL en **metros**, conservando origen y orientación de la pieza.
5. Un control de aceptación comprueba archivo completo, cierre de la superficie, conexiones de sus aristas, volumen y dimensiones respecto del sólido.

El STEP queda en milímetros. La conversión numérica de milímetros a metros se aplica **una sola vez** para el STL: 250 mm pasan a 0,250 m. Aplicar otra escala de 0,001 al insertarlo en Webots haría una pieza mil veces más pequeña.

La conversión dispone de un adaptador para leer pequeños bloques internos de los archivos SolidWorks, llamados MiniFAT. Eso permitió recuperar tres piezas que el lector anterior no extraía bien. El adaptador cambia cómo se leen datos del contenedor; no inventa caras ni modifica el algoritmo geométrico del conversor. Su comprobación independiente está en `tools/patches/comprobar_ministreams.py`.

### Por qué no se aceptó todo automáticamente

El resultado del lote es **50 STEP conservados, 44 STL aceptados y seis piezas rechazadas explícitamente**. Dieciocho de las aceptadas tienen advertencias de curvas aproximadas. «Aceptado» significa que pasó los controles declarados, no que sea una traducción certificada por SolidWorks.

Las seis pendientes del lote son `0-Torre`, `B-CarretelInf`, `B-CarretelSup`, `B-ExtensorM3`, `Z-BujeInterior` y `Z-SoporteEfector`. Los motivos y alternativas están en [EVALUACION_CONVERSION_CAD.md](EVALUACION_CONVERSION_CAD.md). Un código de salida de error al procesar el lote puede significar precisamente estos rechazos parciales; no se deben esconder para presentar un resultado completo.

La torre tuvo un tratamiento **separado y explícito**: se exportaron sus tres sólidos individualmente. En uno se retiraron ocho triángulos de área exactamente cero, sin mover vértices, cerrar huecos ni quitar superficie de área positiva. Las tres mallas individuales pasaron sus controles y pueden usarse visualmente; esto no certifica su unión como una sola malla ni cambia el informe principal 44 + 6. Ver [el registro de la torre](../cad/derivados/torre_por_cuerpos/README.md).

## 4. Cómo se recuperó dónde va cada pieza

Convertir `A-Brazo` muestra su forma en sus coordenadas locales. Todavía falta saber cómo está girado y desplazado en el conjunto. Un motor y una polea pueden tener orígenes locales completamente distintos aunque deban quedar alineados.

`tools/extraer_ensamble.py` recuperó XML comprimido guardado dentro de los diez `.SLDASM`. XML es texto estructurado que aquí relaciona archivos, configuraciones e instancias. Se obtuvieron **106 instancias guardadas, correspondientes a 47 tipos de pieza**, conservando sus nombres y colocaciones.

La transformación de cada instancia contiene una rotación y una traslación. Su significado es: **tomar un punto de la pieza, girarlo y después desplazarlo para ubicarlo en el ensamble**. En el informe se guarda como una matriz de cuatro filas y cuatro columnas. No hay que memorizar la matriz para usar el proyecto; importa no reemplazarla por ajustes visuales a ojo.

Se comprobó su interpretación transformando las cajas envolventes de los componentes. Una **caja envolvente**, abreviada `bbox`, es la caja que encierra la pieza, determinada por sus extremos mínimos y máximos en X,Y,Z. La unión de las cajas transformadas reprodujo la caja guardada de cada uno de los diez ensambles a precisión numérica. Eso respalda la lectura de las colocaciones, **no prueba que todas las piezas actuales sean de la misma revisión que ese montaje guardado**.

Se encontraron diferencias de geometría actual frente al caché: por ejemplo, NEMA17 y algunos ejes tienen dimensiones distintas. Una caja distinta demuestra discrepancia, pero no su causa; una caja igual tampoco garantiza que coincidan todas las perforaciones.

Los diez ensambles no forman un árbol maestro único que incluya a los otros nueve. No se superpusieron todos ciegamente: hay piezas repetidas y poses diferentes. `0-EnsambleColision` reúne la forma general del SCARA, pero contiene solo 20 instancias, no todas las piezas del diseño. La [explicación de ensambles](ENSAMBLE_CAD.md) detalla sus límites.

### La vista estática

`tools/generate_cad_preview.py` genera `scara_cad_inspeccion.wbt` con las colocaciones guardadas. No contiene motores ni física; sirve para inspeccionar la información recuperada.

- Azul identifica geometría aceptada y consistente con la caja guardada; la torre tiene su estado separado por cuerpos.
- Ámbar señala malla aceptada cuya caja difiere del caché.
- Magenta muestra una caja alámbrica en lugar de la pieza cuyo STL no fue aceptado.

Hay 17 instancias con geometría y tres cajas pendientes. La pose guardada tiene la torre arriba y no se declaró como cero mecánico. Una vista estática correctamente armada todavía no es un robot articulado.

## 5. Cómo se localizaron los ejes y se preparó la articulación

Un **eje de giro** es una línea, no necesariamente el origen de una pieza. `tools/extraer_ejes_cad.py` inspecciona superficies cilíndricas de los STEP: agujeros y alojamientos permiten comparar centros y direcciones entre piezas. Se contrastaron líneas de piezas distintas, no solamente coordenadas elegidas por nombre.

Con esa evidencia se confirmaron **250 mm entre J1 y J2 y otros 250 mm entre J2 y J3**. El tubo del antebrazo mide 237 mm, pero su longitud física no es la distancia entre los ejes del mecanismo completo.

Conocer una línea no determina por sí solo:

- Qué ángulo debe considerarse cero y cuál es el sentido positivo del motor.
- La posición exacta del punto de herramienta que quiere controlar el profesor.
- El punto elegido sobre la línea como referencia del eslabón.
- Cómo están acopladas las transmisiones ni cuánto gira el motor por cada grado de la articulación.

La cadena prevista es base fija → J1 → brazo → J2 → antebrazo → J3 → conjunto vertical → J4 → pistón y soporte. Los tres primeros ejes usan `HingeJoint` para giro; J4 usa `SliderJoint` para traslación. Un cuerpo colocado después de una articulación acompaña su movimiento y el de sus antecesoras.

Para colocar una malla en un cuerpo móvil se necesita expresarla en las coordenadas de ese cuerpo. Si tenemos su colocación respecto del mundo, calculamos su posición **respecto del eslabón**, para que Webots no aplique el desplazamiento dos veces. La expresión técnica es:

```text
T_eslabon_pieza = inversa(T_mundo_eslabon) · T_mundo_pieza
```

Cada `T` representa una posición y orientación. Esto permite conservar el archivo STL original y colocar la instancia mediante nodos de escena, sin deformar o girar sus vértices manualmente.

Las poleas y carreteles requieren cuidado: pertenecer a un ensamble no prueba que estén fijos al mismo cuerpo. Los carreteles de canal anular **no son las poleas dentadas 2GT**; por su forma se propone que canalizan cableado, pero el maestro no lo explica expresamente. La integración asigna una mitad a cada lado de su articulación con evidencia geométrica y pertenencia visual provisional. La fase angular y la fijación mecánica no se consideran certificadas.

## 6. Qué ve Webots y qué calcula físicamente

En Webots se separan tres representaciones del mismo cuerpo:

| Capa | Para qué sirve | Ejemplo |
| --- | --- | --- |
| Geometría visual (`Shape`, `Mesh`) | Dibujar la pieza. | STL del brazo con perforaciones. |
| Geometría de contacto (`boundingObject`) | Calcular choques y contactos. | Caja o cilindro simplificado. |
| Propiedades físicas (`Physics`) | Calcular respuesta a fuerzas. | Masa, centro de masa e inercia del cuerpo. |

Cambiar la malla visible **no actualiza automáticamente la masa ni convierte una caja de contacto en el contorno real**. Tampoco se debe sumar la masa completa del brazo una vez por cada pieza visual: cada cuerpo necesita una masa total consistente, sin duplicaciones.

La **masa** indica cuánto cuesta acelerar un cuerpo. El **centro de masa** indica cómo se distribuye su peso. La **inercia** describe su resistencia a cambiar la rotación. Dos objetos de igual masa pueden responder distinto si uno tiene el material lejos del eje. El volumen calculado por CAD no basta para conocer estas propiedades: falta material, relleno de impresión, tornillería y distribución de componentes comerciales.

El modelo articulado usa cajas equivalentes con propiedades provisionales registradas en `config/scara.json`. Al incorporar CAD, las cajas se derivaron de la envolvente de cada grupo y se conservaron las masas exploratorias; el centro de masa y la inercia corresponden a esas cajas, no a materiales CAD verificados. La carga de ensayo se combina con la herramienta actualizando masa, centro e inercia; no se cambia solo un número de masa mientras lo demás queda incoherente.

El [cálculo CAD del 15/10](PROPIEDADES_GEOMETRICAS_CAD.md) ya entrega volumen, centroide y tensor central por densidad para los sólidos válidos. Los conserva por sólido/pieza y por instancia en el marco de su cuerpo. Las sumas por grupo son referencias aditivas con densidad común, sin corrección de solapamientos; no son COM físicos de conjuntos multimaterial. Se encontró la etiqueta «Material <sin especificar>» en los 50 originales. Faltan materiales, impresión, propiedades comerciales y componentes/geometrías para aplicar esos datos a `Physics`; por eso no se cambió el modelo ensayado.

Los motores se controlan por posición con límites finitos de velocidad, aceleración y esfuerzo. El esfuerzo es **torque en N·m para los giros y fuerza en N para J4**. Esto no reproduce todavía la electrónica de los motores paso a paso, pérdidas de pasos, holguras, rozamientos o transmisiones detalladas.

El control comprueba alcance, límites articulares y separación del recorrido nominal de las cajas de pieza frente al pedestal/piso del banco. La comprobación usa cotas continuas del perfil común, no solo muestras o destino. Es conservadora: puede rechazar un camino cuyo CAD detallado sí fuera libre. No busca desvíos, no comprueba autocolisiones ni obstáculos ajenos al entorno configurado. `selfCollision FALSE` sigue vigente; no demuestra que las piezas puedan atravesarse físicamente.

## 7. De «ir a X,Y,Z» a mover las articulaciones

La **cinemática directa** responde: si conozco J1–J4, ¿dónde queda el extremo? La **inversa** responde: si quiero dejar el extremo en X,Y,Z y con cierto rumbo, ¿qué valores deben tomar J1–J4? Ambas están en `scara/kinematics.py`, independientes de Webots.

Muchos destinos admiten dos posiciones de codo. El programa calcula candidatos, descarta los que exceden límites y elige uno cercano a la configuración estimada actual. Si no hay solución, rechaza la orden antes de iniciar ese movimiento. Hay configuraciones singulares en las que el cálculo requiere una política específica; el origen horizontal se rechaza explícitamente en esta primera versión.

Si no se indica orientación, se conserva el rumbo estimado del extremo respecto del mundo. J3 debe compensar los giros de J1 y J2; mantener únicamente J3 fijo no conservaría el rumbo. También se evita introducir un giro completo innecesario al pasar entre ángulos equivalentes.

Entre origen y destino se usa un perfil suave de posiciones articulares que empieza y termina con velocidad y aceleración nulas. Su duración respeta los límites adoptados de velocidad y aceleración. Eso no garantiza que la punta describa una línea recta ni que el motor físico alcance la consigna bajo cualquier carga.

### La conversación completa

1. El navegador recoge X,Y,Z en mm, orientación en grados y velocidad relativa.
2. `client/app.py` convierte las unidades y llama a la inversa.
3. El programa externo envía posiciones articulares por TCP local a Webots.
4. El controlador interpreta la orden, valida el estado y aplica consignas a los motores.
5. Devuelve aceptación o rechazo, estados periódicos y fin de la secuencia de consignas.

TCP entrega un flujo de bytes: un mensaje puede llegar partido, o varios llegar juntos. `scara/transport.py` reúne fragmentos y separa mensajes completos. El contrato de prueba usa JSON por línea, con límite de 16 KiB. JSON es texto estructurado con nombres y valores; no es necesario programarlo a mano para usar la interfaz.

**`scara-dev/1` es provisional.** El profesor todavía debe entregar su protocolo. Se eligió para probar el recorrido completo, no para reemplazar la especificación docente. La distribución definitiva de la cinemática entre programa externo e intérprete dependerá de esa especificación.

## 8. Por qué se muestran varios estados y cómo se prueban fallas

El diseño no tiene encoders. Por eso se separa lo ordenado, la estimación de control y lo que realmente ocurrió dentro del simulador. La estimación actual sigue una referencia ideal; no se la presenta como un modelo validado de pasos perdidos. La posición interna de Webots se usa para ensayos, no como si fuera un sensor del diseño.

`completed` significa **«terminó la secuencia de consignas»**, no «la punta llegó con precisión al destino». Para comprobar llegada se necesita observar después el estado físico simulado, con tolerancias y tiempos definidos.

El banco permite pérdida de esfuerzo, Hall fijo, cierre de conexión y carga de ensayo. Una inyección de falla es conocida por el banco; detener como reacción a esa inyección no demuestra detección autónoma con sensores reales.

Ante pérdida de esfuerzo se cancela la secuencia, se mantiene el esfuerzo reducido y se invalida la referencia. Limpiar el aviso no devuelve fuerza ni posición conocida. El ensayo debe reiniciarse: usar una posición perfecta oculta de Webots para «recuperar» la estimación falsearía la ausencia de encoders.

La sobrecarga se avisa cuando el peso **conocido por el banco** supera los 8 N estáticos provisionales de J4. La masa se aplica sin reducir artificialmente el esfuerzo nominal. Se exige reinicio antes de cambiarla tras perder referencia, para no provocar un retorno automático hacia una consigna antigua.

La desconexión reconocida detiene las consignas. Reconectar no habilita, no repite órdenes y no reanuda una trayectoria. El reinicio recarga la simulación a su condición inicial y deja `STOPPED`; no representa reparación ni homing físico. La [guía de fallas](FALLAS_Y_VALIDACION.md) distingue estos casos de un atasco o desprendimiento, todavía pendientes.

## 9. Qué demostraron las pruebas ya guardadas

| Nivel | Evidencia disponible | Alcance |
| --- | --- | --- |
| Archivos CAD | `cad/derivados/informe.json`, informe de torre y vistas. | Validez y aproximación geométrica según controles declarados. No certifica materiales ni equivalencia exacta con SolidWorks. |
| Ensambles y ejes | XML, matrices, cajas y cilindros contrastados. | Colocaciones guardadas y distancias entre ejes. No resuelve mates, revisión oficial ni ceros físicos. |
| Software independiente | **30 pruebas Python aprobadas** con OCP, incluida integración, propiedades y colisiones. | Matemática, límites, estados, carga, transporte y coherencia de marcos; nueve regresiones del pedestal. Tres pruebas requieren OCP, las demás no. |
| Webots nativo anterior | Nueve comprobaciones en `validation/historico/banco_cajas/validation/simulation.json`. | Banco de cajas: movimiento, rumbo, propiedades físicas, caída, Hall, desconexión y reinicio. |
| Interfaz completa anterior | `validation/historico/banco_cajas/validation/client_native.json`. | Órdenes desde navegador hasta el banco anterior. Es una ejecución separada de las nueve automatizadas. |
| Interfaz completa actual | `validation/client_native.json`, con resultado aprobado sobre CAD articulado parcial. | Habilitación, dos destinos, respuesta final visible y reinicio a STOPPED con nuevo ensayo, carga cero y referencia válida. No acredita todos los controles ni todos los destinos. |
| Colocaciones CAD articuladas | Once capturas de estado, con 30 instancias cada una, y seis llegadas articulares aprobadas en `validation/cad_motion.json`. | Reconstrucción del montaje guardado, posiciones realmente alcanzadas, poses iniciales/restauradas y movimiento de los descendientes correctos en J1–J4. |
| Movimiento y fallas sobre CAD | **Nueve comprobaciones aprobadas** en `validation/simulation.json`, repetidas después de integrar CAD. | Pose inicial, movimiento nominal/rumbo, rechazo, Hall/rearme, masa/inercia/fuerza, caída, sobrecarga, desconexión y recarga del ensayo actual. |

En el ensayo nominal de la versión CAD, el error final de la punta fue aproximadamente **0,0248 mm dentro del simulador**. Con 0,4 kg móviles, la fuerza de sostén fue aproximadamente **3,924 N**. J4 cayó **59,999 mm** al quitar esfuerzo y **60,051 mm** con la sobrecarga de 1 kg añadido, manteniendo en este último caso el límite de **8 N**. Son controles de coherencia del modelo, **no precisión ni capacidad certificadas del robot que pudiera construirse**.

El [informe de validación](VALIDACION_WEBOTS.md) documenta tolerancias, tiempos, compilación y limitaciones. Es importante conservar evidencia antes de cambiar el modelo: agregar mallas o cambiar parámetros no permite reutilizar automáticamente una aprobación anterior. El ensayo de movimiento/fallas actual tiene su propio `validation/simulation.json` aprobado, separado del histórico.

La prueba actual de navegador envió **(240, 250, 35) mm** y regresó a **(250, 250, 34,67) mm**. El error del extremo observado fue aproximadamente 0,025 mm en ambos destinos dentro del simulador. Se comprobó que el aviso visible mostrara el fin de consignas y que «Reiniciar ensayo» generara otro `trial_id`, dejando STOPPED, carga cero y referencia válida. La [evidencia de interfaz](../validation/client_native.json) registra las acciones y estados; no convierte `completed` en garantía de llegada fuera de esos casos comprobados.

Los registros conservan copias de las órdenes exactamente serializadas para que un cambio posterior de la lista de posiciones no altere retrospectivamente una orden guardada. Cada carga del mundo genera además un `trial_id` único: el ensayo comprueba que cambie al reiniciar, en lugar de adivinar que hubo recarga porque el reloj volvió a un valor pequeño. Es instrumentación del banco provisional, no una exigencia añadida al protocolo del profesor.

## 10. Incorporación CAD a la cadena móvil: resultado parcial comprobado

**`scara.wbt` ahora contiene un robot CAD articulado parcial de 30 instancias: 27 con geometría y tres cajas alámbricas pendientes.** Son las 20 instancias del conjunto global y diez montajes o carcasas incorporados mediante registro entre subconjuntos. La torre cuenta como una instancia aunque su dibujo use tres mallas. `scara_cad_inspeccion.wbt` conserva la vista estática de 20 instancias y tiene otro propósito.

### Cómo se incorporaron componentes de otros ensambles

`tools/registrar_subensambles.py` compara piezas compartidas de los conjuntos. La idea es alinear un subconjunto con el global usando varias referencias coherentes, en vez de llevar una pieza «a ojo» o confiar en una sola coincidencia ambigua. El registro comprueba identidad de las versiones guardadas y deja fuera propuestas incompatibles. No fusiona mecánicamente todos los snapshots ni resuelve sus restricciones.

De ese registro se adoptaron seis adiciones fijas —base y dos carcasas NEMA23—, dos soportes del brazo y dos del antebrazo. Las poleas, rodamientos y colocaciones ambiguas no se agregaron para completar artificialmente la apariencia. Los NEMA23 se ven como componentes enteros: sus rotores y transmisión interna todavía no están separados ni animados.

La configuración [cad_integration.json](../config/cad_integration.json) declara a qué cuerpo pertenece cada instancia. El resultado usado por el generador es [integracion_articulada.json](../cad/ensambles/integracion_articulada.json), con matrices pieza→cuerpo y huellas de fuentes. Las [reglas de integración](INTEGRACION_CAD_CRITERIOS.md) explican qué decisiones son convenciones reversibles y cuáles siguen sin demostración mecánica.

| Grupo | Instancias | Qué lo mueve |
| --- | ---: | --- |
| `base` · base fija | 8 | Permanece fija. Incluye torre, soportes y carcasas NEMA23. |
| `arm` · brazo | 6 | J1. |
| `forearm` · antebrazo | 8 | J1 y J2. |
| `wrist` · conjunto Z exterior | 6 | J1, J2 y J3. |
| `tool` · pistón y soporte | 2 | J1, J2, J3 y desplazamiento J4. |

Las tres cajas alámbricas son `B-CarretelInf`, `B-CarretelSup` y `Z-SoporteEfector`: tienen colocación y grupo, pero no se publicó su malla rechazada. Algunas geometrías aceptadas conservan advertencias y discrepancias contra el caché; incorporar su apariencia no elimina ese estado.

### Referencias elegidas, sin confundirlas con homing

Se tomó el montaje guardado, se giró 180° sobre X para orientar la torre hacia abajo y se alineó el vector J1→J2 guardado con +X. Después se llevó J1 al centro horizontal del mundo y la cara inferior de torre a Z=0. Es un cambio rígido de referencia: no deforma ni vuelve a escalar las mallas.

Los centros elegidos de los agujeros sitúan el hombro a **0,2913625 m**, con el codo **78 mm más abajo**. Las distancias horizontales siguen siendo 250 mm. El punto provisional del extremo se toma del marco guardado del soporte, con offset vertical **−0,1186956411 m** respecto de la muñeca a J4=0.

La pose que reconstruye el snapshot es aproximadamente `[0; 0,0415858; 0,0722365; 0,060]`, con giros en radianes y J4 en metros. **No es la configuración inicial ni un home certificado.** Se eligió J4=60 mm como referencia de simulación. La configuración inicial sigue siendo `[0; π/2; −π/2; 0,060]`, y ahora deja el punto provisional en aproximadamente **(250; 250; 34,6669) mm**, orientación 0°.

Por eso no se debe copiar un offset vertical del banco anterior manteniendo las mallas del nuevo montaje: la cinemática y las colocaciones dejarían de describir el mismo punto. La definición oficial de ceros, signos y TCP sigue pendiente; las convenciones usadas están registradas y pueden reemplazarse.

### Evidencia obtenida dentro de Webots

`tools/check_cad_motion.py` observó once estados del modelo: inicial, reconstrucción de pose guardada, antes/después de cada uno de los cuatro ejes y restauración inicial. En cada estado contrastó las **30 posiciones y orientaciones de instancia**, para un total de **330 colocaciones observadas**. Comprobó además **seis llegadas articulares**, comparando los objetivos con las posiciones realmente alcanzadas y no solo con el fin temporal de las consignas. No son 330 configuraciones articulares distintas ni una exploración de todo el espacio de trabajo.

El [informe CAD nativo](../validation/cad_motion.json) tiene resultado aprobado. El mayor error de posición entre la colocación observada y la esperada fue **2,570476×10⁻⁵ m, aproximadamente 0,0257 mm**, dentro de la tolerancia de 1 mm del ensayo. Se comprobó que los grupos anteriores a cada joint permanezcan fijos y los descendientes correspondientes se muevan. La diferencia numérica pertenece al modelo y solver del simulador; no es precisión real del SCARA.

La incorporación cambia la representación visual y las envolventes de cuerpo; **masas, inercias equivalentes, fuerzas, colisiones, transmisiones, fijaciones y TCP siguen siendo provisionales**. La prueba de colocaciones no demuestra ajuste físico de tornillos, ausencia de colisiones ni fidelidad de los actuadores. Los nueve casos de movimiento/fallas también se repitieron y aprobaron sobre esta nueva versión, con evidencia propia separada del banco de cajas. La interacción desde navegador contra CAD aprobó además los dos destinos y reinicio descritos en la sección 9; es una comprobación separada y de alcance limitado.

Vista del modelo articulado en la pose inicial; las cajas magenta identifican geometrías pendientes:

![CAD articulado parcial en Webots](../validation/scara_cad_articulado.png)

## 11. Mapa de carpetas

```text
SCARA/
├── README.md                     abrir y probar el proyecto
├── 00-SCARA-Master.pdf            documento del diseño
├── CONSIGNA-TP-FINAL.pdf          requisitos de la cátedra
├── Modelos3D/                    originales CAD y planos
├── fotografias/                  referencia visual; inspiración no es una medida
├── config/                       parámetros, agrupación CAD y procedencia
├── cad/
│   ├── derivados/                STEP, STL, informes y torre por cuerpos
│   └── ensambles/                XML, previews, colocaciones y ejes
├── scara/                        matemática, estados y TCP sin depender de Webots
├── client/                       programa externo e interfaz de navegador
├── webots/
│   ├── worlds/                   mundos que se abren en Webots
│   ├── protos/                   definición reutilizable del robot
│   └── controllers/              intérprete ejecutado por Webots
├── tools/                        programas para generar, extraer y comprobar
├── tests/                        comprobaciones automáticas de software
├── validation/                   resultados y capturas de ensayos
│   └── historico/banco_cajas/     fuentes e informes del banco anterior
└── docs/                         decisiones, proceso, fuentes y pendientes
```

### Archivos que se editan y archivos que se generan

Los **originales** son la referencia recibida. Los **fuentes** son programas o parámetros que editamos deliberadamente. Los **generados** son salidas de esos programas. Un **informe** explica de dónde salió una salida y qué se comprobó. Editar un generado para arreglar algo sin cambiar su fuente hace que el cambio desaparezca al regenerarlo.

| Archivo o grupo | Quién lo usa y qué hace | Qué editar o generar |
| --- | --- | --- |
| `config/scara.json` | Matemática, controlador y generador leen dimensiones, límites, cuerpos y fuentes. | Editar valores fundamentados; regenerar y repetir controles correspondientes. No tratar sus estimaciones como mediciones. |
| `config/cad_integration.json` | Integrador lee la referencia canónica, puntos locales, grupos y adiciones registradas. | Fuente de decisiones reversibles. Editar con evidencia y volver a integrar/generar; no cambia por sí sola los ceros físicos oficiales. |
| `tools/requirements-cad.txt` | Define versiones para el entorno CAD aislado. | No se necesita para usar cliente o Webots; cambiar versiones exige comprobar resultados. |
| `tools/convertir_cad.py` | Conversor y kernel procesan piezas y publican solo STL aceptados. | Fuente del pipeline. Genera `cad/derivados/step`, `stl` e `informe.json`. |
| `tools/patches/ole_ministreams.py` | Adaptador del lector interno usado en conversión/extracción. | No editar para forzar una pieza a pasar. Mantener licencia y NOTICE. |
| `tools/patches/comprobar_ministreams.py` | Contrasta extracción de bloques pequeños y lectura normal. | Ejecutar al cambiar el adaptador; necesita la fuente del conversor fijado. |
| `tools/extraer_ensamble.py` | Lee las referencias y transformaciones guardadas. | Genera `cad/ensambles/informe.json`, `xml/` y `previews/`. No editar a mano una matriz extraída para ocultar inconsistencias. |
| `tools/extraer_ejes_cad.py` | Analiza cilindros de STEP y cruza líneas entre piezas. | Genera `ejes_propuestos.json` y `evidencia_ejes_cilindros.json`; necesita OCP. |
| `tools/registrar_subensambles.py` | Busca un registro coherente entre snapshots usando piezas compartidas y versiones compatibles. | Genera `registro_subensambles.json`; conserva ambigüedades y no duplica automáticamente todos los componentes. |
| `cad/ensambles/registro_subensambles.json` | Integrador consulta las adiciones sustentadas por referencias y transformaciones. | Generado; si cambian sus fuentes, volver a registrar. No modificar a mano una propuesta para que parezca comprobada. |
| `cad/ensambles/criterios_integracion.json` | Registra las convenciones y evidencia geométrica de la integración inicial de 20 instancias. | Respaldo de decisiones, junto con `docs/INTEGRACION_CAD_CRITERIOS.md`; el manifiesto efectivo de 30 instancias es distinto. |
| `tools/integrate_cad.py` | Deriva marcos, referencias y matrices locales de las 30 instancias. | Genera `integracion_articulada.json`; con `--update-config` actualiza geometría y cajas de `config/scara.json`, conservando las masas exploratorias. |
| `cad/ensambles/integracion_articulada.json` | Generador y ensayos usan cada instancia, grupo, malla, matriz y fuente. | Manifiesto generado de la integración efectiva; no confundir con el informe de extracción XML. |
| `tools/exportar_torre_cuerpos.py` | Exporta/verifica los tres cuerpos de torre por separado. | Genera `torre_por_cuerpos/`; conserva crudos, derivados y reporte del filtro explícito. |
| `tools/calcular_propiedades_cad.py` | Integra volumen, centroide y tensor central BREP; coloca y agrega instancias en sus marcos. | Necesita OCP; genera los dos archivos de `cad/propiedades/`. No asigna densidad ni actualiza la física activa. |
| `cad/propiedades/propiedades_geometricas.json` y `.csv` | Informe trazable y tabla explorable por pieza/sólido/instancia/grupo. | Generados; consultar unidades, exclusiones y cobertura en `docs/PROPIEDADES_GEOMETRICAS_CAD.md`. No sumar las distintas vistas entre sí. |
| `tests/test_cad_properties.py` | Contrasta escala, tensor central, rotación y agregación con geometrías conocidas. | Dos pruebas sin OCP y tres adicionales en el entorno CAD; no necesita Webots. |
| `validation/cad_properties.json` | Guarda suite completa, contraste de BREP colocados en cinco grupos, tolerancias, hashes y preservación de entradas. | Evidencia de precálculo, separada de los ensayos nativos anteriores. Al cambiar el cálculo, regenerar resultados y repetir la validación pertinente. |
| `tools/generate_cad_preview.py` | Crea la vista estática, con colores por estado. | Genera `scara_cad_inspeccion.wbt` e `inspeccion_webots.json`; comprueba hashes y no sobrescribe el mundo dinámico. |
| `tools/generate_world.py` | Construye mundo y robot articulado desde parámetros y manifiesto CAD. | Editar la fuente si cambia la estructura; produce `scara.wbt` y `SCARA.proto`. |
| `webots/protos/SCARA.proto` | Webots instancia el robot y expone propiedades modificables de la herramienta. | Es generado. No es el lugar principal para editar permanentemente parámetros. |
| `webots/worlds/scara.wbt` | Webots abre la escena dinámica y su robot. | Es generado; conservar sus dependencias. |

| Archivo o grupo | Quién lo usa y qué hace | Qué editar o generar |
| --- | --- | --- |
| `scara/kinematics.py` | Cliente/tests resuelven directa, inversa y perfil articular; controlador aplica referencia. | Fuente matemática; comprobar límites y correspondencia al cambiar geometría. |
| `scara/frames.py` | Integrador y tests calculan las posiciones/orientaciones de los cinco cuerpos. | Fuente de transformaciones rígidas, independiente de Webots; no almacena propiedades materiales. |
| `scara/dynamics.py` | Generador/controlador calculan cajas equivalentes y combinación con carga. | Fuente física provisional; no sustituye propiedades CAD/materiales. |
| `scara/collisions.py` | Cajas de pieza y comprobación continua del segmento articular nominal frente al entorno. | Biblioteca estándar. Usa manifiesto CAD, entorno y margen/resolución de `config/scara.json`; no busca caminos alternativos ni usa sensores simulados. |
| `tools/check_collisions.py` | Diagnóstico CAD por BREP en once poses y contraste del guard del recorrido. | Requiere OCP; genera `validation/collisions.json`, no conecta con Webots. |
| `tools/check_collisions_native.py` | Rechazo TCP, cajas efectivas y contacto por gravedad en Webots. | Recarga el mundo de ensayo e inyecta pérdida de fuerza; permite `--port` y verificar una copia con `--snapshot-root`. |
| `tools/check_joint_stops.py` | Llegada y sostén de J4 en extremos e interior, con agregado en cada paso físico. | Requiere Webots y copia de ensayo identificada por `--snapshot-root`; recarga por escenario y guarda resultados aunque fallen. |
| `validation/j4_stops_before_every_step.json`, `j4_stops_after_*.json`, `j4_diagnosis.json` | Fallo reproducido, quince escenarios de sostén y trazabilidad del ajuste de integración. | Los experimentos `j4_experiment_*` son preliminares; los `j4_stops_after_*` usan todos los pasos físicos. |
| `tests/test_collisions.py` | Nueve regresiones de pedestal, trayectoria intermedia, margen, carga, Runtime, cliente y terminación del cálculo. | Sin OCP. Muestreo independiente complementa la cota continua, no la sustituye. |
| `validation/collisions.json`, `collision_tests.json`, `collisions_native.json` | Diagnóstico BREP, suite y ensayo nativo de la revisión de colisiones. | Informes con hashes; distinguir de la evidencia anterior preservada en `historico/antes_colisiones_20261015/`. |
| `scara/runtime.py` | Controlador conserva estados, objetivos, fallas, referencia y rearme. | Fuente de reglas del banco; no depende de APIs Webots. |
| `scara/transport.py` | Controlador atiende TCP sin bloquear la simulación. | Fuente del transporte provisional; delimita mensajes, limita tamaños y limpia sesiones perdidas. |
| `webots/controllers/scara_bridge/scara_bridge.py` | Webots lo inicia para recibir comandos y aplicar consignas a motores. | Fuente del adaptador nativo. Ejecutarlo mediante Webots, no instalando un paquete `controller`. |
| `client/app.py` | La terminal inicia HTTP local y el enlace TCP con Webots; resuelve la inversa. | Fuente del programa externo. No necesita dependencias de CAD. |
| `client/index.html` | El navegador muestra controles, estados y explicaciones. | Fuente HTML/CSS/JavaScript. No calcula ni inventa posición física. |
| `client/test_app.py`, `tests/test_*.py` | Python ejecuta las comprobaciones independientes. | Fuentes de prueba; no son archivos de Webots ni programas de usuario. |
| `tests/test_cad_integration.py` | Comprueba reconstrucción de poses y coherencia de ejes/TCP en configuraciones aleatorias. | Prueba matemática del montaje; no sustituye lectura de poses nativas ni un análisis de colisiones. |
| `tools/check_simulation.py` | Un cliente de ensayo recarga y prueba el mundo nativo. | Genera un informe; usa TCP e instrumentación interna, con la interfaz externa cerrada. |
| `tools/check_cad_motion.py` | Interroga poses CAD en Webots durante movimientos separados de J1–J4. | Genera `validation/cad_motion.json`; recarga el mundo y necesita exclusividad TCP. |
| `validation/cad_motion.json` | Conserva las once capturas nativas de estado, 330 colocaciones contrastadas y seis llegadas articulares. | Evidencia del modelo CAD articulado según sus hashes y tolerancias. |
| `validation/simulation.json` | Conserva la ejecución nativa de nueve comprobaciones. | Evidencia generada: cambios de fuentes requieren nueva corrida, no editar `passed`. |
| `validation/client_native.json` y capturas | Documentan la prueba visual e interfaz contra Webots. | Evidencia de una ejecución; no certifica todos los botones ni todos los destinos. |
| `cad/derivados/history/` | Conserva informes anteriores, incluyendo el lote 41 + 9. | Histórico; no confundir con el informe actual. |
| `validation/historico/banco_cajas/` | Conserva configuración, fuentes, mundo e informes de la versión anterior. | Evidencia histórica; no usar sus hashes y aprobaciones como si fueran del robot CAD actual. |
| Archivos `__init__.py` | Permiten que Python reconozca carpetas como paquetes. | No son programas que haya que abrir o ejecutar por separado. |

Los documentos tienen otra función: el [plan](PLAN_GEMELO_DIGITAL.md) registra acuerdos e hitos; [ENSAMBLE_CAD](ENSAMBLE_CAD.md) y [EVALUACION_CONVERSION_CAD](EVALUACION_CONVERSION_CAD.md) justifican el tratamiento de archivos; [INTEGRACION_CAD_CRITERIOS](INTEGRACION_CAD_CRITERIOS.md) explica agrupación, marcos y convenciones; [VALIDACION_WEBOTS](VALIDACION_WEBOTS.md) conserva alcance de ensayos; [DATOS_PARA_EL_PROFESOR](DATOS_PARA_EL_PROFESOR.md) reúne consultas; el [glosario](../GLOSSARY.md) define términos. El checkpoint es una memoria de continuación, no la especificación mecánica ni un manual para entregar por sí solo.

## 12. Cómo leer un informe sin saber programar

`informe.json` no es una pieza ni un programa. Es una tabla estructurada de datos que registra qué entrada se usó, qué herramienta la procesó, qué salida produjo y qué controles pasó o falló. Se puede abrir como texto; los documentos explicativos resumen sus campos relevantes.

| Término | Significado práctico |
| --- | --- |
| `source` | Archivo del que se obtuvo un dato. |
| `provenance` o procedencia | De dónde viene un valor: plano, CAD, cálculo, estimación o ensayo; permite saber qué falta confirmar. |
| `sha256` o hash | Huella calculada de los bytes de un archivo. Si cambia, ya no estamos hablando exactamente del mismo archivo. |
| `revision`, versión o build | Identificación del código o aplicación usada. Dos copias con el mismo nombre comercial pueden ser distintas. |
| `status` | Resultado según criterios declarados: aceptado, rechazado o pendiente. |
| `warnings` | Advertencias que deben revisarse aunque una salida haya sido aceptada. |
| `null` | Dato no asignado o no disponible; no significa cero. Por ejemplo, no inventar una masa donde aparece `mass_kg: null`. |
| Tolerancia | Diferencia máxima admitida para una comprobación concreta. No es automáticamente precisión del robot. |

Un hash **no prueba que la geometría sea correcta**: ayuda a comprobar que se utilizó el mismo archivo que se revisó. La procedencia y las pruebas geométricas aportan información distinta. Tampoco se debe presentar `status: passed` sin indicar qué se ensayó y con qué modelo.

Ejemplo para el informe: «Se utilizaron las mallas cuyos archivos coinciden con las huellas registradas en el reporte de conversión, y se contrastó su escala y volumen con los sólidos importados. Las piezas rechazadas se mantuvieron identificadas, sin sustituirlas por mallas reparadas silenciosamente».

## 13. Cómo reproducir cada etapa

No es necesario repetir las conversiones para abrir el resultado. Usar estos comandos solo al reconstruir una etapa o comprobar un cambio. Todos se ejecutan **desde la raíz de SCARA**. En Windows el Python habitual puede llamarse `python` y el del entorno CAD está en `.venv-cad/Scripts/python.exe`.

### Ejecutar y probar software ya preparado

```sh
python3 -m unittest discover -v
python3 -m client.app
```

El primer comando termina con el resultado de pruebas; el segundo deja un servidor abierto. Son acciones separadas. El [README](../README.md) explica cómo abrir el mundo y usar la interfaz.

### Regenerar el mundo dinámico

```sh
python3 tools/integrate_cad.py --update-config
python3 tools/generate_world.py
```

El primer comando reconstruye el manifiesto y actualiza geometría/cajas desde las decisiones CAD; el segundo genera el robot. Después abrir de nuevo el mundo y reiniciar el cliente si cambió la configuración. Repetir los controles pertinentes antes de atribuirle una validación anterior.

### Reconstruir conversión CAD

Se utilizó Python 3.12 en un entorno aislado; los paquetes CAD fijados soportan Python 3.11–3.14. Esto es independiente del Python 3.9 usado para cliente y controlador.

```sh
python3.12 -m venv .venv-cad
.venv-cad/bin/python -m pip install --only-binary=:all: -r tools/requirements-cad.txt
.venv-cad/bin/python -B tools/convertir_cad.py --converter-root /ruta/al/sldprt2step-revisado
```

La ruta debe contener por separado la revisión `fa954124f4f126e0c465c8f96454978ac80b812e` del conversor. El script comprueba su identidad y no lo descarga. La [evaluación CAD](EVALUACION_CONVERSION_CAD.md#reproducción) explica el origen, versiones y alternativas. Para probar una muestra, usar `--parts A-Brazo --output /ruta/a/salida-aislada`; no reemplazar el informe completo con un piloto.

### Reconstruir extracción, ejes y vista estática

```sh
python3 -B tools/extraer_ensamble.py --self-check
python3 -B tools/extraer_ensamble.py --converter-root /ruta/al/sldprt2step-revisado
.venv-cad/bin/python -B tools/extraer_ejes_cad.py
.venv-cad/bin/python -B tools/exportar_torre_cuerpos.py
python3 -B tools/generate_cad_preview.py --self-check
python3 -B tools/generate_cad_preview.py
python3 -B tools/registrar_subensambles.py --self-check
python3 -B tools/registrar_subensambles.py
python3 tools/integrate_cad.py --update-config
python3 tools/generate_world.py
```

La extracción necesita el informe de geometría existente y el lector revisado. Los análisis STEP necesitan OCP; generar la vista usa las mallas ya preparadas. Cambiar una fuente sin volver a extraer o verificar su informe puede producir un rechazo por hash distinto; es una protección contra mezclar versiones, no una instrucción para desactivar el control.

### Repetir ensayos nativos

Con **`scara.wbt` en reproducción, `client.app` cerrado y ningún otro cliente conectado**:

```sh
python3 tools/check_cad_motion.py --webots-version "versión y compilación reales" --output validation/cad-local.json
python3 tools/check_simulation.py --webots-version "versión y compilación reales" --output validation/ensayo-local.json
```

Son dos ejecuciones consecutivas: la primera comprueba colocaciones y descendientes; la segunda movimiento, carga, fallas y recuperación. Ambas recargan el mundo y terminan correctamente en la condición inicial `STOPPED`; no conservan la sesión de trabajo. No ejecutarlas contra un dispositivo real ni una vista estática. Una pausa de Webots pausa también la atención TCP de este controlador. Conservar una salida de ensayo nueva al cambiar el modelo y compararla con la anterior.

Los ensayos pueden usar **Fast**, manteniendo el paso físico configurado, actualmente **2 ms** tras el diagnóstico de J4: avanzan más segundos simulados por segundo de reloj, sin redefinir la duración física de los movimientos. Los informes anteriores usaban16ms; no mezclar sus hashes/resultados con la revisión actual. Las esperas usan tiempo simulado, separado del tiempo de pared para comunicación. Al finalizar, usar reproducción en tiempo real para observar e interactuar con el robot.

## 14. Cómo llevar esto al informe de la materia

Un relato técnico defendible puede seguir esta secuencia:

1. **Objetivo y alcance.** Simular el diseño entregado, sin hardware existente, conservando datos confirmados y supuestos reemplazables.
2. **Datos de entrada.** Inventario, revisión de documentos, discrepancias y primera comprobación independiente en Onshape.
3. **Tratamiento geométrico.** Conversión local, escala, controles de aceptación, resultados 44 + 6 y recuperación particular de torre.
4. **Reconstrucción del montaje.** Extracción de instancias y transformaciones, contraste de cajas, identificación de líneas de eje y límites de la caché guardada.
5. **Modelo articulado.** Selección de cuerpos, articulaciones, referencias y separación de representación visual, colisión y propiedades físicas. Incorporar la evidencia parcial de 30 instancias de la sección 10 y declarar sus supuestos.
6. **Control y comunicación.** Cinemática externa, perfil suave, intérprete Webots, estados y contrato provisional pendiente de adaptación al oficial.
7. **Fallas y recuperación.** Diferenciar inyección de diagnóstico, limitar esfuerzo sin desactivar física y justificar el reinicio cuando no hay referencia confiable.
8. **Validación.** Pruebas de software, ensayos nativos, tolerancias, resultados y huellas de archivos. Explicar qué demuestra cada nivel.
9. **Limitaciones y trabajo futuro.** Propiedades reales, protocolo, transmisiones, homing, colisiones, piezas pendientes y portabilidad comprobada en otros equipos.

Se pueden citar números y archivos guardados, evitando afirmaciones como «todos los modelos son exactos», «se reproduce el hardware» o «el robot tiene precisión de 0,0248 mm». La explicación correcta conecta el resultado con su evidencia y su alcance.

## 15. Pendientes reales

La documentación y los ensayos no eliminan los datos faltantes. Continúan pendientes la revisión mecánica coherente, el uso previsto de tres piezas que no aparecen activas en los ensambles guardados, geometrías rechazadas, agrupación de transmisiones, ceros/signos/TCP y propiedades materiales. Faltan el protocolo del profesor, homing y pérdidas de pasos, planificación de colisiones, atasco mecánico y desprendimiento. La ejecución nativa debe repetirse en Windows/Linux.

No hace falta pedir al grupo que mida manualmente cada colocación ya recuperada. Las consultas humanas se concentran en decisiones de cátedra, referencia oficial y propiedades ausentes. El [listado para el profesor](DATOS_PARA_EL_PROFESOR.md) reúne esas cuestiones, sin enviar mensajes en nombre del grupo.
