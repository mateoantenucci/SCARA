# Recuperación del ensamble CAD

Este documento explica la extracción de colocaciones y la vista estática. La [integración móvil](INTEGRACION_CAD_CRITERIOS.md) utiliza esas fuentes y añade componentes revisados de otros conjuntos. El manifiesto efectivo y los ensayos se consultan desde [Validación](historico/VALIDACION_WEBOTS.md).

Se recuperaron **106 instancias guardadas de los diez `.SLDASM`**, con archivo de origen, configuración, identificador, visibilidad y matriz de colocación. No fue necesario SolidWorks, Onshape ni otra conversión de piezas. La fuente es el XML comprimido que SolidWorks dejó dentro de cada archivo: **no se resolvieron restricciones ni se reconstruyó el ensamble con las revisiones actuales de todas las piezas**.

El resultado concreto es el mundo estático [scara_cad_inspeccion.wbt](../webots/worlds/scara_cad_inspeccion.wbt), generado desde `0-EnsambleColision`. Es el conjunto local que reúne torre, brazo, antebrazo y mecanismo Z; no se lo declara ensamble maestro oficial. Conserva exactamente la pose y el marco guardados. El mundo dinámico `scara.wbt` sigue separado.

**La vista global tiene 20 instancias de 19 piezas distintas, no las 50 piezas ni todas sus instancias.** Los diez ensambles juntos ubican 47 piezas distintas en sus propios marcos; tres archivos nunca aparecen activos en sus árboles: `2GT_80Teet_8Bore.SLDPRT`, `BorneraX6.SLDPRT` y `KY-003.SLDPRT`. La ausencia no prueba que sean innecesarios para el diseño final.

Hay 28 tipos de pieza ubicados en los otros conjuntos pero ausentes de la vista global: base inferior, motores NEMA23, ejes/poleas/rodamientos, soportes de brazo y antebrazo y componentes internos de Z. Se pueden estudiar registros entre conjuntos usando piezas compartidas, pero no superponerlos como si fueran un mismo estado: comparten piezas móviles, contienen poses distintas, revisiones mezcladas y copias repetidas. Falta confirmar qué snapshot mecánico debe reunirlos y qué piezas pertenecen a cada cuerpo. No se agregaron instancias mediante relaciones ambiguas ni se declaró un ensamble completo.

## Qué se recuperó y cómo se comprobó

[tools/extraer_ensamble.py](../tools/extraer_ensamble.py) lee el contenedor con el lector CFB y adaptador MiniFAT revisados. El stream `COMPINSTANCETREE__ZLB` tiene un encabezado de 24 bytes, datos zlib y un trailer de ocho bytes nulos. Se contrastan tamaños declarados, descompresión completa, límite de tamaño y estructura XML; no se buscan matrices mediante patrones heurísticos.

Dentro del XML hay `swFile`, `swModel`, `swConfiguration` y `swReference`. Cada referencia activa contiene `swTransform`, `swModelRef`, número de instancia, configuración, `swSuppressed` y `swHidden`. Los nombres antiguos que aparezcan fuera de ese árbol no sustituyen estas referencias. La ayuda de SolidWorks confirma que el documento padre incorpora información XML de sus referencias y estados. [API oficial de referencias externas](https://help.solidworks.com/2021/english/api/swdocmgrapi/SolidWorks.Interop.swdocumentmgr~SolidWorks.Interop.swdocumentmgr.ISwDMDocument27~GetExternalFeatureReferences3.html).

Se conservaron los [XML exactos](../cad/ensambles/xml), las [imágenes PNG guardadas por SolidWorks](../cad/ensambles/previews) y el [informe trazable](../cad/ensambles/informe.json). Las PNG son previews nativos, no renders nuevos del pipeline. Los hashes registran cada original, stream, XML, preview, lector, adaptador y reporte de geometría. Las referencias se resuelven por nombre de archivo único en `Modelos3D`; no se intenta abrir la antigua ruta Windows `Z:\...`.

La convención observada para `swTransform` es una matriz 4×4 almacenada por columnas: las traslaciones están en posiciones 12, 13 y 14. El JSON la expresa como filas para aplicar `p_ensamble = R · p_pieza + t`, con `t` en metros. El script comprueba rotación ortonormal, determinante +1 y última fila `[0,0,0,1]`.

**Control fuerte de interpretación:** se transformaron las ocho esquinas de cada bounding box local guardada y se calculó su unión. En los diez conjuntos reproduce los seis extremos de la bounding box del ensamble con un error máximo menor que `2e-16 m`. Esto verifica la convención y asociación de matrices a instancias para estos archivos; no demuestra que el ensamble esté actualizado contra cada pieza actual. El self-check incorpora una rotación de 90° no simétrica, traslación y rechazo de stream truncado.

| Ensamble guardado | Instancias | Diferencias contra BREP actual mayores a 0,05 mm |
| --- | ---: | --- |
| `0-EnsambleBase` | 16 | Ninguna en bounding box |
| `0-EnsambleColision` | 20 | NEMA17 ×2: 3 mm; R-CarretelSup: 0,178 mm |
| `0-EnsambleTorre` | 15 | A-Eje y A-EjeInterior: 30 mm |
| `A-EnsambleBrazo` | 14 | Ninguna en bounding box |
| `A-EnsambleCarretel` | 2 | Ninguna en bounding box |
| `B-EnsambleAntebrazo` | 10 | NEMA17: 3 mm |
| `R-EnsambleCarretel` | 2 | R-CarretelSup: 0,178 mm |
| `R-EnsambleRotacion` | 9 | R-CarretelSup: 0,178 mm |
| `Z-EnsambleEfector` | 8 | Ninguna en bounding box |
| `Z-EnsambleM4` | 10 | Ninguna en bounding box |

Todas las referencias de estos árboles resuelven a archivos locales y aparecen con `swSuppressed="NO"` y `swHidden="NO"`. Todos tienen una configuración `Predeterminado` guardada, marcada sin necesidad de actualización por el propio caché. Esa marca no invalida las discrepancias encontradas al comparar archivos separados. Los diez árboles observados contienen piezas directas: **no hay un único ensamble que haga referencia a los otros nueve como subensambles**.

La referencia antigua `2GT_60Teet_40Bore.SLDPRT` no está en el árbol actual de `R-EnsambleRotacion`; allí se usa `2GT_80Teet_40Bore.SLDPRT`, disponible localmente. El indicio textual anterior no demuestra una pieza activa faltante.

Una bbox distinta prueba una discrepancia de caché/geometría, sin identificar automáticamente su causa. Una bbox coincidente tampoco prueba que todas las perforaciones y caras sean iguales. En particular, no se cambió una pieza actual por una versión antigua para hacer coincidir el montaje.

## Mundo estático de inspección

[tools/generate_cad_preview.py](../tools/generate_cad_preview.py) produce una vista sin `Physics`, motores ni objetos de colisión:

- **16 instancias azules:** malla aceptada y bounding box actual coincidente con la guardada dentro de 0,05 mm.
- **Torre azul con estado separado:** tres mallas de sus sólidos, validadas individualmente; el tercer STL descarta ocho triángulos de área exactamente cero. No se declara válida una unión global de las tres mallas ni se acepta la torre como una malla global. El lote vigente es 47 + 3.
- **Tres instancias ámbar:** dos NEMA17 y R-CarretelSup; la malla actual pasó el gate, pero su bbox difiere de la caché.
- `B-CarretelInf`, `B-CarretelSup` y `Z-SoporteEfector` ya usan mallas cerradas aceptadas. La [recuperación de geometrías](RECUPERACION_GEOMETRIAS.md) conserva sus marcos y documenta la corrección; no quedan referencias magenta en esta vista.

Las 20 instancias tienen nombre y estado en el árbol de escena: **las 20 tienen geometría**, de las cuales una contiene las tres mallas de torre. [inspeccion_webots.json](../cad/ensambles/inspeccion_webots.json) registra la disposición, hashes y malla de cada una. No hay suelo: el marco guardado tiene la torre por encima de los brazos, como muestra el [preview nativo](../cad/ensambles/previews/0-EnsambleColision.png). Una rotación de 180° sobre X permite orientar el conjunto en sentido contrario, pero **no se aplicó** ni se declaró esa pose como cero del robot.

La torre usa [el informe independiente por cuerpos](../cad/derivados/torre_por_cuerpos/informe.json) y [tools/exportar_torre_cuerpos.py](../tools/exportar_torre_cuerpos.py). Se conservan los crudos: cuerpos 1 y 2 idénticos, 648 triángulos cada uno; cuerpo 3 de 2990 a 2982, quitando solo ocho registros con producto cruzado exactamente nulo sobre coordenadas float32 racionales. No se movieron/soldaron vértices, añadieron caras ni quitaron triángulos de área positiva; bbox y volumen se conservaron. Cada derivado pasa aristas cerradas/manifold, volumen y bbox frente a su propio sólido BREP. **No se certifica el contacto o unión entre los tres cuerpos.**

El generador coloca los tres `Shape` bajo la misma matriz XML de `0-Torre-1`, comprueba hashes del original, STEP, informe del lote, exportador, mallas crudas y derivadas, y recalcula métricas de cada STL. El estado explícito es `body_meshes_validated_zero_area_cleanup`; el informe principal continúa con `0-Torre` rechazada como malla global.

Este mundo muestra colocaciones recuperadas, no esfuerzos, articulaciones o fidelidad dinámica. En la revisión inicial se comprobó la carga y el render nativo azul/ámbar/magenta en Webots R2025b Nightly Build 13/10/2026, build ejecutable `a459c02c7292d23ae437101c76111ec1668198c8`. El primer intento reveló una convención de cámara incorrecta; se corrigió a +X hacia delante y +Z arriba y se agregó una prueba. Luego se alejó la cámara 35% para encuadrar torre y soporte con paneles visibles. La [captura nativa histórica del 14/10](../validation/scara_cad_inspeccion.png) muestra la torre con sus tres mallas y las tres referencias alámbricas restantes. Se exportó y revisó después de un paso de render; la [captura previa sin torre](../validation/scara_cad_sin_torre.png) se conserva como historial. El commit del tag de descarga no debe confundirse con el build del ejecutable.

## Ejes y longitud de eslabones

[ejes_propuestos.json](../cad/ensambles/ejes_propuestos.json) registra líneas de eje y el marco del soporte en el sistema guardado de `0-EnsambleColision`. [evidencia_ejes_cilindros.json](../cad/ensambles/evidencia_ejes_cilindros.json) conserva superficies cilíndricas medidas con OCP sobre los STEP ya existentes y sus hashes. [tools/extraer_ejes_cad.py](../tools/extraer_ejes_cad.py) reproduce esas mediciones y exige encontrar los cilindros identificados y sus líneas coincidentes entre piezas. No se reconvirtieron piezas.

| Eje | Evidencia geométrica | Punto sobre la línea en el ensamble, m |
| --- | --- | --- |
| J1 | Agujero Ø16 de A-BridaEje; coincide con agujero Ø16 de A-Brazo en z local 30 mm y la línea de torre | `(-0,032666639; 0,010499991; 0,162021372)` |
| J2 | Agujero Ø9 de A-Brazo en z local 280 mm; coincide con agujero Ø8 de B-Antebrazo y centros de carreteles B | `(-0,028960537; -0,239472537; 0,162021372)` |
| J3 | Cilindros coaxiales Ø35/40/44 de Z-BujeExterior; coincide con alojamiento cilíndrico de R-Bancada y línea de Z-Cuerpo | `(-0,035649955; -0,489383024; 0,225021372)` |
| J4 | Línea longitudinal central de Z-Piston, coaxial con Z-Cuerpo y J3 | `(-0,035649955; -0,489383024; 0,194717013)` |

Las cuatro líneas son paralelas a Z, dentro del redondeo numérico. Los puntos se eligen sobre caras/referencias identificadas; mover un punto a lo largo de su eje representa la misma línea y **no define por sí solo un anchor único ni un offset cinemático**. Los signos provienen de los ejes de superficies y no son signos positivos de los motores.

Las distancias horizontales de J1 a J2 y de J2 a J3 son ambas **0,250 m**, con diferencias de redondeo menores a `2e-15 m`. La segunda confirma que el caño de antebrazo de 237 mm no debe usarse como longitud cinemática. Se comprobaron coincidencias de líneas entre piezas distintas, no solamente distancia entre orígenes elegidos por nombre.

El marco guardado del soporte `Z-SoporteEfector` se conserva completo, su geometría ya está recuperada y **el TCP oficial sigue sin definirse**. Posición cero, referencias Hall, topes, signos, carrera útil y pose de homing no se obtienen de este snapshot.

## Del ensamble guardado al modelo móvil

La pertenencia de piezas a los cuerpos, la transformación canónica y la forma de conservar las colocaciones al articular están en [Criterios de integración](INTEGRACION_CAD_CRITERIOS.md). Los carreteles y otros mecanismos no se asignan automáticamente al cuerpo por pertenecer a un mismo archivo de ensamble.

## Reproducción

Con la revisión local del conversor descrita en [Conversión CAD](EVALUACION_CONVERSION_CAD.md), reemplazar `/ruta/conversor` por su carpeta:

```sh
python3 -B tools/extraer_ensamble.py --self-check
python3 -B tools/extraer_ensamble.py --converter-root /ruta/conversor
python3 -B tools/generate_cad_preview.py --self-check
python3 -B tools/generate_cad_preview.py
```

Si hay que regenerar las mallas de torre o repetir la medición de ejes, usar el Python con OCP:

```sh
python -B tools/exportar_torre_cuerpos.py
python -B tools/extraer_ejes_cad.py
```

Los generadores comprueban hashes y la vista fija no sobrescribe `webots/worlds/scara.wbt`. Para otro conjunto, `generate_cad_preview.py` admite `--assembly A-EnsambleBrazo.SLDASM --output /ruta/otra_vista.wbt` dentro del proyecto. No es necesario reconvertir para usar los mundos ya preparados.

Las colocaciones guardadas no resuelven revisión oficial, ceros, homing ni TCP. Una reconstrucción fresca en el CAD de origen serviría como contraste independiente. No se requiere medir a mano posiciones que ya recuperamos; las discrepancias concretas están en [Consultas para el profesor](historico/DATOS_PARA_EL_PROFESOR.md).
