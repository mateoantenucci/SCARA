# Criterios para integrar el CAD en la cadena móvil

La integración exploratoria puede conservar las colocaciones guardadas y adoptar un sistema de coordenadas útil sin esperar ceros de motor oficiales. El [JSON de criterios](../cad/ensambles/criterios_integracion.json) contiene la transformación canónica, los marcos de cada cuerpo, la pose articular de referencia y las matrices pieza→cuerpo de las 20 instancias. La configuración y el generador del modelo móvil consumen estas decisiones por separado.

Es una decisión reversible de representación. No se declaran homing, calibración, fijaciones verificadas experimentalmente, masas CAD ni TCP oficial. Las tres geometrías visibles inicialmente rechazadas se recuperaron el 16/10 y ya superan el gate; las asignaciones de cuerpo conservan su carácter documentado y provisional.

## Qué son los carreteles y a qué lado pertenecen

Los seis modelos tienen dos caras de un canal anular con pasos radiales. **No son las poleas dentadas 2GT que transmiten el par de M1–M3.** La función de canalizar cableado es una inferencia de su forma; el master no la explica expresamente. Tampoco corresponde describirlos como dos abrazaderas que aprietan un mismo caño cuadrado: sus agujeros centrales actuales son de 9–36 mm y no pueden abrazar exteriormente los caños de brazo de 50×50 mm.

Se propone una mitad por cada lado de la articulación. Se contrastaron los planos [A-Carreteles](../Modelos3D/A-Carreteles.PDF), [A-EnsambleCarretel](../Modelos3D/A-EnsambleCarretel.PDF), [R-EnsambleCarretel](../Modelos3D/R-EnsambleCarretel.PDF), [A-EnsambleBrazo](../Modelos3D/A-EnsambleBrazo.PDF) y [R-EnsambleRotacion](../Modelos3D/R-EnsambleRotacion.PDF), sus secciones renderizadas, los STEP actuales y las matrices XML.

**Hay una revisión distinta en los planos de carreteles A:** el PDF muestra agujeros centrales de 35/40 mm; los nativos actuales convertidos muestran 16/17 mm. Para decidir colocaciones de esta integración se usa la geometría nativa actual, no la cota del PDF anterior.

| Instancia | Cuerpo propuesto | Evidencia actual y contacto en la pose guardada |
| --- | --- | --- |
| A-CarretelInf | Base fija | Cara anular exterior `z_local=0` coincide con la cara superior de torre `z_local=0`; agujero Ø17 con holgura alrededor del eje Ø16. |
| A-CarretelSup | Brazo | Cara exterior coincide con el extremo del resalte de A-BridaEje `z_local=14,7625 mm`; agujero Ø16 igual al nominal del eje/brida de J1. |
| B-CarretelSup | Brazo | Cara exterior coincide con la cara `y_local=-25 mm` de A-Brazo junto al centro del codo. |
| B-CarretelInf | Antebrazo | Cara exterior coincide con la cara `y_local=-25 mm` de B-Antebrazo junto al codo. |
| R-CarretelInf | Antebrazo | Cara exterior coincide con `y_local=-25 mm` de R-Bancada; Ø36 deja holgura alrededor del cuello móvil Ø35. Su patrón diagonal de anclaje concuerda con el del alojamiento. |
| R-CarretelSup | Z exterior que gira | Cara exterior coincide con el extremo `z_local=91 mm` de Z-BujeExterior; agujero Ø35 y detalle de anclaje a radio 17,5 mm compatibles con ese cuello giratorio. |

Los seis contactos de plano calculados tienen diferencia menor a `1e-12 m`, con sus coordenadas y superficies en el JSON. A y R aportan además diferencias entre diámetro de holgura y de ajuste; B se apoya sobre todo en la cara de cada eslabón y la sección del conjunto. Estos datos justifican la **pertenencia visual propuesta**, pero no prueban que un ajuste impreso sea suficiente para transmitir fuerza ni resuelven sus tornillos o mates angulares.

Las fases angulares de las mitades no quedan fijadas por el registro de snapshots: entre conjuntos se observan giros relativos de los carreteles; el detalle radial de R-CarretelSup no aparece alineado con el del buje en todas las poses guardadas. No se corrige girando piezas para hacer coincidir un tornillo por intuición. Se conserva su matriz inicial y, desde ahí, cada mitad acompaña al cuerpo adoptado.

Meter ambas mitades A en base, ambas B en brazo y ambas R en antebrazo mantendría cada pareja inmóvil entre sí durante el giro del joint. Esa opción perdería la diferencia entre los dos lados del canal. La propuesta divide las parejas y deja documentado que la fijación angular todavía no está certificada.

## Agrupación de las instancias del ensamble global

| Cuerpo | Instancias del snapshot |
| --- | --- |
| Base | 0-Torre, A-CarretelInf |
| Brazo | A-Brazo, A-BridaEje, A-CarretelSup, B-CarretelSup |
| Antebrazo | B-Antebrazo, NEMA17-1, R-Bancada, R-ContraBancada, B-CarretelInf, R-CarretelInf |
| Z exterior | Z-BujeExterior, Z-Cuerpo, Z-SoporteM4, Z-SoporteRuleman, NEMA17-2, R-CarretelSup |
| Z deslizante | Z-Piston, Z-SoporteEfector |

La descripción del master, pp. 5 y 9, distingue cuerpo exterior, pistón y soporte; pp. 11–12 sitúan motores M1/M2 en la base y M3 sobre el antebrazo. Los planos de rotación muestran R-Bancada/R-ContraBancada como alojamiento y Z-BujeExterior atravesándolo con rodamientos. Son el apoyo de la separación principal entre antebrazo y conjunto Z. La vista de 20 instancias no incluye todavía todo el montaje interno ni los dos motores de base; esos elementos no deben duplicarse al registrar otros subconjuntos.

### Ampliación desde otros ensambles

La primera ampliación añadió diez montajes/carcazas desde el [registro de subensambles](../cad/ensambles/registro_subensambles.json), con esta pertenencia:

| Cuerpo | Adiciones revisadas |
| --- | --- |
| Base fija | 0-Bancada, 0-ElevadorM2, 0-PlatinaSuperior, 0-SoporteMotores, NEMA23 ×2 |
| Brazo | B-SoporteRuleman ×2, que alojan los rodamientos del codo en A-Brazo |
| Antebrazo | B-SoporteEjeFijo y B-SoporteM3 |

Se aprueba esa pertenencia **para la representación visual parcial**. Los dos NEMA23 se muestran completos como carcazas fijas: su eje forma parte de la misma malla y no se anima como rotor. No interpretar la apariencia estática del eje como ausencia del movimiento de la articulación. Los componentes omitidos no se agregan al cuerpo fijo solo porque pertenezcan al mismo subensamble; poleas y rodamientos incorporados después conservan su asignación explícita.

La vía Torre→global depende de la única instancia compartida 0-Torre; Base→Torre tiene más referencias compatibles. Es evidencia de colocaciones guardadas coherentes, no certificación de todos los mates. El [manifiesto articulado](../cad/ensambles/integracion_articulada.json) conserva el registro de origen de cada adición y separa `registered_mount_visual_only` de las asignaciones principales y de los carreteles provisionales.

La reconstrucción inicial de las 20 poses originales coincidió con el JSON de criterios dentro de `1,2e-15` en entradas de matriz. Las mallas permanecen en metros, sin una segunda escala. Las adiciones posteriores conservan identificadores y procedencia en el [manifiesto efectivo](../cad/ensambles/integracion_articulada.json); el [montaje](MONTAJE_Y_AUTOCOLISIONES.md) explica rodamientos, tapa y polea de muñeca. La cantidad ensayada y sus comprobaciones están centralizadas en [Validación](historico/VALIDACION_WEBOTS.md).

No se agrega masa por cada archivo CAD. El PROTO mantiene cuatro bloques `Physics`, uno por cuerpo móvil, con las masas exploratorias anteriores de 0,30; 0,50; 0,35 y 0,15 kg; el cambio de visuales y envolventes no convierte esas masas, centros o inercias en propiedades materiales medidas. Los motores M1/M2 permanecen dentro de la base fija. Continúa siendo una simulación con dinámica equivalente provisional y visuales CAD parciales, no un ensamble completo de las 50 piezas.

## Sistema canónico y pose de referencia

Se define una única transformación rígida desde el snapshot:

1. Girar 180° sobre X del ensamble guardado para orientar el pedestal hacia abajo.
2. Girar alrededor de Z para alinear el vector J1→J2 con +X.
3. Trasladar el centro horizontal de J1 a `(0,0)` y el plano `z_local=221,6 mm` de 0-Torre a `z=0`.

Esta decisión no necesita aprobación del profesor como si fuera una medida faltante: es nuestra convención de simulación, reversible y trazable. El JSON conserva la matriz exacta. La elección de alturas de anchor sí debe ser coherente con las mallas, por eso se toman centros de los agujeros:

- Hombro: A-Brazo local `(0,0,30 mm)` → altura **0,2913625 m**.
- Codo: B-Antebrazo local `(0,0,220 mm)` → altura **0,2133625 m**.
- Muñeca: línea J3 a la misma altura que el frame del codo; elegir otro punto sobre la misma línea no cambia su eje si se compensan las matrices.

La bajada entre los frames elegidos de hombro y codo es **78 mm**. Esa separación no se debe reemplazar por el nominal de torre del master manteniendo a la vez las matrices visuales de este snapshot. Las distancias horizontales entre ejes permanecen en 250 mm.

La pose articular que reproduce el snapshot en ese sistema es:

```text
q1 = 0
q2 = 0,04158581792222517 rad
q3 = 0,07223652440584233 rad
q4 = 0,060 m
```

Se eligió `q4=60 mm` como referencia a mitad del recorrido de 120 mm para disponer de movimiento en ambos sentidos; **no es una posición home medida**. Para el rumbo del conjunto Z se usa **−X local** de Z-Cuerpo. Los −X locales de Z-Cuerpo, Z-Piston y Z-SoporteEfector coinciden en rumbo en este snapshot: **0,11382234232806758 rad**. Elegir el otro lado del cuadrado sumaría π y es una convención distinta, no evidencia de un cero mecánico.

## Punto de herramienta provisional

El centro del plano exterior del soporte, `Z-SoporteEfector local (0,0,0)`, se toma como punto de referencia para el prototipo sin pinza. La caja local y el plano sitúan allí la cara exterior; la malla recuperada conserva ese marco. Esto no convierte la referencia provisional en un TCP oficial.

En la pose de referencia ese punto queda en:

```text
x = 0,49978385862038005 m
y = 0,010393458169144124 m
z = 0,03466685886479948 m
```

Con el frame de muñeca elegido a altura `0,2133625 m` y J4 positivo hacia abajo, el offset constante a `q4=0` resulta **−0,11869564113520076 m**. Así, `z_punto = z_muñeca − q4 + offset` reproduce exactamente la altura guardada. No llamar a este punto TCP oficial ni usarlo como evidencia de longitud de una pinza inexistente.

## Cómo conservar las colocaciones al articular

Los marcos de eslabón se fijan en esa pose de referencia. Para cada instancia se calcula:

```text
T_mundo_pieza_guardada = T_canónico_desde_guardado · T_guardado_pieza
T_eslabón_pieza = inversa(T_mundo_eslabón_en_qref) · T_mundo_pieza_guardada
```

El JSON trae ambas matrices por instancia. La reconstrucción de las 20 poses desde sus marcos coincide con la original dentro de redondeo; también se comprobaron la cinemática directa XYZ, el rumbo, el plano de base y la cobertura de grupos sin duplicar instancias. Los STL ya están en metros: estas matrices no vuelven a escalar geometría.

Los límites, masa, centro de masa, inercia, esfuerzos y sensores siguen usando parámetros explícitamente provisionales mientras se incorporan otras evidencias. Cambiar las mallas no convierte esas propiedades en mediciones CAD. Las pruebas de movimiento deberán observar las dos caras de cada articulación y comprobar que el pistón/soporte conserven su rumbo relativo al conjunto Z durante la carrera.

## Regenerar después de una decisión de montaje

La fuente editable es `config/cad_integration.json`. Después de cambiarla con evidencia:

```sh
python3 tools/integrate_cad.py
python3 tools/generate_world.py
```

Si también deben actualizarse las dimensiones cinemáticas o las cajas equivalentes de configuración, `integrate_cad.py --update-config` lo hace conservando las masas exploratorias. Es un cambio deliberado de configuración: repetir los controles afectados. Una adición solo visual puede integrarse sin esa opción para conservar la física activa.

No editar a mano el manifiesto ni el mundo/PROTO para fijar un cambio permanente. Los ensayos nativos deben usar una copia recargada de la versión regenerada.
