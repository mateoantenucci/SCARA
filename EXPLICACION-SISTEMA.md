# SCARA — Cómo está hecho el sistema

Guía de defensa: arquitectura, protocolo TCP scara-dev/1, movimiento de cada pieza y archivos involucrados.

Banco de simulación en Webots. Una orden viaja: navegador → HTTP → cliente Python → TCP → controlador Webots → motores/física. Este documento explica cada etapa, qué archivo la implementa y qué métodos clave contiene.

## 1. Las dos conexiones (no confundir)

```text
NAVEGADOR ──HTTP :8765──► client/app.py ──TCP :9000──► scara_bridge.py ──API──► WEBOTS
 (index.html)              puente + validación           controlador + Server     física
```

| Conexión | Quién inicia | Puerto | Qué viaja |
| --- | --- | --- | --- |
| Navegador ↔ client/app.py | navegador | 8765 | HTTP: JSON REST, la página HTML, sondeo de estado |
| client/app.py ↔ scara_bridge.py | cliente Python (app.py) | 9000 | TCP crudo: una orden JSON por línea, protocolo scara-dev/1 |

La consigna pide una aplicación externa conectada al controlador por mensajes de texto sobre TCP/IP. El navegador nunca habla TCP: app.py es el puente HTTP↔TCP y scara_bridge.py es el puente TCP↔API de Webots.

## 2. La cadena mecánica — cómo se mueve cada pieza

```text
                    Z (arriba)
                    ↑
    ┌────────────────────────────┐
    │  TORRE / BASE (fija)       │  grupo "base" — nunca se mueve
    └─────────────┬──────────────┘
                  │  J1 · ROTACIONAL · ±135° (±2,356 rad)
                  │  gira el BRAZO respecto de la torre
                  ▼
    ┌────────────────────────────┐
L1  │  BRAZO (arm)               │  250 mm hasta J2 · masa prov. 0,3 kg
0,25└─────────────┬──────────────┘
                  │  J2 · ROTACIONAL · ±135°
                  │  gira el ANTEBRAZO respecto del brazo
                  ▼
    ┌────────────────────────────┐
L2  │  ANTEBRAZO (forearm)       │  250 mm hasta J3 · masa prov. 0,5 kg
0,25└─────────────┬──────────────┘
                  │  J3 · ROTACIONAL · ±150° (±2,618 rad)
                  │  gira el CONJUNTO VERTICAL (muñeca)
                  ▼
    ┌────────────────────────────┐
    │  MUÑECA (wrist)            │  cuerpo del pistón · 0,35 kg
    │  ║ J4 · PRISMÁTICA         │  carrera 0–0,12 m · +J4 = BAJA
    │  ║ (corredera vertical)    │
    └─────────────┬──────────────┘
                  ▼
    ┌────────────────────────────┐
    │  PISTÓN + TOOL (tool)      │  0,15 kg + carga de ensayo 0–2 kg
    │  TCP = punta de herramienta│  pose inicial ≈ (250; 250; 34,67) mm
    └────────────────────────────┘
```

### Regla de arrastre (pregunta clásica)

- J1 mueve brazo + antebrazo + muñeca + tool (arrastra todo lo que cuelga de él).

- J2 mueve antebrazo + muñeca + tool.

- J3 mueve muñeca + tool: cambia el rumbo (orientación) del extremo, no su X,Y.

- J4 mueve solo el pistón/tool en Z: sube y baja. +J4 baja, +Z sube.

### Cadena de marcos y cinemática directa

frames.chain_frames(q) construye las matrices 4×4 de los 5 cuerpos:

```text
base → (+shoulder_z, q1) → arm → (+L1, q2) → forearm → (+L2, q3) → wrist
     → (+tool_z_offset − q4) → tool   (= marco del TCP)
x     = L1·cos(q1) + L2·cos(q1 + q2)
y     = L1·sen(q1) + L2·sen(q1 + q2)
rumbo = q1 + q2 + q3
z     = shoulder_z + elbow_z_offset + tool_z_offset − q4
```

q2 es relativo al brazo, por eso el segundo tramo usa q1+q2. Geometría: l1 = l2 = 0,25 m; shoulder_z ≈ 0,291 m; elbow_z_offset ≈ −0,078 m; tool_z_offset ≈ −0,119 m.

## 3. El recorrido de una orden — etapa por etapa

```text
ETAPA 1 · PANTALLA                     archivo: client/index.html
─────────────────────────────────────────────────────────────────
Campos X,Y,Z (mm), orientación (°), velocidad 10–100 %, botones
Habilitar / Detener / Conectar / fallas / carga.
  GET  /api/state        (sondeo periódico de estado)
  POST /api/command      POST /api/connection
                    │ HTTP 127.0.0.1:8765
                    ▼
ETAPA 2 · HTTP + VALIDACIÓN            archivo: client/app.py
─────────────────────────────────────────────────────────────────
handler_for(bridge) → Handler(BaseHTTPRequestHandler)
  do_GET : "/" → index.html · "/api/state" → bridge.snapshot()
  do_POST: solo loopback + Origin propio + application/json + ≤16 KiB
           "/api/command" → bridge.command(request) → 202 encolada
finite_json(raw)   → JSON estricto: rechaza NaN / Infinity
number(value,name) → número finito, no booleano
Bridge.command(request):                       ← ACÁ PASA LO IMPORTANTE
  move_cartesian: mm→m, °→rad
       → inverse(x,y,z,yaw)              [kinematics]
       → validate_joints()               [límites]
       → CollisionChecker.validate_path  [colisiones]
       → reescribe la orden como "move_joints" + positions[4] + speed
  también valida fault (eje 1–4, factor 0–1) y payload (0–2 kg)
  asigna id = uuid4() → encola frame JSON+"\n" en pending (cola 64)
                    │ TCP 127.0.0.1:9000 · JSON por línea · scara-dev/1
                    ▼
ETAPA 3 · TRANSPORTE TCP               archivo: scara/transport.py
─────────────────────────────────────────────────────────────────
class Server — servidor NO bloqueante (vive dentro del lazo de física)
  __init__ : socket + SO_REUSEADDR + listen(1) + setblocking(False)
             buffers: received (entrada) / outgoing (salida) / lost
  poll()   : accept() si no hay cliente → recv(4096)×8 → acumula
             corta frames por "\n" (≤16 KiB) → json.loads estricto
             send() vacía outgoing → devuelve lista de mensajes
  send()   : json.dumps + "\n" → outgoing (si >256 KiB → disconnect)
  disconnect(): cierra cliente, lost=True, limpia ambos buffers
                    │ (mismo socket, otro extremo — cliente TCP)
                    ▼
Bridge._run() en client/app.py — hilo "scara-tcp"
  conecta (timeout 0,3 s) → envía frames pendientes de SU generación
  recv(4096) → corta por "\n" → _receive(frame):
     evento "state" → guarda telemetría · otros → cola responses(20)
  si se cae: generation += 1 → pendientes viejos se descartan:
             NADA se reenvía solo tras reconectar
                    │
                    ▼
ETAPA 4 · CONTROLADOR WEBOTS           archivo: webots/controllers/
                                         scara_bridge/scara_bridge.py
─────────────────────────────────────────────────────────────────
main(): Supervisor() → lazo while robot.step(timestep) != -1
Por cada paso de física (timestep = 2 ms):
 1) runtime.advance(now)    → interpola consigna; emite "completed"
 2) server.poll()           → recoge órdenes; si lost → runtime.stop()
 3) runtime.handle(request) → aplica orden → send(accepted/rejected)
 4) motor.setPosition(commanded[i]) + setVelocity + setAcceleration
    + setAvailableTorque/Force(max_effort × factor)  ← entran las fallas
 5) cada ~0,128 s → send({"event":"state", state:{...}})
    commanded · estimated · simulated (sensores) · poses por forward()
    hall · faults · payload_mass · tcp_world (posición real del tool)
Comandos extra de instrumentación (solo lectura, nunca realimentan):
  inspect_j4_window · inspect_contacts · inspect_cad
  reset_trial → robot.worldReload()   (recarga el mundo; NO es homing)
  payload cambiado → box_with_payload() → campos toolMass del PROTO
                    │
                    ▼
ETAPA 5 · LÓGICA DEL BANCO             archivo: scara/runtime.py
─────────────────────────────────────────────────────────────────
class Runtime — Python puro, NO conoce Webots ni TCP → testeable
  handle(request, now):  despacha comandos → accepted / rejected
    move_joints: solo en IDLE → motion=(start,target,t0,dur,id) MOVING
    stop · rearm · clear_faults · fault · payload · status
  advance(now): commanded = interpolate(...)  [perfil quíntico]
                estimated = commanded  (referencia ideal, sin encoder)
                al terminar → motion=None → IDLE + evento "completed"
  stop():       commanded = estimated (consigna fija; no es un freno)
  effort_factors(): factores por falla effort_loss (bajan el torque)
  hall_output():    pisa la lectura Hall si hay falla hall_stuck
                    │
                    ▼
ETAPA 6 · MATEMÁTICA                   archivos: scara/kinematics.py
                                        frames.py · dynamics.py
                                        collisions.py
─────────────────────────────────────────────────────────────────
kinematics.forward(q)             → [x,y,z,yaw] del TCP
kinematics.inverse(x,y,z,yaw)     → codo ±acos, ±vueltas, conserva
                                    rumbo; elige candidato más cercano
kinematics.validate_joints(q)     → 4 valores dentro de limits[]
kinematics.trajectory_duration()  → duración sin violar vel/acel máx
kinematics.interpolate()          → s(u)=10u³−15u⁴+6u⁵ (arranque/fin
                                    suaves, vel y acel nulas en extremos)
frames.chain_frames(q)            → matrices 4×4 de los 5 cuerpos
dynamics.box_with_payload()       → masa+centro+inercia de tool + cubo
                                    de ensayo de 40 mm
collisions.CollisionChecker
  __init__ : cajas de piezas CAD + obstáculos con margen de 1 mm
  validate_path(start,target,payload): subdivide el intervalo s∈[0,1]
    hasta cota de 0,25 mm; si no prueba separación → RECHAZA recorrido
                    │
                    ▼
ETAPA 7 · FÍSICA                       archivos: webots/worlds/scara.wbt
                                        webots/protos/SCARA.proto
─────────────────────────────────────────────────────────────────
Webots integra la dinámica: los motores reciben setPosition() con
vel/acel/esfuerzo limitados; j*_sensor devuelven la posición real;
feedback de torque/fuerza en J2–J4. Gravedad, contactos y topes los
calcula el motor de física — no nuestro código.
```

## 4. El protocolo scara-dev/1

Contrato provisional de desarrollo (pendiente del protocolo del profesor). Cada mensaje es un objeto JSON terminado en \n. Toda orden lleva un id (UUID) que la respuesta repite para correlacionarla.

| Dirección | Mensaje | Función |
| --- | --- | --- |
| cliente → controlador | move_joints + positions[4], speed | Mover a una configuración articular (rad, m) |
| cliente → controlador | stop · rearm · clear_faults | Frenar / habilitar / quitar fallas |
| cliente → controlador | fault + kind, axis, factor | Inyectar effort_loss o hall_stuck |
| cliente → controlador | payload + mass | Carga de ensayo 0–2 kg |
| cliente → controlador | status · reset_trial · inspect_* | Consulta / recarga / instrumentación |
| controlador → cliente | accepted / rejected + id | Respuesta correlacionada a cada orden |
| controlador → cliente | state | Telemetría periódica (~7,8 Hz): comandado, estimado, simulado, hall, fallas… |
| controlador → cliente | completed + id | Terminaron las consignas (NO certifica llegada física) |

## 5. Máquina de estados (dentro de la etapa 5)

```text
          rearm              move_joints          termina consignas
STOPPED ────────► IDLE ────────────────────► MOVING ─────────────► IDLE
   ▲               │  ◄──────── stop ──────────│
   │               │                           │
   │          clear_faults             fault / desconexión
   └───────────────┴───────── FAULT ◄──────────┘
```

- effort_loss baja drive_factors y pone reference_valid=False: la posición estimada ya no es confiable → hay que reset_trial (recarga el mundo; no es homing).

- payload que supera el esfuerzo de J4 → falla "overload" y stop.

- hall_stuck congela la salida Hall elegida en 0 o 1 (señal de ensayo).

- Toda entrada inválida → evento "rejected" sin cambiar el estado.

## 6. Defensas del TCP (el "por qué" que pregunta el profesor)

- Framing TCP es un flujo de bytes sin fronteras de mensaje: un mensaje puede llegar partido o varios pegados. Solución: delimitador \n y buffer acumulativo (received).

- Límites 16 KiB por frame y 256 KiB de salida. Un cliente roto no puede llenar memoria ni colgar el lazo.

- JSON estricto: se rechazan NaN e Infinity en ambos sentidos (allow_nan=False al enviar; parse_constant/parse_float al recibir). Un NaN corrompería la física en silencio.

- Un cliente solo un cliente a la vez (listen(1)); al cerrar, recv()=0 u OSError → lost=True → runtime.stop() cancela la trayectoria. Reconectar no repite nada.

- No bloqueante el Server es no bloqueante porque corre dentro del lazo de física de Webots: bloquear = congelar la simulación.

- Generación el cliente guarda pendientes en una cola de 64; cada reconexión incrementa generation y descarta lo viejo → ninguna orden fantasma se ejecuta tras una caída.

- Red solo loopback (127.0.0.1) en ambos extremos; POST con Origin externo → 403.

## 7. Datos duros para citar

- Geometría l1 = l2 = 0,25 m; shoulder_z ≈ 0,291 m; elbow_z_offset ≈ −0,078 m; tool_z_offset ≈ −0,119 m.

- Límites J1/J2 ±135° (±2,356 rad) · J3 ±150° (±2,618 rad) · J4 0–120 mm, positivo hacia abajo.

- Unidades interfaz mm/° → internamente SI (m, rad).

- Tiempos frame ≤ 16 KiB · salida ≤ 256 KiB · estado cada ~0,128 s · timestep físico 2 ms.

- Inicio posición inicial (0; 90°; −90°; 0,06) → TCP ≈ (250; 250; 34,67) mm.

- Velocidad velocidad relativa de consigna: 10–100 % (0,1–1,0).

## 8. Preguntas probables del profesor

**¿Por qué TCP y no UDP?** Las órdenes no pueden perderse ni llegar desordenadas; TCP lo garantiza y el estado es un stream continuo.

**¿Cómo separan mensajes si TCP es un stream?** Delimitador \n, buffer acumulativo, máximo 16 KiB por frame.

**¿Por qué JSON y no binario?** La consigna pide mensajes de texto; es legible, depurable con nc y autodescriptivo.

**¿Qué pasa si se corta la conexión?** El servidor lo detecta (recv vacío / error) → stop() cancela la trayectoria. Al reconectar no se repite nada; hay que habilitar de nuevo.

**¿Dónde se calcula la cinemática inversa?** En el cliente, antes de enviar. Al controlador le llegan posiciones articulares ya validadas (límites + colisiones).

**¿Por qué un hilo en el cliente?** Para que el socket TCP no compita con los handlers HTTP; se comunican por una cola acotada y una generación que invalida órdenes viejas.

**¿Por qué no bloqueante en Webots?** Corre dentro del lazo de física; bloquear congelaría la simulación.

**¿Qué significa completed?** Que terminaron las consignas interpoladas, no que el robot llegó. La llegada se verifica comparando simulated contra tolerancias.

**¿Por qué hay ordenado / estimado / simulador?** Ordenado = consigna al motor; estimado = referencia ideal (no hay encoders); simulador = lo que Webots calculó físicamente.

**¿Qué pasa si pierde esfuerzo un motor?** effort_loss baja el torque disponible e invalida la referencia; hay que reiniciar el ensayo. J4 puede caer por gravedad.

## 9. Archivos → responsabilidad → métodos clave

| Archivo | Qué es | Métodos / piezas clave |
| --- | --- | --- |
| client/index.html | Pantalla del operador | Campos destino, botones, fetch a /api/* |
| client/app.py | Puente HTTP↔TCP + validación | finite_json · number · Bridge.command (inversa + colisiones) · Bridge._run (hilo socket) · _receive · snapshot · handler_for |
| scara/transport.py | Servidor TCP no bloqueante, JSON por línea | Server.__init__ · poll (accept/recv/split \n/send) · send · disconnect |
| webots/controllers/scara_bridge/scara_bridge.py | Controlador Webots: TCP ↔ motores/sensores | main (lazo step) · advance → poll → handle → setPosition → state cada 0,128 s · inspect_* · reset_trial |
| scara/runtime.py | Máquina de estados del banco (sin Webots) | Runtime.handle (comandos) · advance (interpolación) · stop · effort_factors · hall_output |
| scara/kinematics.py | Cinemática R-R-R-P en SI | forward · inverse · validate_joints · trajectory_duration · interpolate (quíntico) |
| scara/frames.py | Matrices 4×4 de los 5 cuerpos | multiply · transform_point · rigid_inverse · z_pose · chain_frames |
| scara/collisions.py | Rechazo conservador de recorridos | piece_boxes · CollisionChecker.validate_path (subdivisión de intervalos) · first_conflict |
| scara/dynamics.py | Propiedades de cajas equivalentes | box_with_payload (masa, centro, inercia de tool+carga) |
| config/scara.json | Fuente de verdad del modelo | geometry · limits · max_velocity/acceleration/effort · body_properties · environment · collision_check |
| webots/worlds/scara.wbt + protos/SCARA.proto | Mundo y robot generados | Motores j*_motor, sensores j*_sensor, boundingObject, Physics, campos toolMass |

Recordatorio honesto para la defensa: el protocolo scara-dev/1, las masas, los esfuerzos, los ceros y los sensores Hall son provisionales de banco; no hay hardware físico contra el que esté calibrado el modelo.
