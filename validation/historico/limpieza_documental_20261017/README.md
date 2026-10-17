# Limpieza documental del 17 de octubre de 2026

Se revisaron los 22 documentos explicativos del árbol principal, la consigna, el maestro y el inventario de planos originales. Se contrastaron implementación y evidencias de conversión, propiedades, montaje y ensayos. Los PDF originales, CAD, programas, configuración y resultados de pruebas se conservan; esta limpieza modifica documentación.

La lectura empieza en [Entender el proyecto desde cero](../../../docs/PROCESO_Y_ARCHIVOS.md). El [README](../../../README.md) sirve para operar, el [plan](../../../docs/PLAN_GEMELO_DIGITAL.md) conserva acuerdos y [validación](../../../docs/VALIDACION_WEBOTS.md) centraliza versiones y resultados. Los documentos especializados conservan métodos, decisiones, fórmulas y límites útiles para el informe y la defensa.

## Qué se limpió

Se retiraron cabeceras acumuladas de avances, pendientes superados, IDs de sesiones/pestañas, estados de procesos y rutas temporales caducables. Se consolidaron la guía inicial, el checkpoint y las explicaciones repetidas. Las comparativas comerciales de herramientas dejaron lugar a un índice de las fuentes técnicas usadas.

La agenda todavía usada por la ronda paralela se trasladó a `.agent-state/`, sin eliminar su coordinación. No es parte de la documentación técnica para estudiar o entregar. Los snapshots históricos anteriores no se reescribieron: conservan la identidad y contexto de los ensayos; su [índice](../README.md) los separa de la lectura vigente.

Durante la revisión, el chat de coordinación agregó la polea de muñeca. Sus informes de 39 instancias se incorporaron explícitamente al índice de validación; el precálculo guardado de 38 y las baterías anteriores mantienen su alcance, sin atribuirles resultados nuevos. También se incorporaron los materiales nominales encontrados en planos y G-code, que no equivalen a propiedades físicas activadas.

## Inventario de decisiones documentales

| Documento anterior | Tratamiento |
| --- | --- |
| `README.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `GLOSSARY.md` | Conservado: referencia durable, sin cambios. |
| `docs/CHECKPOINT_CONTINUAR.md` | Retirado; contenido durable integrado en la guía y documentos temáticos. Original en respaldo. |
| `docs/COLISIONES_Y_RECORRIDOS.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/DATOS_PARA_EL_PROFESOR.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/DIAGNOSTICO_TOPE_J4.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/ENSAMBLE_CAD.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/EVALUACION_CONVERSION_CAD.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/FALLAS_Y_VALIDACION.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/FUENTES_CAD_WEBOTS.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/GUIA_PROYECTO_SCARA_WEBOTS.md` | Retirado; contenido durable integrado en la guía y documentos temáticos. Original en respaldo. |
| `docs/INTEGRACION_CAD_CRITERIOS.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/MONTAJE_Y_AUTOCOLISIONES.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/PLAN_GEMELO_DIGITAL.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/PROCESO_Y_ARCHIVOS.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/PROPIEDADES_GEOMETRICAS_CAD.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/RECUPERACION_GEOMETRIAS.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/SESIONES_HASTA_EL_PROFESOR.md` | Trasladado a .agent-state/ronda-profesor-20261017/SESIONES.md; agenda operativa activa, fuera de lectura. |
| `docs/TRANSMISION.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/VALIDACION_WEBOTS.md` | Depurado o consolidado; ver función de lectura en la guía. |
| `docs/adr/0001-simulacion-del-diseno-sin-hardware.md` | Conservado: referencia durable, sin cambios. |
| `cad/derivados/torre_por_cuerpos/README.md` | Conservado: referencia durable, sin cambios. |

## Respaldo y comprobación

`documentacion_anterior.tar.gz` conserva los 22 documentos antes de la limpieza; `fuentes_sha256.json` registra sus huellas. `checkpoint_antes_retiro.tar.gz` conserva además la última actualización del checkpoint recibida durante la coordinación. Para recuperar, extraer en una carpeta aparte y comparar antes de sustituir los archivos actuales.

Se comprueban enlaces locales y anclas de la documentación de lectura. Las fuentes de los informes nativos de la ampliación de muñeca se contrastan con la carpeta de trabajo. Esta revisión documental no ejecuta de nuevo Webots ni declara cerradas pruebas de comportamiento, contactos o portabilidad que la ronda técnica aún esté preparando.

Resultado de comprobación al cierre de la limpieza: **262 enlaces locales y sus dos anclas explícitas válidos**, bloques de código cerrados y **22/22 documentos del respaldo con SHA-256 coincidente**. La documentación principal pasó de 2569 a 1819 líneas, con una guía de comprensión más completa.
