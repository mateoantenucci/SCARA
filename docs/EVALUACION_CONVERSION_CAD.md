# Conversión CAD: método, resultados y reproducción

La ruta implementada es **sldprt2step con adaptadores explícitos → OpenCascade/OCP sin VTK → STL en metros**. La conversión resuelve formas individuales; las colocaciones y articulaciones se recuperan por separado, como explica [Ensamble CAD](ENSAMBLE_CAD.md).

## Resultado del lote

Se conservan **50 STEP y 47 STL aceptados**, con tres rechazos globales identificados en [cad/derivados/informe.json](../cad/derivados/informe.json). Veintiuna de las piezas aceptadas conservan advertencias de curvas/superficies aproximadas. Aceptación topológica no equivale a fidelidad certificada por SolidWorks.

| Rechazo global | Motivo y tratamiento |
| --- | --- |
| `0-Torre` | BREP válido con tres sólidos; la malla global no supera el control de aristas. Sus tres cuerpos se usan como visuales separados y validados individualmente; ver [torre por cuerpos](../cad/derivados/torre_por_cuerpos/README.md). |
| `B-ExtensorM3` | BREP inválido. No se acepta su volumen ni se incorpora automáticamente al montaje. |
| `Z-BujeInterior` | BREP válido, pero la malla presenta aristas libres/no manifold. Puede tener propiedades geométricas calculadas sin un STL visual aceptado. |

Los dos carreteles B y `Z-SoporteEfector` ya se recuperaron. La [recuperación de geometrías](RECUPERACION_GEOMETRIAS.md) documenta la corrección y la regresión que la respalda. Las corridas anteriores de 41/44 STL aceptados se conservan en `cad/derivados/history/` y en los snapshots; no son el estado del lote vigente.

No hizo falta instalar CadQuery completo ni Blender. Los originales no se modifican y el pipeline local no necesita subirlos a servicios de conversión. Una comprobación de la distancia entre agujeros del brazo realizada por el usuario en Onshape aporta un contraste independiente, sin certificar todas las piezas.

## Conversor y adaptadores

Se fija [sldprt2step](https://github.com/BlinkingSun/sldprt2step) a la revisión `fa954124f4f126e0c465c8f96454978ac80b812e`. Es un conversor Python de piezas `.SLDPRT`; no reconstruye ensambles, materiales ni restricciones. Los algoritmos aproximan algunas curvas y superficies, por lo que cada salida pasa controles propios.

El adaptador [ole_ministreams.py](../tools/patches/ole_ministreams.py), `SCARA-CFB-MiniFAT-1`, agrega la lectura de streams menores de 4096 bytes almacenados en MiniFAT, que el lector original trataba como FAT normal. Valida límites y ciclos, y conserva los offsets de origen. No cambia la geometría ni modifica el upstream. La [regresión](../tools/patches/comprobar_ministreams.py) contrasta los bytes recuperados con una extracción independiente y comprueba que la lectura normal del brazo no cambia.

El adaptador [intersection_precision.py](../tools/patches/intersection_precision.py) refina curvas de intersección con objetivo de 10⁻⁹ m frente al 10⁻⁷ m original. Mantiene superficies y topología. Resolvió tres geometrías sin cosido, relleno de huecos ni `ShapeFix`. Ese objetivo numérico no es una cota certificada de error geométrico ni precisión física.

El pipeline comprueba el hash del árbol Python fijado y registra adaptadores, código, fuentes y artefactos por separado. Las identidades exactas están en el informe, evitando mantener una segunda tabla de hashes en esta guía. Se conservan [licencia Apache-2.0](../tools/patches/LICENSE-sldprt2step.txt) y [NOTICE](../tools/patches/NOTICE-sldprt2step.txt).

## Kernel, unidades y controles

Se usan `cadquery-ocp-novtk==8.0.1.1.0` y `cadquery-ocp-proxy==8.0.1.1.0`, fijados en [requirements-cad.txt](../tools/requirements-cad.txt). El código lee STEP con `STEPControl_Reader`, comprueba BREP con `BRepCheck_Analyzer`, mide con `BRepGProp`/`BRepBndLib` y tesela con `BRepMesh_IncrementalMesh`.

Los STEP declaran **milímetros** y los STL se exportan en **metros**, aplicando el factor 0,001 una sola vez. No cambia el origen ni la orientación de pieza. Volumen y tensor geométrico requieren factores 10⁻⁹ y 10⁻¹⁵ respectivamente; la inercia de masa expresada en kg·mm² se convierte con 10⁻⁶. No son magnitudes intercambiables.

Para publicar una malla se exige:

1. STEP en milímetros y BREP no nulo y válido.
2. Al menos un sólido real, con cantidad coherente con el conversor, validez individual y volumen positivo/finito. Una colección de caras sin sólidos no alcanza.
3. Caja envolvente finita y no degenerada.
4. STL completo, cerrado y sin aristas no manifold al comparar coordenadas float32; volumen orientado dentro del 1% del BREP y caja dentro de la tolerancia de teselación.
5. En el piloto `A-Brazo`, dimensiones de 300×50×50 mm, interior hueco y pared coherente, sin convertir el tubo en una barra maciza.

La teselación usa tolerancia lineal 0,05 mm y angular 0,3 rad, con `relative=False`. Son parámetros visuales. Cada etapa tiene timeout de 90 s y conserva advertencias, tiempos, versiones y SHA-256. La palabra `ok` del conversor no basta para aceptar la salida.

| Piloto | Sólidos OCCT | Volumen geométrico, mm³ | Triángulos |
| --- | ---: | ---: | ---: |
| A-Brazo | 1 | 69.501,053 | 3.300 |
| Z-Cuerpo | 1 | 21.537,529 | 912 |
| 2GT_80Teet_40Bore | 1 | 9.166,652 | 8.376 |
| NEMA17 | 1 | 65.771,943 | 1.248 |

La [vista del brazo](../cad/derivados/vistas/A-Brazo.png) conserva hueco y perforaciones. La mayor diferencia STL/BREP de estos pilotos fue aproximadamente 0,2074% en la polea. Sigue siendo un contraste de la teselación frente al BREP convertido, no frente al CAD reconstruido en SolidWorks.

Los STEP rechazados se conservan para diagnóstico, pero solo `cad/derivados/stl/` contiene mallas publicadas por el control del lote. La recuperación separada de torre está en otra ruta. No se cambia el resultado de un rechazo para completar visualmente el robot.

## Reproducción

No hay que reconvertir para usar la simulación entregada. Para reproducir la conversión, usar Python compatible con las dependencias CAD y un entorno aislado; obtener por separado la revisión fijada del conversor. El script exige su carpeta local y no descarga código remoto.

```sh
python3.12 -m venv .venv-cad
.venv-cad/bin/python -m pip install --only-binary=:all: -r tools/requirements-cad.txt
.venv-cad/bin/python -B tools/convertir_cad.py \
  --converter-root /ruta/sldprt2step-fa954124f4f126e0c465c8f96454978ac80b812e \
  --output /tmp/scara-conversion-repeticion
```

La salida alternativa conserva los derivados activos. En Windows el ejecutable está en `Scripts/python.exe`. Para una muestra agregar `--parts A-Brazo Z-Cuerpo NEMA17 2GT_80Teet_40Bore`. Para una actualización incremental de las tres piezas recuperadas, consultar el procedimiento y el significado de `--merge` en [Recuperación](RECUPERACION_GEOMETRIAS.md).

La comprobación de formato no requiere OCP:

```sh
python3 -B tools/patches/comprobar_ministreams.py \
  --converter-root /ruta/sldprt2step-fa954124f4f126e0c465c8f96454978ac80b812e
```

El lote devuelve código 1 si conserva piezas rechazadas, aunque las demás hayan pasado. Antes de sustituir un informe, el programa archiva el anterior y registra su hash. Para las propiedades físicas, seguir [Propiedades geométricas CAD](PROPIEDADES_GEOMETRICAS_CAD.md): el volumen calculado no asigna por sí solo masa, densidad ni esfuerzo disponible.
