# Montaje y choques entre piezas

Actualizado el 16 de octubre de 2026. El robot tiene **34 piezas colocadas**. Este avance mejora el montaje y evita un choque encontrado, pero todavía no completa la revisión de todos los movimientos posibles.

## Qué agregamos

Se incorporaron **cuatro rodamientos: dos en la base y dos en el brazo**. Sus posiciones y alojamientos coinciden con los archivos disponibles.

Se muestran de forma simplificada: no animamos sus anillos por separado ni les sumamos una masa nueva. Las masas y los esfuerzos del robot siguen siendo provisionales.

## Qué choque encontramos y cómo se evita

Al plegar mucho el codo, el soporte de la herramienta puede entrar en la torre. Lo comprobamos en cuatro posiciones del modelo.

Ahora el programa **rechaza el recorrido antes de mover** si la herramienta o la carga de ensayo pueden tocar la base fija. También revisa el tramo intermedio: que el inicio y el destino estén libres no alcanza. Se mantienen las comprobaciones contra pedestal y piso.

El control usa formas simplificadas y un margen de 1 mm. Puede rechazar algún movimiento que la geometría real permitiría. Si un motor pierde fuerza, este control previo no garantiza evitar un choque.

## Qué comprobamos

| Comprobación | Resultado |
| --- | --- |
| Montaje en movimiento | Las 34 piezas acompañan a sus articulaciones; seis llegadas comprobadas en Webots. |
| Revisión interna | 41 posiciones revisadas; cuatro invasiones entre soporte y torre, rechazadas por el control. |
| Software | 32 pruebas aprobadas, incluidas las nuevas de torre y cruce intermedio. |
| Contactos y rechazos en Webots | Seis comprobaciones aprobadas: incluye torre, pedestal, caída por pérdida de fuerza y reinicio. |

En las posiciones inicial y guardada, y en los extremos verticales de la posición inicial, no encontramos invasiones entre piezas de cuerpos distintos. Esto no demuestra que todo el espacio de trabajo esté libre.

## Qué queda pendiente

- **Dos rodamientos de muñeca:** sus alojamientos aparecen desplazados 3 mm entre los archivos. No los añadimos ni movimos piezas a ojo.
- **Poleas y transmisión:** falta confirmar qué gira con cada motor y cómo está conectado.
- **Otros choques internos:** todavía no se comprueban continuamente todos los pares de piezas ni los componentes omitidos.
- **Contactos físicos internos:** las cajas actuales ocupan también huecos del montaje. Activarlos indiscriminadamente produciría choques falsos; hay que representar mejor esas zonas.

La consulta sobre el desfase de 3 mm quedó agregada a [Datos para el profesor](DATOS_PARA_EL_PROFESOR.md). El próximo trabajo es resolver esas uniones y mejorar la representación de contacto antes de ampliar la protección interna.

## Respaldo para consultar cuando haga falta

[Resumen de esta revisión](../validation/mounting.json) · [Colocación de rodamientos](../validation/mounting_evidence.json) · [Revisión interna](../validation/self_collisions.json) · [Movimiento en Webots](../validation/cad_motion_mounting.json) · [Contactos y rechazos](../validation/collisions_native_mounting.json).

Los informes guardan mediciones y fuentes para repetir el trabajo. No hace falta leerlos para usar el robot. Para abrirlo, seguí el [README](../README.md); para entender las carpetas, la [guía breve](PROCESO_Y_ARCHIVOS.md).
