# Colisiones y recorridos: primera revisión del pedestal

**Actualización 16/10, geometrías recuperadas:** la [auditoría vigente](../validation/collisions_recovery.json) analiza las **22 instancias móviles con BREP válido, sin exclusiones**, en las mismas once poses. Confirma ocho intersecciones: pistón y soporte contra pedestal en cuatro poses; el guard rechaza sus recorridos. La [regresión nativa](../validation/collisions_native_recovery.json) aprobó sus cinco comprobaciones. El soporte ya tiene volumen BREP admisible. Los resultados y exclusiones anteriores siguientes describen la etapa previa, conservada como historial. Las autocolisiones internas siguen pendientes.

Registro del punto 2, iniciado el **15/10/2026**. El objetivo es identificar las invasiones del pedestal y rechazar las consignas que no demuestran separación del entorno. Es una primera revisión geométrica del banco; quedan pendientes las interferencias entre piezas del robot y la validación mecánica del montaje.

**Actualización16/10:** la oscilación de J4 descrita abajo ya fue [diagnosticada y reducida](DIAGNOSTICO_TOPE_J4.md) dentro del criterio del banco, pasando de16 a2ms sin mover topes. Los informes del15/10 y el uso temporal de119mm quedan como historia. La revisión actual volvió a comprobar el caso de colisión a120mm en [collisions_native_j4.json](../validation/collisions_native_j4.json), junto con movimiento/fallas y montaje CAD; la amplitud residual máxima observada de J4 es0,174mm.

Para explorar el proyecto, empezar por el [README](../README.md). Este documento continúa el [cálculo de propiedades geométricas del CAD](PROPIEDADES_GEOMETRICAS_CAD.md): utiliza sus STEP, transformaciones y exclusiones, sin asignar materiales nuevos.

## 1. Qué estamos comparando

Hay cuatro representaciones con funciones distintas:

| Representación | Qué contiene | Para qué sirve aquí |
|---|---|---|
| CAD BREP convertido a STEP | Caras, aristas y sólidos de cada pieza aceptada. | Calcular distancia e intersección de sólidos con el pedestal y suelo. |
| Mallas visuales | Triángulos que se ven en Webots. | Mostrar el montaje; su apariencia no demuestra que exista contacto físico. |
| `boundingObject` de Webots | Cajas que aproximan el volumen ocupado. | El motor físico usa estas cajas para resolver contactos. |
| Comprobador de recorridos | Cajas y cotas matemáticas calculadas en Python. | Rechazar antes del movimiento una consigna potencialmente invasiva. |

Una invasión de una caja puede ser un falso positivo respecto de la pieza real. Una intersección positiva del BREP sí confirma una interferencia del CAD convertido en esa pose, dentro de las convenciones actuales. Ninguna de las dos demuestra por sí sola cómo se comportará el robot físico.

El pedestal de ensayo ocupa **X,Y entre −200 y +200 mm; Z entre −200 y 0 mm**. El suelo ocupa X,Y entre −1000 y +1000 mm y Z entre −210 y −200 mm. El plano superior del pedestal es `Z=0`; no es un piso infinito a esa altura. Un TCP por debajo de ese plano puede ser admisible si está lateralmente fuera del pedestal.

## 2. Problemas encontrados

### El pistón invade realmente el pedestal al plegar y bajar

La geometría actual establece:

```text
Z_TCP = 94,666858865 mm − J4_mm
```

Con **J4=120 mm**, el TCP provisional queda en **−25,333141135 mm**. El extremo inferior del sólido válido `Z-Piston-1` queda aproximadamente en **−6,333141135 mm**. La diferencia de 19 mm corresponde a la relación actual entre el pistón y el punto de herramienta; no debe confundirse el TCP con la punta del sólido.

La envolvente del conjunto de herramienta llega hasta el TCP: su penetración vertical posible es de **25,33 mm**. Incluye `Z-SoporteEfector-1`, cuyo BREP sigue rechazado. Por eso se puede medir la intersección real del pistón, pero no atribuir al soporte un volumen CAD certificado.

El análisis BREP reproduce estas invasiones:

| Pose | J1 | J2 | J3 | J4 | Volumen del pistón dentro del pedestal |
|---|---:|---:|---:|---:|---:|
| Plegado hacia X | 0° | 135° | −135° | 120 mm | 0,543955 cm³ |
| Plegado diagonal | 22,5° | 135° | −135° | 120 mm | 0,442191 cm³ |
| Plegado opuesto | 0° | −135° | 135° | 120 mm | 0,543955 cm³ |
| Punto medio del recorrido siguiente | −15° | 120° | 0° | 120 mm | 0,543955 cm³ |

Son resultados del modelo convertido y de su montaje provisional. No son mediciones de penetración del robot construido. La pose inicial y sus dos extremos de J4 quedan separados del pedestal; en esas poses el mecanismo está hacia `(250,250)` mm, fuera de su planta. No se encontró invasión del suelo entre las once poses examinadas; la menor distancia BREP al suelo fue aproximadamente **193,67 mm**.

### Dos extremos libres pueden tener un recorrido invasivo

Se construyó este caso, completamente dentro de los límites articulares declarados:

| Momento | J1 | J2 | J3 | J4 | Resultado |
|---|---:|---:|---:|---:|---|
| Inicio | −60° | 120° | 0° | 120 mm | Extremo separado del pedestal. |
| Mitad | −15° | 120° | 0° | 120 mm | Pistón dentro del pedestal. |
| Final | 30° | 120° | 0° | 120 mm | Extremo separado del pedestal. |

Comprobar solo el destino, o solo inicio y final, dejaba pasar este movimiento. La consigna actual interpola las articulaciones; el TCP sigue una curva y no una recta entre ambos puntos cartesianos. Se necesita comprobar el recorrido articular que efectivamente se ordena.

### Las cajas agregadas exageraban el volumen ocupado

Antes había una caja por cuerpo: base, brazo, antebrazo, muñeca y herramienta. Estas cinco cajas envolvían también los espacios vacíos entre piezas. Por ejemplo, la caja agregada de herramienta daba aproximadamente **80,90 cm³** dentro del pedestal en el plegado de 135°, frente a **0,543955 cm³** del pistón BREP válido. Son objetos diferentes; no hay que interpretar el primer número como volumen de CAD interferente.

Se reemplazaron los cinco `boundingObject Box` por cinco `Group` que contienen **30 cajas locales, una por instancia**:

| Cuerpo | Cajas |
|---|---:|
| Base | 8 |
| Brazo | 6 |
| Antebrazo | 8 |
| Muñeca | 6 |
| Herramienta | 2 |

Cada caja conserva su colocación de pieza mediante `body_from_piece`. El resultado sigue siendo conservador: una caja puede ocupar agujeros y espacios que el sólido no ocupa. Las tres instancias sin geometría volumétrica aceptada conservan su caja explícita; su ausencia visual no abre un paso libre artificial.

La base se apoya en el pedestal. El comprobador previo excluye sus ocho instancias estáticas y analiza las **22 instancias móviles**. La auditoría BREP puede evaluar **19** de ellas; excluye `B-CarretelSup-1`, `B-CarretelInf-1` y `Z-SoporteEfector-1`, con sus motivos registrados en el JSON.

## 3. Cambios realizados

### Un mismo entorno para generar y comprobar

La geometría del pedestal y suelo pasó de valores escritos directamente en el generador a `environment` en [config/scara.json](../config/scara.json). [tools/generate_world.py](../tools/generate_world.py) y [scara/collisions.py](../scara/collisions.py) leen esa misma definición. Así, modificar una dimensión del banco puede regenerarse y verificarse con el mismo dato.

`piece_boxes()` obtiene las cajas del [manifiesto de integración](../cad/ensambles/integracion_articulada.json). El generador y el comprobador reutilizan esa función. La comprobación exige que la geometría cinemática de configuración coincida con la del manifiesto.

### Rechazo previo en el controlador y en el cliente

En [scara/runtime.py](../scara/runtime.py), `move_joints` valida límites, duración y recorrido **antes de asignar una nueva trayectoria o cambiar a `MOVING`**. Este es el punto común para las órdenes TCP de bajo nivel: evita depender de que todos los clientes hagan una comprobación correcta.

En [client/app.py](../client/app.py), `Bridge.command()` comprueba también la trayectoria después de resolver `move_cartesian` por cinemática inversa y antes de encolar el mensaje. Esto permite mostrar el rechazo sin enviar una orden destinada a fallar. La comprobación del controlador sigue siendo necesaria porque el estado del cliente puede tener retraso.

Un rechazo conserva posiciones, trayectoria, modo, fallas, carga y referencia. Si ya hay movimiento, la regla existente impide reemplazarlo mediante otra orden de movimiento. El rechazo no introduce un desvío ni detiene por su cuenta una trayectoria previamente aceptada.

Al cambiar la carga conocida se comprueba además la ocupación de su cubo de ensayo en la pose actual, antes de modificar masa o estado. El cubo tiene **40 mm de lado**, centrado en el TCP, según el supuesto ya utilizado por [scara/dynamics.py](../scara/dynamics.py). Se reserva su volumen en el comprobador cuando la carga es positiva.

**Ese cubo es una reserva geométrica del comprobador.** Este cambio no agrega un sólido ni una nueva caja de contacto para la carga en Webots. La masa, centro e inercia ajustables continúan usando el modelo anterior de carga equivalente. Por tanto, reservar el cubo en una consigna no demuestra que Webots vaya a resolver físicamente el contacto de una carga añadida.

El cálculo parte de `estimated`, la referencia ideal del banco. Los sensores simulados y `inspect_contacts` se utilizan como instrumentación de ensayo, sin sustituir esa referencia por la posición real durante una falla. La pérdida de esfuerzo sigue invalidando la referencia; quitar la falla no habilita nuevamente el movimiento.

## 4. Cómo se comprueba el recorrido completo

Todas las articulaciones comparten el mismo escalar suave y monótono del perfil quíntico. Por eso el conjunto de posiciones recorridas es:

```text
q(s) = inicio + s · (destino − inicio), con 0 ≤ s ≤ 1
```

La velocidad elegida modifica cuánto tarda en recorrerlo, pero no ese camino articular. Esta propiedad permite comprobar el segmento en `s`, sin simular cada instante ni utilizar una lista finita de poses como única protección.

Para cada pieza, el algoritmo parte del intervalo `[0,1]`:

1. Coloca los ocho vértices de su caja en el punto medio del intervalo.
2. Forma su caja alineada con los ejes del mundo —AABB—.
3. La amplía con una cota del desplazamiento máximo posible desde ese punto medio hasta cualquier posición del intervalo.
4. Si la caja ampliada queda separada de cada obstáculo, todo ese intervalo queda descartado como libre.
5. Si no demuestra separación, divide el intervalo en dos. Cuando la cota de desplazamiento ya es suficientemente pequeña y todavía hay superposición, rechaza conservadoramente.

La cota se obtiene de las derivadas de las rotaciones, una cota de Lipschitz. No supone que el movimiento sea rectilíneo en XYZ. Sean `Δi` los cambios articulares, `R` la mayor distancia XY de un vértice al origen de su cuerpo, y `l1,l2` las longitudes de los brazos. Se acota la rapidez respecto de `s` mediante:

```text
Brazo:       B = R·|Δ1|
Antebrazo:   B = l1·|Δ1| + R·|Δ1+Δ2|
Muñeca/tool: B = l1·|Δ1| + l2·|Δ1+Δ2| + R·|Δ1+Δ2+Δ3|
```

En un intervalo de semiancho `h`, cada coordenada X,Y se amplía en `B·h`. La coordenada Z es constante para brazo, antebrazo y muñeca; para herramienta/carga su variación afín se acota con `|Δ4|·h`. Estas cotas contienen todos los vértices durante el intervalo, aunque pueden ser más amplias que el volumen barrido real.

La política está documentada en `collision_check`:

| Parámetro | Valor actual | Significado |
|---|---:|---|
| `margin_m` | 0,001 m | Se amplía cada obstáculo 1 mm por coordenada antes de comprobar separación. |
| `interval_bound_m` | 0,00025 m | Al llegar a una cota de desplazamiento de 0,25 mm, una superposición todavía no resuelta se rechaza. |

**0,25 mm no es penetración permitida.** Es el criterio de resolución de intervalos inciertos. Tampoco es precisión física del robot. El margen de 1 mm es un parámetro de ensayo, sin certificación metrológica o de seguridad.

`first_conflict()` devuelve una pieza, obstáculo e intervalo que no demuestran separación. Por el orden de revisión de piezas, no debe interpretarse como el primer instante de contacto físico. Puede haber falsos rechazos por las cajas y sus cotas; reducirlos requerirá mejor geometría cuando exista evidencia de que restringen un recorrido necesario.

La revisión del algoritmo encontró que una resolución positiva pero impracticable, por ejemplo `1e-300 m`, podía subdividir hasta perder precisión y no terminar. Se agregó un presupuesto global de **4096 intervalos** y rechazo cuando el punto medio ya no puede distinguirse de un extremo. Agotar cualquiera de esos recursos rechaza la consigna; nunca la aprueba por falta de tiempo o precisión.

## 5. Qué se verificó y dónde está la evidencia

La [auditoría geométrica](../validation/collisions.json) contiene once poses, los 19 sólidos móviles admisibles, las 22 cajas móviles, las cuatro cajas agregadas anteriores, distancias y volúmenes por obstáculo. Guarda fecha, versiones OCP, hashes de fuentes/originales/STEP/mallas y comprueba que las entradas no cambiaron durante el cálculo. El campo `status` y la lista `checks` indican el resultado de esa ejecución.

[tests/test_collisions.py](../tests/test_collisions.py) agrega nueve regresiones sin dependencia de OCP:

- Conservación de recorridos de demostración y movimientos separados de cada eje.
- Rechazo de los plegados invasivos y conservación de la caja del soporte efector pendiente.
- Rechazo del recorrido con extremos libres y zona intermedia invasiva, en ambos sentidos.
- Aplicación del margen de 1 mm antes del contacto geométrico.
- Reserva del cubo de carga y rechazo de una trayectoria que sería libre sin carga.
- Rechazo en `Runtime` sin modificar su estado, incluyendo cambio de carga en una pose incompatible.
- Rechazo cartesiano en `Bridge` sin encolar ni alterar el estado del cliente.
- Contraste independiente de colocaciones muestreadas sobre recorridos aceptados, con semilla fija. Este último contraste complementa la cota continua; el muestreo no la reemplaza.
- Rechazo ante resolución numérica impracticable, evitando bloquear el controlador al comprobar el recorrido.

La [prueba nativa de colisiones](../validation/collisions_native.json) es una evidencia distinta: ejecuta el controlador y el motor físico de Webots. Consultar su `status`, `checks`, `webots_version`, `sources` y cualquier `error` para conocer el resultado de la corrida. El script [tools/check_collisions_native.py](../tools/check_collisions_native.py) verifica las 30 cajas, rechazos de consignas sin movimiento, y una caída por pérdida de esfuerzo contra el pedestal. Esa caída comprueba contactos de las cajas actuales, incluida la aproximación del soporte efector; no valida su BREP faltante.

**Resultado definitivo:** el diagnóstico offline aprobó sus cuatro comprobaciones; la [suite completa](../validation/collision_tests.json) aprobó **30/30 pruebas con OCP**, sin omisiones. El ensayo nativo aprobó **cinco comprobaciones**: cajas efectivas, rechazo del destino invasivo sin movimiento, rechazo del cruce intermedio, contacto por gravedad y reinicio STOPPED. La copia de ejecución se contrastó con las fuentes: solo cambia `controllerArgs` para usar otro puerto.

La [comparación anterior/posterior](../validation/collisions_before_after.json) vuelve a cargar el `Runtime` preservado antes de los cambios: aceptaba tanto el plegado invasivo como el recorrido con extremos libres. La revisión actual rechaza ambas consignas. Es una comparación de aceptación de órdenes, no una afirmación de que el motor físico anterior permitiera atravesar el pedestal: sus cajas podían frenar el movimiento y separar la posición real de la estimada.

Se repitieron además los **nueve escenarios de movimiento/fallas** en [simulation_collisions.json](../validation/simulation_collisions.json) y las **330 comparaciones de colocación CAD en once estados**, con seis llegadas, en [cad_motion_collisions.json](../validation/cad_motion_collisions.json). Ambos informes aprobaron. Los hashes de los cinco informes actuales coinciden con sus fuentes finales. Las masas, centros y parámetros de inercia se contrastaron con el snapshot anterior y permanecen iguales; también se verificaron los 50 originales CAD sin cambios.

La [identidad del ensayo aislado](../validation/collisions_execution.json) conserva plataforma, versión, hash del ejecutable, mundo temporal y fuentes copiadas. La copia terminó STOPPED, en la pose inicial, carga cero y referencia válida, y se cerró al completar la revisión. El navegador contra el banco completo no se repitió en esta etapa; su evidencia anterior sigue siendo histórica. El rechazo previo de `Bridge` sí tiene regresión independiente.

En la caída, J4 pasó de aproximadamente **80,0015 a 94,6774 mm**, en vez de llegar al tope de 120 mm. El TCP quedó a **−0,0294 mm**, con cuatro contactos cerca de Z=0 dentro de la planta del pedestal. Esa pequeña penetración corresponde a la resolución del contacto del solver; no se afirmó contacto matemático sin penetración. La referencia quedó inválida y el esfuerzo de J4 en cero, como correspondía a la falla. El ensayo terminó con recarga a STOPPED.

El caso nativo de extremos libres usa **119 mm**, mientras el diagnóstico BREP y la regresión geométrica conservan 120 mm. La invasión intermedia subsiste a 119 mm; esa diferencia evita mezclar el contacto con la oscilación de tope encontrada a continuación.

### Problema adicional observado: oscilación en el tope exacto de J4

Al mantener `[-60°,120°,0°,120 mm]`, una pose lateralmente libre del pedestal, se observó oscilación sostenida: en una ventana de dos segundos simulados J4 recorrió aproximadamente **109,096–120,051 mm**, sin contactos reportados. Se conservó la [sonda con muestras, contactos y hashes](../validation/j4_stop_probe.json). La discrepancia llega a unos **10,9 mm respecto de la consigna**; una orden terminada no acredita llegada estable.

Al cerrar el15/10 era compatible con una interacción del actuador y el tope, todavía por aislar. El [diagnóstico del16/10](DIAGNOSTICO_TOPE_J4.md) la reprodujo sin plegar los brazos, contrastó la rama motor/tope de ODE y redujo su amplitud a0,174mm al pasar de16 a2ms. No se modificaron límites ni se trasladó el pedestal. La protección geométrica continúa comprobando la trayectoria ordenada; el ajuste numérico y su regresión verifican por separado el sostén de J4.

## 6. Cómo repetir

### Auditoría geométrica sin abrir Webots

Desde la raíz del proyecto, utilizar el entorno CAD existente o recrearlo según [el procedimiento del punto 1](PROPIEDADES_GEOMETRICAS_CAD.md#6-cómo-reproducirlo):

```sh
/private/tmp/scara-cad-piloto-20261014/venv/bin/python tools/check_collisions.py --output /tmp/scara-colisiones-repeticion.json
python3 -m unittest tests.test_collisions -v
```

El primer comando necesita OCP y lee los STEP ya convertidos. No reconvierte originales ni conecta con Webots. `--output` evita sobrescribir evidencia anterior; sin esa opción escribe `validation/collisions.json`. Un hash distinto del manifiesto o un cambio de entradas durante el cálculo produce un error que debe investigarse antes de usar el resultado.

Para regenerar el mundo después de cambiar `environment` o la política de cajas:

```sh
python3 tools/generate_world.py
```

El mundo abierto no se actualiza automáticamente. Recargar una sesión activa cambia su ensayo; para esta revisión se utilizó otra copia aislada.

### Ensayo nativo aislado

El equipo del usuario usa **Webots R2025b nightly** por problemas de R2025a en macOS 27. Se inspeccionó `/Applications/Webots 2.app`; la versión ejecutable informa la compilación del 14/10 y el commit **`a459c02c7292d23ae437101c76111ec1668198c8`**. Los encabezados `.proto`/`.wbt` siguen declarando R2025a como formato del archivo.

La revisión utiliza una copia temporal en `/private/tmp/scara-colisiones-native-20261015`: copias de `scara`, `config`, `webots` y `cad/ensambles`, con enlace a los derivados CAD originales, que no se modifican. En el mundo de esa copia, la instancia se configura así:

```text
DEF SCARA SCARA { controllerArgs [ "--port" "19001" ] }
```

Los dos puertos tienen funciones distintas:

| Puerto | Función |
|---|---|
| `19001` | TCP `scara-dev/1` del controlador y de los scripts de ensayo. |
| `19003` | Puerto de la segunda instancia de la aplicación Webots. |

La sesión de trabajo del usuario, con TCP **9000** y cliente HTTP **8765**, queda aparte. No se conecta el cliente web a la copia de ensayo. Para una repetición, preparar una copia nueva con estas mismas fuentes, comprobar que los puertos elegidos estén libres y guardar hashes que permitan asociar esa copia con los scripts ejecutados desde el repositorio.

El comando que resultó operativo en este equipo fue:

```sh
"/Applications/Webots 2.app/Contents/MacOS/webots" --batch --mode=fast --stdout --stderr --port=19003 /private/tmp/scara-colisiones-native-20261015/webots/worlds/scara.wbt
```

Un primer arranque con `--no-rendering` y `--minimize` quedó sin controlador en este equipo; la reproducción documentada conserva la combinación anterior. `Fast` reduce el tiempo de pared y mantiene el paso físico de 16 ms del mundo.

Con esa copia reproduciendo y atendiendo su controlador, desde la raíz de las mismas fuentes:

```sh
python3 tools/check_collisions_native.py --port 19001 --snapshot-root /private/tmp/scara-colisiones-native-20261015 --webots-version "R2025b nightly; build 14/10/2026; a459c02c7292d23ae437101c76111ec1668198c8" --output /tmp/scara-colisiones-native-repeticion.json
```

Esta prueba **recarga su mundo y provoca una falla de esfuerzo**. Al completar satisfactoriamente deja su ensayo inicial en `STOPPED`. Ante un fallo conserva `status=failed` y el error en la salida. No se debe ejecutarla sobre la sesión de trabajo que se quiera conservar. Verificar después que los hashes de la copia utilizada y los informados por el script corresponden a las mismas fuentes; cambiar solo el puerto de la instancia es una diferencia explícita del montaje del ensayo.

Para reproducir específicamente la sonda del tope, en esa misma copia de ensayo y sin otro script conectado:

```sh
python3 - <<'PY'
import math
from tools.check_simulation import Bench
r = dict(requests=[], events=[])
b = Bench('127.0.0.1', 19001, r)
try:
    b.connect(); b.reset(); b.command('rearm')
    for z in (.06, .12):
        request_id = b.command('move_joints', positions=[-math.pi/3, 2*math.pi/3, 0, z], speed=1)
        b.wait(lambda e: e.get('id') == request_id and e.get('event') == 'completed')
    samples = b.observe(2)
    request_id = b.command('inspect_contacts')
    contacts = b.wait(lambda e: e.get('id') == request_id and e.get('event') == 'contact_snapshot')
    print(min(s['simulated'][3] for s in samples), max(s['simulated'][3] for s in samples), contacts)
    b.reset()
finally:
    b.close()
PY
```

Este comando también recarga y mueve el ensayo. Una eventual ausencia de oscilación en otra compilación debe registrarse como resultado distinto, conservando versión, condiciones y muestras.

## 7. Conservación de lo anterior

Antes de modificar el modelo se preservaron **17 fuentes e informes** en [validation/historico/antes_colisiones_20261015](../validation/historico/antes_colisiones_20261015/), con [snapshot.json](../validation/historico/antes_colisiones_20261015/snapshot.json). Incluye configuración, cliente, controlador, generador, mundo/PROTO, manifiesto, informes nativos y resultados de propiedades geométricas.

El punto 1 mantiene su alcance histórico. Sus hashes de configuración y archivos Webots corresponden al momento anterior a cambiar entorno y colisiones; una diferencia con los archivos actuales es esperable. No se usa esa diferencia para invalidar el precálculo volumétrico ni para afirmar que su informe validó el nuevo comportamiento. Los STEP y originales se verifican de nuevo en la auditoría del punto 2.

## 8. Límites y datos que faltan

- **Autocolisiones pendientes.** `selfCollision FALSE` continúa en el robot. No se analizan ni resuelven contactos entre brazo, carreteles, muñeca, torre u otras piezas del robot.
- **Sin búsqueda de desvíos.** Una trayectoria rechazada requiere otro destino o una secuencia de puntos intermedios válidos; no se calcula automáticamente una ruta alternativa.
- **Seguimiento físico sin garantía geométrica.** La cota corresponde a las consignas nominales. La dinámica, pérdida de esfuerzo, caída, atraso del motor o contacto pueden separar al cuerpo simulado de esa referencia. El ensayo de falla existe precisamente para observar esa diferencia.
- **CAD y montaje incompletos.** Faltan los tres BREP móviles excluidos, piezas todavía no incorporadas, cables, herramienta real, carga real, pertenencia y fase de transmisiones. Las cajas pendientes son aproximaciones declaradas.
- **Recorridos y referencias provisionales.** Se necesitan ceros/signos de montaje, límites físicos, topes, homing y TCP confirmados. Los límites numéricos actuales no acreditan que cada combinación sea mecánicamente posible.
- **Física material pendiente.** No se cambiaron masas, centros, inercias, esfuerzos máximos, fricción ni otros materiales de contacto. Continúan las masas exploratorias y las propiedades de cajas anteriores, según el punto 1.
- **Tope exacto de J4, actualización16/10.** El diagnóstico posterior cumple el criterio de sostén con paso2ms y residuo≤0,174mm en los escenarios medidos. Repetir al cambiar masas, esfuerzos, topes, paso o build; no es una garantía de estabilidad ilimitada ni de hardware.

La siguiente ampliación debe contrastar las interferencias internas y las piezas pendientes con el montaje real. Antes de reemplazar una envolvente por una forma más precisa o habilitar un recorrido hoy rechazado, debe quedar registrada la geometría que lo justifica y una comprobación reproducible.
