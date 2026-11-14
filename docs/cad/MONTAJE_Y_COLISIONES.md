# Montaje y colisiones

Este documento cubre qué protege el planificador de la URC contra choques, qué auditorías CAD lo respaldan, qué se diagnosticó y corrigió en el montaje (rodamientos, poleas, montajes restantes) y qué límites tiene todo eso. La conversión y los criterios de integración están en [DEL_CAD_A_WEBOTS.md](DEL_CAD_A_WEBOTS.md); las masas y los centros, en [PROPIEDADES.md](PROPIEDADES.md). El montaje no certifica cómo fabricar o ensamblar el robot real. Los casos ensayados están en la [campaña de validación](../../validation/campana/INFORME.md).

## 1. Qué protege el planificador

El planificador verifica cada recorrido antes de enviarlo: PTP y LIN en `urc/validation.py`, y cada segmento del jog en `urc/jog.py` (D28, D75). No basta con comprobar destino o extremos. Un rechazo no cambia posiciones, trayectoria ni modo, y no se calcula una ruta alternativa.

| Qué se comprueba | Contra qué |
| --- | --- |
| Cajas de las piezas móviles | Pedestal y suelo de `config/scara.json` |
| Herramienta y carga | Cajas de la base fija |
| Jog (segmentos de 20 ms) | Lo mismo; dentro de la zona de margen solo deja alejarse |

El entorno de ensayo: pedestal de X,Y entre −200 y +200 mm y Z entre −200 y 0 mm; suelo de X,Y entre −1000 y +1000 mm y Z entre −210 y −200 mm. Z=0 es la cara superior del pedestal, no un piso infinito: un extremo con Z negativa puede estar libre fuera de la planta del pedestal. Es geometría de banco (`tools/generate_world.py`), no del diseño CAD.

### Por qué hace falta comprobar el recorrido

`Z_TCP = 94,666858865 mm − J4_mm`. A J4=120 mm la herramienta queda en −25,333 mm: plegado sobre el pedestal, el pistón y el soporte lo invaden. Un caso con inicio y final libres y tramo intermedio invasivo:

| Momento | J1 | J2 | J3 | J4 |
| --- | ---: | ---: | ---: | ---: |
| Inicio | −60° | 120° | 0° | 120 mm |
| Mitad | −15° | 120° | 0° | 120 mm |
| Final | 30° | 120° | 0° | 120 mm |

La interpolación es articular, así que el extremo sigue una curva. Antes se aceptaba; ahora se rechaza ([`collisions_before_after.json`](../../validation/cad/collisions_before_after.json), comparación de aceptación de consignas, no ejecución física).

### Cajas y carga

`piece_boxes()` de [`scara/collisions.py`](../../scara/collisions.py) saca una caja local por instancia del manifiesto `cad/ensambles/integracion_articulada.json`; la usan el generador de Webots y el comprobador. Las cajas agregadas por cuerpo exageraban el volumen. Los centros e inercias de la física equivalente quedan aparte. Con carga positiva, el comprobador reserva un cubo de 40 mm en el TCP (como `scara/dynamics.py`); es una reserva geométrica, no un sólido de contacto de Webots. La URC hoy no pasa carga al comprobador.

### Cómo se acota el recorrido

Las articulaciones comparten un escalar monótono del perfil quíntico, `q(s) = inicio + s·(destino − inicio)`, `0 ≤ s ≤ 1`. Para cada caja e intervalo de `s`: se colocan sus ocho vértices en el punto medio y se forma una caja alineada con los ejes; se amplía con una cota del desplazamiento posible; si queda separada de los obstáculos se aprueba, y si no se subdivide hasta la resolución mínima, donde se rechaza.

Con `Δi` los cambios articulares, `R` la distancia XY máxima de los vértices al origen de su cuerpo y `l1`, `l2` las longitudes:

```text
Brazo:       B = R·|Δ1|
Antebrazo:   B = l1·|Δ1| + R·|Δ1+Δ2|
Muñeca/tool: B = l1·|Δ1| + l2·|Δ1+Δ2| + R·|Δ1+Δ2+Δ3|
```

Para un intervalo de semiancho `h`, X,Y se amplían en `B·h`. Z es constante salvo en herramienta y carga, donde varía hasta `|Δ4|·h`. La cota puede superar el barrido real.

| Parámetro | Valor | Significado |
| --- | ---: | --- |
| `margin_m` | 0,001 m | Ampliación de cada obstáculo. |
| `interval_bound_m` | 0,00025 m | Resolución para rechazar superposiciones inciertas; no es penetración permitida. |
| `MAX_INTERVALS` | 4096 | Presupuesto por llamada; agotarlo rechaza. |

Si el punto medio no se distingue numéricamente de un extremo, también se rechaza. `first_conflict()` informa pieza, obstáculo e intervalo incierto, no el primer instante de contacto. Herramienta y carga se comprueban además contra la base fija; no se extiende a todos los pares porque las cajas rellenan huecos del CAD.

Si el robot queda dentro de la zona de margen (jog, o redondeo a pasos junto a un límite), `first_conflict_leaving()` admite el camino si la separación crece hasta salir. El jog con referencia (D75) planifica segmentos de 20 ms de a uno, tres en cola, cada uno verificado; como frena en el último enviado, no mira más adelante.

```sh
python3 -m unittest tests.test_collisions -v
```

`tests/test_collisions.py` cubre plegados invasivos, cruce intermedio en ambos sentidos, margen, carga y terminación numérica.

## 2. Auditorías CAD de poses

Miden intersecciones BREP en poses elegidas. Requieren el Python con OCP de `tools/requirements-cad.txt`; no conectan con Webots. Desde la raíz:

```sh
python tools/check_collisions.py        # validation/cad/collisions.json
python tools/check_self_collisions.py   # validation/cad/self_collisions.json
```

| Auditoría | Resultado vigente |
| --- | --- |
| [`check_collisions.py`](../../tools/check_collisions.py): once poses y un recorrido frente a pedestal y suelo ([`collisions.json`](../../validation/cad/collisions.json)) | `passed`. 22 instancias móviles, 19 con BREP válido y 3 excluidas (`B-CarretelSup`, `B-CarretelInf`, `Z-SoporteEfector`; conservan caja, sin volumen CAD). 4 intersecciones confirmadas: pistón y soporte plegados sobre el pedestal. |
| Con geometrías recuperadas ([`collisions_recovery.json`](../../validation/cad/collisions_recovery.json)) | `passed`; confirma pistón y soporte invasivos. |
| [`check_self_collisions.py`](../../tools/check_self_collisions.py): 41 poses, 34 instancias ([`self_collisions.json`](../../validation/cad/self_collisions.json)) | `interferences_found`: las 4 invasiones conocidas del soporte contra la torre y 12 solapes iniciales de cajas sin volumen CAD. |

Una interferencia encontrada es resultado de auditoría, no un fallo. Los solapes sin volumen CAD muestran por qué no se pueden activar contactos internos generales con las cajas actuales. El control rechaza los recorridos nominales de las cuatro poses invasivas, incluido el tramo intermedio. El ensayo de contactos en Webots era de una etapa previa; queda en el tag `pre-limpieza` y hoy no hay herramienta para repetirlo.

## 3. Montaje

### Rodamientos y tapa de muñeca

Hay seis rodamientos simplificados (dos en base, dos en brazo, dos en muñeca): visuales, sin anillos animados ni masa. El montaje guardado tenía `R-ContraBancada` girada media vuelta respecto de `R-EnsambleRotacion`; sus lados son asimétricos y eso explicaba un desfase de 3 mm. Con `R-Bancada` como referencia coinciden rodamientos, agujeros y apoyos. Se adoptó esa colocación ya guardada, sin desplazar la tapa ni retocarla. Falta confirmar la revisión oficial y la fijación de los aros.

Reproducción: `python tools/check_wrist_bearings.py`. Respaldo: [`wrist_bearing_diagnosis.json`](../../validation/cad/wrist_bearing_diagnosis.json) (17 comprobaciones) y [`wrist_bearings.json`](../../validation/cad/wrist_bearings.json). Estado previo: [`antes_rodamientos_muneca_20261017/`](../../validation/historico/antes_rodamientos_muneca_20261017/).

### Poleas

Las poleas de salida `2GT_80Teet_16Bore` y `2GT_60Teet_8Bore` acompañan al brazo y al antebrazo, con posiciones guardadas y fijación y fase provisionales ([`pulley_mounts.json`](../../validation/cad/pulley_mounts.json), `tools/check_pulley_mounts.py`). Para la `2GT_80Teet_40Bore` de muñeca se compararon dos colocaciones:

| Colocación | Resultado |
| --- | --- |
| B (`B-EnsambleAntebrazo`) | Invade el escalón del buje 470,376 mm³. Descartada. |
| R (`R-EnsambleRotacion`) | Apoya en el escalón de 31 mm, Ø40 mm, 12 mm de acople axial, sin intersección con seis vecinos. Adoptada. |

La pose R se vincula al cuerpo que gira con J3; no se certifica que transmita el torque real. [`remaining_mounts.json`](../../validation/cad/remaining_mounts.json) (`tools/check_remaining_mounts.py`) conserva ambas alternativas. [`pulley_geometry.json`](../../validation/cad/pulley_geometry.json) (`tools/check_pulley_geometry.py`) cuenta dientes: solo la de muñeca modela 80 cortes (cada 4,5°). Es inspección de geometría; no acredita correas, fases ni signos. La [transmisión](../TRANSMISION.md) no se simula con correas y rotores.

### Piezas que siguen faltando

Ejes de torre, algunas poleas y subconjuntos verticales tienen colocaciones incompatibles entre snapshots, sin registro global que conserve las revisiones; se retienen las alternativas en vez de mezclar. En M3 el extensor indica salida Ø8 mm y el piñón agujero Ø5 mm: no encajan, y el BREP del extensor es inválido (solo diagnóstico). Los tres piñones de motor y la transmisión interior requieren giros propios respecto de sus soportes.

## 4. Límites

- No hay comprobación continua general de autocolisiones ni planificación de desvíos. `selfCollision FALSE` desactiva los contactos internos generales. Las poses auditadas no cubren todo el espacio articular, y los BREP son muestras finitas.
- La cota sigue consignas ideales: una falla (pasos perdidos), la gravedad o un atraso del motor pueden separar la posición física de la referencia. No hay garantía frente a una caída por pérdida de fuerza.
- Las cajas pueden rechazar de más donde ocupan un hueco funcional.
- Faltan piezas, cables, herramienta y carga reales, y la revisión oficial de topes, referencias y transmisión. Propiedades materiales y de contacto son aproximaciones.
- La oscilación al llegar a J4=120 mm se trató como problema numérico (paso de 2 ms); no se recortó la carrera a 119 mm ni se movió el pedestal.
- Pendientes: revisión oficial, fijaciones, fases, anillos, correas, ejes y referencias; materiales comerciales antes de reemplazar la física provisional.

Si cambia el entorno o la política de cajas, regenerar con `python3 tools/generate_world.py` y repetir las comprobaciones afectadas.
