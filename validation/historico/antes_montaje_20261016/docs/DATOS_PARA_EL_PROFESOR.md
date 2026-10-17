# Consultas necesarias para completar el SCARA

Fecha: 14 de octubre de 2026. Borrador para la cátedra; no enviado. Las preguntas se concentran en información ausente o contradictoria, no en tareas que podemos resolver leyendo CAD o desarrollando software.

Actualización 15/10/2026: ya calculamos propiedades geométricas de 46 tipos / 48 sólidos válidos y de 27/30 instancias. Los 50 originales contienen la etiqueta «Material <sin especificar>»; no se obtuvo material/densidad confirmado. [Método, resultados y límites](PROPIEDADES_GEOMETRICAS_CAD.md). No hace falta pedir que se calculen manualmente volúmenes e inercias geométricas ya recuperables.

## Estado que podemos mostrar y datos ya resueltos

El modelo articulado integra **30 instancias: 27 con geometría y tres con cajas de alambre rotuladas**. Parte de las 20 instancias de `0-EnsambleColision` y suma diez montajes/carcazas registrados desde otros subensambles: cuatro soportes de base, dos NEMA23, dos B-SoporteRuleman, B-SoporteEjeFijo y B-SoporteM3. Las instancias repetidas son montajes distintos; esto todavía no representa las 50 piezas y todas sus cantidades. Evidencia en el [manifiesto articulado](../cad/ensambles/integracion_articulada.json).

| Resultado | Certeza y alcance |
| --- | --- |
| J1–J2 y J2–J3: **250 mm entre ejes** | Alto para las geometrías disponibles: calculado desde superficies cilíndricas CAD y contrastado entre piezas/ensambles. Los 237 mm del caño de antebrazo no son su longitud cinemática. No necesitamos que se vuelva a medir. |
| Colocaciones de las piezas y líneas de articulación | Recuperadas de los archivos y contrastadas numéricamente; no hay que reconstruirlas a mano. Las diez adiciones son un registro de poses guardadas coherentes, no una certificación de todos los mates o revisiones. |
| Escala y coordenadas del modelo móvil | Resueltas por nosotros: metros, Z hacia arriba, base en el suelo y transformación que conserva la pose CAD. Los anchors siguen las líneas de los agujeros. Es una convención reversible, no el cero mecánico oficial. |
| Agrupación estructural | Suficiente para articular el prototipo. Las seis mitades de carretel tienen pertenencia visual provisional, explicada abajo. Los NEMA23 se muestran como carcasas completas; sus ejes internos aún no se animan. |
| Dinámica | Cuatro cuerpos móviles con masas, centros, inercias y esfuerzos exploratorios. Precálculo geométrico disponible para 27 instancias; aplicar masas/inercias requiere materiales, completar componentes y resolver exclusiones. |

Los detalles y las comprobaciones se conservan en [ENSAMBLE_CAD.md](ENSAMBLE_CAD.md) e [INTEGRACION_CAD_CRITERIOS.md](INTEGRACION_CAD_CRITERIOS.md). La torre se incorporó mediante sus tres cuerpos validados por separado, con eliminación explícita de ocho triángulos de área exactamente cero; no se declara validada su unión como una sola malla.

## Consulta necesaria: revisión del diseño y geometrías pendientes

1. **Referencia mecánica vigente:** indicar qué ensamble/configuración y revisión deben representar la entrega, especialmente para resolver las contradicciones de la tabla siguiente. Recuperamos los diez ensambles existentes, pero ninguno contiene como dependencias a los otros nueve; hay poses y geometrías de distintas revisiones. Si existe un maestro consistente con sus dependencias, un Pack and Go y/o STEP de ese maestro sería útil. No se solicita medir ni colocar manualmente cada pieza.
2. **Contraste opcional de tres geometrías recuperadas:** `B-CarretelInf`, `B-CarretelSup` y `Z-SoporteEfector` ya superan las comprobaciones después de corregir la precisión del conversor; no bloquean la visualización. Si están disponibles, facilitar un STEP sólido por pieza de la revisión/configuración indicada, con unidades explícitas y origen/orientación local conservados. Un STL adicional debe declarar unidades y tolerancias. Sirve para contrastar fidelidad y revisión: en Z hay stamps guardados 191/196 con la misma bbox. El [diagnóstico y pedido concreto](RECUPERACION_GEOMETRIAS.md) detalla la comparación necesaria; no se atribuye daño a los nativos.

## Discrepancias mecánicas identificadas

| Elemento | Fuente A | Fuente B o vacío | Dato solicitado y efecto |
| --- | --- | --- | --- |
| Cuerpo vertical | Maestro p. 20: 200 mm | [Z-Cuerpo.PDF](../Modelos3D/Z-Cuerpo.PDF): 190 mm | Revisión vigente; cambia geometría, masa y alturas. |
| Pistón | Maestro p. 21: 175 mm | [Z-Piston.PDF](../Modelos3D/Z-Piston.PDF): 180 mm | Revisión vigente; cambia masa y extremos de carrera. |
| Varilla ACME | Maestro p. 12: 120 mm más encastres | [Z-VarillaACME.PDF](../Modelos3D/Z-VarillaACME.PDF): 200 mm; geometría nativa actual convertida: 195 mm totales | Revisión vigente del tornillo. No confundir su longitud con el recorrido nominal de 120 mm. |
| Buje exterior | Maestro p. 22 | [Plano suelto](../Modelos3D/Z-BujeExterior.PDF) con otra geometría | Qué revisión corresponde al diseño final. |
| Carreteles A | [A-Carreteles.PDF](../Modelos3D/A-Carreteles.PDF): agujeros centrales Ø35/40 mm | Geometría nativa actual: Ø16/17 mm | Confirmar revisión; cambia el ajuste con eje/brida y la interpretación del montaje. |
| Polea de muñeca | Archivo [2GT_80Teet40Bore.PDF](../Modelos3D/2GT_80Teet40Bore.PDF): nombre 80Teet | Descripción del plano dice 60 dientes | Cantidad efectiva de dientes y relación de transmisión. |
| Motores NEMA17 | Caché de ensambles: caja envolvente de 42 mm en dos direcciones | Pieza actual: 45 mm en una de ellas, diferencia de 3 mm | Confirmar modelo/revisión comercial; la diferencia de caja no permite atribuir por sí sola un cambio al cuerpo del motor. |
| Ejes de la torre | Caché de `0-EnsambleTorre` | A-Eje y A-EjeInterior actuales son 30 mm más largos en bbox | Confirmar revisión; no estirar ni recortar las piezas para hacerlas coincidir. |
| Velocidad rotacional | Maestro p. 8: 4,44°/s | Misma celda: 266 rpm | Corrección de tabla. Esas magnitudes no son equivalentes; 4,44 también aparece como pasos/grado. |

El [maestro](../00-SCARA-Master.pdf) tiene versión 02/05/2026; varios planos sueltos son posteriores. Eso sugiere revisiones, pero no permite elegir silenciosamente una como definitiva.

La referencia activa de la polea en el XML guardado de `R-EnsambleRotacion` es `2GT_80Teet_40Bore.SLDPRT`, disponible localmente. El nombre antiguo de 60 dientes no era una dependencia activa faltante; solo queda aclarar la contradicción de dientes en el plano.

## Consulta necesaria: transmisión y fases de los seis carreteles

La forma y los contactos permiten proponer una mitad a cada lado de las articulaciones. No alcanzan para certificar su fijación ni su fase angular. Por ahora adoptamos:

| Pareja | Mitad y cuerpo que acompaña en el prototipo |
| --- | --- |
| A | Inferior → base; superior → brazo |
| B | Superior → brazo; inferior → antebrazo |
| R | Inferior → antebrazo; superior → conjunto Z que gira |

Solicitar la función y la fijación efectiva de cada mitad, sus orientaciones de montaje y cómo se relacionan con el mecanismo de transmisión. Los canales anulares sugieren guiado de cables, pero esa función es una inferencia; no los confundimos con las poleas dentadas 2GT. Distintos snapshots conservan fases angulares distintas, por lo que no giramos piezas para alinear tornillos sin evidencia. Conservamos la pose guardada y la asignación es reversible.

Para el paso de motores a articulaciones también hace falta confirmar la configuración vigente de poleas, signos, acoplamiento M1/M2 y microstepping. Nosotros calculamos las relaciones a partir de esa configuración; no se necesita que la cátedra derive la cinemática.

## Consulta necesaria: propiedades físicas, sensores y comunicación

| Tema | Información externa que falta | Qué seguimos resolviendo nosotros |
| --- | --- | --- |
| Materiales y masas | Material/densidad por pieza o sólido; impresiones con paredes, tapas, patrón/relleno e inserciones; modelo exacto, masa y distribución/COM/inercia de componentes comerciales; tornillería, correas, cables y otros elementos no representados, con ubicación/cantidad. El porcentaje de relleno no equivale directamente a igual porcentaje de densidad maciza. | Ya están V, centroide y tensor por densidad de 46 tipos / 48 sólidos y 27/30 instancias. Agregaremos por masa/material sin duplicar ocurrencias ni tratar motores como sólidos homogéneos; completar geometría y comprobar cobertura/solapamientos antes de sustituir las cajas. |
| Motores y esfuerzo | Fichas/curvas de los modelos vigentes, corriente y alimentación de drivers, microstepping y cualquier dato conocido de pérdidas/fricción. El maestro identifica Minebea 23KM-K381-P1 para M1/M2, Shinano Kenshi STP-42D221-03 para M3 y 42D265 para M4; confirmar esa selección. | Buscar documentación del modelo confirmado, derivar torque/fuerza tras la transmisión y construir una aproximación parametrizada. NEMA indica tamaño, no torque disponible; una velocidad sin carga no es un límite validado bajo carga. |
| Hall y homing | Posición y orientación de sensores/imanes, lógica de activación y procedimiento previsto para encontrar ceros y extremos. El maestro p. 14 prevé Hall de comienzo/fin y ausencia de encoders; confirmar la configuración vigente. | Ubicar referencias desde el CAD cuando existan y simular activaciones/fallas. Los ceros oficiales no se deducen de una pose guardada. |
| TCP y herramienta | Punto y orientación oficiales de herramienta, herramienta prevista y carga nominal si ya se definieron. | Usar provisionalmente el centro de la cara exterior de Z-SoporteEfector, sin pinza. La pose guardada se reproduce con J4 a 60 mm por convención; no se presenta como home medido. Adaptar el marco cuando se defina el TCP oficial. |
| Protocolo TCP/IP | Especificación del profesor y ejemplos de ida/vuelta: rol cliente/servidor, codificación y delimitación, unidades/referencias, comandos, aceptación y fin, estados, errores, cancelación y reconexión. Incluir las reacciones esperadas ante fallas si forman parte del contrato. | Ya hay cliente externo e intérprete en Webots para experimentar. El contrato provisional `scara-dev/1` permite avanzar; adaptaremos el intérprete al contrato oficial, sin trasladar la planificación al controlador. |

Estas consultas no detienen la integración visual ni el movimiento. Seguimos con las colocaciones y ejes recuperados, el marco canónico elegido, el TCP provisional, la pertenencia visual propuesta de carreteles y parámetros físicos explícitos. Podemos implementar escenarios de fallas y comprobar coherencia matemática/reproducibilidad; su equivalencia con el comportamiento real queda pendiente de especificaciones o ensayos futuros. Ningún supuesto se presenta como dato medido ni como validación experimental de un robot todavía no disponible.
