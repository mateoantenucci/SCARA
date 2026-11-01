# Propiedades geométricas del CAD y paso a propiedades físicas

El [precálculo actual del 17/10/2026](../cad/propiedades/propiedades_geometricas_39.json) analiza los 50 STEP: **49 tipos de pieza, 51 sólidos y 39/39 instancias**. Solo `B-ExtensorM3` queda excluida por BREP inválido. La [sesión 8](../validation/sesion8/INFORME.md) incorpora una sola ocurrencia de la polea de muñeca ya integrada y contrasta el delta; el par JSON/CSV sin sufijo conserva la corrida histórica de 38. No se asignaron materiales ni se aplicó el precálculo a la física activa.

Este documento explica qué calculamos, cómo repetirlo y qué información falta. Para abrir el robot, consultar el [README](../README.md); para entender todo el recorrido del proyecto, [Proceso y archivos](PROCESO_Y_ARCHIVOS.md).

Los informes históricos conservan sus fuentes mediante hashes. La [recuperación de tres geometrías](RECUPERACION_GEOMETRIAS.md) amplió la cobertura inicial; la evidencia de una corrida no se atribuye automáticamente a una selección posterior.

## 1. Qué se puede explorar

| Archivo | Contenido y uso |
| --- | --- |
| [propiedades_geometricas_39.csv](../cad/propiedades/propiedades_geometricas_39.csv) | Informe actual de 39 instancias. Tabla para abrir en una planilla. Filtrar `kind` para ver piezas, sólidos, instancias o grupos. Los valores están en unidades SI; las filas excluidas tienen las propiedades vacías, nunca cero. |
| [propiedades_geometricas_39.json](../cad/propiedades/propiedades_geometricas_39.json) | Informe actual completo: volumen, centroide, tensor central, sólidos individuales, originales y STEP con SHA-256, advertencias del conversor, transformaciones y cobertura por grupo. |
| [JSON histórico de 38](../cad/propiedades/propiedades_geometricas.json) y [CSV histórico de 38](../cad/propiedades/propiedades_geometricas.csv) | Corrida anterior preservada, con sus fuentes y cobertura propias. |
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
| B-ExtensorM3 | BREP global inválido. | No forma parte de las instancias del modelo integrado. |

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

La tabla siguiente corresponde a la corrida actual de 39 instancias:

| Grupo | Instancias calculadas/seleccionadas | Suma aditiva, cm³ | Centroide de referencia en el cuerpo, mm | Instancia seleccionada sin propiedades |
| --- | ---: | ---: | --- | --- |
| base | 10/10 | 940,295545 | (0,044969; −2,487440; 150,256227) | Ninguna entre las seleccionadas. |
| arm — brazo | 9/9 | 190,937678 | (126,449145; −0,017318; −31,367298) | Ninguna entre las seleccionadas. |
| forearm — antebrazo | 11/11 | 408,848515 | (114,483463; 0,002618; −2,982666) | Ninguna entre las seleccionadas. |
| wrist — muñeca/conjunto Z | 7/7 | 206,203102 | (0,013177; −0,008948; 139,415011) | Ninguna entre las seleccionadas. |
| tool — pistón/herramienta | 2/2 | 38,297109 | (−0,000003; 0,036039; 49,975097) | Ninguna entre las seleccionadas. |

**Estos centroides no son los centros de masa físicos del grupo multimaterial.** La cobertura 39/39 no demuestra que los cuerpos del diseño estén completos. Las sumas siguen siendo referencias parciales y aditivas, sin auditoría de solapamientos internos: continúan pendientes tornillos, correas, ejes y otras piezas no incorporadas, además de la asignación provisional de seis mitades de carretel. NEMA17×2 y R-CarretelSup mantienen discrepancias de revisión/caja respecto del caché.

Cuando existan materiales diferentes, se calcula `mi = rhoi Vi`, luego `C = Σ mi ci / Σ mi` y finalmente `I = Σ [rhoi Ji + mi ((di·di) E − di diᵀ)]`, usando ahora `di = ci − C`. En un componente comercial se usa su masa, COM e inercia sustentados por ficha/modelo equivalente, sin volver a multiplicarlos por una densidad.

## 6. Cómo reproducirlo

Para explorar el CSV/JSON no hacen falta dependencias CAD. Para recalcular se requiere Python 3.11–3.14 y las versiones de [requirements-cad.txt](../tools/requirements-cad.txt); el cliente y Webots siguen usando su Python habitual sin OCP.

Crear un entorno aislado si hace falta recalcular; no es necesario descargar el conversor para este precálculo:

```sh
python3.12 -m venv /tmp/scara-propiedades-venv
/tmp/scara-propiedades-venv/bin/python -m pip install -r tools/requirements-cad.txt
/tmp/scara-propiedades-venv/bin/python tools/calcular_propiedades_cad.py --output /tmp/scara-propiedades-repeticion
/tmp/scara-propiedades-venv/bin/python -m unittest tests.test_cad_properties -v
```

Usar un Python compatible instalado en el equipo; el Python 3.9 del sistema sirve para el banco, pero no para estas dependencias OCP. En Windows cambian los ejecutables del venv a `Scripts/python.exe`. `--output` permite comparar otra corrida sin sobrescribir la evidencia. El comando sin esa opción sobrescribe el par sin sufijo de `cad/propiedades/`, conservado como histórico de 38; elegir un destino nuevo para comparar repeticiones. No se editan los informes a mano.

La corrida actual examinó 50 piezas, calculó 49 tipos/51 sólidos y 39 instancias, y conservó sus entradas protegidas. Una repetición usa las instancias del manifiesto al ejecutarse, por lo que el conteo puede cambiar. La exclusión conocida de `B-ExtensorM3` se informa y no provoca fallo; un hash diferente o una incoherencia de integración sí detienen el cálculo. Fecha UTC, intérprete y versiones permiten distinguir corridas.

Las comprobaciones geométricas usan cajas analíticas y geometría transformada independientemente con OCCT: permiten detectar una escala elevada a la potencia incorrecta, un tensor alrededor del origen en lugar del centroide, signos de términos cruzados o un traslado duplicado. Su aprobación no valida materiales ni las aproximaciones del conversor.

**Resultado histórico del 15/10:** aprobaron las **21 pruebas** de la suite completa con OCP —16 existentes y cinco nuevas—, sin omisiones. Se contrastaron además los cinco grupos de la cobertura anterior por otro camino: releer sus STEP, transformar los BREP con `gp_Trsf`, formar un compuesto y volver a integrar directamente, sin llamar a las funciones de rotación/suma del precálculo. La mayor diferencia relativa del tensor fue **7,30×10⁻¹⁵**, la de volumen **1,78×10⁻¹⁵**, y la distancia máxima de centroides **5,03×10⁻¹⁶ m**. Son acuerdos numéricos entre dos caminos sobre aquel CAD convertido, no incertidumbre física del diseño ni un contraste repetido de las sumas actuales. El [registro histórico](../validation/cad_properties.json) conserva métodos, tolerancias y resultados por cuerpo.

La [comprobación de sesión 8](../validation/sesion8/contraste.json) releyó y transformó los STEP de muñeca para integrar compuestos BREP de seis y siete ocurrencias sin usar las funciones de composición del productor. Máximos errores: volumen relativo 2,22×10⁻¹⁶, centroides 1,67×10⁻¹⁶ m y tensor relativo 4,37×10⁻¹⁵; dentro de 10⁻⁹, 10⁻¹⁰ m y 10⁻⁹ respectivamente. Las 38 ocurrencias anteriores y los otros cuatro grupos coinciden exactamente con el informe anterior; esos cuatro grupos no se recalcularon por el camino independiente. El delta de volumen de muñeca, 9,166651648 cm³, corresponde a la polea añadida una vez. Se mantienen los límites de suma aditiva y kernel/STEP compartidos. 

## 7. Datos que faltan para reemplazar la física provisional

En los **50 originales** aparece el literal UTF-16LE `Material <sin especificar>`, registrado por pieza en el JSON. La revisión del stream nativo `Header2` con el lector OLE existente también dio 50/50. Esto acredita la etiqueta guardada; no es un parser completo de densidades ni descarta todos los posibles overrides internos. No se extrajo ningún material físico confirmado.

### Materiales nominales ya localizados

Que los nativos declaren «Material <sin especificar>» no significa que no haya indicaciones en otras fuentes. El [maestro, p. 9](../00-SCARA-Master.pdf#page=9) indica acero en L0 y tubos de aluminio en L1–L4. Los planos de B-SoporteRuleman, R-Bancada, R-ContraBancada, Z-BujeExterior, Z-BujeInterior y Z-SoporteEfector indican PLA con relleno del 30%. Los planos de poleas distinguen aluminio y PLA; el tornillo ACME indica acero y la tuerca bronce.

Son materiales de diseño a confirmar para la revisión elegida; no asignan una densidad uniforme a todo el cuerpo articulado. Motores y rodamientos comerciales necesitan propiedades propias.

El G-code `A-CarretelInf.gcode` contiene un trabajo conjunto de A-CarretelInf **y A-CarretelSup**. Declara tres perímetros, tres capas superiores e inferiores, relleno rectilíneo del 30% y densidad de perfil 1,25 g/cm³, con material sin identificar. Estima 33,56 g para el trabajo conjunto; no se puede dividir por dos para asignar masas ni vincular sin contraste a los CAD actuales. No prueba que las piezas se hayan impreso ni determina sus inercias.

La [revisión documental de física](../validation/physics_sources.json) registra fuentes, campos y límites. Se conserva la física provisional hasta respaldar la aplicación por pieza.

| Dato pendiente | Qué necesitamos concretamente | Por qué afecta la física |
| --- | --- | --- |
| Revisión y montaje vigentes | Ensamble/configuración de referencia, cantidades, fijaciones de carreteles y piezas omitidas; resolver discrepancias documentadas. | Define qué geometría y qué masa pertenecen a cada cuerpo. |
| Geometría adicional excluida | Sólido válido de `B-ExtensorM3`, si la revisión y el montaje requieren incorporarlo. La cobertura por instancia se consulta en el informe de la corrida. | El extensor sigue sin volumen/distribución admisibles para una incorporación futura. |
| Piezas homogéneas | Material y densidad por pieza o sólido, con fuente y revisión. | Convierte V y Jc en masa e inercia. Una torre de tres sólidos podría requerir materiales distintos. |
| Impresiones 3D | Filamento, paredes/perímetros, tapas, patrón y porcentaje de relleno, zonas macizas/inserciones; G-code de la pieza/revisión si existe. | El porcentaje de relleno no multiplica uniformemente volumen e inercia. El G-code suelto existente no caracteriza todas las piezas. |
| Componentes comerciales | Modelo exacto, masa y distribución/COM/inercia de motores, rodamientos, acoples, etc.; distinguir carcasa y rotor. | Su CAD simplificado y su envolvente no representan necesariamente el interior. Una masa de catálogo por sí sola no determina el tensor. |
| Elementos auxiliares | Tornillería, correas, cables, imanes, sensores, herramientas y carga prevista; ubicación y fijación. | Pueden cambiar COM e inercia aunque no sean visualmente dominantes. |
| Esfuerzo y transmisión | Motor/driver/alimentación/corriente, curva torque–velocidad, poleas y relaciones, acoplamiento M1/M2, paso ACME, eficiencia, fricción/holgura y condiciones de sostén. | Las propiedades inerciales no determinan los esfuerzos disponibles ni la caída por falta de sostén. |
| Herramienta y contactos | TCP, herramienta/carga nominal, topes, geometrías de colisión y propiedades de contacto pertinentes. | Afecta marcos, carga equivalente, recorridos y respuesta a contactos. |

La lista para consultar al profesor está en [DATOS_PARA_EL_PROFESOR.md](historico/DATOS_PARA_EL_PROFESOR.md). Hall/homing y protocolo también siguen pendientes para cerrar el comportamiento del banco, aunque no impiden calcular estas integrales.

El camino posterior es: revisar montaje, componentes adicionales y solapamientos → documentar materiales/modelos comerciales → agregar masas y tensores en cada marco → revisar cobertura → adaptar el generador y la combinación con carga → repetir comprobaciones físicas y nativas. Una hipótesis de densidad efectiva puede estudiarse como escenario declarado; no se convierte automáticamente en material confirmado.

En Webots se podrá fijar `density -1`, masa explícita, `centerOfMass` local y tensor central en el orden `[Ixx Iyy Izz], [Ixy Ixz Iyz]`. Habrá que adaptar también `scara/dynamics.py`, el generador y los ensayos: hoy reconstruyen cajas y una carga cúbica de 40 mm. Cambiar solo `mass` o copiar Jc sin multiplicar por rho dejaría un modelo incoherente.

## 8. Estado del banco y fuentes

Se preservó la física activa: masas exploratorias **0,30 / 0,50 / 0,35 / 0,15 kg**, centros e inercias de cajas, esfuerzos de demostración y cajas de colisión actuales. El precálculo no necesita conectarse a Webots. La recuperación del 16/10 sí regeneró el modelo y comprobó movimiento en [cad_motion_recovery.json](../validation/cad_motion_recovery.json): 11 snapshots, 330 colocaciones y seis llegadas aprobadas; esto no valida las propiedades materiales pendientes.

Referencias primarias para interpretar el cálculo: [OCCT BRepGProp](https://www.occt3d.com/dev/doc/refman/html/class_b_rep_g_prop.html), [OCCT GProp_GProps](https://www.occt3d.com/dev/doc/refman/html/class_g_prop___g_props.html) —matriz central y composición— y [Physics de Webots, revisión R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/physics.md) —campos, unidades y marco—. La configuración particular de una nightly debe contrastarse al integrar y ensayar la física futura.
