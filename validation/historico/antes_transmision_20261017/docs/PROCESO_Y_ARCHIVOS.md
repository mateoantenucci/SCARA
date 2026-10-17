# Guía breve del proyecto SCARA

Estamos construyendo una simulación del diseño entregado por la cátedra. Como todavía no existe un robot físico, usamos sus piezas CAD, planos y documentos como referencia.

**Estado al 17/10/2026:** el robot simulado tiene cuatro articulaciones y **36 piezas colocadas, todas con geometría**. Algunas son copias de una misma pieza. Hay **47 archivos STL aceptados** en el lote de conversión; eso no significa que todos formen parte de este montaje. Los originales permanecen intactos y la física sigue siendo provisional.

El trabajo actual es **revisar el montaje y los choques entre las propias piezas del robot** (autocolisiones). Se muestran seis rodamientos simplificados. Para incorporar los dos de muñeca se corrigió una tapa invertida usando su colocación guardada en el subensamble. Se conserva el control de herramienta/carga frente a la base fija. La [revisión de montaje](MONTAJE_Y_AUTOCOLISIONES.md) sigue en curso.

## Para abrirlo

Seguí la [primera ejecución del README](../README.md#primera-ejecución-paso-a-paso). Ahí están los requisitos y los pasos para iniciar Python, Webots y la interfaz del navegador. No necesitás SolidWorks ni convertir piezas para probar lo ya preparado.

- [scara.wbt](../webots/worlds/scara.wbt): robot que se mueve, con física provisional y control desde el navegador.
- [scara_cad_inspeccion.wbt](../webots/worlds/scara_cad_inspeccion.wbt): vista fija para mirar las colocaciones recuperadas. No mueve el robot.

Conservá la carpeta completa: los mundos necesitan las piezas, el controlador y la configuración.

## Qué hicimos

1. **Recuperar las formas.** Convertimos piezas de SolidWorks a formatos que podemos revisar y mostrar en Webots. Las tres geometrías que faltaban en el robot actual ya se recuperaron.
2. **Recuperar las colocaciones.** Leímos dónde estaban guardadas las piezas en los ensambles, sin acomodarlas a ojo.
3. **Armar el robot móvil.** Agrupamos las piezas que se mueven juntas y las vinculamos a las cuatro articulaciones. El montaje todavía es parcial.
4. **Conectar y probar.** El navegador pide un destino; Python calcula los movimientos y Webots los simula. También se probaron fallas y recuperación.

**Ver una pieza no garantiza su comportamiento físico.** Su forma, los volúmenes usados para detectar choques y sus propiedades físicas son cosas distintas. Por ahora usamos aproximaciones para masas, fuerzas y contactos.

## Qué se comprobó

- La conversión, la escala y la geometría aceptada tienen controles registrados.
- Las piezas del montaje actual siguen los movimientos de sus articulaciones en Webots.
- Se probaron movimiento, comunicación, carga de ensayo y algunas fallas.
- Se rechazan recorridos nominales que invaden las envolventes del pedestal o el piso configurados.
- También se comprueba la separación nominal de herramienta y carga frente a la base fija.
- Se corrigió y volvió a ensayar la oscilación del eje vertical en su tope.

Estas pruebas describen **este modelo y los casos ensayados**. Todavía no comprueban todo el espacio de movimiento, los choques internos ni el comportamiento del robot que se pudiera fabricar. Los resultados y su alcance están en la [validación de Webots](VALIDACION_WEBOTS.md).

## Qué sigue y qué falta confirmar

1. **Montaje y autocolisiones:** revisar interferencias y agregar solo piezas cuya colocación tenga respaldo.
2. **Física fundamentada:** incorporar materiales, impresión, datos comerciales y transmisiones cuando estén confirmados.
3. **Comportamiento y entrega:** adaptar el protocolo del profesor, definir la búsqueda de referencia inicial (homing) y las fallas docentes, y probar en Windows y Linux.

Falta confirmar la revisión mecánica, los ceros, los topes, la herramienta y los sensores. Las preguntas están reunidas en [Datos para el profesor](DATOS_PARA_EL_PROFESOR.md).

## Qué leer según lo que necesites

No hace falta leer toda la documentación seguida. Empezá por esta guía y el README; abrí el resto cuando necesites ese tema.

| Necesidad | Documento |
| --- | --- |
| Abrir, mover y probar el robot | [README](../README.md) |
| Entender los acuerdos y próximos pasos | [Plan del gemelo digital](PLAN_GEMELO_DIGITAL.md) |
| Ver cómo se recuperaron las tres geometrías | [Recuperación de geometrías](RECUPERACION_GEOMETRIAS.md) |
| Consultar otras conversiones y sus límites | [Evaluación de conversión CAD](EVALUACION_CONVERSION_CAD.md) y [torre por cuerpos](../cad/derivados/torre_por_cuerpos/README.md) |
| Entender de dónde salen las colocaciones | [Ensamble CAD](ENSAMBLE_CAD.md) y [criterios de integración](INTEGRACION_CAD_CRITERIOS.md) |
| Revisar choques con el entorno | [Colisiones y recorridos](COLISIONES_Y_RECORRIDOS.md) |
| Revisar montaje e interferencias internas | [Montaje y autocolisiones](MONTAJE_Y_AUTOCOLISIONES.md) |
| Saber qué datos geométricos están calculados | [Propiedades geométricas CAD](PROPIEDADES_GEOMETRICAS_CAD.md) |
| Revisar las pruebas y fallas | [Validación Webots](VALIDACION_WEBOTS.md), [fallas](FALLAS_Y_VALIDACION.md) y [diagnóstico del eje vertical](DIAGNOSTICO_TOPE_J4.md) |
| Resolver una palabra desconocida | [Glosario](../GLOSSARY.md) |
| Consultar lo entregado por la cátedra | [Documento maestro](../00-SCARA-Master.pdf) y [consigna final](../CONSIGNA-TP-FINAL.pdf) |

La [explicación anterior completa](../validation/historico/antes_montaje_20261016/docs/PROCESO_Y_ARCHIVOS.md) se conserva como referencia histórica. Sus estados y cantidades corresponden a sus respectivas etapas.

## Dónde está cada cosa

| Carpeta | Contenido |
| --- | --- |
| `cad/` | Piezas convertidas, colocaciones recuperadas y propiedades calculadas. |
| `webots/` | Mundos, definición del robot y controlador de la simulación. |
| `client/` | Programa externo e interfaz del navegador. |
| `scara/` | Cálculos de movimiento y reglas de control. |
| `config/` | Parámetros y decisiones del modelo; varios siguen siendo provisionales. |
| `tools/` y `tests/` | Herramientas para generar archivos y comprobar cambios. |
| `validation/` | Resultados y capturas de los ensayos; `historico/` conserva etapas anteriores. |
| `docs/` | Guías, decisiones y preguntas pendientes. |

**No hace falta editar archivos para usar el proyecto.** Si se cambia el modelo, se modifican sus fuentes y se vuelven a generar las salidas correspondientes. Los informes de pruebas anteriores no validan automáticamente una versión nueva.
