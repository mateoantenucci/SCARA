# Validación del SCARA con CAD articulado parcial

**Revisión vigente del16/10:** [diagnóstico J4](DIAGNOSTICO_TOPE_J4.md), paso físico2ms, quince escenarios de sostén aprobados y regresiones propias en [simulation_j4.json](../validation/simulation_j4.json), [cad_motion_j4.json](../validation/cad_motion_j4.json) y [collisions_native_j4.json](../validation/collisions_native_j4.json). La instrumentación nueva mide cada paso físico; se guarda residuo numérico y no se promete precisión real. Los informes y descripciones del14–15/10 siguientes conservan su contexto histórico de16ms.

Actualización del punto 2: los informes originales siguientes conservan la revisión anterior. La revisión de colisiones tiene evidencia propia aprobada en [collisions_native.json](../validation/collisions_native.json), [simulation_collisions.json](../validation/simulation_collisions.json) y [cad_motion_collisions.json](../validation/cad_motion_collisions.json). Son cinco casos nuevos, nueve regresiones de dinámica/fallas y 330 comparaciones CAD. El [proceso de colisiones](COLISIONES_Y_RECORRIDOS.md) explica fuentes, copia aislada, límites y la oscilación pendiente del tope J4; no se trasladó automáticamente una aprobación histórica al modelo nuevo.

Ensayo ejecutado el 14/10/2026 en macOS Apple Silicon con Webots R2025b `nightly_13_10_2026`. La ventana del ejecutable identifica el build `a459c02c7292d23ae437101c76111ec1668198c8`; el tag del repositorio resuelve a `303f6bc2af6b241098d2773cd3f9ae507187f2ef`, que es una referencia distinta. Se usa esta compilación por el fallo de arranque de R2025a en macOS 27, documentado en el checkpoint.

**Resultado de la integración del 14/10: 16 pruebas Python, nueve comprobaciones integradas y el ensayo de movimiento CAD aprobados.** La revisión del punto 2 amplió la suite a30 pruebas, todas aprobadas; evidencia en [collision_tests.json](../validation/collision_tests.json). El mundo contiene 30 instancias: 27 con geometría CAD y tres representaciones alámbricas de piezas cuya malla sigue rechazada. La torre usa tres cuerpos validados individualmente. El [manifiesto articulado](../cad/ensambles/integracion_articulada.json) conserva las fuentes, poses y asignaciones de cuerpo.

La evidencia del smoke está en [`validation/simulation.json`](../validation/simulation.json): nueve comprobaciones, 137 eventos, solicitudes, tolerancias y hashes. El [ensayo CAD](../validation/cad_motion.json) registra 11 instantáneas de las 30 instancias —330 comparaciones de pose— y seis llegadas articulares. Ambos informes corresponden al modelo actual; los hashes de sus archivos fuente coincidían al revisar esta documentación. La interfaz también tiene una [comprobación nativa actual aprobada](../validation/client_native.json), descrita más abajo.

Los resultados anteriores del banco de cajas se conservan en [`validation/historico/banco_cajas/`](../validation/historico/banco_cajas/). No se usan como validación del CAD actual.

Esto valida el funcionamiento de una cadena R-R-R-P con visuales CAD parciales y física equivalente provisional. Las masas de los cuatro cuerpos móviles siguen siendo 0,30; 0,50; 0,35 y 0,15 kg; los centros e inercias proceden de cajas envolventes equivalentes. La base es fija. No certifica prestaciones del SCARA, materiales, acoplamientos, precisión física ni el protocolo docente pendiente.

## Resultados

| Comprobación | Evidencia |
| --- | --- |
| Pose inicial | Error del extremo frente a la cinemática de referencia: 0,0247 mm. Posiciones y orientación finitas, dentro de tolerancias. |
| Movimiento nominal XYZ y orientación | Desde aproximadamente (250, 250, 34,667) mm hasta (300, 200, 50) mm, orientación omitida y velocidad relativa 70 %. Error final del extremo: 0,0248 mm; máximo error de rumbo observado: 6,68×10⁻⁷ rad. Se espera el fin de consignas y luego 0,7 s simulados para comprobar llegada. |
| Rechazo previo | Un objetivo articular fuera de recorrido se rechaza conservando estado y consigna. |
| Hall y rearme | Lectura entregada fija activa frente a nominal inactiva; falla detiene, rearme se rechaza mientras está activa. Limpiar deja STOPPED; habilitar requiere otra orden. |
| Masa, centro e inercia | Para 0,25 kg añadidos, el cuerpo pasa de 0,15 a 0,40 kg. Los valores leídos de Physics coinciden con el cálculo de masa/centro/inercia. Feedback vertical en reposo: 3,924 N de magnitud, frente a 0,40×9,81=3,924 N. |
| Pérdida de fuerza J4 | Con carga añadida de 0,25 kg y esfuerzo disponible nulo, caída de 59,999 mm. Limpiar no devuelve fuerza ni referencia; habilitar se rechaza hasta reiniciar ensayo. |
| Sobrecarga conocida | Añadir 1 kg produce caída de 60,051 mm con esfuerzo disponible todavía en 8 N. El aviso procede del peso conocido que supera la capacidad estática provisional. Cambiar masa y rearmar se rechazan tras perder referencia. |
| Corte y reconexión | Durante una trayectoria se cierra TCP. Al reconectar, STOPPED y referencia congelada durante la ventana de observación; no repite órdenes ni habilita automáticamente. |
| Reinicio de ensayo | Recarga restaura pose inicial, carga cero, referencia válida y STOPPED; no equivale a homing físico. |

Las diferencias pequeñas frente a la cinemática pertenecen al solver y a las restricciones del mundo simulado. **No significan que un robot construido alcance precisión de centésimas de milímetro.** Los contactos con topes admiten una pequeña desviación numérica; no se fuerzan posiciones perfectas por software.

## Comprobación de las piezas CAD en movimiento

[`tools/check_cad_motion.py`](../tools/check_cad_motion.py) consulta las posiciones y orientaciones mundiales reales de los nodos `Pose` mediante Supervisor. La consulta `inspect_cad` es instrumentación del banco: no introduce destinos ni usa estas mediciones para corregir el control.

Se reconstruye primero el ensamble guardado en su sistema canónico y luego se mueve cada articulación por separado. Las comprobaciones distinguen los cuerpos que deben permanecer fijos de los que deben acompañar a cada eje; J4 baja 15 mm conservando el rumbo relativo del pistón y soporte. También se comprueba la llegada a las seis consignas, con tolerancias de 0,005 rad y 0,0005 m, después de 0,6 s simulados de asentamiento.

| Medición del informe CAD | Resultado |
| --- | --- |
| Instantáneas y cobertura | 11 × 30 instancias = 330 comparaciones de posición y orientación; incluye pose inicial, ensamble guardado, antes/después de J1–J4 y restauración. |
| Mayor diferencia de posición | 0,025705 mm, frente a una tolerancia de 1 mm. |
| Mayor diferencia de entrada de matriz de rotación | 5,1944×10⁻⁶, frente a una tolerancia de 0,01. |
| Seis llegadas | Mayor error de giro: 3,734×10⁻⁶ rad; mayor error de J4: 0,001472 mm. |
| Masas y restauración | Los valores `Physics` leídos coinciden con las masas provisionales configuradas; el reinicio recupera el estado inicial. |

La prueba valida que las piezas sigan **la pertenencia de cuerpo declarada** y que su pose guardada pueda reconstruirse. No demuestra por sí sola que los mates, ajustes, fases angulares ni materiales coincidan con un robot construido. Las tres piezas pendientes siguen siendo cajas alámbricas; las discrepancias entre algunas revisiones de malla y caché permanecen rotuladas en el manifiesto.

## Tolerancias declaradas antes de ejecutar

- Error articular final: menos de 0,005 rad en ejes de giro y 0,0005 m en J4.
- Error XYZ final y entre TCP real simulado y directa de sensores: menos de 0,001 m.
- Conservación de rumbo: menos de 0,02 rad.
- Feedback vertical estático: diferencia menor de 0,2 N frente al peso calculado.
- Caída por F01/F05: más de 0,03 m dentro de 1,2 s simulados; límite superior de J4 más tolerancia de contacto de 0,002 m.

Las muestras de estado llegan aproximadamente cada 0,128 s simulados. Webots se ejecutó en modo Fast con `basicTimeStep=16 ms`; los plazos de trayectorias, asentamiento y caídas usan tiempo simulado. Fast cambia la relación con el tiempo de pared, no ese paso de simulación. Los timeouts de conexión del cliente usan tiempo de pared. No se mide con las muestras un máximo continuo ni una respuesta certificada del sistema.

El banco identifica cada ejecución del controlador con `trial_id`: al recargar se exige observar otro identificador, además de STOPPED, carga cero y referencia válida. Las solicitudes del informe son copias del JSON enviado; modificar después una lista de destinos no cambia retroactivamente la evidencia.

## Interfaz externa contra el simulador real

Con el CAD actual se comprobó la cadena completa desde el navegador: habilitar, enviar (240, 250, 35) mm al 30 % con orientación vacía y regresar a (250, 250, 34,67) mm. Se observaron aceptación, movimiento y fin de consignas. Los errores finales del extremo fueron 0,024723 y 0,024761 mm, respectivamente, dentro de la tolerancia de 1 mm. El aviso superior cambió de «encolada» a la respuesta de fin correspondiente y se comprobó su texto en el navegador.

La [evidencia HTTP y estado nativo](../validation/client_native.json), con estado `passed`, registra tres pasos y hashes vigentes: ida, vuelta y reinicio. El último paso muestra una `trial_id` distinta, STOPPED, carga cero y referencia válida; no se limita a leer un estado anterior al reinicio.

Esta comprobación de interfaz es una ejecución separada de los nueve escenarios automatizados, reproducible siguiendo la primera prueba del README. No acredita todos los controles ni fallas de la interfaz, y no reemplaza las pruebas de TCP.

## Qué se corrigió al probar

El primer ensayo encontró que modificar directamente los campos Physics internos del PROTO era rechazado por Webots. La interfaz del PROTO ahora expone masa, centro e inercia de la herramienta mediante campos conectados con `IS`; el controlador los modifica en la instancia. Se verifica su lectura efectiva después del siguiente paso físico. Las restricciones de acceso están descritas en [Supervisor R2025a](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/supervisor.md#wb_supervisor_node_get_field).

La revisión también detectó que quitar una carga excesiva después de que cediera J4 podía devolverlo hacia una consigna antigua sin rearme. Ahora el peso de ensayo conocido que supera el sostén estático genera un aviso explícito del banco, cancela la trayectoria e invalida la referencia. El esfuerzo sigue en 8 N para representar sobrecarga sin mezclar pérdida de fuerza; se exige recargar el ensayo para cambiar carga tras perder referencia.

El banco no agrega un encoder ni obtiene un diagnóstico real de la diferencia de posiciones. El caso sublímite no certifica capacidad dinámica: aceleración, rozamiento, transmisión y configuración pueden exigir más esfuerzo que el peso estático.

## Cómo repetir

1. Abrir `webots/worlds/scara.wbt` y ejecutar la simulación. No conectar la interfaz ni otro cliente: el servidor admite una conexión de ensayo a la vez.
2. Desde la raíz del proyecto:

```sh
python3 tools/check_simulation.py --webots-version "versión y compilación utilizadas"
```

Para comprobar después la geometría en movimiento, manteniendo la interfaz desconectada:

```sh
python3 tools/check_cad_motion.py --webots-version "versión y compilación utilizadas"
```

En Windows puede usarse `python`. Los programas recargan el mundo y requieren un único cliente TCP; el smoke además cambia carga e inyecta fallas. Al terminar correctamente dejan el banco detenido, en su estado inicial. Es necesario mantener Webots en reproducción; una pausa detiene también la atención TCP de este controlador. Fast puede reducir el tiempo de pared necesario.

Los informes predeterminados se sobrescriben en `validation/simulation.json` y `validation/cad_motion.json`. Para comparar otra ejecución conservarlos antes, o elegir otra ruta con `--output validation/otra_ejecucion.json`. Contienen hashes; regenerar el modelo o modificar parámetros requiere repetir los ensayos correspondientes.

## Límites todavía abiertos

- El CAD articulado es parcial: hay 30 instancias, tres representaciones pendientes y asignaciones de montaje provisionales. Las colisiones usan envolventes; masas, COM, inercias y límites de esfuerzo no son propiedades materiales confirmadas.
- Los informes previos a la revisión de colisiones solo comprobaban cinemática y límites. Por ejemplo, `q=[−π/8, 3π/4, −5π/8, 0,12]` cumple límites pero invade el pedestal. La [actualización del punto 2](COLISIONES_Y_RECORRIDOS.md) rechaza ahora el recorrido nominal completo de las envolventes frente al pedestal/piso configurados y aporta evidencia nueva; no busca desvíos ni comprueba todo el volumen del diseño. `selfCollision FALSE` tampoco demuestra ausencia de autocolisiones.
- J1 no dispone de feedback de torque con la base estática utilizada. Se publica `null` y no se inventa una lectura.
- Los Hall siguen siendo regiones lógicas provisionales; no hay búsqueda física de referencia, conteo de pasos, pérdida de pasos ni encoder del diseño.
- No se verifican atascos mecánicos, desprendimientos, detección de una interrupción silenciosa de red ni protocolo oficial del profesor.
- El smoke de nueve comprobaciones usa TCP directamente contra Webots. La interfaz tiene pruebas separadas con un servidor de referencia y una comprobación nativa de movimiento desde el navegador, descrita arriba.
- Windows/Linux y otras compilaciones de Webots todavía necesitan repetir la ejecución nativa.
