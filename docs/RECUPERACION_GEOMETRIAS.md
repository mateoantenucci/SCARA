# Recuperación de las tres geometrías pendientes del montaje

16 de octubre de 2026. Se recuperaron `B-CarretelInf`, `B-CarretelSup` y `Z-SoporteEfector` corrigiendo una tolerancia numérica del conversor de curvas de intersección. Las tres piezas superan ahora el control de sólidos BREP y de mallas cerradas. No se reconstruyeron piezas desde planos, no se añadieron superficies y no se aplicaron `ShapeFix`, cosido ni relleno de huecos.

El resultado completó la geometría de las **30 instancias seleccionadas en aquella etapa**. El montaje posterior y sus ensayos están en [Validación](historico/VALIDACION_WEBOTS.md). No completa por sí solo el montaje mecánico: siguen pendientes componentes, revisión oficial, fijaciones y fases de los carreteles, además de la revisión de interferencias internas. El alcance continúa siendo el de [simulación del diseño con evidencia declarada](adr/0001-simulacion-del-diseno-sin-hardware.md).

## Diagnóstico y corrección

El [informe de conversión anterior](../validation/historico/antes_geometrias_20261016/cad/derivados/informe.json) conservaba los rechazos sin publicar sus STL:

| Pieza | Resultado anterior | Resultado recuperado |
| --- | --- | --- |
| B-CarretelInf | El conversor declaraba un sólido, pero OCCT obtenía 25 caras y cero sólidos. | Un sólido válido, 25 caras OCCT y malla cerrada. |
| B-CarretelSup | El mismo defecto: 25 caras sin sólido admisible. | Un sólido válido, 25 caras OCCT y malla cerrada. |
| Z-SoporteEfector | Un sólido inválido; advertencias de blends e intersecciones. | Un sólido válido y malla cerrada; continúan las advertencias sobre superficies aproximadas. |

El objetivo de refinamiento de curvas de intersección pasó de **10⁻⁷ a 10⁻⁹ m**. El [adaptador de precisión](../tools/patches/intersection_precision.py) cambia únicamente el parámetro `tol` de `_refine_on_surfaces` en `XtStepMapper.intersection_curve`: refinamiento adaptativo Hermite con proyección sobre las superficies. Conserva las superficies, la topología XT, los puntos iniciales de las curvas, las alternativas de ejecución y los límites de refinamiento del conversor original; tampoco modifica los nativos.

El objetivo anterior, 10⁻⁷ m = 10⁻⁴ mm, era mayor que la incertidumbre declarada por el STEP, **10⁻⁵ mm**. El nuevo objetivo es 10⁻⁹ m = 10⁻⁶ mm. Esta comparación explica la inconsistencia numérica que se corrige, pero **no certifica un error máximo igual al objetivo**: el algoritmo conserva límites de profundidad, presupuesto y longitud de cuerda. Tampoco declara precisión física de las piezas, de la impresión ni del robot.

La geometría se vuelve a generar desde los mismos `.SLDPRT` y se somete al mismo control geométrico del lote. No se da por recuperada una pieza porque el conversor devuelva `ok`, porque el volumen de un conjunto de caras sea calculable o porque su apariencia parezca correcta. Se exigen sólidos válidos y volumen positivo, caja envolvente finita, y STL cerrado y manifold con volumen y dimensiones coherentes con su BREP.

Los dos STEP B anteriores son idénticos al normalizar únicamente los nombres de pieza de `FILE_NAME` y `PRODUCT`. Sus nativos tienen hashes distintos; no se sustituyó una mitad por la otra. La coincidencia de la geometría traducida permite estudiar un defecto común, pero no certifica que las piezas sean intercambiables ni que tengan la misma función de montaje.

## Resultados geométricos

| Pieza | Sólidos válidos | Caras OCCT | Volumen BREP, mm³ | Triángulos STL | Diferencia de volumen STL/BREP |
| --- | ---: | ---: | ---: | ---: | ---: |
| B-CarretelInf | 1 | 25 | 12.725,752428 | 8.290 | 0,148 % |
| B-CarretelSup | 1 | 25 | 12.725,752428 | 8.290 | 0,148 % |
| Z-SoporteEfector | 1 | 49 | 22.148,156985 | 6.188 | 0,1124 % |

Las tres mallas tienen **cero aristas libres y cero aristas no manifold** en la comparación de coordenadas float32 exportadas. Se conservan las cajas locales: 70 × 70 × 14 mm para ambas mitades B y 60 × 60 × 19 mm para el soporte. Los STEP declaran milímetros; los STL se publican en metros aplicando una sola vez el factor 0,001, sin cambiar origen ni orientación local.

En el soporte, el STEP declara 48 caras y la transferencia OCCT produce 49. El número diferente se registra; la aceptación depende de los sólidos y sus comprobaciones, no de exigir igualdad entre esos dos conteos de caras. Las aproximaciones de blends y curvas de intersección siguen siendo una limitación del traductor.

Se comprobó también la convergencia al bajar el objetivo de 10⁻⁹ a 10⁻¹⁰ m, con resultados en el [informe consolidado](../validation/cad_recovery.json). Para B, ensayado sobre `B-CarretelInf` y con candidatos geométricos idénticos en ambas mitades, el cambio relativo de volumen es **1,08 × 10⁻⁶** y el máximo cambio de componente del centroide es **2,98 × 10⁻⁶ mm**. En Z, los cambios son **5,16 × 10⁻¹²** y **6,50 × 10⁻¹¹ mm**, respectivamente. Ambos ensayos conservan sólidos y mallas válidos. La convergencia respalda la corrección numérica, pero no constituye un contraste independiente con SolidWorks u otro traductor.

El lote pasa de **44 a 47 STL aceptados**, con tres rechazos globales restantes: `0-Torre`, `B-ExtensorM3` y `Z-BujeInterior`. La torre conserva además su [recuperación visual por sólidos](../cad/derivados/torre_por_cuerpos/README.md), separada de la aceptación de una malla global. El [informe vigente](../cad/derivados/informe.json) actualiza estas tres piezas y conserva las otras 47 entradas; el historial y el snapshot preservan el resultado anterior.

El [precálculo regenerado](../cad/propiedades/propiedades_geometricas.json) confirma **49 tipos de pieza, 51 sólidos y 30/30 instancias seleccionadas**, frente a los 46 tipos, 48 sólidos y 27/30 anteriores. Solo `B-ExtensorM3` queda excluida del cálculo por BREP inválido, fuera de esas 30 instancias. Una cobertura de 30/30 describe únicamente esta selección; no declara incorporadas todas las piezas del diseño ni asignadas sus propiedades físicas.

El consolidado confirma **152 archivos originales intactos**, las **47 entradas retenidas idénticas** y la configuración de física idéntica byte a byte. La regeneración deja **30 instancias con malla y cero cajas alámbricas pendientes**. Las matrices pieza→cuerpo solo presentan diferencias de redondeo en cinco instancias, con variación máxima de **2,78 × 10⁻¹⁷**; los parámetros geométricos se conservan.

## Contraste con las fuentes locales

Se verificó la identidad de los tres nativos contra los SHA-256 del informe anterior. Antes de esta recuperación no había STL, OBJ, 3MF, Parasolid ni IGES alternativos de esas mismas piezas en el repositorio. Los nuevos STL son derivados de esta corrección. Los STL originales de carreteles A pertenecen a otras piezas y no sirven como reemplazo sustentado de B.

Las referencias activas de los ensambles usan la configuración **`Predeterminado`**, sin supresión ni ocultamiento. Las cajas actuales coinciden con las guardadas dentro de aproximadamente 10⁻¹⁰ m. Esa coincidencia comprueba una referencia exterior; no demuestra igualdad de todas las caras o perforaciones.

| Pieza | Referencias de ensamble guardadas | Evidencia y límite |
| --- | --- | --- |
| B-CarretelSup | `0-EnsambleColision`, `A-EnsambleBrazo` | Stamp de modelo 267; pertenece visualmente al brazo según el contacto de planos documentado. No tiene plano individual local. |
| B-CarretelInf | `0-EnsambleColision`, `A-EnsambleBrazo`, `B-EnsambleAntebrazo` | Stamp 266; pertenece visualmente al antebrazo. No tiene plano individual local. |
| Z-SoporteEfector | `0-EnsambleColision`, `Z-EnsambleEfector` | Stamp 191 en el global y 196 en el conjunto Z, con la misma caja exterior. La diferencia no permite elegir una revisión oficial. |

Los stamps son valores de caché de SolidWorks, no números de revisión mecánica aprobada. Las matrices y el origen de las referencias se conservan en el [informe de ensambles](../cad/ensambles/informe.json). La recuperación geométrica mantiene la [pertenencia de cuerpos y colocaciones adoptadas](INTEGRACION_CAD_CRITERIOS.md); no gira mitades para alinear tornillos ni resuelve mates pendientes.

El [plano de Z-SoporteEfector](../Modelos3D/Z-SoporteEfector.PDF), revisado visualmente, muestra diámetro exterior 60, altura total 19, placa 4, resalte 15 y alojamiento cuadrado 20. Esas cotas son coherentes con la caja en milímetros del STEP. El plano no imprime una declaración general de unidades. El [maestro, p. 24](../00-SCARA-Master.pdf), reproduce ese plano y declara el acoplamiento rígido al pistón y al efector; el [plano de Z-EnsambleEfector](../Modelos3D/Z-EnsambleEfector.PDF) muestra su disposición en sección.

El plano del soporte indica **PLA, relleno del 30 % y masa desconocida**. No se convierte ese porcentaje en densidad efectiva ni se asigna masa al sólido recuperado. Paredes, tapas, relleno, inserciones y revisión deben fundamentarse antes de usarlo en la física. El punto de herramienta sigue siendo la referencia provisional documentada, sin herramienta añadida ni TCP oficial confirmado.

## Reproducción y comprobaciones posteriores

Usar el entorno OCP y las versiones fijadas en [requirements-cad.txt](../tools/requirements-cad.txt). `RUTA` debe apuntar a la revisión local del conversor indicada en el [documento de conversión](EVALUACION_CONVERSION_CAD.md); el proceso no necesita subir modelos a servicios externos.

```sh
python tools/patches/comprobar_intersecciones.py \
  --converter-root RUTA \
  --output validation/cad_recovery_regression.json

python tools/convertir_cad.py \
  --converter-root RUTA \
  --parts B-CarretelInf B-CarretelSup Z-SoporteEfector \
  --merge
```

`--merge` actualiza solo esas tres piezas y conserva las otras 47 entradas; el historial conserva el informe reemplazado. **Ese comando retorna código 1 por los tres rechazos globales retenidos**, aunque las tres piezas solicitadas hayan pasado. Se debe leer el informe combinado, no interpretar ese código como un nuevo rechazo de las recuperadas.

Después se regeneran los artefactos dependientes en este orden, usando el mismo Python con OCP:

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

La integración se ejecuta **sin `--update-config`**: la configuración de física conserva sus bytes. Las cajas de colisión mantienen su función de envolvente; una malla visual más completa no convierte automáticamente las colisiones en contactos de superficies CAD.

La evidencia de esta recuperación y sus verificaciones posteriores se separa por alcance:

| Evidencia | Resultado confirmado |
| --- | --- |
| [cad_recovery.json](../validation/cad_recovery.json) | `passed`: consolida resultados, convergencia, preservación de originales/entradas/configuración y las 30 instancias con malla, sin referencias alámbricas pendientes. |
| [cad_recovery_regression.json](../validation/cad_recovery_regression.json) | `passed: true`: 15/15 comprobaciones de la comparación real sin/con adaptador, incluyendo sólidos, mallas y preservación de fuentes. |
| [propiedades_geometricas.json](../cad/propiedades/propiedades_geometricas.json) | 49 tipos, 51 sólidos y 30/30 instancias; 217 entradas protegidas conservadas durante el cálculo. |
| [collisions_recovery.json](../validation/collisions_recovery.json) | Cuatro controles aprobados; 11 poses y 22 BREP móviles, sin exclusiones. Se confirman ocho intersecciones contra el pedestal: pistón y soporte en cuatro poses; el comprobador rechaza esas invasiones. |
| [cad_motion_recovery.json](../validation/cad_motion_recovery.json) | `passed`: 11 snapshots, 330 colocaciones de instancia comprobadas y seis llegadas articulares. Error máximo de posición de colocación: aproximadamente 4,50 × 10⁻⁶ m. |
| [collisions_native_recovery.json](../validation/collisions_native_recovery.json) | `passed`: cinco controles nativos aprobados, incluidas 30 cajas por instancia, rechazo de destino/recorrido invasivos, contacto bajo gravedad y restauración del ensayo. El contacto del soporte se aproxima con su caja. |

La auditoría BREP ahora puede medir también el soporte: antes solo se certificaba el volumen de invasión del pistón. Las ocho intersecciones son resultados esperados de poses invasivas de ensayo; aprobar el informe significa que se detectan y rechazan, no que todo el espacio de trabajo esté libre. Las poses finitas, el ensayo de movimiento y los cinco controles nativos tampoco resuelven las autocolisiones internas ni validan componentes aún no representados.

## Exportación alternativa como contraste opcional

La exportación alternativa deja de ser un requisito para mostrar estas tres piezas. Sigue siendo útil para contrastar fidelidad del traductor y confirmar la revisión mecánica vigente. El pedido concreto, si se dispone del CAD original, es:

1. Identificar revisión y configuración de los tres nativos por nombre y SHA-256 del informe, y aclarar qué ensamble debe representar la entrega. Para Z, reconciliar los stamps 191/196 sin elegirlos por intuición.
2. Abrir y reconstruir cada pieza de esa revisión en el CAD de origen; exportar **un STEP sólido por pieza**, con unidades explícitas y conservando origen y orientación local. Registrar versión del exportador, configuración y fecha. No fusionar los tres componentes ni desplazar sus marcos para hacerlos coincidir con el ensamble.
3. Si se exporta también STL, entregar un archivo por pieza, declarar sus unidades y tolerancias y conservar el mismo marco. STL no incorpora por sí solo una unidad inequívoca y no sustituye el sólido BREP para propiedades o interferencias volumétricas.
4. Conservar los archivos alternativos en una ruta separada, con hashes. Comparar cantidad y validez de sólidos, dimensiones, agujeros, volumen, centroide y colocación antes de sustituir derivados activos. Una caja exterior coincidente no basta.

No se requiere redibujar desde los PDF ni medir manualmente colocaciones ya recuperadas. Las consultas sobre revisión, fijaciones, materiales y herramienta siguen reunidas en [Datos para el profesor](historico/DATOS_PARA_EL_PROFESOR.md).
