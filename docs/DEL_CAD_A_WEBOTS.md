# Del CAD de la cátedra al robot en Webots

Este documento detalla, paso por paso, cómo las piezas y ensambles SolidWorks de la cátedra (`Modelos3D/`) se convirtieron en el robot articulado de Webots: conversión de piezas, geometrías recuperadas, colocaciones de los ensambles, criterios de integración (cuerpos, ejes, pose canónica) y generación del mundo. Sirve para justificar o reproducir una decisión del CAD. Las propiedades geométricas y masas están en [PROPIEDADES](PROPIEDADES.md); el montaje, las autocolisiones y los recorridos, en [MONTAJE_Y_COLISIONES](MONTAJE_Y_COLISIONES.md). Los términos están en el [glosario](GLOSARIO.md).

La idea que ordena todo: **convertir las piezas resuelve formas, no armado.** La forma de una pieza no dice dónde va, a qué cuerpo rígido pertenece ni cómo gira. Cada paso de abajo cubre un problema distinto.

## 1. Conversión de piezas

La ruta es **sldprt2step con adaptadores explícitos → OpenCascade/OCP sin VTK → STL en metros**. No hizo falta CadQuery completo ni Blender. Los originales no se modifican y nada se sube a servicios de conversión.

### Resultado del lote

Hay **50 STEP y 47 STL aceptados**, con tres rechazos globales registrados en [informe.json](../cad/derivados/informe.json). Veintiuna de las piezas aceptadas conservan advertencias de curvas o superficies aproximadas. Aceptación topológica no equivale a fidelidad certificada por SolidWorks.

| Rechazo global | Motivo y tratamiento |
| --- | --- |
| `0-Torre` | BREP válido con tres sólidos; la malla global no supera el control de aristas. Sus tres cuerpos se usan como visuales separados (ver §2). |
| `B-ExtensorM3` | BREP inválido. No se acepta su volumen ni entra al montaje. |
| `Z-BujeInterior` | BREP válido, pero la malla tiene aristas libres o no manifold. Puede tener propiedades geométricas sin STL visual aceptado. |

No se cambia el resultado de un rechazo para completar visualmente el robot. Como contraste independiente, la distancia entre agujeros del brazo se comprobó en Onshape; no certifica las demás piezas.

### Conversor y adaptadores

Se fija [sldprt2step](https://github.com/BlinkingSun/sldprt2step) a la revisión `fa954124f4f126e0c465c8f96454978ac80b812e`. Convierte piezas `.SLDPRT`; no reconstruye ensambles, materiales ni restricciones. Aproxima algunas curvas y superficies, así que cada salida pasa controles propios.

| Adaptador | Qué hace | Qué no hace |
| --- | --- | --- |
| [ole_ministreams.py](../tools/patches/ole_ministreams.py) (`SCARA-CFB-MiniFAT-1`) | Lee los streams menores de 4096 bytes guardados en MiniFAT, que el lector original trataba como FAT normal. Valida límites y ciclos y conserva offsets. | No cambia la geometría ni el upstream. |
| [intersection_precision.py](../tools/patches/intersection_precision.py) | Refina las curvas de intersección con objetivo de 10⁻⁹ m (el del conversor es 10⁻⁷ m). | No usa cosido, relleno de huecos ni `ShapeFix`. El objetivo no es una cota certificada de error. |

El pipeline verifica el hash del árbol Python fijado y registra adaptadores, código, fuentes y artefactos por separado; las identidades exactas están en el informe. Se conservan la [licencia Apache-2.0](../tools/patches/LICENSE-sldprt2step.txt) y el [NOTICE](../tools/patches/NOTICE-sldprt2step.txt) del conversor.

### Kernel, unidades y controles

Se usan `cadquery-ocp-novtk==8.0.1.1.0` y `cadquery-ocp-proxy==8.0.1.1.0` ([requirements-cad.txt](../tools/requirements-cad.txt)): `STEPControl_Reader` para leer, `BRepCheck_Analyzer` para validar, `BRepGProp`/`BRepBndLib` para medir y `BRepMesh_IncrementalMesh` para teselar.

Los STEP declaran **milímetros** y los STL se exportan en **metros**, aplicando el factor 0,001 una sola vez y sin cambiar origen ni orientación de pieza. Volumen y tensor geométrico usan factores 10⁻⁹ y 10⁻¹⁵; la inercia de masa en kg·mm² se convierte con 10⁻⁶. No son intercambiables.

Para publicar una malla se exige: STEP en milímetros con BREP válido; al menos un sólido real, válido y de volumen positivo (una colección de caras no alcanza); caja envolvente finita; STL cerrado, sin aristas libres ni no manifold (float32), con volumen dentro del 1 % del BREP y caja dentro de la tolerancia de teselación; y, en el piloto `A-Brazo`, 300×50×50 mm con interior hueco. La teselación usa tolerancia lineal 0,05 mm y angular 0,3 rad (`relative=False`), parámetros visuales. Cada etapa tiene timeout de 90 s y conserva advertencias, versiones y SHA-256. El `ok` del conversor no alcanza para aceptar una salida.

### Reproducción

No hace falta reconvertir para usar la simulación. Para reproducir, usá Python compatible en un entorno aislado y la revisión fijada del conversor, obtenida por separado (el script exige la carpeta local y no descarga código):

```sh
python3.12 -m venv .venv-cad
.venv-cad/bin/python -m pip install --only-binary=:all: -r tools/requirements-cad.txt
.venv-cad/bin/python -B tools/convertir_cad.py \
  --converter-root /ruta/sldprt2step-fa954124f4f126e0c465c8f96454978ac80b812e \
  --output /tmp/scara-conversion-repeticion
```

La salida alternativa no toca los derivados activos. En Windows el ejecutable está en `Scripts/python.exe`. Para una muestra, agregá `--parts A-Brazo Z-Cuerpo NEMA17 2GT_80Teet_40Bore`. La comprobación de formato no requiere OCP:

```sh
python3 -B tools/patches/comprobar_ministreams.py \
  --converter-root /ruta/sldprt2step-fa954124f4f126e0c465c8f96454978ac80b812e
```

El lote devuelve código 1 mientras conserve piezas rechazadas, aunque las demás hayan pasado. Antes de sustituir un informe, el programa archiva el anterior y registra su hash.

## 2. Geometrías recuperadas

### B-CarretelInf, B-CarretelSup y Z-SoporteEfector

El conversor las rechaza por una tolerancia numérica en las curvas de intersección. Se regeneran desde los mismos `.SLDPRT` con el adaptador de precisión y el mismo control del lote; no se reconstruyeron desde planos ni se añadieron superficies.

| Pieza | Causa del rechazo | Resultado |
| --- | --- | --- |
| B-CarretelInf y B-CarretelSup | El conversor declaraba un sólido, pero OCCT obtenía 25 caras y cero sólidos. | 1 sólido válido, 25 caras, 8.290 triángulos, 12.725,752428 mm³, diferencia STL/BREP 0,148 %, caja 70×70×14 mm. |
| Z-SoporteEfector | Sólido inválido, con advertencias de blends e intersecciones. | 1 sólido válido, 49 caras OCCT (el STEP declara 48), 6.188 triángulos, 22.148,156985 mm³, diferencia 0,1124 %, caja 60×60×19 mm. |

Las tres mallas tienen cero aristas libres y cero no manifold. El STEP declara incertidumbre de 10⁻⁵ mm: el objetivo del conversor (10⁻⁴ mm) es mayor y el del adaptador (10⁻⁶ mm) es menor. Eso explica el rechazo, pero **no certifica un error máximo igual al objetivo**; las advertencias sobre blends aproximados siguen. Los dos STEP B son idénticos salvo los nombres de pieza, pero sus nativos tienen hashes distintos: no se sustituyó una mitad por la otra.

Los stamps de SolidWorks (191/196 para Z-SoporteEfector, 266/267 para los carreteles B) son valores de caché, no revisiones aprobadas, y no permiten elegir una revisión oficial. El [plano de Z-SoporteEfector](../Modelos3D/Z-SoporteEfector.PDF) indica **PLA, relleno 30 % y masa desconocida**: no se lo convierte en densidad ni masa. El [maestro, p. 24](../00-SCARA-Master.pdf), declara su acople rígido al pistón y al efector.

**Reproducción de la recuperación** (`RUTA` es la carpeta local del conversor):

```sh
python tools/patches/comprobar_intersecciones.py \
  --converter-root RUTA \
  --output validation/cad/cad_recovery_regression.json

python tools/convertir_cad.py \
  --converter-root RUTA \
  --parts B-CarretelInf B-CarretelSup Z-SoporteEfector \
  --merge
```

`--merge` actualiza solo esas tres piezas y conserva las otras 47 entradas. **Retorna código 1 por los tres rechazos globales retenidos**, aunque las tres piezas hayan pasado: se lee el informe combinado. Después se regeneran los dependientes, con el mismo Python OCP:

```sh
python tools/exportar_torre_cuerpos.py
python tools/extraer_ensamble.py --converter-root RUTA
python tools/extraer_ejes_cad.py
python tools/registrar_subensambles.py
python tools/integrate_cad.py
python tools/generate_world.py
python tools/generate_cad_preview.py
python tools/calcular_propiedades_cad.py
```

La integración corre **sin `--update-config`**: la configuración de física conserva sus bytes. Una malla visual más completa no vuelve contactos CAD a las cajas de colisión.

Evidencia vigente en `validation/cad/`: [cad_recovery.json](../validation/cad/cad_recovery.json) (`passed`; 152 originales, 47 entradas retenidas y configuración de física intactos), [cad_recovery_regression.json](../validation/cad/cad_recovery_regression.json) (15/15), [collisions_recovery.json](../validation/cad/collisions_recovery.json) (11 poses, 22 BREP móviles; ocho intersecciones esperadas contra el pedestal, rechazadas), [cad_motion_recovery.json](../validation/cad/cad_motion_recovery.json) (330 colocaciones, error máximo ≈ 4,50 × 10⁻⁶ m) y [collisions_native_recovery.json](../validation/cad/collisions_native_recovery.json) (cinco controles nativos). Aprobarlos significa que las invasiones de prueba se detectan, no que el espacio de trabajo esté libre.

### Torre por cuerpos

`0-Torre` tiene tres sólidos válidos pero no pasa como malla global. Se exporta cada sólido por separado en [torre_por_cuerpos](../cad/derivados/torre_por_cuerpos/README.md), con [informe individual](../cad/derivados/torre_por_cuerpos/informe.json):

Volúmenes BREP de 9.457,636133 mm³ (cuerpos 01 y 02, 648 triángulos, error 0,00768 %) y 373.897,663364 mm³ (cuerpo 03, 2.990 → 2.982 triángulos, error 0,00564 %).

En el cuerpo 03, ocho triángulos de área exactamente cero (verificada con aritmética racional sobre las coordenadas float32) causaban autoaristas; se eliminaron solo esos. No se soldaron ni movieron vértices, no se cerraron huecos ni se quitó superficie de área positiva; caja y volumen quedan idénticos. Los crudos de OCCT se conservan en `crudos/`. Las coordenadas están en metros y las tres mallas comparten la colocación de la instancia de torre. **No se certifica el contacto ni la unión entre los tres cuerpos**, ni que formen una malla manifold única. Para regenerar: `python -B tools/exportar_torre_cuerpos.py` (con `--output /ruta` para una prueba sin reemplazar la salida; no descarga nada y verifica hashes).

## 3. Colocaciones de los ensambles

### Qué se recuperó y cómo

Se recuperaron **106 instancias guardadas de los diez `.SLDASM`**, con archivo de origen, configuración, identificador, visibilidad y matriz. La fuente es el XML comprimido que SolidWorks deja dentro de cada archivo: no se necesitó SolidWorks ni Onshape, y **no se resolvieron restricciones ni se reconstruyó el ensamble con las revisiones actuales de las piezas**.

[tools/extraer_ensamble.py](../tools/extraer_ensamble.py) lee el contenedor con el lector CFB y el adaptador MiniFAT: descomprime el stream `COMPINSTANCETREE__ZLB` (encabezado de 24 bytes, zlib, trailer de ocho bytes nulos), valida tamaños y estructura XML y toma de cada `swReference` activa `swTransform`, instancia, configuración, `swSuppressed` y `swHidden`. Las referencias se resuelven por nombre único en `Modelos3D`, sin abrir la ruta Windows original. Se conservan los [XML exactos](../cad/ensambles/xml), los [previews PNG nativos](../cad/ensambles/previews) y el [informe trazable](../cad/ensambles/informe.json), con hashes.

`swTransform` es una matriz 4×4 por columnas (traslación en las posiciones 12, 13, 14); el JSON la expresa por filas para aplicar `p_ensamble = R · p_pieza + t`, con `t` en metros.

**Control de interpretación:** al transformar las ocho esquinas de cada caja local y unirlas, se reproducen los seis extremos de la caja del ensamble con error máximo menor que 2·10⁻¹⁶ m en los diez conjuntos. Verifica la convención y la asociación matriz–instancia, no que el ensamble esté al día con cada pieza.

| Ensamble guardado | Instancias | Diferencias de caja contra BREP actual > 0,05 mm |
| --- | ---: | --- |
| `0-EnsambleBase` | 16 | Ninguna |
| `0-EnsambleColision` | 20 | NEMA17 ×2: 3 mm; R-CarretelSup: 0,178 mm |
| `0-EnsambleTorre` | 15 | A-Eje y A-EjeInterior: 30 mm |
| `A-EnsambleBrazo` | 14 | Ninguna |
| `A-EnsambleCarretel` | 2 | Ninguna |
| `B-EnsambleAntebrazo` | 10 | NEMA17: 3 mm |
| `R-EnsambleCarretel` | 2 | R-CarretelSup: 0,178 mm |
| `R-EnsambleRotacion` | 9 | R-CarretelSup: 0,178 mm |
| `Z-EnsambleEfector` | 8 | Ninguna |
| `Z-EnsambleM4` | 10 | Ninguna |

Todas las referencias resuelven a archivos locales, sin supresión ni ocultamiento, con una configuración `Predeterminado` que el propio caché marca sin necesidad de actualización (marca que no invalida las discrepancias de la tabla). Una caja distinta prueba una discrepancia sin identificar su causa; una coincidente no prueba que perforaciones y caras sean iguales. No se cambió una pieza actual por una antigua para hacer coincidir el montaje.

### Relación entre conjuntos

- Los diez ensambles ubican **47 piezas distintas** en sus propios marcos. Tres archivos no aparecen activos en ningún árbol: `2GT_80Teet_8Bore.SLDPRT`, `BorneraX6.SLDPRT` y `KY-003.SLDPRT`; la ausencia no prueba que sean innecesarios.
- **Los diez árboles contienen piezas directas: ningún ensamble referencia a los otros nueve como subensamble.** No forman un maestro único.
- `0-EnsambleColision` reúne torre, brazo, antebrazo y mecanismo Z: **20 instancias de 19 piezas distintas**. Es el conjunto local de referencia, no un ensamble maestro oficial. Quedan 28 tipos de pieza ausentes de esa vista (base inferior, motores NEMA23, ejes, poleas, rodamientos, soportes de brazo y antebrazo, componentes internos de Z).
- Los conjuntos no se superponen como un mismo estado: comparten piezas móviles, tienen poses y revisiones distintas y copias repetidas. [registrar_subensambles.py](../tools/registrar_subensambles.py) los relaciona por piezas compartidas y conserva las ambigüedades en [registro_subensambles.json](../cad/ensambles/registro_subensambles.json). La vía Torre→global depende de una única instancia compartida (`0-Torre`); Base→Torre tiene más referencias compatibles. Es evidencia de colocaciones coherentes, no certificación de mates.
- No se agregaron instancias mediante relaciones ambiguas. `R-EnsambleRotacion` usa `2GT_80Teet_40Bore.SLDPRT` (disponible localmente), no `2GT_60Teet_40Bore.SLDPRT`.

## 4. Criterios de integración

La integración conserva las colocaciones guardadas y adopta un sistema de coordenadas útil sin esperar ceros oficiales de motor. Es una decisión **reversible de representación**: no declara homing, calibración, fijaciones verificadas, masas CAD ni TCP oficial. La fuente editable es [config/cad_integration.json](../config/cad_integration.json); el [JSON de criterios](../cad/ensambles/criterios_integracion.json) guarda la transformación canónica, los marcos y las matrices pieza→cuerpo de las 20 instancias del snapshot, y el [manifiesto efectivo](../cad/ensambles/integracion_articulada.json) tiene las 43 del modelo móvil.

### Cuerpos

Instancias del snapshot (`0-EnsambleColision`):

| Cuerpo | Instancias |
| --- | --- |
| Base | 0-Torre, A-CarretelInf |
| Brazo | A-Brazo, A-BridaEje, A-CarretelSup, B-CarretelSup |
| Antebrazo | B-Antebrazo, NEMA17-1, R-Bancada, R-ContraBancada, B-CarretelInf, R-CarretelInf |
| Muñeca (Z exterior) | Z-BujeExterior, Z-Cuerpo, Z-SoporteM4, Z-SoporteRuleman, NEMA17-2, R-CarretelSup |
| Herramienta (Z deslizante) | Z-Piston, Z-SoporteEfector |

El master (pp. 5 y 9) distingue cuerpo exterior, pistón y soporte; pp. 11–12 ubican M1/M2 en la base y M3 sobre el antebrazo. Los planos de rotación muestran R-Bancada/R-ContraBancada como alojamiento atravesado por Z-BujeExterior con rodamientos.

**Piezas de otros ensambles.** Al snapshot se suman **23 ocurrencias registradas** desde otros ensambles: en total **43 instancias** en el manifiesto (39 con malla aceptada, 3 con malla aceptada y caja distinta de la caché y la torre por cuerpos). Pertenencia aprobada para la representación visual:

| Cuerpo | Adiciones |
| --- | --- |
| Base | 0-Bancada, 0-ElevadorM2, 0-PlatinaSuperior, 0-SoporteMotores, NEMA23 ×2, dos rodamientos 6203-2RS, poleas 2GT 20T/6,35 ×2 y 80T/10 |
| Brazo | B-SoporteRuleman ×2, dos rodamientos 608zz, polea 80T/16 |
| Antebrazo | B-SoporteEjeFijo, B-SoporteM3, dos rodamientos 6907-2RS, poleas 60T/8 y 20T/5 |
| Muñeca | polea 80T/40 (ver abajo) |

Los dos NEMA23 son carcazas fijas (el eje es parte de la malla) y los seis rodamientos son simplificaciones sin anillos ni masa. Las poleas de salida 80T/16 y 60T/8 acompañan al brazo y al antebrazo (fase guardada, provisional). Las poleas de motor y la 80T/10 giran **solo como visual**, sin física: las anima la planta (`PULLEYS` en `webots/controllers/scara_uci/scara_uci.cpp`) según las articulaciones (`rotating_occurrences`). La polea de muñeca 80T/40 se toma de `R-EnsambleRotacion`, que apoya en el escalón de Z-BujeExterior sin invasión BREP; la pose de `B-EnsambleAntebrazo` lo invade 470,3756 mm³. Quedan fuera los ejes ambiguos, la 60T del eje interior y la transmisión no sustentada ([TRANSMISION](TRANSMISION.md)). Ningún componente se agrega a un cuerpo solo por compartir subensamble.

**Corrección de colocación.** `R-ContraBancada-1` adopta su pose relativa a `R-Bancada-1` de `R-EnsambleRotacion`: la tapa del ensamble global está invertida y desplaza 3 mm los asientos. Se conserva el original y no se deforma geometría; es una corrección de la simulación, no revisión mecánica oficial. Rodamientos, tapa y polea de muñeca se detallan en [MONTAJE_Y_COLISIONES](MONTAJE_Y_COLISIONES.md).

**Masas.** No se asigna masa por archivo CAD. El PROTO tiene cuatro bloques `Physics`, uno por cuerpo móvil, con masas exploratorias de 0,30; 0,50; 0,35 y 0,15 kg (`config/scara.json`). Cambiar visuales o envolventes no las vuelve propiedades medidas. M1/M2 quedan dentro de la base fija. Es dinámica equivalente provisional con visuales CAD parciales, no un ensamble de las 50 piezas.

### Los seis carreteles

Son canales anulares con pasos radiales de dos caras: **no son las poleas 2GT que transmiten el par**. Que canalicen cableado es una inferencia de su forma, no algo que el master explique, y no son abrazaderas sobre el caño de 50×50 mm (sus agujeros son de 9–36 mm). Se propone **una mitad a cada lado de la articulación**, contrastando los planos ([A-Carreteles](../Modelos3D/A-Carreteles.PDF), [R-EnsambleCarretel](../Modelos3D/R-EnsambleCarretel.PDF), [R-EnsambleRotacion](../Modelos3D/R-EnsambleRotacion.PDF)), los STEP actuales y las matrices XML.

| Instancia | Cuerpo | Evidencia (contacto en la pose guardada) |
| --- | --- | --- |
| A-CarretelInf | Base | Cara exterior en la cara superior de la torre; Ø17 con holgura sobre el eje Ø16. |
| A-CarretelSup | Brazo | Cara exterior en el resalte de A-BridaEje (`z_local=14,7625 mm`); Ø16 igual al eje. |
| B-CarretelSup | Brazo | Cara exterior en `y_local=-25 mm` de A-Brazo, junto al codo. |
| B-CarretelInf | Antebrazo | Cara exterior en `y_local=-25 mm` de B-Antebrazo, junto al codo. |
| R-CarretelInf | Antebrazo | Cara exterior en `y_local=-25 mm` de R-Bancada; Ø36 sobre el cuello Ø35. |
| R-CarretelSup | Muñeca | Cara exterior en `z_local=91 mm` de Z-BujeExterior; Ø35 y anclaje a radio 17,5 mm. |

Los seis contactos de plano difieren en menos de 10⁻¹² m (coordenadas en el JSON). Justifican la **pertenencia visual propuesta**, no que un ajuste impreso transmita fuerza ni que los tornillos o mates angulares estén resueltos. Los seis figuran en `provisional_attachments`.

Los planos de carreteles A muestran agujeros de 35/40 mm y los nativos actuales 16/17 mm: se usa la geometría nativa. Las **fases angulares** no quedan fijadas por los snapshots; no se giran piezas para alinear un tornillo, se conserva la matriz inicial y cada mitad acompaña a su cuerpo.

### Ejes y longitud de eslabones

[tools/extraer_ejes_cad.py](../tools/extraer_ejes_cad.py) reproduce las mediciones de cilindros con OCP sobre los STEP existentes y exige hallar los cilindros identificados y sus líneas coincidentes entre piezas ([ejes_propuestos.json](../cad/ensambles/ejes_propuestos.json), [evidencia_ejes_cilindros.json](../cad/ensambles/evidencia_ejes_cilindros.json)). Puntos en el sistema guardado de `0-EnsambleColision`, en metros:

| Eje | Evidencia | Punto sobre la línea |
| --- | --- | --- |
| J1 | Agujero Ø16 de A-BridaEje; coincide con Ø16 de A-Brazo (z local 30 mm) y la línea de la torre | `(-0,032666639; 0,010499991; 0,162021372)` |
| J2 | Agujero Ø9 de A-Brazo (z local 280 mm); coincide con Ø8 de B-Antebrazo y centros de carreteles B | `(-0,028960537; -0,239472537; 0,162021372)` |
| J3 | Cilindros coaxiales Ø35/40/44 de Z-BujeExterior; coincide con R-Bancada y Z-Cuerpo | `(-0,035649955; -0,489383024; 0,225021372)` |
| J4 | Línea central de Z-Piston, coaxial con Z-Cuerpo y J3 | `(-0,035649955; -0,489383024; 0,194717013)` |

Las cuatro líneas son paralelas a Z. Los puntos son referencias sobre caras identificadas: desplazar uno a lo largo de su eje describe la misma línea y **no define un anchor único ni un offset cinemático**. Los signos salen de las superficies, no de los motores. Las distancias horizontales J1–J2 y J2–J3 son ambas **0,250 m** (diferencias < 2·10⁻¹⁵ m), por lo que el caño de antebrazo de 237 mm no es la longitud cinemática.

### Sistema canónico y pose de referencia

Una única transformación rígida desde el snapshot: (1) girar 180° sobre X para orientar el pedestal hacia abajo; (2) girar sobre Z para alinear J1→J2 con +X; (3) trasladar el centro horizontal de J1 a `(0,0)` y el plano `z_local=221,6 mm` de `0-Torre` a `z=0`. Es nuestra convención de simulación, reversible y trazable; el JSON guarda la matriz exacta. Alturas de los frames, desde los centros de agujero: hombro (A-Brazo local `(0,0,30 mm)`) **0,2913625 m**; codo (B-Antebrazo local `(0,0,220 mm)`) **0,2133625 m**; muñeca, línea J3 a la altura del codo. La bajada hombro–codo es **78 mm** y no se la reemplaza por el nominal del master mientras se usen las matrices de este snapshot.

Pose articular que reproduce el snapshot:

```text
q1 = 0
q2 = 0,04158581792222517 rad
q3 = 0,07223652440584233 rad
q4 = 0,060 m
```

`q4 = 60 mm` es la mitad del recorrido de 120 mm, para tener movimiento en ambos sentidos; **no es un home medido**. El rumbo del conjunto Z es **−X local** de Z-Cuerpo; los −X locales de Z-Cuerpo, Z-Piston y Z-SoporteEfector coinciden en **0,11382234232806758 rad**. Elegir el otro lado del cuadrado suma π: es otra convención, no un cero mecánico.

**Punto de herramienta provisional:** el centro del plano exterior del soporte, `Z-SoporteEfector local (0,0,0)`, para el prototipo sin pinza. En la pose de referencia queda en `x = 0,49978385862038005 m`, `y = 0,010393458169144124 m`, `z = 0,03466685886479948 m`. Con la muñeca a 0,2133625 m y J4 positivo hacia abajo, el offset constante a `q4=0` es **−0,11869564113520076 m**: `z_punto = z_muñeca − q4 + offset`. No es un TCP oficial ni evidencia de una pinza inexistente.

### Conservar las colocaciones al articular

Los marcos de eslabón se fijan en la pose de referencia. Para cada instancia:

```text
T_mundo_pieza_guardada = T_canónico_desde_guardado · T_guardado_pieza
T_eslabón_pieza = inversa(T_mundo_eslabón_en_qref) · T_mundo_pieza_guardada
```

El JSON trae ambas matrices por instancia. Reconstruir las 20 poses originales desde los marcos coincide con el JSON dentro de 1,2·10⁻¹⁵. Los STL ya están en metros: estas matrices no vuelven a escalar.

### Regenerar tras una decisión de montaje

Editá `config/cad_integration.json` con evidencia y corré:

```sh
python3 tools/integrate_cad.py
python3 tools/generate_world.py
```

`integrate_cad.py --update-config` actualiza además dimensiones cinemáticas y cajas equivalentes conservando las masas exploratorias; es un cambio deliberado de configuración, así que repetí los controles afectados. Una adición solo visual se integra sin esa opción. No edites a mano el manifiesto, el mundo ni el PROTO: son generados.

## 5. Generación del mundo y vista de inspección

`tools/generate_world.py` construye el robot y el mundo dinámico desde `config/scara.json` y el manifiesto; el mundo dinámico `scara.wbt` es independiente de la vista de inspección.

[tools/generate_cad_preview.py](../tools/generate_cad_preview.py) genera el mundo estático [scara_cad_inspeccion.wbt](../webots/worlds/scara_cad_inspeccion.wbt) desde `0-EnsambleColision`, sin `Physics`, motores ni colisión, conservando la pose y el marco guardados. Muestra colocaciones recuperadas, no esfuerzos ni dinámica. Sus 20 instancias tienen todas geometría:

- **16 azules:** malla aceptada con caja actual coincidente con la guardada dentro de 0,05 mm.
- **Torre:** tres `Shape` bajo la matriz de `0-Torre-1`, con las mallas por cuerpo. Estado `body_meshes_validated_zero_area_cleanup`; en el informe principal `0-Torre` sigue rechazada como malla global.
- **3 ámbar:** los dos NEMA17 y R-CarretelSup (malla aceptada, caja distinta de la caché).

El generador verifica hashes de original, STEP, informe, exportador y mallas, y recalcula las métricas de cada STL; [inspeccion_webots.json](../cad/ensambles/inspeccion_webots.json) registra disposición, hashes y malla de cada instancia. No hay suelo: el marco guardado deja la torre por encima de los brazos ([preview nativo](../cad/ensambles/previews/0-EnsambleColision.png)); la rotación de 180° sobre X solo se aplica en la integración (§4). No sobrescribe `webots/worlds/scara.wbt`; para otro conjunto admite `--assembly A-EnsambleBrazo.SLDASM --output /ruta/otra_vista.wbt` dentro del proyecto.

Las capturas [scara_cad_inspeccion.png](../validation/cad/scara_cad_inspeccion.png) y [scara_cad_sin_torre.png](../validation/cad/scara_cad_sin_torre.png) se tomaron con Webots R2025b Nightly, build `a459c02c7292d23ae437101c76111ec1668198c8`.

Reproducción de extracción y vista (con la revisión local del conversor en `/ruta/conversor`):

```sh
python3 -B tools/extraer_ensamble.py --self-check
python3 -B tools/extraer_ensamble.py --converter-root /ruta/conversor
python3 -B tools/generate_cad_preview.py --self-check
python3 -B tools/generate_cad_preview.py
python -B tools/exportar_torre_cuerpos.py   # Python con OCP
python -B tools/extraer_ejes_cad.py         # Python con OCP
```

No hace falta reconvertir para usar los mundos ya preparados.

## 6. Límites

- Aceptación topológica no es fidelidad certificada: quedan 3 rechazos globales y 21 piezas con advertencias.
- Las colocaciones son las guardadas por SolidWorks: sin mates resueltos ni maestro único de los diez conjuntos.
- No hay revisión oficial, ceros, homing, topes, signos de motor ni TCP oficial; marcos, `q4 = 60 mm` y rumbo son convenciones provisionales.
- Los carreteles tienen pertenencia visual propuesta, con fase y fijación sin resolver; las poleas giratorias son solo visuales; los rodamientos están simplificados; los NEMA23 son carcazas fijas.
- La torre son tres mallas validadas por separado, sin certificar su unión.
- Las masas son exploratorias; las colisiones siguen siendo cajas.
- Un contraste independiente exigiría exportar desde el CAD de origen un STEP sólido por pieza (unidades, origen y orientación locales, versión del exportador y hashes) y comparar sólidos, dimensiones, volumen, centroide y colocación antes de sustituir derivados.
- El alcance es el de una simulación del diseño sin hardware (D0 del [registro de decisiones](REGISTRO_DE_DECISIONES.md)).

## 7. Fuentes técnicas

Las referencias de Webots describen R2025a.

- Webots R2025a: [Mesh](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/mesh.md), [Solid](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/solid.md), [Physics](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/physics.md), [HingeJointParameters](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/hingejointparameters.md), [Motor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/motor.md), [PositionSensor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/positionsensor.md), [Supervisor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/supervisor.md), [controlador](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/controller-programming.md) y [TCP/IP](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/interfacing-webots-to-third-party-software-with-tcp-ip.md).
- [sldprt2step, revisión fijada](https://github.com/BlinkingSun/sldprt2step/tree/fa954124f4f126e0c465c8f96454978ac80b812e) y [paquete OCP sin VTK](https://pypi.org/project/cadquery-ocp-novtk/8.0.1.1.0/) (versiones en `tools/requirements-cad.txt`).
- [OCCT BRepGProp](https://www.occt3d.com/dev/doc/refman/html/class_b_rep_g_prop.html) y [GProp_GProps](https://www.occt3d.com/dev/doc/refman/html/class_g_prop___g_props.html): integrales geométricas; ver [PROPIEDADES](PROPIEDADES.md).
- [API SolidWorks de referencias externas](https://help.solidworks.com/2021/english/api/swdocmgrapi/SolidWorks.Interop.swdocumentmgr~SolidWorks.Interop.swdocumentmgr.ISwDMDocument27~GetExternalFeatureReferences3.html): datos que el documento padre guarda de sus referencias.
- Documentación de la cátedra: [00-SCARA-Master.pdf](../00-SCARA-Master.pdf), [CONSIGNA-TP-FINAL.pdf](../CONSIGNA-TP-FINAL.pdf).
