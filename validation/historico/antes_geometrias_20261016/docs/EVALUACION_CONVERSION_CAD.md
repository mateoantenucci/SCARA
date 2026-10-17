# Evaluación de la conversión CAD

14 de octubre de 2026. Este documento registra la etapa de conversión local de las 50 piezas y su validación con kernel CAD; esa etapa no recupera por sí sola el montaje. **Actualización posterior:** ya se recuperaron colocaciones y se integraron 30 instancias en la cadena articulada. Ver [Proceso y archivos](PROCESO_Y_ARCHIVOS.md) para el estado actual; los resultados y límites de conversión siguientes siguen vigentes.

## Veredicto y ruta propuesta

La ruta implementada es **sldprt2step + adaptador MiniFAT explícito → Open CASCADE/OCP sin VTK → STL en metros**. Se obtuvieron **50 STEP y 44 STL que pasan los controles geométricos**; seis piezas quedaron rechazadas con motivo explícito. Los STL aceptados permiten continuar el modelo sin esperar esas seis. No equivalen todavía a una certificación de fidelidad respecto de los originales abiertos en otro CAD.

No hizo falta instalar CadQuery completo ni Blender. Onshape sigue siendo un contraste útil —ya permitió comprobar la cota del brazo— y una alternativa para recuperar el ensamble. Las colocaciones y referencias del ensamble siguen siendo un trabajo separado.

| Etapa | Qué resuelve | Qué falta comprobar |
| --- | --- | --- |
| sldprt2step | Obtener STEP localmente desde las piezas nativas | Compatibilidad y calidad geométrica por pieza; no recupera el ensamble. |
| CadQuery/Open CASCADE | Leer STEP, validar sólidos, medir y teselar | Comparación de medidas, cuerpos, huecos y volumen; unidades y tolerancias. |
| Transformaciones de colocación | Pasar del marco de cada pieza a su cuerpo móvil | Instancias, posiciones y orientaciones de los ensambles, ejes y ceros. |
| Blender, opcional | Simplificación o tratamiento visual que haga falta | Que la mejora compense otra herramienta; no deformar referencias funcionales. |
| Webots | Articulaciones, colisiones, dinámica e interpretación del protocolo | Conjunto de pruebas del robot; el CAD convertido por sí solo no define el movimiento. |

## sldprt2step

Repositorio verificado: [BlinkingSun/sldprt2step](https://github.com/BlinkingSun/sldprt2step). Licencia Apache-2.0; Python 3.9 o superior y biblioteca estándar. Procesa localmente sin SolidWorks ni servicios de conversión.

Su alcance declarado comprende sólidos de piezas `.SLDPRT`, con aproximaciones para determinadas curvas y superficies. Excluye `.SLDASM`, materiales y relaciones de montaje. Por tanto, hace falta validar cada resultado y obtener por separado las propiedades físicas y las colocaciones del ensamble.

Revisión descargada para el piloto: `fa954124f4f126e0c465c8f96454978ac80b812e`. Se revisaron imports y operaciones de archivo antes de ejecutarla. La comprobación interna de éxito no sustituye validar un sólido con un kernel CAD. [README de esa revisión](https://github.com/BlinkingSun/sldprt2step/blob/fa954124f4f126e0c465c8f96454978ac80b812e/README.md), [entrypoint](https://github.com/BlinkingSun/sldprt2step/blob/fa954124f4f126e0c465c8f96454978ac80b812e/sldprt2step.py).

### Corrección de formato: mini-streams CFB

La primera corrida dejó 41 STL aceptados y nueve rechazos. Tres fallaban porque el lector OLE upstream trataba los streams menores de 4096 bytes como cadenas FAT normales: no implementaba MiniFAT. Es un problema del contenedor; los tres archivos sí contenían geometría Parasolid.

El [adaptador local](../tools/patches/ole_ministreams.py), identificado como `SCARA-CFB-MiniFAT-1`, agrega esa lectura mediante una subclase cargada explícitamente en cada subproceso de conversión. **No edita archivos upstream ni cambia los algoritmos de geometría.** Lee MiniFAT, root mini-stream y cadenas de mini-sectores, valida límites/ciclos y conserva el offset físico del primer mini-sector. [Licencia](../tools/patches/LICENSE-sldprt2step.txt) y [NOTICE](../tools/patches/NOTICE-sldprt2step.txt) upstream quedan preservados.

El [test de regresión](../tools/patches/comprobar_ministreams.py) confirma que el lector anterior obtiene bytes incorrectos y el adaptador recupera, en las tres piezas, los SHA-256 exactos del stream y del Parasolid obtenidos con una extracción independiente. También comprueba que la partición grande de `A-Brazo`, leída por FAT normal, no cambia. No se reemplaza una pieza por una primitiva ni se rellenan huecos.

El pipeline verifica el hash del árbol Python de la revisión fijada antes de ejecutarlo. El manifiesto registra separadamente el árbol original, el adaptador y la identidad efectiva:

| Identidad | SHA-256 |
| --- | --- |
| Árbol Python upstream, revisión fijada | `5abed6e10f5eea683f2b208c848c7f3f165cb22c6d414035fd00e41ac8481104` |
| Adaptador `ole_ministreams.py` | `85886233f45ee9e43bec5bec11bd8ec5b176f96a21511ab18ca7855ff7fa003c` |
| Identidad efectiva: SHA-256 de `árbol:adaptador` | `84f17c8af207d2833a94790ba4149defa5962f16920d89af64a19d813315fc2b` |

## Kernel y escala

Se usa `cadquery-ocp-novtk==8.0.1.1.0` y su dependencia `cadquery-ocp-proxy==8.0.1.1.0`: los bindings oficiales del ecosistema CadQuery para OCCT, sin VTK. Se descargaron los wheels de PyPI, se inspeccionaron METADATA e imports del proxy, y se instalaron sin red desde esos archivos en un venv temporal. No se instalaron aplicaciones ni paquetes globales. [Paquete PyPI](https://pypi.org/project/cadquery-ocp-novtk/8.0.1.1.0/), [sistema de construcción de CadQuery](https://github.com/CadQuery/ocp-build-system).

El código importa STEP con `STEPControl_Reader`, valida con `BRepCheck_Analyzer`, mide con `BRepGProp`/`BRepBndLib`, tesela con `BRepMesh_IncrementalMesh` y exporta STL binario. No invoca `ShapeFix`, cosido, relleno de huecos ni reparaciones de malla. La transferencia STEP utiliza el comportamiento normal del importador OCCT y sus tolerancias internas.

La cadena debe registrar unidades en cada etapa. Una conversión numérica mm→m afecta longitudes por 10^-3, volúmenes por 10^-9 e inercias geométricas por 10^-15. La inercia de masa, una vez calculada en kg·mm², se convierte a kg·m² por 10^-6. Evitar aplicar el factor dos veces o confundir inercia geométrica con inercia de masa.

Primero medir en el sólido original y calcular propiedades con densidades fundamentadas; después generar la representación visual. Desplazar o girar la malla para colocarla exige transformar también su centro de masa y tensor de inercia al marco del cuerpo correspondiente. No se obtiene una masa fiable únicamente porque el STL se vea correcto.

## Sombras y número de triángulos

La cifra **21.845 triángulos** tiene fundamento para las sombras de `Mesh` en Webots R2025a: su código comprueba si `3 * numberOfTriangles() > 65535`. No es un límite general para importar la pieza o simular el robot. Tampoco es un presupuesto compartido por todo el SCARA ni basta contar vértices únicos en Blender.

Podemos bajar detalle si afecta rendimiento o desactivar sombras en geometrías concretas. Una malla no necesita ser diezmada si su detalle y rendimiento ya son adecuados. [Código R2025a de la comprobación](https://github.com/cyberbotics/webots/blob/R2025a/src/webots/nodes/WbTriangleMeshGeometry.cpp), [Shape R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/shape.md).

## Controles y resultados

El pipeline reproducible está en [tools/convertir_cad.py](../tools/convertir_cad.py), las dos dependencias fijadas en [tools/requirements-cad.txt](../tools/requirements-cad.txt), y los resultados por pieza en [cad/derivados/informe.json](../cad/derivados/informe.json). El entorno utilizado está en `/private/tmp/scara-cad-piloto-20261014/venv`; no forma parte de la entrega. No se enviaron modelos a servicios externos.

Cada pieza se procesa en subprocesos con timeout de 90 segundos por etapa. El informe registra SHA-256 del original, código del pipeline y fuentes del conversor, revisión declarada, versiones del kernel, advertencias, resultados, unidades, tiempos y hashes de artefactos. La declaración `ok` del conversor nunca basta para publicar un STL.

Para publicar el STL se exige:

- STEP con declaración explícita de milímetros; BREP no nulo y válido.
- Al menos un sólido real de OCCT, con cantidad igual a la informada por el conversor; validez individual y volumen positivo/finito de cada sólido. Un compuesto válido con caras, pero sin sólidos, se rechaza.
- Bounding box finita y no degenerada.
- STL completo, cerrado y sin aristas no manifold al comparar las coordenadas float32 exportadas; volumen orientado coincidente con BREP dentro del 1% y bounding box dentro de la tolerancia de teselación.
- En `A-Brazo`, dimensiones 300×50×50 mm, punto central de la sección vacío, punto a 0,6 mm del exterior dentro de la pared y volumen inferior al tubo sin perforaciones de pared 1,2 mm.

No se cambia el origen ni la orientación de pieza. La escala mm→m se aplica **una sola vez** al sólido usado para exportar el STL. Tolerancias: 0,05 mm lineal y 0,3 rad angular; `relative=False`. El STEP queda en milímetros. Estos valores son para la representación visual, no para fijar una precisión del robot.

Los cuatro pilotos pasaron:

| Pieza | Sólidos OCCT | Caras OCCT | Volumen geométrico mm³ | Triángulos STL |
| --- | ---: | ---: | ---: | ---: |
| A-Brazo | 1 | 29 | 69.501,053 | 3.300 |
| Z-Cuerpo | 1 | 22 | 21.537,529 | 912 |
| 2GT_80Teet_40Bore | 1 | 168 | 9.166,652 | 8.376 |
| NEMA17 | 1 | 23 | 65.771,943 | 1.248 |

El tubo `A-Brazo` mantiene el vacío y sus perforaciones en la [vista de comprobación](../cad/derivados/vistas/A-Brazo.png), renderizada desde el STL y revisada visualmente. Su volumen STL difiere del BREP aproximadamente 0,0041%; el mayor error entre los cuatro pilotos es el de la polea, aproximadamente 0,2074%. La cota entre ejes verificada por el usuario en Onshape continúa siendo un contraste independiente.

En el lote completo final, 44 piezas pasan y seis no. Los 44 STL suman 121.822 triángulos; el máximo por archivo es 9.538. **Ninguno necesita simplificación para el umbral de sombras de 21.845**. De las 44 piezas aceptadas, 18 incluyen advertencias de curvas de intersección o SP-curves aproximadas; el informe conserva esas advertencias. La validez topológica no demuestra que esa aproximación coincida con otro traductor dentro de una tolerancia conocida.

| Pieza rechazada | Resultado observado | Próximo criterio para recuperarla |
| --- | --- | --- |
| `0-Torre` | BREP válido con tres sólidos; STL: ocho aristas de borde y diez no manifold en la comprobación global | Comprobar sólidos/zonas de contacto y teselación por separado. Un contacto entre cuerpos también puede disparar este control; no se declara el CAD original dañado. |
| `B-CarretelInf` | Conversor informa un sólido; OCCT obtiene cero sólidos y 25 caras | Contrastar STEP con otro traductor; no aceptarlo por el volumen calculable de un conjunto de caras. |
| `B-CarretelSup` | Igual: cero sólidos y 25 caras | Mismo criterio. |
| `B-ExtensorM3` | Un sólido, pero `BRepCheck_Analyzer.IsValid()` falso | Contrastar geometría y curvas aproximadas con otro traductor. |
| `Z-BujeInterior` | BREP válido; STL: cuatro aristas de borde y cuatro no manifold | Inspeccionar zonas y teselación; no rellenar huecos automáticamente. |
| `Z-SoporteEfector` | Un sólido, pero BREP inválido; advertencias de blends e intersecciones | Contrastar con un traductor CAD que resuelva esa geometría. |

Las tres recuperadas pasan los mismos controles, sin excepciones:

| Pieza | Geometría convertida | Volumen geométrico mm³ | Triángulos |
| --- | --- | ---: | ---: |
| `A-EjeInterior` | Ø9,5 × 190 mm | 13.467,615 | 164 |
| `B-Eje` | Ø8 × 130 mm | 6.534,513 | 164 |
| `Z-VarillaACME` | Ø8 × 195 mm | 9.801,769 | 164 |

La longitud guardada de `Z-VarillaACME`, 195 mm, difiere del plano PDF de 200 mm y de la descripción del master. Es una discrepancia de revisiones a reconciliar; no cambia por sí sola la carrera nominal de 120 mm. La apariencia cilíndrica corresponde a la geometría nativa guardada y no prueba una rosca o avance físico.

Los STEP que llegaron a importación se conservan aunque el gate posterior los rechace; **solo [cad/derivados/stl](../cad/derivados/stl) contiene mallas publicadas por el gate**. La revisión SHA-256 final confirmó los 50 originales intactos, los hashes de cada artefacto y que no exista un STL publicado para las seis piezas rechazadas. El proceso retorna código 1 cuando alguna pieza falla; esto representa un lote parcial explícito.

Antes de sustituir un informe existente, el script lo archiva en [cad/derivados/history](../cad/derivados/history), incluyendo su hash en el informe nuevo; cada pieza registra su resultado anterior. Allí queda la corrida **41 + 9** sin alterar, y las tres recuperadas mantienen el motivo de rechazo previo. Los 41 STL ya aceptados conservaron sus hashes después del adaptador.

## Reproducción

Usar Python 3.11–3.14 y un entorno aislado. Descargar por separado la revisión fijada del [conversor](https://github.com/BlinkingSun/sldprt2step/tree/fa954124f4f126e0c465c8f96454978ac80b812e); el script no descarga ni ejecuta código remoto. El directorio debe contener `sldprt2step.py` y `sldprt2step_lib`.

```sh
python3.12 -m venv .venv-cad
.venv-cad/bin/python -m pip install --only-binary=:all: -r tools/requirements-cad.txt
.venv-cad/bin/python -B tools/convertir_cad.py \
  --converter-root /ruta/sldprt2step-fa954124f4f126e0c465c8f96454978ac80b812e
```

El test de formato no necesita OCP:

```sh
python3 -B tools/patches/comprobar_ministreams.py \
  --converter-root /ruta/sldprt2step-fa954124f4f126e0c465c8f96454978ac80b812e
```

Para repetir los cuatro pilotos, agregar `--parts A-Brazo Z-Cuerpo NEMA17 2GT_80Teet_40Bore --output /ruta/salida-piloto`. Cada ejecución escribe un informe para las piezas solicitadas: usar otra salida para una muestra evita reemplazar el informe del lote completo. En Windows el ejecutable del venv está en `Scripts/python.exe`.

Wheels utilizados en este macOS arm64 / CPython 3.12:

| Archivo | SHA-256 |
| --- | --- |
| `cadquery_ocp_novtk-8.0.1.1.0-cp312-cp312-macosx_11_0_arm64.whl` | `b76212dcda2ea19a501b26225f5d36ae1a5eed35e594c2af948a534e7f82a908` |
| `cadquery_ocp_proxy-8.0.1.1.0-py3-none-any.whl` | `98c71bb60cfb651afe179b134ab88580fd75384fce0cc6d633f727002cd18abd` |

El volumen y su centroide son **propiedades geométricas**. El informe deja `mass_kg: null`: no asigna densidad, masa, centro de masa físico ni inercia. Motores con varios materiales, impresiones FDM, tornillería y distribución del conjunto necesitan un tratamiento posterior. Tampoco se han validado colocaciones, distancias entre ejes del ensamble, límites, articulaciones o correspondencia con un robot físico.
