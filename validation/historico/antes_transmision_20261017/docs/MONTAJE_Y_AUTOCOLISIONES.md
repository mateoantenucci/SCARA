# Montaje y choques entre piezas

Actualizado el 17 de octubre de 2026. El robot tiene **36 piezas colocadas**, con los dos rodamientos de muñeca que faltaban. El montaje sigue siendo un prototipo: todavía no certifica cómo fabricar o ensamblar el robot real.

## Qué agregamos

Ahora se ven **seis rodamientos: dos en la base, dos en el brazo y dos en la muñeca**. Los últimos son `Z6907`.

Son representaciones visuales: no animamos sus anillos por separado ni sumamos masas. La configuración física no cambió; masas y esfuerzos siguen siendo provisionales.

## Por qué parecían no encajar

El montaje general guardado tenía `R-ContraBancada` girada **media vuelta** respecto del montaje de muñeca. Sus dos lados no son iguales, y esa inversión explicaba el desfase de 3 mm entre los alojamientos.

En `R-EnsambleRotacion`, usando `R-Bancada` como referencia, ambos rodamientos encajan, coinciden los cuatro agujeros y las caras de apoyo se encuentran. Lo contrastamos con el CAD y los planos.

Para el prototipo usamos **esa colocación ya guardada en el subensamble**. No desplazamos la pieza 3 mm ni retocamos su forma. La diferencia respecto del montaje general queda registrada; los originales siguen intactos y falta confirmar la revisión mecánica oficial.

## Qué choque encontramos y cómo se evita

Al plegar mucho el codo, el soporte de la herramienta puede entrar en la torre. Lo comprobamos en cuatro posiciones del modelo.

Ahora el programa **rechaza el recorrido antes de mover** si la herramienta o la carga de ensayo pueden tocar la base fija. También revisa el tramo intermedio: que el inicio y el destino estén libres no alcanza. Se mantienen las comprobaciones contra pedestal y piso.

El control usa formas simplificadas y un margen de 1 mm. Puede rechazar algún movimiento que la geometría real permitiría. Si un motor pierde fuerza, este control previo no garantiza evitar un choque.

## Qué comprobamos en esta revisión

| Comprobación | Resultado |
| --- | --- |
| Montaje de muñeca | Alojamientos, agujeros y apoyos coinciden con la colocación elegida. |
| Montaje en movimiento | Las 36 piezas conservan la colocación prevista; seis llegadas comprobadas en Webots. |
| Revisión interna | 41 posiciones revisadas; siguen las cuatro invasiones conocidas entre soporte y torre, rechazadas por el control. No aparecieron otras nuevas. |
| Software | 33 pruebas aprobadas, sin omisiones. |
| Contactos y rechazos en Webots | Seis comprobaciones aprobadas: incluye torre, pedestal, caída por pérdida de fuerza y reinicio. |

Los resultados cubren los casos ensayados. Todavía no demuestran que todo el espacio de movimiento esté libre de choques.

## Qué sigue

- **Uniones y revisión mecánica:** validar la revisión oficial y confirmar qué anillo de cada rodamiento se fija a cada pieza.
- **Poleas y transmisión:** falta confirmar qué gira con cada motor y cómo está conectado.
- **Propiedades físicas:** incorporar materiales, impresión y datos comerciales confirmados.
- **Otros choques internos:** todavía no se comprueban continuamente todos los pares de piezas ni los componentes omitidos.
- **Contactos físicos internos:** las cajas actuales ocupan también huecos del montaje. Activarlos indiscriminadamente produciría choques falsos; hay que representar mejor esas zonas.

Las decisiones que necesitan confirmación siguen reunidas en [Datos para el profesor](DATOS_PARA_EL_PROFESOR.md).

## Respaldo para consultar cuando haga falta

**Revisión actual, 17/10:** [resumen](../validation/wrist_bearings.json) · [diagnóstico de muñeca](../validation/wrist_bearing_diagnosis.json) · [movimiento en Webots](../validation/cad_motion_wrist.json) · [contactos y rechazos](../validation/collisions_native_wrist.json) · [revisión interna](../validation/self_collisions_wrist.json).

**Etapa anterior, 16/10:** [resumen histórico](../validation/mounting.json).

Los informes guardan mediciones y fuentes para repetir el trabajo. No hace falta leerlos para usar el robot. Para abrirlo, seguí el [README](../README.md); para entender las carpetas, la [guía breve](PROCESO_Y_ARCHIVOS.md).
