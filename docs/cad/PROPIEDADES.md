# Propiedades geométricas del CAD y paso a masas

Este documento explica qué se calcula del CAD (volumen, centroide y tensor geométrico de cada pieza), cómo se reproduce, dónde están los resultados y cómo se pasaría de esas propiedades a las masas de [`config/scara.json`](../../config/scara.json). También dice qué falta para que las masas dejen de ser provisionales. La conversión y las colocaciones están en [Del CAD a Webots](DEL_CAD_A_WEBOTS.md); los choques, en [Montaje y colisiones](MONTAJE_Y_COLISIONES.md).

**Estado.** El precálculo cubre los 50 STEP: 49 tipos de pieza, 51 sólidos y 39/39 instancias del modelo. Solo `B-ExtensorM3` queda excluida, por BREP inválido, y no está en el modelo. No se asignó ningún material ni se aplicó el resultado a la física activa: las masas de Webots son provisionales (ver [Límites](#límites)).

## Qué se calcula

Para cada sólido, con integración BREP exacta de OCCT sobre el STEP convertido:

- **Volumen V**: espacio ocupado, sin los huecos (en m³).
- **Centroide c**: centro volumétrico (en m). Coincide con el centro de masa solo si la densidad es uniforme.
- **Tensor central Jc**: distribución del volumen alrededor del centroide, matriz completa con términos cruzados, en ejes paralelos a los del marco indicado (en m⁵). No se diagonalizó.

```text
Jc = ∫ [ (r·r) E − r rᵀ ] dV,  r = posición − centroide,  E = identidad
Jxy = −∫ rx ry dV  (análogamente Jxz y Jyz)

Pieza homogénea de densidad rho (kg/m³):
masa = rho V     centro de masa = c     inercia central I = rho Jc  (kg·m²)
```

Jc es la inercia a densidad de referencia 1 kg/m³; esa referencia no es un material del robot. El STEP se pasa a milímetros en OCCT y se aplican los factores 10⁻⁹ (volumen), 10⁻³ (centroide) y 10⁻¹⁵ (tensor: una distancia al cuadrado sobre un volumen). `GProp_GProps.Mass()` entrega volumen, no kilogramos.

Ejemplo, `A-Brazo` en su marco de pieza: V = 6,9501053162809×10⁻⁵ m³ (69,501053 cm³), c ≈ (0; 0,084705; 150,101162) mm y diagonal de Jc ≈ (5,424834×10⁻⁷; 5,427294×10⁻⁷; 5,524795×10⁻⁸) m⁵. Es el tubo con sus huecos, no una barra maciza de 300×50×50 mm. La cantidad de decimales permite reproducir el cálculo; no declara esa exactitud respecto del diseño.

## Dónde están los resultados

| Archivo | Contenido |
| --- | --- |
| [`cad/propiedades/propiedades_geometricas_39.json`](../../cad/propiedades/propiedades_geometricas_39.json) | **Vigente (39 instancias).** Volumen, centroide, tensor central, sólidos, SHA-256 de originales y STEP, advertencias del conversor, transformaciones y cobertura por grupo. |
| [`cad/propiedades/propiedades_geometricas_39.csv`](../../cad/propiedades/propiedades_geometricas_39.csv) | Lo mismo en tabla, para una planilla. SI; las filas excluidas tienen las propiedades vacías, nunca cero. |
| [`cad/propiedades/propiedades_geometricas.json`](../../cad/propiedades/propiedades_geometricas.json) y [`.csv`](../../cad/propiedades/propiedades_geometricas.csv) | Corrida de 38 instancias. |
| [`tools/calcular_propiedades_cad.py`](../../tools/calcular_propiedades_cad.py) | El cálculo. Lee los artefactos existentes; no reconvierte, no repara ni escribe originales, configuración, mundo o PROTO. |
| [`tests/test_cad_properties.py`](../../tests/test_cad_properties.py) | Escala, tensor central, rotación y composición. |
| [`validation/cad/cad_properties.json`](../../validation/cad/cad_properties.json) | 21 pruebas aprobadas sin omisiones y contraste independiente de cinco cuerpos (corrida de 38). |
| [`validation/cad/physics_sources.json`](../../validation/cad/physics_sources.json) | Revisión documental de fuentes de física: campos, fuentes y límites. |
| [`validation/cad/cad_recovery_regression.json`](../../validation/cad/cad_recovery_regression.json) | 15/15 controles al comparar las tres conversiones recuperadas con y sin la corrección de curvas de intersección. |
| [`validation/cad/cad_motion_recovery.json`](../../validation/cad/cad_motion_recovery.json) | Modelo regenerado con las piezas recuperadas: 11 snapshots, 330 colocaciones y seis llegadas aprobadas. No valida materiales. |
| [`validation/cad/sesion8/`](../../validation/cad/sesion8/INFORME.md) | Procedencia del paso de 38 a 39 instancias. |

### 38 contra 39

El de 39 es el vigente: agrega una sola ocurrencia, la polea de muñeca `2GT_80Teet_40Bore` (+9,166651648 cm³ en `wrist`); lo demás coincide exactamente con el de 38. El de 38 sigue en el repo porque lo leen [`tools/check_collisions.py`](../../tools/check_collisions.py) y [`tools/check_self_collisions.py`](../../tools/check_self_collisions.py), y se dejó con ese nombre. El comando de reproducción sin `--output` sobrescribe el par sin sufijo (el de 38): para comparar, elegí siempre un destino nuevo.

### Vistas del CSV

`part` es un tipo de pieza en su marco local; `solid`, un sólido de esa pieza; `instance`, una ocurrencia colocada y expresada en el marco de su cuerpo; `body`, la suma de las instancias de un grupo. **Las cuatro vistas se solapan: no sumes todas las filas.** `computed` quiere decir que se integró un BREP válido, no que la masa real sea conocida. `partial_additive_reference` es una suma geométrica de referencia; `excluded` conserva el motivo.

## Resultados

| Pieza | Volumen, cm³ | Alcance |
| --- | ---: | --- |
| A-Brazo | 69,501053 | Tubo y perforaciones del sólido convertido. |
| B-Antebrazo | 54,121249 | Marco local de pieza; la longitud del tubo no es la distancia entre ejes. |
| B-CarretelInf / B-CarretelSup | 12,725752 c/u | Sólidos recuperados; cada instancia se cuenta en su cuerpo. |
| Z-Cuerpo | 21,537529 | Revisión disponible. |
| Z-Piston | 16,148952 | Solo el pistón; el soporte va aparte. |
| Z-SoporteEfector | 22,148157 | Sólido recuperado. |
| 0-Torre | 392,812936 | Tres sólidos válidos; no es una unión global certificada. |
| Z-BujeInterior | 8,449958 | BREP válido aunque no tenga STL aceptado; no está en el robot. |
| NEMA17 | 65,771943 | Volumen del CAD; no dice nada de la masa ni del interior del motor. |

Hay 49 tipos con propiedades, pero el lote visual tiene 47 STL aceptados y tres rechazos globales (`0-Torre`, `B-ExtensorM3` y `Z-BujeInterior`): son controles distintos. La torre y el buje interior tienen BREP admisible para integrales; la torre además tiene su recuperación visual por cuerpos. De `B-ExtensorM3` no se usa ningún volumen del kernel ni se lo reemplaza por su caja.

### Sumas por grupo

Con una colocación de rotación R y traslación t: `ci = R c + t` y `Ji = R J Rᵀ`. Para un grupo a densidad común:

```text
V = Σ Vi      c = Σ Vi ci / V      di = ci − c
J = Σ [ Ji + Vi ((di·di) E − di diᵀ) ]
```

La traslación no cambia el tensor central de una pieza; el término de ejes paralelos aparece al reunir piezas. Los marcos son los cinco cuerpos de `scara/frames.py`.

| Grupo | Instancias | Suma aditiva, cm³ | Centroide en el cuerpo, mm |
| --- | ---: | ---: | --- |
| base | 10/10 | 940,295545 | (0,044969; −2,487440; 150,256227) |
| arm (brazo) | 9/9 | 190,937678 | (126,449145; −0,017318; −31,367298) |
| forearm (antebrazo) | 11/11 | 408,848515 | (114,483463; 0,002618; −2,982666) |
| wrist (muñeca y conjunto Z) | 7/7 | 206,203102 | (0,013177; −0,008948; 139,415011) |
| tool (pistón y herramienta) | 2/2 | 38,297109 | (−0,000003; 0,036039; 49,975097) |

**Estos centroides no son los centros de masa físicos**: el grupo es multimaterial. Las sumas son **aditivas, no uniones booleanas**: un volumen superpuesto se cuenta dos veces, así que no hay «volumen total real del robot» ni cota inferior garantizada. Faltan tornillos, correas, ejes y otras piezas, y hay una asignación provisional de seis mitades de carretel. NEMA17×2 y R-CarretelSup tienen discrepancias de revisión/caja respecto del caché.

## Cómo se reproduce

Para mirar el CSV o el JSON no hace falta nada. Para recalcular, Python 3.11–3.14 con [`tools/requirements-cad.txt`](../../tools/requirements-cad.txt) (OCP). El Python 3.9 del sistema no sirve para esto; el cliente y Webots siguen con su Python habitual. No hace falta descargar el conversor.

```sh
python3.12 -m venv /tmp/scara-propiedades-venv
/tmp/scara-propiedades-venv/bin/python -m pip install -r tools/requirements-cad.txt
/tmp/scara-propiedades-venv/bin/python tools/calcular_propiedades_cad.py --output /tmp/scara-propiedades-repeticion
/tmp/scara-propiedades-venv/bin/python -m unittest tests.test_cad_properties -v
```

En Windows el ejecutable es `Scripts/python.exe`. Sin `--output` se sobrescribe la evidencia (ver arriba). Los informes no se editan a mano. Sin OCP, la suite general omite las 3 pruebas de propiedades CAD.

La corrida vigente examinó 50 piezas, calculó 49 tipos / 51 sólidos y 39 instancias, y conservó los **217 archivos protegidos**. Una repetición usa las instancias del manifiesto del momento, así que el conteo puede cambiar. `B-ExtensorM3` se informa y no hace fallar; un hash distinto o una incoherencia de integración sí detienen el cálculo.

### Criterios de aceptación

El cálculo se detiene si falla alguno: `derive()` del integrador existente coincide con sus fuentes (10⁻¹² absoluto/relativo); los SHA-256 de cada SLDPRT y STEP coinciden con el lote de conversión; el BREP tiene al menos un sólido, shells cerrados, volumen positivo y finito y ninguna cara ajena; el tensor es finito, simétrico y positivo (con segundo momento positivo); volumen y centroide coinciden con el informe BREP previo (volumen relativo ≤10⁻⁶, centroides a ≤10⁻⁸ m); cada instancia se cuenta una vez; y al final los archivos protegidos conservan sus hashes. La integral es `BRepGProp.VolumeProperties` con `OnlyClosed=True`, `SkipShared=True` y `UseTriangulation=False`, sin teselar ni reparar. No se certificó equivalencia con SolidWorks: son integrales del CAD convertido, con el mismo kernel y STEP que el productor.

### Contrastes independientes

Cajas analíticas y geometría transformada por otro camino en OCCT detectan una escala con la potencia equivocada, un tensor tomado en el origen, signos cruzados o un traslado duplicado. No validan materiales ni las aproximaciones del conversor.

- **Corrida de 38.** Los cinco grupos se releyeron, se transformaron los BREP con `gp_Trsf`, se armó un compuesto y se integró de nuevo, sin las funciones de rotación y suma del precálculo. Máxima diferencia relativa de tensor 7,30×10⁻¹⁵, de volumen 1,78×10⁻¹⁵ y de centroides 5,03×10⁻¹⁶ m.
- **Muñeca con 6 y 7 instancias.** Mismo método sobre los compuestos afectados: volumen 2,22×10⁻¹⁶, centroides 1,67×10⁻¹⁶ m y tensor 4,37×10⁻¹⁵ de error máximo, dentro de 10⁻⁹, 10⁻¹⁰ m y 10⁻⁹. Los otros cuatro grupos coinciden exactamente con el informe de 38, sin recalcularlos por el camino independiente.

Son acuerdos numéricos entre dos caminos, no incertidumbre física del diseño. La evidencia está en `validation/cad/cad_properties.json` y `validation/cad/sesion8/contraste.json`. `verificar_sesion8.py` compara hashes de archivos que ya no están en el repo: para reproducir esa verificación hay que partir del tag `pre-limpieza`.

## De propiedades geométricas a masas

Procedimiento previsto, no aplicado todavía:

1. **Pieza homogénea:** `m = rho V`, centro de masa `c`, inercia central `rho Jc`.
2. **Grupo multimaterial:** `mi = rhoi Vi`, `C = Σ mi ci / Σ mi`, `I = Σ [rhoi Ji + mi ((di·di) E − di diᵀ)]` con `di = ci − C`.
3. **Componente comercial:** masa, COM e inercia de su ficha o de un modelo equivalente, sin multiplicar por una densidad.
4. **Webots:** `density -1`, masa explícita, `centerOfMass` local y tensor central en el orden `[Ixx Iyy Izz], [Ixy Ixz Iyz]`. Habría que adaptar también `scara/dynamics.py`, el generador y los ensayos, que hoy reconstruyen cajas y una carga cúbica de 40 mm. Cambiar solo `mass`, o copiar Jc sin multiplicar por rho, deja un modelo incoherente.

**Hoy.** `config/scara.json` conserva masas exploratorias de **0,30 kg (brazo), 0,50 (antebrazo), 0,35 (muñeca) y 0,15 (herramienta)**, con centro e inercia de las cajas envolventes de cada grupo CAD. El campo `provenance.body_properties` del archivo lo declara: no son propiedades materiales validadas. La herramienta suma además la carga del banco, hasta 5 kg ([Transmisión](../TRANSMISION.md)). El maestro v2 llama a estas masas «provisionales»; la tabla de su sección de física dice «calculadas del CAD con densidades nominales», pero el precálculo no se usó para fijarlas: vale lo que dice `config/scara.json`.

## Límites

- **Materiales.** Los 50 originales llevan la etiqueta `Material <sin especificar>` (literal UTF-16LE y stream `Header2`). Acredita la etiqueta, no descarta overrides internos. No hay material físico confirmado.
- **Materiales nominales de diseño**, a confirmar para la revisión elegida: el [maestro v1, p. 9](../../00-SCARA-Master.pdf#page=9) indica acero en L0 y tubos de aluminio en L1–L4. Los planos de B-SoporteRuleman, R-Bancada, R-ContraBancada, Z-BujeExterior, Z-BujeInterior y Z-SoporteEfector piden PLA con relleno del 30 %; los de las poleas distinguen aluminio y PLA; el ACME es de acero y la tuerca de bronce. No dan una densidad uniforme al cuerpo articulado.
- **Relleno de impresión.** El porcentaje de relleno no multiplica uniformemente volumen e inercia: importan perímetros, tapas, patrón y zonas macizas. El G-code `A-CarretelInf.gcode` es un trabajo conjunto de A-CarretelInf y A-CarretelSup (tres perímetros, tres capas, relleno rectilíneo del 30 %, perfil de 1,25 g/cm³, material sin identificar, 33,56 g en total). No se puede partir por la mitad ni atar a los CAD actuales, y no prueba que se hayan impreso.
- **Componentes comerciales.** Motores, rodamientos y acoples tienen CAD simplificado: el volumen no dice masa ni distribución internas (carcasa y rotor). Una masa de catálogo sola no determina el tensor.
- **Elementos auxiliares.** Tornillería, correas, cables, imanes, sensores y carga cambian COM e inercia aunque no dominen visualmente. Los imanes y escuadras de los Hall solo están en Webots, no en el CAD.
- **Esfuerzo.** Las propiedades inerciales no determinan los torques disponibles ni la caída por falta de sostén: eso depende de motor, driver, transmisión, fricción y holgura ([Transmisión](../TRANSMISION.md)).
- **Solapamientos.** Las sumas no auditan interferencias internas ni uniones booleanas.

Una hipótesis de densidad efectiva puede estudiarse como escenario declarado; no pasa a ser material confirmado.

## Referencias

[OCCT BRepGProp](https://www.occt3d.com/dev/doc/refman/html/class_b_rep_g_prop.html), [OCCT GProp_GProps](https://www.occt3d.com/dev/doc/refman/html/class_g_prop___g_props.html) (matriz central y composición) y [Physics de Webots R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/physics.md) (campos, unidades y marco).
