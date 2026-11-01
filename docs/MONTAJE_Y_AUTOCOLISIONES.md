# Montaje y choques entre piezas

Este documento explica las decisiones mecánicas del prototipo. El [manifiesto](../cad/ensambles/integracion_articulada.json) identifica las instancias efectivas y la [validación](VALIDACION_WEBOTS.md) centraliza cantidades, versiones y resultados ensayados. El montaje todavía no certifica cómo fabricar o ensamblar el robot real.

## Rodamientos y tapa de muñeca

Se muestran seis rodamientos simplificados: dos en base, dos en brazo y dos en muñeca. Son visuales que no animan los anillos por separado ni incorporan nuevas masas.

El montaje global guardado tenía `R-ContraBancada` girada media vuelta respecto de `R-EnsambleRotacion`. Sus lados son asimétricos: esa inversión explicaba un desfase de 3 mm entre alojamientos.

Usando `R-Bancada` como referencia del subensamble R, coinciden ambos rodamientos, los cuatro agujeros y las caras de apoyo. El prototipo adopta esa colocación ya guardada. No se desplazó la tapa 3 mm ni se retocó su forma. Falta confirmar revisión oficial y fijación de aros.

Respaldo: [diagnóstico de muñeca](../validation/wrist_bearing_diagnosis.json) y [consolidado de rodamientos](../validation/wrist_bearings.json).

## Poleas incorporadas y elección de la de muñeca

Las poleas de salida `2GT_80Teet_16Bore` y `2GT_60Teet_8Bore` acompañan al brazo y antebrazo, respectivamente. Se conservan las posiciones guardadas, con fijación y fase angular provisionales.

Para la polea `2GT_80Teet_40Bore` de muñeca se compararon dos colocaciones de ensambles distintos. La de B invade el escalón del buje unos 470,376 mm³. La de R apoya en el escalón local de 31 mm, coincide en diámetro de 40 mm y tiene 12 mm de acople axial, sin intersección positiva con seis vecinos revisados. Se adopta la pose R y se la vincula al cuerpo que gira con J3. No se acomoda a ojo ni se certifica que ese ajuste transmita el torque real.

El [diagnóstico de montaje restante](../validation/remaining_mounts.json) conserva ambas alternativas, mediciones y límites. Las [relaciones de transmisión](TRANSMISION.md) todavía no se aplican como una simulación completa de correas y rotores.

## Por qué siguen faltando piezas

Los ejes de torre y algunas poleas tienen colocaciones incompatibles entre snapshots. Los subconjuntos verticales tampoco proporcionan un registro global que conserve las identidades de revisión exigidas por el integrador. Se retienen esas alternativas en vez de mezclar revisiones silenciosamente.

M3 tiene una discrepancia concreta: el extensor indica salida Ø8 mm y el piñón revisado agujero Ø5 mm. En las colocaciones analizadas tienen 17 mm de solapamiento axial, pero los diámetros impiden ese montaje. El BREP del extensor es inválido; sus superficies solo sirven para diagnóstico, apoyado también por el plano. No se usa para masa o intersecciones aceptadas. La revisión vigente del conjunto debe aclararse.

Los tres piñones de motor y la transmisión interior requieren giros propios respecto de sus soportes. Pertenecer al ensamble no justifica fijarlos a la carcasa.

## Choques internos y protección disponible

Al plegar mucho el codo, el soporte puede entrar en la torre. Se comprobaron cuatro poses invasivas y el programa rechaza sus recorridos nominales, incluida la zona intermedia. También comprueba herramienta/carga contra la base fija y piezas móviles contra pedestal/piso, con cajas y margen de 1 mm.

La auditoría interna del montaje con polea de muñeca examinó 41 poses: mantiene las cuatro invasiones conocidas y registra 23 solapes iniciales de cajas sin volumen CAD intersectado. Estos falsos solapes ilustran por qué no se pueden activar contactos internos generales con las cajas actuales.

La comprobación de poses seleccionadas no cubre todo el movimiento. `selfCollision FALSE` mantiene desactivados los contactos internos generales. No hay protección continua de todos los pares ni garantía frente a una caída por pérdida de fuerza. El [documento de colisiones](COLISIONES_Y_RECORRIDOS.md) explica el algoritmo y sus límites.

## Pendientes mecánicos

Confirmar revisión oficial, fijaciones, fases, anillos de rodamientos, recorrido de correas, ejes y referencias. Mejorar formas de contacto donde una caja ocupa un hueco funcional. Completar materiales y propiedades comerciales antes de reemplazar la física provisional. Las [consultas para el profesor](historico/DATOS_PARA_EL_PROFESOR.md) reúnen las decisiones externas.
