# Protocolo de comunicación SCARA `scara-dev/1`

**Estado:** contrato provisional implementado, para revisión de la cátedra. **Revisión documental: 20/10/2026.** Describe el comportamiento actual del software; no constituye un protocolo aprobado por el profesor ni una especificación de firmware físico. La creación de este documento no modifica el código ni incorpora funciones nuevas.

## 1. Resumen para revisar con el profesor

El programa externo Python se conecta como cliente al controlador de Webots, que escucha como servidor TCP local. Intercambian objetos JSON terminados en salto de línea. El cliente solicita acciones; el controlador valida, responde y publica estados periódicos.

Las posiciones recibidas por el controlador son articulares. La interfaz web permite pedir XYZ, pero su programa Python resuelve la cinemática inversa antes de enviar las articulaciones. El controlador genera el perfil de consignas y las aplica a los motores simulados.

| Decisión actual | Valor |
| --- | --- |
| Nombre del contrato de desarrollo | `scara-dev/1` |
| Servidor | Controlador de Webots: `scara_bridge.py` y `scara/transport.py` |
| Cliente de referencia | `client/app.py` |
| Dirección y puerto predeterminados | `127.0.0.1:9000` |
| Transporte y formato | TCP, texto UTF-8, JSON por línea |
| Delimitador | LF, byte `0x0A`, representado como `\n` |
| Unidades de movimiento | J1–J3 en radianes, J4 en metros |
| Movimiento | Punto a punto con perfil articular suave; no garantiza recta cartesiana |
| Estados de operación | `STOPPED`, `IDLE`, `MOVING`, `FAULT` |
| Resultado de una orden | `accepted` o `rejected`; el movimiento puede producir después `completed` |
| Estado periódico | Evento `state`, aproximadamente cada 128 ms simulados |
| Rearme | Explícito; conectar o limpiar fallas no inicia un movimiento |

El identificador `scara-dev/1` se informa en la telemetría y en el cliente, pero **no se negocia al conectar** ni se exige como campo de las solicitudes. No existe un mensaje obligatorio de saludo o selección de versión. El cliente debe conocer este contrato.

## 2. Participantes y fronteras

```text
Navegador → HTTP local → Programa externo Python → TCP → Controlador de simulación
                                                             ↓ API de Webots
                                                        Motores y sensores
```

El navegador se comunica con Python en `127.0.0.1:8765`. Esa interfaz HTTP es diferente del enlace TCP al controlador; se resume en el anexo A. No se utiliza WebSocket.

`scara_bridge.py` es parte del controlador, no parte del programa externo. Obtiene las órdenes de `Server.poll()`, delega reglas a `Runtime.handle()` y aplica posiciones/esfuerzos mediante la API de Webots. No recibe por TCP llamadas como `setPosition`: recibe órdenes del contrato SCARA y las traduce a llamadas de API.

El servidor atiende un cliente activo a la vez. Los puertos son configurables: el controlador admite `--port`; el programa externo admite `--webots-port` para ese enlace y `--port` para su servidor HTTP. La instancia entregada utiliza los valores predeterminados.

## 3. Delimitación y recepción de mensajes

Cada mensaje es un objeto JSON serializado en una única línea, seguido por LF. En los ejemplos de bloques `json`, añadir ese salto de línea al transmitir. No usar JSON con saltos de línea de formato entre sus campos. Un salto dentro de una cadena se representa escapado como `\n` dentro del JSON.

TCP es un flujo de bytes: una lectura puede contener un fragmento o varios mensajes. Ambas partes acumulan fragmentos, separan por LF y conservan lo incompleto para otra lectura. Una solicitud incompleta no se ejecuta hasta completar su línea. Al perder la conexión se descartan los fragmentos pendientes.

El código usa `MAX_FRAME = 16 * 1024`. Para interoperar en ambos sentidos, la línea serializada **incluido LF** debe ocupar como máximo 16384 bytes: el emisor del servidor cuenta el delimitador; su receptor comprueba el contenido anterior a LF. No es un límite de caracteres Unicode. Un tamaño excesivo puede causar cierre de conexión, no una respuesta de rechazo.

Los números deben ser finitos. Se rechazan JSON inválido, UTF-8 inválido y constantes no finitas. El transporte devuelve en esos casos, cuando la conexión sigue disponible:

```json
{"event":"rejected","id":null,"message":"JSON invalido"}
```

No hay una cola ilimitada: la implementación limita el procesamiento por paso y desconecta si su buffer saliente supera 256 KiB. Esos límites internos no constituyen una garantía de tiempo de respuesta.

## 4. Solicitudes, identificadores y respuestas comunes

Una solicitud normal tiene `command` y, para correlacionar respuestas, `id`:

```json
{"id":"orden-001","command":"rearm"}
```

| Campo | Regla de las órdenes normales |
| --- | --- |
| `command` | Nombre exacto, sensible a mayúsculas/minúsculas. Los desconocidos se rechazan. |
| `id` | Opcional; puede ser `null` o texto de hasta 80 caracteres. Se devuelve en la respuesta. El cliente de referencia genera un UUID textual. |
| Campos específicos | Los de cada orden, descritos abajo. |

Usar un `id` textual diferente por solicitud. **El controlador no elimina duplicados ni recuerda órdenes por `id`**: repetirlo no garantiza que una orden se ejecute solo una vez. No reenviar automáticamente un movimiento cuyo resultado se desconoce.

El receptor no aplica un esquema que rechace todos los campos adicionales. Para compatibilidad, enviar solamente los documentados. No existen códigos numéricos estables de error: `message` es texto explicativo y no debe tratarse como un enum fijo.

Una orden admitida normalmente responde:

```json
{"event":"accepted","id":"orden-001","mode":"IDLE"}
```

Una rechazada responde, por ejemplo:

```json
{"event":"rejected","id":"orden-002","message":"Primero quitar las fallas inyectadas"}
```

`accepted` confirma la admisión, no la ejecución física ni el éxito de un movimiento. `rejected` no anuncia un movimiento parcial. Los mensajes `state` pueden intercalarse con las respuestas: el cliente discrimina por `event` y correlaciona por `id` cuando ese evento lo contiene. Los estados periódicos no llevan el `id` de una solicitud.

## 5. Estados y reglas de movimiento

| `mode` | Significado |
| --- | --- |
| `STOPPED` | Sin trayectoria y sin habilitación para iniciar movimiento. |
| `IDLE` | Habilitado y disponible para una orden de movimiento. |
| `MOVING` | Hay una secuencia de consignas en ejecución. |
| `FAULT` | Hay fallas registradas y se canceló la trayectoria. |

Al arrancar se usa `initial_positions`, carga cero, factores de esfuerzo nominales y referencia inicial de simulación válida. El modo es `STOPPED`. Esa referencia es una condición inicial del ensayo, no un home encontrado mediante sensores.

Flujo nominal: `STOPPED` → `rearm` → `IDLE` → `move_joints` → `MOVING` → fin de consignas → `IDLE`.

`stop`, desconexión reconocida y falla notificada cancelan el perfil. La consigna queda en la referencia estimada al cancelar. La física sigue activa: no se fuerzan posiciones exactas ni se garantiza inmovilidad instantánea o sostén con esfuerzo insuficiente.

## 6. Órdenes operativas

### `rearm`: habilitar movimiento

Sin parámetros adicionales. Rechaza si hay fallas, si la referencia es inválida o si está en movimiento. Al aceptar pasa a `IDLE` y restituye los factores nominales; la pérdida de esfuerzo que invalida referencia impide usar esta orden hasta recargar el ensayo. No hace homing ni mueve a una posición inicial.

### `move_joints`: solicitar movimiento articular

```json
{"id":"mov-001","command":"move_joints","positions":[0,1.5707963267948966,-1.5707963267948966,0.05],"speed":0.3}
```

| Parámetro | Regla |
| --- | --- |
| `positions` | Cuatro números finitos `[q1,q2,q3,q4]`; booleanos no admitidos como números. Son destinos absolutos respecto de los ceros de simulación adoptados, no incrementos. |
| `speed` | Opcional; número entre 0.1 y 1.0. Predeterminado 0.5. Escala los límites usados para calcular la duración; no es velocidad en rad/s o m/s. |

Solo acepta en `IDLE`. Valida articulaciones, duración y recorrido nominal antes de crear la trayectoria. Rechaza una segunda orden de movimiento durante `MOVING`; no reemplaza el destino ni forma una cola de trayectorias.

Los límites provienen de [config/scara.json](../config/scara.json). En esta revisión: J1/J2 ±135°, J3 ±150° y J4 entre 0 y 0.120 m; J4 positivo baja el soporte. Son convenciones y límites del banco, no ceros/topes físicos certificados. La comprobación cubre entorno y herramienta/carga frente a base fija, con las aproximaciones de [Colisiones](COLISIONES_Y_RECORRIDOS.md).

El controlador interpola las articulaciones con un perfil quíntico común. La velocidad solicitada cambia la duración, no convierte el camino del extremo en una recta. Al terminar devuelve:

```json
{"event":"completed","id":"mov-001","message":"Finalizaron las consignas; comprobar llegada en instrumentacion"}
```

**`completed` significa fin del perfil, no llegada física ni sostén estable.** No se decide por un umbral de error de los sensores. La llegada se comprueba por instrumentación separada y tolerancias de ensayo. Si la trayectoria se cancela, no se genera su finalización normal después de la cancelación.

### `stop`: cancelar la trayectoria

```json
{"id":"stop-001","command":"stop"}
```

Sin parámetros. Cancela el perfil y conserva una referencia fija. Queda `STOPPED` si no hay fallas y `FAULT` si las hay. No modifica los factores de esfuerzo ni recupera referencia. La siguiente trayectoria requiere `rearm` y una orden nueva.

### `status`: consultar modo y solicitar actualización de estado

```json
{"id":"consulta-001","command":"status"}
```

Sin parámetros. Devuelve `accepted` con el modo; el puente también fuerza una próxima publicación de estado. Los datos completos llegan como evento `state` independiente, sin ese `id`. No hay un RPC de instantánea completa correlacionada por el identificador de esta solicitud.

## 7. Órdenes del banco de ensayos

Estas operaciones ayudan a estudiar el modelo. No se proponen automáticamente como comandos operativos de un robot físico.

### `fault`: inyectar una falla

```json
{"id":"falla-001","command":"fault","kind":"effort_loss","axis":4,"factor":0}
```

| Parámetro | Regla |
| --- | --- |
| `kind` | `effort_loss` o `hall_stuck`. |
| `axis` | Entero entre 1 y 4; los booleanos no son ejes válidos. |
| `factor` | Opcional, predeterminado 0. Para esfuerzo: número de 0 a 1. Para Hall: valor numérico 0 o 1. |

`effort_loss` multiplica el esfuerzo nominal disponible del eje: 0 lo anula y 0.5 lo reduce al 50%. Un factor menor que 1 invalida la referencia. La reducción queda retenida por eje mediante el mínimo de lo aplicado: enviar después un factor mayor no restaura fuerza. El mapa `faults` conserva la última solicitud por tipo/eje, pero `effort_available` refleja el límite retenido.

`hall_stuck` fija la señal Hall entregada como inactiva/activa. No cambia la pose física ni implementa un sensor real. La inyección por sí sola no invalida la referencia en esta implementación.

Ambas registran la falla y cancelan la trayectoria. El banco conoce la inyección; no demuestra diagnóstico autónomo del robot. Incluso `effort_loss` con factor 1 registra una falla y detiene, aunque no reduzca el esfuerzo.

### `clear_faults`: quitar avisos de falla

```json
{"id":"limpiar-001","command":"clear_faults"}
```

Rechaza durante `MOVING`. Vacía `faults` y queda `STOPPED`; no inicia movimiento. No restituye los factores de esfuerzo retenidos ni convierte en válida una referencia perdida.

Tras Hall fijo, si no se perdió referencia por otra causa, puede limpiarse y luego rearmarse. Tras pérdida de esfuerzo o sobrecarga, el banco requiere `reset_trial` antes de recuperar movimiento.

### `payload`: configurar carga conocida

```json
{"id":"carga-001","command":"payload","mass":0.25}
```

`mass` es un número finito entre 0 y 2 kg, adicional a la masa permanente del conjunto deslizante. Rechaza durante movimiento. Si la referencia es inválida, no permite cambiar la carga; enviar el mismo valor no la recupera.

Antes de cambiar masa comprueba la ocupación nominal de la carga cuando la referencia es válida. Al aceptar, el puente actualiza masa, centro e inercia equivalentes del conjunto mediante campos del PROTO; el efecto físico requiere los pasos correspondientes de Webots. No añade una pieza visual de carga ni una nueva caja de contacto para ella.

Si `(masa permanente deslizante + mass) × 9.81` supera el esfuerzo nominal configurado de J4, registra `overload:J4`, invalida referencia y cancela la trayectoria. La solicitud puede responder **`accepted` con modo `FAULT`**: se aceptó aplicar esa masa y se reconoció una sobrecarga. No reduce artificialmente el esfuerzo nominal para producirla. El aviso se basa en carga conocida por el ensayo, no en un sensor de peso.

### `reset_trial`: recargar condición inicial

```json
{"id":"reinicio-001","command":"reset_trial"}
```

El puente cancela movimiento, intenta enviar `accepted` con un texto de recarga y llama a `worldReload()`. Esta respuesta no incluye necesariamente `mode`, y el código no garantiza que el acuse llegue antes de cerrarse la conexión.

La recarga reinicia el controlador y cambia `trial_id`. El cliente debe reconectar y comprobar la nueva identidad, `STOPPED`, carga cero y referencia inicial válida antes de habilitar. No basta observar un reloj pequeño. No hace homing ni una reparación física.

Esta orden aplica la validación común de `id` descrita en la sección 4; un identificador inválido se rechaza sin recargar el mundo.

## 8. Telemetría: evento `state`

La estructura exterior es `{"event":"state","state":{...}}`. Esta línea es una descripción de estructura: los puntos suspensivos no son JSON transmisible. El contenido completo se compone de los campos siguientes:

| Campo en `state` | Tipo / unidades / significado |
| --- | --- |
| `time` | Segundos simulados. Puede volver a cero al recargar. |
| `trial_id` | UUID textual nuevo al iniciar el controlador; identifica el ensayo. |
| `mode` | Uno de los cuatro modos de la sección 5. |
| `commanded`, `estimated`, `simulated` | Tres listas de cuatro números `[rad,rad,rad,m]`. Consigna, referencia ideal y lectura física simulada. |
| `estimated_pose`, `simulated_pose` | Listas `[x,y,z,yaw]`, en `[m,m,m,rad]`, calculadas por cinemática directa. La segunda usa las articulaciones simuladas. |
| `hall`, `hall_nominal`, `end_hall` | Listas de cuatro booleanos. Inicio entregado, inicio nominal y región nominal del extremo final. `hall_stuck` modifica `hall`, no `end_hall`. |
| `faults` | Objeto de fallas por clave, por ejemplo `effort_loss:J4` u `overload:J4`; vacío si no hay avisos. |
| `payload_mass` | Carga adicional en kg. |
| `reference_valid` | Booleano; referencia aceptada por el banco para permitir rearme. |
| `effort_available` | Cuatro límites efectivos `[N·m,N·m,N·m,N]`. |
| `effort_feedback` | Cuatro lecturas aproximadas de esfuerzo. J1 es `null` con la base fija actual; otras lecturas no finitas se publican como `null`. |
| `effort_feedback_note` | Texto explicativo sobre las limitaciones anteriores. |
| `tcp_world` | Posición mundial `[x,y,z]` en m del punto de herramienta observado por Supervisor; `null` si no está disponible. Aquí TCP significa Tool Center Point. |
| `tcp_world_yaw` | Rumbo mundial en rad, observado desde la orientación del nodo; `null` si no está disponible. |
| `tool_physics` | Objeto con `mass` en kg, `center` local de tres componentes en m e `inertia` central de seis componentes en kg·m²; `null` si no está disponible. Orden: `[Ixx,Iyy,Izz,Ixy,Ixz,Iyz]`. |
| `model_status`, `protocol` | Textos de alcance del modelo y nombre `scara-dev/1`. |

No confundir TCP de red (Transmission Control Protocol) con TCP de herramienta (Tool Center Point).

El estado se publica aproximadamente cada 0.128 s simulados y se fuerza una actualización después de las órdenes comunes. La cadencia real depende del paso y de esas solicitudes; no es una frecuencia de red de tiempo real garantizada. Si las posiciones de sensor no son finitas se omite esa publicación.

Los Hall nominales se generan provisionalmente cerca de los límites articulares: tolerancia 0.01 rad para giros y 0.0005 m para J4. No representan todavía ubicación/polaridad de imanes y sensores confirmados. `estimated` sigue el perfil ideal, sin modelo de pasos perdidos. Las observaciones del simulador son instrumentación y no encoders del diseño físico.

## 9. Instrumentación adicional de Webots

Son solicitudes TCP admitidas por el puente, aunque no se ofrecen como órdenes comunes de la interfaz web. Usan la validación de `id` de `status` antes de responder. No se usan para cerrar el control con la posición perfecta del simulador.

| Orden y parámetros | Respuestas después de `accepted` |
| --- | --- |
| `inspect_cad`, sin parámetros | Un `cad_snapshot` por cuerpo y un `cad_snapshot_complete`. Cada instantánea lleva el mismo `id`, tiempo, grupo, articulaciones simuladas, posición/orientación del cuerpo, masa y poses de sus piezas. Rechaza si manifiesto y nodos no coinciden. |
| `inspect_contacts`, sin parámetros | `contact_snapshot` con `id`, tiempo, total de contactos, ID del nodo herramienta, cajas por cuerpo y hasta 16 contactos con punto e ID del nodo. `total_contacts` puede superar el detalle enviado. |
| `inspect_j4_window`, `seconds` opcional | Acepta duración entre 0.1 y 5 s simulados; predeterminado 2. Solo una ventana activa. Después envía `j4_window`, agregando lectura de J4 en cada paso físico. |

`cad_snapshot` usa rotaciones de nueve componentes, matrices 3×3 por filas. `parts` contiene `name`, `position` y `orientation` de cada instancia. La finalización de la consulta CAD es independiente de la finalización de movimientos.

`j4_window` conserva `id`, `trial_id`, `start_time`, `end_time`, `duration_s`, `target_m`, `samples`, `minimum_m`, `maximum_m`, `max_error_m`, `command_changed`, `basic_time_step_ms` e `invalid_samples`. El tiempo real de ventana se discretiza a pasos. Para interpretar estabilidad, revisar lecturas inválidas y cambios de consigna, no solo mínimos/máximos. La ventana no ordena movimiento ni decide llegada.

## 10. Desconexión, tiempos y orden de operaciones

Al reconocer EOF o error del socket, el servidor descarta buffers y el puente solicita detención. El cliente de referencia también descarta órdenes pendientes al perder sesión; reconecta con reintentos de aproximadamente 1 s de pared, sin reenviar esas órdenes ni rearmar automáticamente.

No hay heartbeat, timeout de inactividad de aplicación ni plazo máximo de detección de una interrupción silenciosa. No se promete detectar inmediatamente un cable cortado sin un cierre/error reconocido.

La física y los perfiles usan tiempo simulado; los intentos de conexión usan tiempo de pared. Pausar Webots pausa la atención de solicitudes. Las operaciones del servidor son no bloqueantes; no espera indefinidamente un mensaje para permitir el siguiente paso físico.

Los mensajes de una conexión se procesan en el orden recuperado del flujo; no hay transacciones ni ejecución atómica de un lote. `accepted` y `completed` se refieren a fases diferentes. Tras una desconexión, primero consultar el nuevo estado y luego decidir una nueva orden; el identificador no implementa recuperación de transacciones.

## 11. Conversaciones de ejemplo

Secuencia nominal, con telemetría intercalable. Las flechas y anotaciones explican la dirección y no se transmiten:

```text
Cliente → controlador: {"id":"habilitar-1","command":"rearm"}
Controlador → cliente: {"event":"accepted","id":"habilitar-1","mode":"IDLE"}
Cliente → controlador: {"id":"mover-1","command":"move_joints","positions":[0,1.5707963267948966,-1.5707963267948966,0.05],"speed":0.3}
Controlador → cliente: {"event":"accepted","id":"mover-1","mode":"MOVING"}
Controlador → cliente: {"event":"completed","id":"mover-1","message":"Finalizaron las consignas; comprobar llegada en instrumentacion"}
```

El ejemplo parte de una recarga limpia, sin fallas ni carga, y movimiento habilitado. La llegada debe comprobarse aparte; la conversación no declara una precisión de hardware.

Secuencia de pérdida de esfuerzo en J4:

```text
Cliente → controlador: {"id":"f1","command":"fault","kind":"effort_loss","axis":4,"factor":0}
Controlador → cliente: {"event":"accepted","id":"f1","mode":"FAULT"}
Cliente → controlador: {"id":"f2","command":"clear_faults"}
Controlador → cliente: {"event":"accepted","id":"f2","mode":"STOPPED"}
Cliente → controlador: {"id":"f3","command":"rearm"}
Controlador → cliente: {"event":"rejected","id":"f3","message":"Referencia no confirmada tras perder esfuerzo: reiniciar ensayo. No hay encoders reales"}
```

Se recarga mediante `reset_trial` y se comprueba el nuevo ensayo antes de habilitar. La desaparición del aviso en `faults` no acredita recuperación de fuerza ni referencia.

## 12. Decisiones propuestas para revisión docente

Confirmar o modificar:

1. Roles cliente/servidor, dirección/puertos, codificación y delimitador.
2. Órdenes articulares o cartesianas y dónde se resuelve la inversa; unidades, ceros, sentidos y punto de herramienta.
3. Significado de aceptación y fin: conservar fin de consignas o agregar llegada verificada con criterio, tolerancia y plazo explícitos.
4. Política ante órdenes durante movimiento, stop, desconexión, reintentos e identificadores repetidos.
5. Estado/referencia inicial, homing y recuperación después de perder esfuerzo o sobrecarga.
6. Qué operaciones de ensayo/instrumentación deben exponerse y cuáles quedar privadas del banco.
7. Necesidad de negociación de versión, códigos de error y vivacidad de conexión.

Son preguntas de revisión, no cambios ya implementados. Los mensajes oficiales que se acuerden deberán incorporarse al intérprete y a sus pruebas. La [validación](VALIDACION_WEBOTS.md) distingue software, escenarios nativos y límites del modelo.

## Anexo A. Interfaz HTTP del programa externo

Es otra interfaz, entre navegador y Python; no reemplaza el contrato TCP al controlador.

| Ruta | Función |
| --- | --- |
| `GET /` | Entrega `client/index.html`. |
| `GET /api/state` | Entrega conexión, último estado recibido y últimas respuestas; incluye pose inicial de referencia. |
| `POST /api/connection` | JSON `{"connect":true}` o `{"connect":false}` para controlar la conexión TCP. No habilita movimiento. |
| `POST /api/command` | Recibe órdenes admitidas por la interfaz, valida y encola. Devuelve HTTP 202 con `event: queued` e identificador; no confirma aceptación del controlador. |

La interfaz acepta `stop`, `rearm`, `clear_faults`, `status`, `reset_trial`, `fault`, `payload` y `move_cartesian`. No acepta `move_joints` directo ni las órdenes `inspect_*` a través de este endpoint.

`move_cartesian` usa `x_mm`, `y_mm`, `z_mm`, `yaw_deg` y `speed`. Orientación omitida o `null` conserva rumbo cuando es admisible; `speed` es fracción 0.1–1, aunque el formulario muestre porcentaje. Python convierte unidades, resuelve inversa y comprueba recorrido antes de enviar `move_joints` por TCP. `move_cartesian` no es una orden TCP admitida por el controlador actual.

Los POST requieren `application/json` y cuerpo de 1 a 16384 bytes. Una validación fallida devuelve HTTP 400, falta de conexión 409, tipo de contenido incorrecto 415 y origen externo rechazado 403. El cliente puede rechazar antes de encolar o el controlador puede rechazar después. No confundir HTTP 202 con evento TCP `accepted`.

La cola del cliente tiene 64 entradas. `stop` y `reset_trial` descartan entradas aún pendientes del cliente; no retiran bytes ya enviados ni aportan una prioridad especial dentro de TCP. La interfaz conserva hasta 20 respuestas no periódicas y solo el último `state`: no es un historial completo de ensayos.

## Anexo B. API de Webots y archivos del modelo

La API es una biblioteca que usa nuestro controlador; no es el protocolo TCP. Llamadas usadas en `scara_bridge.py`:

| Grupo | Llamadas y uso |
| --- | --- |
| Inicio y tiempo | `Supervisor()`, `getBasicTimeStep()`, `step(timestep)`, `getTime()`: crear acceso al robot y sincronizar el bucle con tiempo simulado. |
| Dispositivos | `getDevice(name)`: obtener `j1_motor`–`j4_motor` y `j1_sensor`–`j4_sensor`. |
| Consignas y límites | `setPosition()`, `setVelocity()`, `setAcceleration()`: objetivo, límite de velocidad en el modo de posición usado y aceleración del motor. |
| Esfuerzo disponible | `setAvailableTorque()` en J1–J3 y `setAvailableForce()` en J4: acotar esfuerzo; no equivalen a ordenar un torque/fuerza exacto. |
| Lecturas | `enable()`, `getValue()`, `enableTorqueFeedback()`, `getTorqueFeedback()`, `enableForceFeedback()`, `getForceFeedback()`: habilitar y leer instrumentación. J1 no habilita feedback de torque con la base fija actual. |
| Nodos de escena | `getFromDef()`, `getFromProtoDef()`, `getField()`, `getBaseNodeField()`, `getSFNode()`: localizar robot, cuerpos, poses y campos. |
| Inspección | `getPosition()`, `getOrientation()`, `getContactPoints()`, `getId()`, `getCount()`: poses, contactos e identificación/conteo. |
| Propiedades de carga | `getSFFloat()`, `getMFVec3f()`, `setSFFloat()`, `setMFVec3f()`: consultar y modificar masa/centro/inercia expuestos en la instancia del PROTO. |
| Recarga | `worldReload()`: reiniciar el ensayo completo. |

No usamos `setTorque()`/`setForce()` como control directo de esfuerzo: mantenemos control por posición y limitamos el esfuerzo disponible. Los sensores y Supervisor verifican ensayos, sin convertirlos en encoders del robot diseñado.

[SCARA.proto](../webots/protos/SCARA.proto) define un tipo reutilizable de robot: jerarquía de cuerpos, tres juntas de giro y una prismática, motores/sensores, mallas/apariencias, cajas de contacto, física y campos configurables. Declara el controlador predeterminado `scara_bridge` y habilita Supervisor. La extensión `.proto` aquí significa prototipo Webots; no contiene el protocolo de mensajes.

[scara.wbt](../webots/worlds/scara.wbt) define el mundo que se abre: importa el PROTO, configura paso de 2 ms, cámara, luces, fondo, piso/pedestal e instancia `DEF SCARA SCARA { }`. El PROTO describe el robot; el mundo lo coloca en una escena. Ambos se generan mediante `tools/generate_world.py`; no contienen la lógica Python del controlador ni las formas STL completas, que se referencian por ruta.

## Fuentes de esta especificación

Implementación contrastada: [transporte](../scara/transport.py), [reglas de estado](../scara/runtime.py), [puente Webots](../webots/controllers/scara_bridge/scara_bridge.py), [cliente](../client/app.py), [cinemática](../scara/kinematics.py) y [configuración](../config/scara.json). Pruebas relacionadas: [transporte](../tests/test_transport.py), [estados](../tests/test_runtime.py) y [cliente](../client/test_app.py).

Referencias primarias de la API, revisión R2025a: [Motor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/motor.md), [Robot](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/robot.md), [PositionSensor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/positionsensor.md) y [Supervisor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/supervisor.md). Describen la API; la versión ejecutada y la evidencia del proyecto se registran por separado en [Validación](VALIDACION_WEBOTS.md).
