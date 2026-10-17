# Propiedades geométricas del CAD y paso a propiedades físicas

Actualizado el 17 de octubre de 2026. **Precálculo geométrico vigente:** se analizaron los 50 STEP existentes, se obtuvieron propiedades de **49 tipos de pieza —51 sólidos— y de las 36/36 instancias seleccionadas** del modelo articulado. Solo `B-ExtensorM3` queda excluida por BREP inválido; no pertenece a esas 36 instancias. Los seis rodamientos incorporados se incluyen como volumen geométrico de referencia, sin inferir sus materiales internos. No se asignaron materiales ni se aplicaron estos resultados a la física activa.

Este documento explica qué calculamos, cómo repetirlo y qué información falta. Para abrir el robot, consultar el [README](../README.md); para entender todo el recorrido del proyecto, [Proceso y archivos](PROCESO_Y_ARCHIVOS.md).

El cálculo inicial del 15/10 cubría 46 tipos, 48 sólidos y 27/30 instancias. El [punto 2 de colisiones](COLISIONES_Y_RECORRIDOS.md) cambió después configuración y envolventes; su estado previo está en [el snapshot anterior a colisiones](../validation/historico/antes_colisiones_20261015/). El 16/10 se [recuperaron las tres geometrías del montaje](RECUPERACION_GEOMETRIAS.md) y se regeneró este precálculo: el [snapshot anterior a geometrías](../validation/historico/antes_geometrias_20261016/cad/propiedades/propiedades_geometricas.json) conserva la cobertura 46/48/27. Cada informe identifica sus fuentes mediante hashes; la evidencia histórica no se atribuye automáticamente al estado vigente.

## 1. Qué se puede explorar

| Archivo | Contenido y uso |
| --- | --- |
| [propiedades_geometricas.csv](../cad/propiedades/propiedades_geometricas.csv) | Tabla para abrir en una planilla. Filtrar `kind` para ver piezas, sólidos, instancias o grupos. Los valores están en unidades SI; las filas excluidas tienen las propiedades vacías, nunca cero. |
| [propiedades_geometricas.json](../cad/propiedades/propiedades_geometricas.json) | Informe completo: volumen, centroide, tensor central, sólidos individuales, originales y STEP con SHA-256, advertencias del conversor, transformaciones y cobertura por grupo. |
| [calcular_propiedades_cad.py](../tools/calcular_propiedades_cad.py) | Fuente del cálculo. Lee los artefactos existentes; no reconvierte, repara ni escribe originales, configuración, mundo o PROTO. |
| [test_cad_properties.py](../tests/test_cad_properties.py) | Comprobaciones reproducibles de escala, tensor central, rotación y composición. |
| [validation/cad_properties.json](../validation/cad_properties.json) | Evidencia histórica del 15/10: 21 pruebas aprobadas sin omisiones y contraste independiente de cinco cuerpos sobre la cobertura anterior. Conserva hashes, métodos y resultados de aquella corrida. |
| [validation/cad_recovery_regression.json](../validation/cad_recovery_regression.json) | Regresión del 16/10: 15/15 controles aprobados al comparar las tres conversiones sin/con la corrección de curvas de intersección. |

En el CSV, `part` es un tipo de pieza en su marco local; `solid` es un sólido de esa pieza, en el mismo marco; `instance` es una ocurrencia colocada, expresada en el marco de su cuerpo; `body` es la suma de las instancias disponibles de un grupo. **Esas cuatro vistas se solapan: no sumar todas las filas.** Dos NEMA17 son dos instancias distintas del mismo tipo y se cuentan una vez cada una al formar sus respectivos grupos.

`computed` significa que se pudieron calcular integrales de un BREP válido. No significa masa real conocida ni componente aprobado para física. `partial_additive_reference` identifica una suma geométrica de referencia; `excluded` conserva el motivo del rechazo. El JSON mantiene `mass_kg` y `density_kg_m3` sin asignar en las piezas.

## 2. Qué significan las magnitudes

El **volumen V** es el espacio ocupado por el sólido recuperado, descontando los huecos que contiene su geometría. El **centroide c** es su centro volumétrico: coincide con el centro de masa si la densidad es uniforme. No coincide necesariamente con el centro de una caja envolvente.

El **tensor central Jc** describe cómo está distribuido ese volumen alrededor del centroide. Se conserva la matriz completa, incluidos los términos cruzados. Sus ejes son paralelos a los del marco indicado; no se giró cada pieza para diagonalizarla.

```text
Jc = ∫ [ (r·r) E − r rᵀ ] dV, con r = posición − centroide
Jxy = −∫ rx ry dV          (análogamente Jxz y Jyz)

Para una pieza homogénea, cuando se conozca rho:
masa = rho V
centro de masa = c
inercia central I = rho Jc
```

`E` es la matriz identidad. V se guarda en **m³**, c en **m**, Jc en **m⁵** y rho deberá expresarse en **kg/m³**. El producto rho·Jc queda en **kg·m²**. También puede interpretarse Jc como el valor numérico de la inercia a densidad de referencia 1 kg/m³; esa referencia no es un material asignado al robot.

El STEP se transfiere explícitamente a milímetros en OCCT. Se aplican los factores **10⁻⁹ al volumen, 10⁻³ al centroide y 10⁻¹⁵ al tensor**. El último factor tiene potencia cinco porque integra una distancia al cuadrado sobre un volumen. No se reutiliza la escala de un STL ni se considera que `GProp_GProps.Mass()` entregue kilogramos: aquí entrega volumen.

Ejemplo real, `A-Brazo`, en su marco de pieza:

```text
V = 6,9501053162809 × 10⁻⁵ m³ = 69,501053 cm³
c ≈ (0; 0,084705; 150,101162) mm
diagonal de Jc ≈ (5,424834×10⁻⁷; 5,427294×10⁻⁷; 5,524795×10⁻⁸) m⁵
masa pendiente = rho × 6,9501053162809 × 10⁻⁵ kg
```

La matriz completa está en el informe. Este ejemplo usa la geometría del tubo con sus huecos, no una barra maciza de 300×50×50 mm. Las cifras conservadas permiten reproducir el cálculo; su cantidad de decimales no declara igual exactitud respecto del diseño original.

## 3. Método y criterios de aceptación

1. Se verifica la integración contra sus fuentes mediante `derive()` del integrador existente. La comparación admite 10⁻¹² absoluto/relativo en números para las diferencias de redondeo entre Python 3.9 y 3.12. Se usan las matrices guardadas del manifiesto vigente.
2. Se contrastan los SHA-256 de cada SLDPRT y STEP con el lote de conversión. Un cambio de fuente detiene el cálculo: no se presenta una revisión diferente con el mismo resultado.
3. OCCT lee cada STEP y comprueba el BREP global y cada sólido. Se exige al menos un sólido, shells cerrados, volumen positivo y finito y ausencia de caras ajenas a los sólidos contabilizados. No se calculan propiedades aceptadas de una colección de caras sueltas.
4. `BRepGProp.VolumeProperties` integra las superficies BREP con `OnlyClosed=True`, `SkipShared=True` y `UseTriangulation=False`. No se tesela ni se ejecuta reparación geométrica. Son integrales numéricas sobre la geometría convertida, no una certificación de traducción exacta desde SolidWorks.
5. Se guarda cada sólido y se suman sus propiedades con ejes paralelos. Se exige tensor finito, simétrico y positivo, y segundo momento volumétrico positivo. Volumen y centroide se contrastan con el informe BREP previo: diferencia relativa de volumen ≤10⁻⁶ y distancia de centroides ≤10⁻⁸ m.
6. Se transforman centroide y tensor a las coordenadas del cuerpo correspondiente. Se contabiliza cada instancia una sola vez y se registran las ausentes. La base también se informa, aunque sigue fija y sin `Physics`.
7. Se comprueba al terminar que los archivos protegidos conservan sus hashes. El informe incluye originales, STEP, fuentes de integración, código del cálculo, configuración y mundo/PROTO. La corrida guardada conservó los **217 archivos protegidos**.

No se certificó la equivalencia independiente con SolidWorks ni se corrigieron intersecciones entre sólidos. **Las sumas son aditivas, no uniones booleanas:** si dos volúmenes se superponen, la suma cuenta esa región dos veces. Por eso no se publica un «volumen total real del robot» ni se interpreta la suma como cota inferior garantizada.

## 4. Resultados y exclusiones

| Pieza de ejemplo | Volumen geométrico, cm³ | Alcance |
| --- | ---: | --- |
| A-Brazo | 69,501053 | Tubo y perforaciones del sólido convertido. |
| B-Antebrazo | 54,121249 | Marco local de pieza; no confundir longitud del tubo con distancia entre ejes. |
| B-CarretelInf / B-CarretelSup | 12,725752 cada una | Sólidos recuperados el 16/10; se contabiliza cada instancia en su propio cuerpo. |
| Z-Cuerpo | 21,537529 | Geometría de la revisión actual disponible. |
| Z-Piston | 16,148952 | Solo el pistón; el soporte se calcula por separado. |
| Z-SoporteEfector | 22,148157 | Sólido recuperado el 16/10, sin masa ni densidad asignadas. |
| 0-Torre | 392,812936 | Suma de tres sólidos válidos; no unión global certificada. |
| Z-BujeInterior | 8,449958 | BREP válido aunque no tenga STL aceptado. No se agregó al robot. |
| NEMA17 | 65,771943 | Volumen del CAD disponible; no permite inferir masa/distribución internas del motor. |

El control para **integrales de sólidos** y el control para **mallas visuales** resuelven cosas distintas. Hay **49 tipos con propiedades calculadas**, mientras el lote visual tiene **47 STL aceptados y tres rechazos globales**: `0-Torre`, `B-ExtensorM3` y `Z-BujeInterior`. La torre y el buje interior tienen BREP admisible para integrales; la torre conserva además su recuperación visual separada por cuerpos. El resultado histórico de 44 STL y seis rechazos permanece archivado.

| Pieza excluida | Motivo | Efecto sobre el modelo articulado |
| --- | --- | --- |
| B-ExtensorM3 | BREP global inválido. | No forma parte de las 36 instancias actuales. |

No se usa el volumen que el kernel pudiera devolver al integrar la geometría inválida excluida ni se sustituye por su caja. Los dos carreteles B y el soporte dejaron de estar excluidos después de corregir el refinamiento de intersecciones en el conversor; pasaron nuevamente los controles BREP, sin cosido ni reparación de sólidos.

## 5. Colocaciones y sumas por grupo

Para una matriz de colocación con rotación R y traslación t:

```text
centroide en cuerpo: ci = R cpieza + t
tensor central en cuerpo: Ji = R Jpieza Rᵀ

Referencia de grupo a densidad común:
Vgrupo = Σ Vi
cgrupo = Σ Vi ci / Vgrupo
Jgrupo = Σ [ Ji + Vi ((di·di) E − di diᵀ) ], di = ci − cgrupo
```

La traslación no cambia el tensor **central de una pieza**. El término de ejes paralelos aparece al reunir piezas respecto del centroide del grupo. Los marcos son los cinco cuerpos de `scara/frames.py`, documentados en [criterios de integración](INTEGRACION_CAD_CRITERIOS.md). Las propiedades expresadas en esos marcos no dependen de la pose actual de Webots.

| Grupo | Instancias calculadas/seleccionadas | Suma aditiva, cm³ | Centroide de referencia en el cuerpo, mm | Instancia seleccionada sin propiedades |
| --- | ---: | ---: | --- | --- |
| base | 10/10 | 940,295545 | (0,044969; −2,487440; 150,256227) | Ninguna entre las seleccionadas. |
| arm — brazo | 8/8 | 161,183880 | (149,792142; −0,011706; −8,890707) | Ninguna entre las seleccionadas. |
| forearm — antebrazo | 10/10 | 390,617901 | (119,828755; 0,000439; −6,715140) | Ninguna entre las seleccionadas. |
| wrist — muñeca/conjunto Z | 6/6 | 197,036450 | (0,013790; −0,009364; 145,970815) | Ninguna entre las seleccionadas. |
| tool — pistón/herramienta | 2/2 | 38,297109 | (−0,000003; 0,036039; 49,975097) | Ninguna entre las seleccionadas. |

**Estos centroides no son los centros de masa físicos del grupo multimaterial.** La cobertura 36/36 no demuestra que los cuerpos del diseño estén completos. Las sumas siguen siendo referencias parciales y aditivas, sin auditoría de solapamientos internos: continúan pendientes tornillos, correas, ejes y otras piezas no incorporadas, además de la asignación provisional de seis mitades de carretel. NEMA17×2 y R-CarretelSup mantienen discrepancias de revisión/caja respecto del caché.

Cuando existan materiales diferentes, se calcula `mi = rhoi Vi`, luego `C = Σ mi ci / Σ mi` y finalmente `I = Σ [rhoi Ji + mi ((di·di) E − di diᵀ)]`, usando ahora `di = ci − C`. En un componente comercial se usa su masa, COM e inercia sustentados por ficha/modelo equivalente, sin volver a multiplicarlos por una densidad.

## 6. Cómo reproducirlo

Para explorar el CSV/JSON no hacen falta dependencias CAD. Para recalcular se requiere Python 3.11–3.14 y las versiones de [requirements-cad.txt](../tools/requirements-cad.txt); el cliente y Webots siguen usando su Python habitual sin OCP.

Entorno ya disponible en esta máquina —temporal, puede caducar—:

```sh
cd /Users/mateoantenucci/Developer/SCARA
/private/tmp/scara-cad-piloto-20261014/venv/bin/python tools/calcular_propiedades_cad.py
/private/tmp/scara-cad-piloto-20261014/venv/bin/python -m unittest tests.test_cad_properties -v
```

Si ese entorno deja de existir, se puede crear uno aislado; no hace falta descargar de nuevo el conversor para este precálculo:

```sh
python3.12 -m venv /tmp/scara-propiedades-venv
/tmp/scara-propiedades-venv/bin/python -m pip install -r tools/requirements-cad.txt
/tmp/scara-propiedades-venv/bin/python tools/calcular_propiedades_cad.py --output /tmp/scara-propiedades-repeticion
/tmp/scara-propiedades-venv/bin/python -m unittest tests.test_cad_properties -v
```

Usar un Python compatible instalado en el equipo; el Python 3.9 del sistema sirve para el banco, pero no para estas dependencias OCP. En Windows cambian los ejecutables del venv a `Scripts/python.exe`. `--output` permite comparar otra corrida sin sobrescribir la evidencia. El comando sin esa opción regenera los dos archivos de `cad/propiedades/`; no se editan a mano.

Resultados esperados con los derivados vigentes: **50 piezas examinadas, 49 calculadas, 51 sólidos, una exclusión (`B-ExtensorM3`), 36 instancias seleccionadas y 36 calculadas, y cinco grupos de referencia**. La exclusión conocida se informa y no provoca fallo del precálculo; un hash diferente o una inconsistencia de integración sí detienen la ejecución. Fecha UTC, intérprete, versiones OCP y hashes permiten distinguir corridas. El informe regenerado del 17/10 confirma esa cobertura y la conservación de las 217 entradas protegidas.

Las comprobaciones geométricas usan cajas analíticas y geometría transformada independientemente con OCCT: permiten detectar una escala elevada a la potencia incorrecta, un tensor alrededor del origen en lugar del centroide, signos de términos cruzados o un traslado duplicado. Su aprobación no valida materiales ni las aproximaciones del conversor.

**Resultado histórico del 15/10:** aprobaron las **21 pruebas** de la suite completa con OCP —16 existentes y cinco nuevas—, sin omisiones. Se contrastaron además los cinco grupos de la cobertura anterior por otro camino: releer sus STEP, transformar los BREP con `gp_Trsf`, formar un compuesto y volver a integrar directamente, sin llamar a las funciones de rotación/suma del precálculo. La mayor diferencia relativa del tensor fue **7,30×10⁻¹⁵**, la de volumen **1,78×10⁻¹⁵**, y la distancia máxima de centroides **5,03×10⁻¹⁶ m**. Son acuerdos numéricos entre dos caminos sobre aquel CAD convertido, no incertidumbre física del diseño ni un contraste repetido de las sumas actuales. El [registro histórico](../validation/cad_properties.json) conserva métodos, tolerancias y resultados por cuerpo. El primer intento de la suite bajo sandbox no pudo abrir el socket local TCP; al repetir con permiso de loopback aprobó completo.

## 7. Datos que faltan para reemplazar la física provisional

En los **50 originales** aparece el literal UTF-16LE `Material <sin especificar>`, registrado por pieza en el JSON. La revisión del stream nativo `Header2` con el lector OLE existente también dio 50/50. Esto acredita la etiqueta guardada; no es un parser completo de densidades ni descarta todos los posibles overrides internos. No se extrajo ningún material físico confirmado.

| Dato pendiente | Qué necesitamos concretamente | Por qué afecta la física |
| --- | --- | --- |
| Revisión y montaje vigentes | Ensamble/configuración de referencia, cantidades, fijaciones de carreteles y piezas omitidas; resolver discrepancias documentadas. | Define qué geometría y qué masa pertenecen a cada cuerpo. |
| Geometría adicional excluida | Sólido válido de `B-ExtensorM3`, si la revisión y el montaje requieren incorporarlo. Las 30 instancias seleccionadas ya tienen propiedades geométricas. | El extensor sigue sin volumen/distribución admisibles para una incorporación futura. |
| Piezas homogéneas | Material y densidad por pieza o sólido, con fuente y revisión. | Convierte V y Jc en masa e inercia. Una torre de tres sólidos podría requerir materiales distintos. |
| Impresiones 3D | Filamento, paredes/perímetros, tapas, patrón y porcentaje de relleno, zonas macizas/inserciones; G-code de la pieza/revisión si existe. | El porcentaje de relleno no multiplica uniformemente volumen e inercia. El G-code suelto existente no caracteriza todas las piezas. |
| Componentes comerciales | Modelo exacto, masa y distribución/COM/inercia de motores, rodamientos, acoples, etc.; distinguir carcasa y rotor. | Su CAD simplificado y su envolvente no representan necesariamente el interior. Una masa de catálogo por sí sola no determina el tensor. |
| Elementos auxiliares | Tornillería, correas, cables, imanes, sensores, herramientas y carga prevista; ubicación y fijación. | Pueden cambiar COM e inercia aunque no sean visualmente dominantes. |
| Esfuerzo y transmisión | Motor/driver/alimentación/corriente, curva torque–velocidad, poleas y relaciones, acoplamiento M1/M2, paso ACME, eficiencia, fricción/holgura y condiciones de sostén. | Las propiedades inerciales no determinan los esfuerzos disponibles ni la caída por falta de sostén. |
| Herramienta y contactos | TCP, herramienta/carga nominal, topes, geometrías de colisión y propiedades de contacto pertinentes. | Afecta marcos, carga equivalente, recorridos y respuesta a contactos. |

La lista para consultar al profesor está en [DATOS_PARA_EL_PROFESOR.md](DATOS_PARA_EL_PROFESOR.md); no se enviaron mensajes. Hall/homing y protocolo también siguen pendientes para cerrar el comportamiento del banco, aunque no impiden calcular estas integrales.

El camino posterior es: revisar montaje, componentes adicionales y solapamientos → documentar materiales/modelos comerciales → agregar masas y tensores en cada marco → revisar cobertura → adaptar el generador y la combinación con carga → repetir comprobaciones físicas y nativas. Una hipótesis de densidad efectiva puede estudiarse como escenario declarado; no se convierte automáticamente en material confirmado.

En Webots se podrá fijar `density -1`, masa explícita, `centerOfMass` local y tensor central en el orden `[Ixx Iyy Izz], [Ixy Ixz Iyz]`. Habrá que adaptar también `scara/dynamics.py`, el generador y los ensayos: hoy reconstruyen cajas y una carga cúbica de 40 mm. Cambiar solo `mass` o copiar Jc sin multiplicar por rho dejaría un modelo incoherente.

## 8. Estado del banco y fuentes

Se preservó la física activa: masas exploratorias **0,30 / 0,50 / 0,35 / 0,15 kg**, centros e inercias de cajas, esfuerzos de demostración y cajas de colisión actuales. El precálculo no necesita conectarse a Webots. La recuperación del 16/10 sí regeneró el modelo y comprobó movimiento en [cad_motion_recovery.json](../validation/cad_motion_recovery.json): 11 snapshots, 330 colocaciones y seis llegadas aprobadas; esto no valida las propiedades materiales pendientes.

El usuario confirmó el 15/10/2026 que usa **Webots R2025b nightly** porque R2025a le daba problemas en **macOS 27**. El ensayo de movimiento del 16/10 registra `R2025b Nightly Build 14/10/2026 a459c02c7292d23ae437101c76111ec1668198c8`; el valor corresponde a esa ejecución, sin atribuirlo a otras instalaciones. Los encabezados `.wbt`/`.proto` R2025a se mantienen; este precálculo se ejecuta fuera del simulador.

Referencias primarias para interpretar el cálculo: [OCCT BRepGProp](https://www.occt3d.com/dev/doc/refman/html/class_b_rep_g_prop.html), [OCCT GProp_GProps](https://www.occt3d.com/dev/doc/refman/html/class_g_prop___g_props.html) —matriz central y composición— y [Physics de Webots, revisión R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/physics.md) —campos, unidades y marco—. La configuración particular de una nightly debe contrastarse al integrar y ensayar la física futura.
