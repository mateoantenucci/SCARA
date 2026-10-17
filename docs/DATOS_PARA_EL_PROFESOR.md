# Reunión con el profesor · SCARA

Guion para el **martes 20 de octubre de 2026**, todavía no enviado. Buscamos acordar la revisión del diseño y el contrato de evaluación. Los avances comprobados, su versión y sus límites están reunidos en [Validación](VALIDACION_WEBOTS.md). El [montaje](MONTAJE_Y_AUTOCOLISIONES.md) explica las elecciones del prototipo.

## Preguntas prioritarias y decisión que destraban

| Orden | Consulta concreta | Permite avanzar con |
| --- | --- | --- |
| 1 | **Revisión mecánica vigente.** Elegir ensamble/configuración y resolver M3 (extensor Ø8 frente a piñón Ø5, solapamiento axial de 17 mm), ejes de torre 30 mm más largos y variantes verticales. Confirmar fijaciones, fases de carreteles y correas. | Incorporar piezas retenidas y cerrar montaje/transmisión desde fuentes coherentes. |
| 2 | **Datos físicos.** Confirmar materiales e impresiones ya localizados y modelos de motores. Facilitar curvas y configuración de drivers: corriente por fase, alimentación y microstepping; datos de masa/distribución o medición por pieza y carga prevista. | Sustituir física provisional con datos respaldados. No pedimos de nuevo los nominales ya encontrados. |
| 3 | **Referencia y homing.** Fijar ceros, sentidos, topes, TCP, Hall/imanes/polaridad y secuencia segura desde posiciones iniciales permitidas, incluido sostén de J4. | Implementar búsqueda, retiro y aproximación lenta con límites y abortos. Recargar el mundo no hace homing. |
| 4 | **Protocolo oficial.** Pedir tramas completas de ida/vuelta: roles TCP, delimitación, unidades, comandos, estados, fin, cancelación, reconexión y política de vivacidad. | Adaptar intérprete y frontera de cinemática, con ejemplos oficiales de aceptación y error. |
| 5 | **Evaluación.** Acordar tarea, fallas exigidas, cobertura de autocolisión, tolerancias, entrega y sistemas operativos requeridos. | Fijar aceptación y próxima batería; distinguir falla inyectada de diagnóstico posible sin encoders. |

## Demostración breve

Usar el [arranque del README](../README.md), un solo cliente/mundo en reproducción, **reinicio limpio y carga 0 kg**. El guion dura unos tres minutos; la interfaz muestra milímetros y grados.

1. **Movimiento:** habilitar; X=240, Y=250, Z=35 mm, velocidad 30 %, orientación vacía. Esperar «Secuencia de consignas terminada» y comparar con «Simulador»: fin de consignas y llegada son observaciones distintas.
2. **Rechazo de choque:** desde esa llegada, X=73.2233, Y=176.7767, Z=34.6669 mm, orientación **0°**, 30 %. Debe avisar posible contacto de `Z-SoporteEfector-1` con `0-Torre-1` sin iniciar movimiento. Este objetivo está dentro del alcance; se rechaza por el recorrido y sus envolventes. La [demo renderizada del paquete final](../validation/sesion7/INFORME.md) confirmó el rechazo local del cliente antes de encolar TCP, con 91 muestras `IDLE` y consigna idéntica. El [caso equivalente por TCP en Webots](../validation/sesion4/final39_demo_collision.json) conserva por separado su rechazo y seis muestras sin iniciar movimiento.
3. **Una falla:** reiniciar, habilitar e inyectar **Hall J1 fijo activo**. Mostrar la señal de ensayo y el bloqueo del rearme. Limpiar fallas, mostrar que sigue «Detenido» sin rearme automático y habilitar explícitamente. Pulsar **Detener movimiento** al terminar; reiniciar ensayo no demuestra reparación ni referencia física.

## Datos que ya resolvimos

Las distancias J1–J2 y J2–J3 son de **250 mm entre ejes**. Recuperamos colocaciones, escalas, líneas de eje y marcos; no hace falta pedir medidas ni colocaciones manuales de todas las piezas. La polea CAD de muñeca tiene **80 dientes contados**: falta confirmar qué revisión rige frente al plano de 60.

Hay materiales nominales en maestro/planos y un perfil de impresión para la pareja A. Se pide confirmar su vigencia y completar datos efectivos; la [guía de propiedades](PROPIEDADES_GEOMETRICAS_CAD.md#materiales-nominales-ya-localizados) distingue esos nominales de las masas/inercias provisionales. Las relaciones nominales de transmisión ya están calculadas en [Transmisión](TRANSMISION.md); nosotros resolveremos cinemática y esfuerzos cuando se confirmen montaje y componentes.

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
| Polea de muñeca | CAD actual: **80 dientes contados en la geometría**; coincide con el maestro p. 12 | [Plano suelto](../Modelos3D/2GT_80Teet40Bore.PDF): descripción de 60 dientes | Confirmar qué revisión rige. El conteo del CAD actual ya está resuelto; falta decidir qué diseño representar. |
| Motor, extensor y piñón M3 | El extensor indica salida Ø8 mm; el piñón revisado agujero Ø5 mm | En el montaje analizado hay 17 mm de solapamiento axial incompatible por diámetro; el extensor tiene BREP inválido | Confirmar piezas y colocación de la transmisión M3. La diferencia de caja del NEMA17 entre caché y geometría también requiere revisión. [Diagnóstico](../validation/remaining_mounts.json). |
| Rodamientos de muñeca | Subensamble R y planos: asientos asimétricos | La tapa del ensamble global está invertida; de ahí salen los 3 mm de desfase | Resuelto en el prototipo usando la pose relativa guardada en R. Confirmar la revisión oficial y la fijación de aros; no se certifican materiales ni ajustes reales. |
| Ejes de la torre | Caché de `0-EnsambleTorre` | A-Eje y A-EjeInterior actuales son 30 mm más largos en bbox | Confirmar revisión; no estirar ni recortar las piezas para hacerlas coincidir. |
| Velocidad rotacional | Maestro p. 8: 4,44°/s | Misma celda: 266 rpm | Corrección de tabla. Esas magnitudes no son equivalentes; 4,44 también aparece como pasos/grado. |

El [maestro](../00-SCARA-Master.pdf) tiene versión 02/05/2026; varios planos sueltos son posteriores. Eso sugiere revisiones, pero no permite elegir silenciosamente una como definitiva.

La referencia activa de la polea en `R-EnsambleRotacion` es `2GT_80Teet_40Bore.SLDPRT`, disponible localmente. Confirmamos sus 80 dientes sin deducirlos del nombre. El [resumen de transmisión](TRANSMISION.md) reúne el contraste y las relaciones indicadas en el maestro; queda pendiente confirmar la revisión oficial.

## Consulta necesaria: transmisión y fases de los seis carreteles

La forma y los contactos permiten proponer una mitad a cada lado de las articulaciones. No alcanzan para certificar su fijación ni su fase angular. Por ahora adoptamos:

| Pareja | Mitad y cuerpo que acompaña en el prototipo |
| --- | --- |
| A | Inferior → base; superior → brazo |
| B | Superior → brazo; inferior → antebrazo |
| R | Inferior → antebrazo; superior → conjunto Z que gira |

Solicitar la función y la fijación efectiva de cada mitad, sus orientaciones de montaje y cómo se relacionan con el mecanismo de transmisión. Los canales anulares sugieren guiado de cables, pero esa función es una inferencia; no los confundimos con las poleas dentadas 2GT. Distintos snapshots conservan fases angulares distintas, por lo que no giramos piezas para alinear tornillos sin evidencia. Conservamos la pose guardada y la asignación es reversible.

El maestro p. 11–12 describe reducciones 4:1 para M1–M3, una etapa 60→60 hacia el codo y avance ACME de 8 mm/vuelta. Para aplicarlas falta confirmar la configuración vigente, fijaciones, recorrido de correas, signos y microstepping. Nosotros calculamos las relaciones y el acoplamiento M1/M2 a partir de ese montaje; no se necesita que la cátedra derive la cinemática.

## Consulta necesaria: propiedades físicas, sensores y comunicación

| Tema | Información externa que falta | Qué seguimos resolviendo nosotros |
| --- | --- | --- |
| Materiales y masas | Confirmar las indicaciones nominales ya localizadas (acero/aluminio, PLA y relleno en piezas concretas) y completar material/densidad por pieza o sólido; impresiones con paredes, tapas, patrón/relleno e inserciones; modelo exacto, masa y distribución/COM/inercia de componentes comerciales; tornillería, correas, cables y otros elementos no representados, con ubicación/cantidad. El porcentaje de relleno no equivale directamente a igual porcentaje de densidad maciza. | El precálculo conserva V, centroide y tensor por densidad con cobertura identificada por revisión. Agregaremos por masa/material sin duplicar ocurrencias ni tratar motores como sólidos homogéneos; completar geometría y comprobar cobertura/solapamientos antes de sustituir las cajas. |
| Motores y esfuerzo | Fichas/curvas de los modelos vigentes, corriente y alimentación de drivers, microstepping y cualquier dato conocido de pérdidas/fricción. El maestro identifica Minebea 23KM-K381-P1 para M1/M2, Shinano Kenshi STP-42D221-03 para M3 y 42D265 para M4; confirmar esa selección. | Buscar documentación del modelo confirmado, derivar torque/fuerza tras la transmisión y construir una aproximación parametrizada. NEMA indica tamaño, no torque disponible; una velocidad sin carga no es un límite validado bajo carga. |
| Hall y homing | Posición y orientación de sensores/imanes, lógica de activación y procedimiento previsto para encontrar ceros y extremos. El maestro p. 14 prevé Hall de comienzo/fin y ausencia de encoders; confirmar la configuración vigente. | Ubicar referencias desde el CAD cuando existan y simular activaciones/fallas. Los ceros oficiales no se deducen de una pose guardada. |
| TCP y herramienta | Punto y orientación oficiales de herramienta, herramienta prevista y carga nominal si ya se definieron. | Usar provisionalmente el centro de la cara exterior de Z-SoporteEfector, sin pinza. La pose guardada se reproduce con J4 a 60 mm por convención; no se presenta como home medido. Adaptar el marco cuando se defina el TCP oficial. |
| Protocolo TCP/IP | Especificación del profesor y ejemplos de ida/vuelta: rol cliente/servidor, codificación y delimitación, unidades/referencias, comandos, aceptación y fin, estados, errores, cancelación y reconexión. Incluir las reacciones esperadas ante fallas si forman parte del contrato. | Ya hay cliente externo e intérprete en Webots para experimentar. El contrato provisional `scara-dev/1` permite avanzar; adaptaremos el intérprete y la frontera de cálculo al contrato oficial. Si pide XYZ en vez de articulaciones, habrá que acordar dónde se resuelve la cinemática. |

Estas consultas no detienen la integración visual ni el movimiento. Seguimos con las colocaciones y ejes recuperados, el marco canónico elegido, el TCP provisional, la pertenencia visual propuesta de carreteles y parámetros físicos explícitos. Podemos implementar escenarios de fallas y comprobar coherencia matemática/reproducibilidad; su equivalencia con el comportamiento real queda pendiente de especificaciones o ensayos futuros. Ningún supuesto se presenta como dato medido ni como validación experimental de un robot todavía no disponible.
