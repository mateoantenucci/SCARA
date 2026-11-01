# Colisiones y comprobación de recorridos

El control rechaza antes de mover los recorridos nominales que no demuestran separación frente al pedestal y al suelo, y los de herramienta/carga frente a la base fija. El [montaje](MONTAJE_Y_AUTOCOLISIONES.md) describe los choques internos estudiados; la [campaña de validación](../validation/campana/INFORME.md) identifica la revisión y los casos ensayados.

## Representaciones y alcance

| Representación | Uso | Límite |
| --- | --- | --- |
| Sólidos BREP convertidos a STEP | Medir distancias e intersecciones CAD en poses de auditoría | Verifica esas geometrías y poses, sin certificar todo el diseño. |
| Mallas visuales | Mostrar las piezas | La apariencia no prueba contacto físico. |
| `boundingObject` de Webots | Resolver contactos físicos con cajas por instancia | Las cajas ocupan también huecos y pueden producir contactos falsos. |
| Comprobador Python | Acotar el recorrido nominal antes de aceptarlo | Conservador; no garantiza seguir la trayectoria durante una falla. |

El entorno de ensayo está en `config/scara.json`: pedestal de X,Y entre −200 y +200 mm y Z entre −200 y 0 mm; suelo de X,Y entre −1000 y +1000 mm y Z entre −210 y −200 mm. Z=0 es la cara superior del pedestal, no un piso infinito. Un extremo con Z negativa puede estar libre si está fuera de la planta del pedestal.

## Problemas que motivaron el control

Con las referencias adoptadas:

```text
Z_TCP = 94,666858865 mm − J4_mm
```

A J4=120 mm, el punto de herramienta queda a −25,333 mm. Si se pliega el brazo sobre el pedestal, el pistón y el soporte pueden invadirlo. La auditoría CAD confirmó esas intersecciones; el soporte ya dispone de geometría recuperada, por lo que la exclusión de su BREP en los primeros informes está superada.

Un caso importante tiene **inicio y final libres, con un tramo intermedio invasivo**:

| Momento | J1 | J2 | J3 | J4 |
| --- | ---: | ---: | ---: | ---: |
| Inicio | −60° | 120° | 0° | 120 mm |
| Mitad | −15° | 120° | 0° | 120 mm |
| Final | 30° | 120° | 0° | 120 mm |

La interpolación es articular: el extremo sigue una curva. Comprobar solo el destino, o ambos extremos, dejaba pasar este movimiento. La [comparación anterior/posterior](../validation/collisions_before_after.json) conserva el rechazo introducido y la [auditoría con las geometrías recuperadas](../validation/collisions_recovery.json) confirma el pistón y soporte invasivos.

Las cajas agregadas de cuerpos completos también exageraban el volumen ocupado. Se reemplazaron por cajas locales por instancia, conservando su colocación. Los centros e inercias de la física equivalente se mantuvieron separados: mejorar contactos no justificaba inventar propiedades materiales.

## Dónde se aplica

`piece_boxes()` de `scara/collisions.py` obtiene las cajas del manifiesto `cad/ensambles/integracion_articulada.json`. Las usan el generador Webots y el comprobador. El entorno también comparte una única definición en configuración.

`Runtime.handle()` valida límites, duración y recorrido antes de crear una trayectoria o pasar a `MOVING`. Es el control común para las órdenes TCP; no depende de que el cliente sea correcto. `Bridge.command()` en `client/app.py` también comprueba después de resolver la inversa y antes de encolar, para mostrar rechazos tempranos. El controlador repite la validación porque el estado del cliente puede estar retrasado.

Un rechazo no modifica posiciones, trayectoria, modo, fallas, carga ni referencia. Durante movimiento se rechaza otra orden de movimiento. No se calcula una ruta alternativa.

Al cambiar carga se comprueba también su ocupación en la pose actual. Si la masa es positiva, el comprobador reserva un cubo de 40 mm centrado en el TCP, consistente con la aproximación de `scara/dynamics.py`. **Es una reserva geométrica, no un sólido adicional de contacto de Webots.** La carga sí modifica masa, centro e inercia equivalentes.

## Cómo se acota todo el recorrido

Las articulaciones comparten un escalar suave y monótono del perfil quíntico:

```text
q(s) = inicio + s · (destino − inicio), 0 ≤ s ≤ 1
```

La velocidad modifica la duración, sin cambiar ese segmento articular. Para cada caja e intervalo de `s`, el algoritmo:

1. Coloca sus ocho vértices en el punto medio y forma una caja alineada con los ejes del mundo, AABB.
2. Amplía esa caja con una cota del desplazamiento posible hasta cualquier punto del intervalo.
3. Si la ampliación está separada de los obstáculos, aprueba ese intervalo.
4. Si no demuestra separación, subdivide. Cuando llega a la resolución mínima sin resolver la superposición, rechaza.

La cota de movimiento XY proviene de las derivadas de las rotaciones. Sean `Δi` los cambios articulares, `R` la distancia XY máxima de los vértices al origen de su cuerpo y `l1,l2` las longitudes:

```text
Brazo:       B = R·|Δ1|
Antebrazo:   B = l1·|Δ1| + R·|Δ1+Δ2|
Muñeca/tool: B = l1·|Δ1| + l2·|Δ1+Δ2| + R·|Δ1+Δ2+Δ3|
```

Para un intervalo de semiancho `h`, X,Y se amplían en `B·h`. Z es constante en brazo/antebrazo/muñeca y varía en herramienta/carga, acotada por `|Δ4|·h`. Así se contiene el recorrido completo, aunque la cota pueda ser más grande que el barrido real.

| Parámetro | Valor | Significado |
| --- | ---: | --- |
| `margin_m` | 0,001 m | Ampliación de cada obstáculo por coordenada. |
| `interval_bound_m` | 0,00025 m | Resolución para rechazar superposiciones aún inciertas; no es penetración permitida. |
| `MAX_INTERVALS` | 4096 | Presupuesto por llamada interna de comprobación; agotarlo rechaza. |

Si el punto medio ya no se distingue numéricamente de un extremo, también se rechaza. Esto evita un cálculo que no termina con resoluciones impracticables. `first_conflict()` identifica una pieza/obstáculo e intervalo incierto; el orden de revisión no garantiza el primer instante físico de contacto.

Además del entorno, se comprueban las cajas de herramienta/carga frente a las cajas fijas de la base. No se aplica indiscriminadamente a todas las uniones: las cajas rellenan alojamientos que en el CAD son huecos.

## Evidencia y repetición

Las pruebas `tests/test_collisions.py` cubren demostraciones admisibles, plegados invasivos, cruce intermedio en ambos sentidos, margen, carga, rechazo sin mutación en Runtime/Bridge y terminación numérica. Un contraste de poses muestreadas complementa la cota continua, sin sustituirla.

Los informes de `tools/check_collisions.py` calculan intersecciones BREP. Los de `tools/check_self_collisions.py` comparan pares internos en poses seleccionadas. `tools/check_collisions_native.py` verifica cajas efectivas, rechazo y contacto bajo gravedad en Webots. El índice de la [validación](historico/VALIDACION_WEBOTS.md) enlaza los resultados consolidados.

Para repetir desde la raíz, usando el Python con OCP en las auditorías CAD:

```sh
python tools/check_collisions.py --output /tmp/scara-colisiones-repeticion.json
python tools/check_self_collisions.py --output /tmp/scara-internas-repeticion.json
python3 -m unittest tests.test_collisions -v
```

Para ensayar Webots, usar una copia recargable, desconectar otros clientes, dejar reproducción activa y ejecutar:

```sh
python3 tools/check_collisions_native.py --webots-version "versión y build usadas" --output /tmp/scara-contactos-repeticion.json
```

El ensayo nativo recarga e inyecta pérdida de esfuerzo. Admite `--port` y `--snapshot-root` para identificar una copia con puerto alternativo. La prueba verifica contactos del modelo simplificado; no son contactos exactos de todas las superficies CAD. Si cambia el entorno o la política de cajas, regenerar con `python3 tools/generate_world.py` y repetir las comprobaciones afectadas.

## Límites que deben acompañar cualquier demostración

No hay comprobación continua general de autocolisiones ni planificación de desvíos. `selfCollision FALSE` mantiene desactivados los contactos internos generales. Los ensayos con poses seleccionadas no cubren todo el espacio articular.

La cota sigue consignas ideales; una falla, gravedad, contacto o atraso del motor pueden separar la posición física de esa referencia. Faltan piezas, cables, herramienta/carga reales y revisión oficial de topes, referencias y transmisión. Las propiedades materiales y de contacto siguen siendo aproximaciones.

La oscilación encontrada al llegar a J4=120 mm se trató como un problema numérico separado: el [diagnóstico](historico/DIAGNOSTICO_TOPE_J4.md) respalda el paso de 2 ms. No se recortó la carrera a 119 mm ni se desplazó el pedestal para ocultar el problema.
