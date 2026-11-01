# Registro de decisiones: grabar y reproducir trayectorias

Por qué el SCARA quedó diseñado así. Sirve para responder al profesor. Cada entrada dice qué se decidió, por qué y qué se descartó. Las decisiones difíciles de revertir tienen además un ADR en [`docs/adr/`](adr/). El análisis completo está en la [investigación del 29/10/2026](historico/INVESTIGACION_TEACH_AND_PLAY_2026-10-29.md). El [documento maestro v2](maestro/SCARA-Master-v2.md) lo resume: cada decisión con su porqué en una línea (sección 11).

Estados:

- **Aceptada:** el grupo la decidió.
- **Propuesta al profesor:** la implementamos y se revisa en clase.
- **Abierta:** falta decidir.

## Origen

Clase del 27/10/2026. El profesor pidió hacer algo similar a AGSABOT:

- Mover articulaciones a mano, guardar puntos y reproducir trayectorias.
- Seguir rectas o el menor recorrido.
- Modelar la cadena cinemática híbrida.
- Proponer un protocolo propio.
- Usar TCP, con Webots como cliente, y socat en el robot real.
- Hacer homing con sensores Hall.
- Tomar los SolidWorks como fuente de verdad.
- Simular los motores lo más real posible.

## Alcance

**D0 · Qué entra en la entrega.**
- **Decisión:** grabar y reproducir trayectorias, homing y fallas, sobre la simulación existente. AGSABOT es referencia de la idea; no se copia su implementación.
- **Por qué:** es lo que pidió el profesor. Leímos el código de AGSABOT y tiene carencias que no queremos heredar: reproduce a ciegas cada 1200 ms, el stop puede no enviarse y no tiene homing.
- **Estado:** Aceptada.

## Arquitectura y comunicación

**D1 · La URC es servidor TCP y la UCI se conecta.**
- **Decisión:** la URC escucha y Webots, socat o un Arduino con Ethernet se conectan a ella.
- **Por qué:**
  - Lo pidió el profesor.
  - Con el robot real, socat abre el USB y es quien se conecta.
  - La URC queda siempre esperando, y el robot puede reiniciarse o desconectarse sin tocarla.
- **Descartado:** Webots como servidor, que es como funcionaba `scara-dev/1`.
- **Estado:** Aceptada.

**D2 · Canal de instrumentación aparte.**
- **Decisión:** el protocolo solo lleva lo que un Arduino podría saber. La verdad del simulador, las fallas, la carga y la recarga van por otro puerto. Ese canal vive en el mismo controlador de Webots.
- **Por qué:** así la URC no puede depender sin querer de información que el robot real no da.
- **Descartado:** mezclar todo en un mensaje, como `scara-dev/1`; o un segundo robot supervisor en Python, que obligaría a pasar las fallas entre dos procesos.
- **Estado:** Aceptada. [ADR 0004](adr/0004-canal-de-instrumentacion-separado.md).

**D3 · Un único firmware en C++ para Arduino y Webots.**
- **Decisión:** el mismo código corre en el Arduino y dentro del controlador de Webots; solo cambia la capa de hardware.
- **Por qué:** el profesor quiere que el día del robot real no haya que desarrollar nada nuevo.
- **Descartado:** un emulador en Python, porque obligaría a escribir el firmware real desde cero más adelante.
- **Estado:** Aceptada. [ADR 0002](adr/0002-firmware-compartido-robot-real-y-simulacion.md).

**D4 · Formato de mensajes.**
- **Decisión:** una línea por mensaje terminada en LF (se ignora CR), de hasta 64 bytes, con campos separados por espacios y solo enteros.
- **Por qué:** es fácil de procesar en un Arduino con 2 KB de RAM, se lee y escribe a mano con `nc` o el monitor serie, y funciona con el `println` de Arduino.
- **Descartado:** JSON (demasiado pesado para un UNO) y el `;` de AGSABOT (no aporta nada).
- **Estado:** Aceptada.

**D5 · El protocolo habla en unidades articulares.**
- **Decisión:** centésimas de grado para J1–J3 y centésimas de mm para J4. El firmware convierte a pasos y resuelve el acople M1/M2.
- **Por qué:** la mecánica (poleas, microstepping, acople) queda encapsulada en el robot. Cambiar un driver no toca la URC, y la telemetría se puede leer.
- **Descartado:** pasos crudos (la URC tendría que conocer la mecánica) y números con decimales (lentos en un Arduino AVR).
- **Estado:** Aceptada. [ADR 0003](adr/0003-protocolo-en-unidades-articulares.md).

**D6 · La URC planifica y el firmware ejecuta.**
- **Decisión:** la URC resuelve la inversa, las rectas y el perfil de velocidad, y manda segmentos cortos con duración. El firmware los encola y ejecuta con su reloj; responde `OK` cuando hay lugar en la cola.
- **Por qué:** el UNO no puede calcular la inversa a la frecuencia que exige una recta. Ejecutar con el reloj del firmware evita que las demoras de red se conviertan en tirones. Es la división de GRBL y Klipper.
- **Descartado:** cinemática en el firmware, o posiciones en tiempo real sin cola.
- **Estado:** Aceptada. [ADR 0005](adr/0005-la-urc-planifica-el-firmware-ejecuta.md).

**D7 · Nombres.**
- **Decisión:** UCI (Unidad de Control Incorporada) y URC (Unidad Remota de Coordinación), como en AGSABOT. No usamos PPM porque no hay panel físico.
- **Por qué:** es el vocabulario que la cátedra ya conoce.
- **Estado:** Aceptada. Ver el [glosario](../GLOSSARY.md).

**D27 · Números iniciales del protocolo.**
- **Decisión:**

  | Parámetro | Valor |
  | --- | --- |
  | Estado | 20 por segundo |
  | PING | cada 250 ms |
  | Watchdog | 1 s sin mensajes ⇒ frena |
  | Segmentos | de 20 ms |
  | Cola del firmware | 16 segmentos |
  | Línea | hasta 64 bytes |
  | Serie | 115200 baudios |

- **Por qué:** los valores caben con holgura en un UNO y en 115200 baudios. La especificación puede ajustarlos.
- **Estado:** Aceptada.

**D26 · La simulación corre en tiempo real durante teach y play.**
- **Decisión:** el firmware dentro de Webots usa el reloj simulado. Durante teach y play, Webots corre a 1×; si la PC no llega, el robot va más lento sin romperse. El modo rápido queda para ensayos sin URC.
- **Por qué:** con tiempo simulado más rápido que el real, el watchdog saltaría porque los PING llegan a ritmo real, y "respetar los tiempos" perdería sentido.
- **Estado:** Aceptada.

**D24 · Puertos y nombre del protocolo.**
- **Decisión:** puerto 9000 para `scara/1` y 9001 para instrumentación, ambos configurables. El firmware informa la versión al arrancar (`BOOT`) y al saludar (`HI`).
- **Estado:** Aceptada.

## Mecánica, electrónica y motores

**D20 · Cuatro motores paso a paso: 2 NEMA 23 (M1, M2, en la base) + 2 NEMA 17 (M3 en el antebrazo, M4 en la columna Z).**
- **Por qué:** coinciden el profesor, el maestro y los planos. El ensamble `0-EnsambleBase` guarda un nombre `NEMA23-2`, pero solo `NEMA23-1` y `NEMA23-3` tienen ubicación y aparecen en los planos: es una instancia suprimida o residual.
- **Estado:** Aceptada.

**D18 · Arduino UNO, conectado por USB + socat.**
- **Decisión:** placa del maestro; un sensor Hall por articulación.
- **Por qué:** con un Hall por eje, el UNO usa 15 de 20 pines por USB. Con shield Ethernet llegaría a 20 de 20, sin margen. El protocolo sirve igual para Ethernet.
- **Descartado:** dos sensores por eje con entradas propias, porque no entran.
- **Estado:** Aceptada.

**D9 · Microstepping 1/8 (1600 pulsos/vuelta).**
- **Decisión:** se configura con las llaves DIP de cada TB6600 y con una constante del firmware.
- **Por qué:** con los 400 pulsos del maestro, un paso de J1 mueve el extremo ~2 mm con el brazo estirado y las rectas se verían escalonadas. Con 1/8 baja a ~0,5 mm y el UNO sigue alcanzando la frecuencia de pulsos con velocidades acotadas.
- **Descartado:** 400 (resolución gruesa) y 1/16 o más (exige más pulsos de los que conviene pedirle al UNO).
- **Estado:** Propuesta al profesor.

**D8 · Modelo de motores N1 + N2.**
- **Decisión:**
  - N1: pasos, transmisión y acople.
  - N2: par limitado según la velocidad, con pérdida de pasos.
- **Por qué:** muestra lo que distingue a un robot con motores paso a paso de uno ideal, incluida una falla realista que el firmware no advierte.
- **Descartado:** N3, el modelo eléctrico completo. Faltan datos de los motores y exigiría pasos de simulación mucho más chicos.
- **Estado:** Aceptada. [ADR 0006](adr/0006-modelo-de-motores-pasos-y-perdida-de-pasos.md).

## Referencia y homing

**D10 · Sensores Hall: uno por articulación, con dos imanes (inicio y fin).**
- **Decisión:** J2 se mide relativo, en el codo. Las referencias de homing están en el extremo negativo de J1 y J2 (el mismo signo), en cualquier extremo de J3 y arriba en J4. En Webots, el imán es un emisor de radio de alcance corto y el KY-003 es un receptor.
- **Por qué:**
  - El maestro prevé inicio y fin en los cuatro ejes, pero no dice dónde. El KY-003 del CAD no está colocado.
  - Los topes que importan son los relativos.
  - Con un solo sensor por eje entra en el UNO.
  - En Webots, la activación sale de la geometría del modelo, no de leer la posición perfecta.
- **Descartado:**
  - Medir J2 desde la base: no protege los topes relativos.
  - `TouchSensor`: genera choques físicos.
  - Calcular el Hall con la posición del simulador: es lo que hacía `scara-dev/1`, y es trampa.
- **Estado:** Propuesta al profesor.

**D11 · Secuencia de homing.**
- **Decisión:**
  1. J4 sube.
  2. J1, moviendo M1 y M2 juntos.
  3. J2 con M2 solo.
  4. J3.

  En cada eje: rápido hasta el Hall, retroceso y aproximación lenta, siempre desde el mismo lado. La búsqueda está acotada en pasos y tiempo. El homing arranca desde la pose de reposo (D30) y termina volviendo a ella. Webots arranca cerca del reposo, con un desvío aleatorio de ±10°, y sin referencia.
- **Por qué:**
  - Subir J4 aleja la herramienta de la mesa.
  - Mover M1 y M2 juntos mantiene fijo J2 mientras se busca J1.
  - Aproximar lento y desde el mismo lado da repetibilidad.
  - Sin referencia no se pueden verificar choques: con el codo muy plegado, el soporte Z puede tocar la torre.
  - Con el chequeo de colisiones del repo, el recorrido completo desde el reposo queda libre. Si J2 buscara en +135° con J1 en −135°, chocaría con la torre: por eso los dos extremos de referencia tienen el mismo signo. Vale con límites provisionales y envolventes simplificadas.
- **Estado:** Aceptada. Los extremos y signos son parte de la propuesta de Hall al profesor (D10).

**D30 · Pose de reposo: brazo estirado.**
- **Decisión:**
  - Pose: J1 = 0°, J2 = 0°, J3 = 0° y J4 abajo (sin corriente cae solo).
  - Se deja ahí al apagar, con el botón «Estacionar», y desde ahí arranca el homing.
  - Antes del homing, la URC muestra un dibujo de la pose y pide confirmarla. Si el robot no está ahí, se lo lleva con jog articular lento.
  - La referencia manual también usa esta pose, con marcas visuales; se documenta como menos precisa que el homing.
- **Por qué:** el profesor sugirió una pose completamente contraída o estirada. Con el chequeo de colisiones, contraída (J2 = ±135°) toca la torre incluso quieta. Estirada queda libre y J1 puede barrer hasta los dos extremos.
- **Descartado:** contraída; o una "zona segura" sin pose definida, que es difícil de verificar a ojo.
- **Estado:** Aceptada.

**D31 · Preferencia de configuración del codo.**
- **Decisión:**
  - Al salir del brazo estirado, el codo dobla hacia el lado preferido: J2 negativo por defecto, configurable.
  - La interfaz muestra siempre la configuración del codo.
  - El jog cartesiano nunca cambia de configuración; para cambiarla se usa un tramo PTP o jog articular.
- **Por qué:** estirado (J2 = 0) es una singularidad. Desde ahí la cinemática inversa tiene dos soluciones equivalentes y hay que elegir una de forma predecible.
- **Estado:** Aceptada.

**D21 · Qué se permite sin referencia.**
- **Decisión:**
  - Antes del homing, solo jog articular lento; capturar y reproducir quedan bloqueados.
  - El Hall de fin de carrera detiene el eje igual.
  - Se capturan siempre posiciones estimadas por pasos.
  - El homing se lanza con un botón de la URC; la referencia manual, con otro botón que pide confirmación.
- **Por qué:** sin referencia, la posición es desconocida. El robot real solo conoce sus pasos.
- **Detalle:** la columna «Simulado» se conserva en el panel del banco de ensayo (canal de instrumentación) para ver el efecto de las fallas. Con el robot real ese panel no existe.
- **Estado:** Aceptada.

## Operación: jog, trayectorias y reproducción

**D12 · Jog con el teclado de la URC, estilo videojuego.**
- **Decisión:** dos modos con las mismas teclas.
  - Cartesiano: W/S y A/D mueven en el plano, R/F suben y bajan, Q/E giran.
  - Articular: J1–J4.
  - Tab cambia de modo; Mayús es lento; Espacio captura; Retroceso borra; Enter termina; Esc frena.
- **Por qué:** funciona igual con el robot real, que no tendrá botonera. Permite jog cartesiano y la lista de puntos queda a la vista.
- **Descartado:** teclas en la ventana de Webots. Solo existirían en simulación y solo darían jog articular.
- **Estado:** Aceptada. [ADR 0007](adr/0007-jog-desde-la-urc.md).

**D13 · Las trayectorias las guarda la URC.**
- **Decisión:** se guardan como JSON con versión de formato. Cada punto registra la pose (articulaciones, que incluyen la configuración del codo), no el camino por el que se llegó.
- **Por qué:** igual que en AGSABOT, el robot solo informa la posición y la PC administra los datos. El camino se calcula al reproducir, así que no hace falta "mover bien" con las teclas.
- **Estado:** Aceptada.

**D14 · Tramos LIN o PTP.**
- **Decisión:** LIN (recta) por defecto y PTP (articular sincronizado) como opción. Si una recta es imposible (fuera de alcance, cambio de codo, límites, choque), se rechaza antes de arrancar y se ofrece PTP.
- **Por qué:** el profesor pidió recta o menor recorrido. Arrancar y frenar a mitad de camino deja al robot en un lugar no planeado.
- **Estado:** Aceptada.

**D28 · Jog verificado una vez referenciado.**
- **Decisión:** con el robot referenciado, la URC planifica los dos modos de jog en segmentos cortos, verificados contra límites y colisiones. La cola se mantiene en 2–3 segmentos para que el robot frene apenas se suelta la tecla. Sin referencia, el firmware hace jog articular lento, protegido solo por los Hall.
- **Por qué:** el jog no debe poder llevar el robot contra la torre. Sin referencia, la URC no sabe dónde está el robot y no puede verificar nada.
- **Estado:** Aceptada.

**D29 · Funciones del gestor de trayectorias.**
- **Decisión:**
  - **Lista de puntos:** XYZ y rumbo, tipo, velocidad y espera; los parámetros se editan por tramo.
  - **Edición:** reordenar, borrar, sobrescribir con la pose actual; capturar inserta después del punto seleccionado.
  - **Ir al punto:** PTP con confirmación previa.
  - **Reproducir:** play desde el principio o desde el seleccionado, loop y velocidad global.
  - **Pausa:** frena; al reanudar, la URC recalcula desde la pose actual hasta el final del tramo.
  - **Stop:** frena y descarta lo pendiente.
  - **Durante la reproducción:** se resalta el tramo en ejecución.
  - **Archivo:** aviso de cambios sin guardar; guardar, guardar como, cargar y nueva.
  - **Validación:** se valida la trayectoria completa antes de cada play.
- **Por qué:** es lo útil de AGSABOT, más lo que le faltaba: stop real, pausa, progreso y validación previa.
- **Estado:** Aceptada.

**D32 · Tramo de aproximación y vuelta del loop.**
- **Decisión:**
  - Reproducir exige robot referenciado.
  - Al apretar play, la URC calcula un tramo PTP desde la pose actual hasta el punto 1, lo verifica como los demás y lo muestra como «tramo 0». No se guarda en el archivo.
  - Los parámetros del punto 1 (cómo se llega a él) se usan para la vuelta del loop, del último punto al primero, que sí puede ser LIN.
- **Por qué:**
  - El punto de partida no está grabado: es donde esté el robot al apretar play. Esa pose se conoce gracias al homing, pero puede ser cualquiera, incluso con el codo del otro lado. Desde ahí una recta podría ser imposible; un PTP entre dos poses alcanzables siempre se puede hacer.
  - Como en los robots industriales, el primer movimiento de un programa es articular.
- **Estado:** Aceptada.

**D33 · Parámetros del tramo de aproximación.**
- **Decisión:**
  - PTP, al 25 % de la velocidad máxima multiplicado por la velocidad global; el 25 % es configurable en la URC.
  - Espera de 0 s.
  - Se omite si el robot ya está a menos de un paso por articulación del punto 1, según la posición estimada.
  - La interfaz muestra su duración estimada.
- **Por qué:** es el único movimiento que arranca desde una pose no grabada. Ir despacio da tiempo a frenar con Esc, como hacen los robots industriales en el primer movimiento de un programa.
- **Estado:** Aceptada.

**D34 · Puntos definidos sin jog.**
- **Decisión:**
  - Se puede agregar un punto escribiendo XYZ y rumbo, o J1–J4. En XYZ el codo toma la configuración preferida, con opción de elegir la otra.
  - Se pueden editar puntos capturados; al editar en XYZ se conserva la configuración del codo del punto.
  - La URC valida al agregar, al editar y al cargar un archivo: versión del formato, alcance, límites y choque en reposo. Si algo falla, informa qué punto y por qué.
  - El JSON se puede editar a mano, pero no se promociona.
- **Por qué:** con jog es difícil clavar un valor exacto. Combinar el jog "a ojo" con la edición permite trayectorias precisas. Un punto escrito nunca fue visitado, así que se valida. Igual el robot llega al paso más cercano: ~0,5 mm en el peor caso.
- **Estado:** Aceptada.

**D22 · Parámetros de cada tramo.**
- **Decisión:**
  - Por defecto: LIN, 50 % de la velocidad máxima y espera de 0 s; se editan en el gestor.
  - Velocidad global de reproducción de 10 % a 100 %.
- **Por qué:** como en los robots industriales, primero se enseñan posiciones y después se ajustan velocidades. La velocidad global permite probar despacio.
- **Estado:** Aceptada.

## Interfaz

**D15 · Interfaz web local servida por la URC.**
- **Por qué:** ya existe, no agrega dependencias y la consigna admite «una página web».
- **Estado:** Aceptada.

## Fallas

**D23 · Catálogo de fallas.**
- **Decisión:** F6 solo si sobra tiempo.

  | Falla | Qué es |
  | --- | --- |
  | F1 | Pérdida de pasos por sobrecarga o aceleración, detectada al cruzar un Hall. |
  | F2 | Driver sin corriente. |
  | F3 | Hall trabado. |
  | F4 | Desconexión o URC que no responde (watchdog). |
  | F5 | Reinicio inesperado de la UCI. |
  | F6 | Correa que patina o se corta (opcional). |

- **Por qué:** son fallas que el robot real puede sufrir. La mayoría se detectan sin encoders, con Hall, tiempos y mensajes.
- **Estado:** Aceptada.

## Proceso y entrega

**D16 · Migración del código actual.**
- **Decisión:** se construye el camino nuevo al lado del viejo y se borra lo viejo cuando el nuevo funciona.
  - **Se conservan:** `kinematics.py` y `collisions.py`, como planificador.
  - **Se mudan al canal de instrumentación:** fallas, carga y recarga.
- **Por qué:** nunca quedarse sin algo que funcione.
- **Estado:** Aceptada.

**D25 · Documentación y evidencia del camino viejo.**
- **Decisión:** se sigue la convención existente de `validation/historico/`.
  - Los documentos que no dependen del control (CAD, montaje, colisiones, propiedades, transmisión) siguen vigentes, con sus referencias actualizadas.
  - Los del banco `scara-dev/1` pasan a `docs/historico/`, con la línea «Reemplazado por…»; su evidencia pasa a `validation/historico/`.
  - Se reescriben el README, la guía desde cero y el plan.
  - Se hace una campaña de validación nueva.
  - Nada se borra: se mueve con `git mv`, sin alterar bytes.
- **Por qué:** una sola descripción vigente del sistema. La historia queda como registro del proceso, pero no se cita como prueba del sistema nuevo.
- **Estado:** Aceptada. Es un ticket propio, posterior a que el camino nuevo funcione.

**D17 · Documento maestro v2.**
- **Decisión:** Markdown en el repo, exportado a PDF, sin tocar el original y con enlaces a los ADR.
- **Estado:** Aceptada.

**D19 · Compilación en Windows.**
- **Decisión:** se valida en la bala trazadora. Si no se logra, se documenta que solo se validó en Mac.
- **Estado:** Aceptada.
- **Resultado (30/10/2026):** compila y corre en Windows 11 con el `g++` 14.2 que trae Webots R2025a en su MSYS2, sin instalar nada más. Hay que usar el `bash` de Webots con `mingw64/bin/cpp` en el PATH, donde Webots guarda las DLL de C++. Detalle en [UCI en Webots](UCI_WEBOTS.md#resultado-en-windows-d19). macOS queda pendiente de verificar.

## Bala trazadora (issue #5)

Decisiones tomadas al construir el primer camino completo. El protocolo completo (issue #6) puede revisarlas.

**D35 · Forma de los mensajes de la bala trazadora.**
- **Decisión:**
  - `BOOT` y `HI` llevan el protocolo y la versión de firmware como entero: `HI scara/1 1`.
  - `S` tiene nueve campos fijos: `S modo ref J1 J2 J3 J4 hall libres último`. El modo es una palabra (`IDLE`, `JOG`; `OFF` desde D40); el resto, enteros.
  - `ERR` lleva un código entero y una palabra: 1 `comando`, 2 `argumentos`, 3 `largo`, 4 `watchdog`, 5 `ocupado`.
  - `JOG j ± vel` usa centésimas por segundo, de 1 a 1000 (10 °/s o 10 mm/s). `JOG`, `ZERO` y `PING` no tienen respuesta: el efecto se ve en el próximo `S`.
- **Por qué:** una palabra para el modo se lee a simple vista con `nc` o el monitor serie y cuesta lo mismo en un UNO. Un código numérico en `ERR` deja que la URC decida sin comparar textos. Responder a cada `JOG` duplicaría el tráfico sin informar nada que `S` no diga.
- **Descartado:** modo como número (ilegible a mano) y textos de error con espacios (complican el parser).
- **Estado:** Aceptada. Ver [`scara/1`](PROTOCOLO_SCARA_1.md).

**D36 · En Webots, el firmware arranca con la primera conexión.**
- **Decisión:** el controlador espera a conectarse con la URC para arrancar el firmware, que entonces envía `BOOT`. Si después la conexión se corta y vuelve, el firmware no se reinicia: la URC saluda con `HELLO` y se entera del estado por `HI` y `S`.
- **Por qué:** imita al UNO por USB, que se reinicia cuando socat abre el puerto. Si el firmware arrancara antes de la conexión, el `BOOT` se perdería. Reiniciarlo en cada reconexión haría perder una referencia válida por un corte de red.
- **Descartado:** guardar las líneas mientras no hay conexión (el UNO no tiene memoria para eso).
- **Estado:** Aceptada.

**D37 · Tres frenos para el jog.**
- **Decisión:**
  - La página renueva el pedido de jog cada 150 ms mientras se mantiene la tecla y frena al soltarla, al perder el foco o al ocultarse.
  - La URC envía `JOG` una sola vez y envía `JOG STOP` si la página no renueva el pedido en 500 ms.
  - El firmware frena si pasa más de 1 s sin mensajes de la URC; la URC envía `PING` cada 250 ms. `PING` y el watchdog entran ya en la bala trazadora.
- **Por qué:** cada frente puede caerse por separado: el navegador (pestaña cerrada con la tecla apretada), la URC o el enlace. Sin el watchdog, cortar la URC en pleno jog deja al robot girando hasta el tope; en el ensayo, J1 se detuvo solo.
- **Estado:** Aceptada.

**D38 · Mundo nuevo al lado del viejo, arrancando en la pose de reposo.**
- **Decisión:** `scara_uci.wbt` usa el mismo `SCARA.proto` con el controlador `scara_uci`; `scara.wbt` no se toca. La planta lleva las articulaciones a la pose de reposo al arrancar (supervisor) y desde ahí suma lo que dan los motores. J4 abajo es 120 mm.
- **Por qué:** el banco viejo tiene que seguir funcionando (D16). Arrancar en reposo hace que `ZERO` sea verdad en la simulación; el desvío aleatorio de ±10° llega con el homing (D11, issue #8).
- **Estado:** Aceptada.

**D39 · Pruebas del firmware como conversaciones.**
- **Decisión:** las pruebas del firmware son archivos de texto con lo que envía la URC, lo que tiene que responder la UCI, avances del reloj y pasos esperados por motor. Un programa C++ las corre contra el núcleo real con una capa de hardware falsa, y `python -m unittest discover` lo compila y lo ejecuta (se omite si no hay compilador). El núcleo se compila sin excepciones ni RTTI y la prueba verifica que no use memoria dinámica.
- **Por qué:** es el seam 1 de la spec: se prueba el comportamiento por el protocolo, no detalles internos. Los mismos archivos servirán para la UCI falsa de Python (seam 2). Integrarlas a `unittest` evita una segunda herramienta (`cmake` no está en todas las máquinas).
- **Estado:** Aceptada.

## Protocolo completo (issue #6)

Decisiones tomadas al completar `scara/1`. La especificación está en [`PROTOCOLO_SCARA_1.md`](PROTOCOLO_SCARA_1.md).

**D40 · La UCI arranca sin corriente; `DISABLE` pierde la referencia.**
- **Decisión:**
  - Al arrancar, el firmware deja los drivers sin corriente (modo `OFF` en `S`). Nada se mueve hasta que la URC envía `ENABLE`.
  - `DISABLE` frena, corta la corriente y borra la referencia.
  - Sin corriente, el jog y `ZERO` se rechazan con `ERR 6 deshabilitado`.
  - La página tiene los botones «Habilitar motores» y «Deshabilitar motores…», con confirmación.
- **Por qué:** sin corriente un paso a paso gira libre: J4 cae y cualquier eje se puede mover a mano sin que el firmware cuente pasos, así que la posición estimada deja de valer. Arrancar sin corriente es lo seguro si el Arduino se reinicia a mitad de un trabajo: no retoma nada solo. Declarar la referencia sin corriente sería declarar una pose que el robot no sostiene.
- **Descartado:** arrancar con corriente (el robot quedaría firme después de un reinicio inesperado, como si nada hubiera pasado) y conservar la referencia al deshabilitar.
- **Estado:** Aceptada.

**D41 · `STOP` conserva la referencia; `HALT` la pierde si había movimiento.**
- **Decisión:**
  - `STOP` frena y conserva la referencia. Con los segmentos (#9), frena con rampa y vacía la cola.
  - `HALT` para en seco y descarta todo. Si había movimiento, borra la referencia.
  - Los dos dejan los drivers con corriente: J4 no cae. El watchdog frena como `STOP`.
  - <kbd>Esc</kbd> y «Stop» envían `STOP`; «Parada inmediata» envía `HALT`.
- **Por qué:** es la división de GRBL entre *feed hold* (frena con rampa y conserva la posición) y *reset* (para ya; si había movimiento, pide homing de nuevo). Parar en seco a velocidad alta puede perder pasos (ADR 0006), y el firmware no se entera. Quieto no hay pasos que perder, así que `HALT` conserva la referencia.
- **Descartado:** `HALT` que corta la corriente (dejaría caer J4, que es justamente la falla F2) y `HALT` que siempre pierde la referencia, aun quieto.
- **Estado:** Aceptada.

**D42 · Conformidad simétrica con las mismas conversaciones.**
- **Decisión:**
  - Las conversaciones de `firmware/test/conversaciones` se corren contra el firmware (D39) y contra la URC: una UCI falsa en Python se conecta por TCP a la sesión real, le envía las líneas de la UCI y comprueba que la URC pueda enviar cada orden.
  - La URC revisa la forma de cada orden antes de enviarla (`urc/protocol.py`). Lo que el firmware rechaza por su forma (`ERR 1`–`3`), la URC se niega a enviarlo con el mismo código.
  - Los códigos de `ERR` son estables: se agregan al final y no se renumeran. Bytes fuera de ASCII imprimible invalidan la línea (`ERR 1`).
  - Las conversaciones ganan `! reinicio` (la UCI se reinicia sin cortar el enlace) y `EN` en `=` (corriente de los drivers).
- **Por qué:** con un solo archivo por caso, los dos lados no pueden divergir sin que falle una prueba. Una prueba de mutación lo confirmó: si la URC acepta `JOG 1 + 0`, falla `errores.txt`; si no borra el estado ante `BOOT`, falla `reinicio.txt`.
- **Descartado:** pruebas separadas para cada lado (cada una podría entender el protocolo a su manera).
- **Estado:** Aceptada.

**D43 · Todo `BOOT` deja al robot sin referencia en la URC.**
- **Decisión:** al leer `BOOT`, la URC descarta el último estado (el robot queda «sin referencia» de inmediato, sin esperar al próximo `S`), las órdenes pendientes y el jog en curso. Si el `BOOT` llega a mitad de una conexión, después de que la UCI ya había hablado, avisa «BOOT inesperado… (F5)».
- **Por qué:** las órdenes pendientes eran para un firmware que ya no existe. Con USB, abrir el puerto reinicia el UNO, así que un `BOOT` al principio de la conexión es lo normal y no merece alarma; a mitad de una conexión indica un reinicio por falla (alimentación, watchdog del micro).
- **Estado:** Aceptada.

## Transmisión N1 (issue #7)

Decisiones tomadas al completar la transmisión N1 en el firmware y en la planta simulada. Cómo funciona y la evidencia: [Transmisión](TRANSMISION.md#transmisión-n1-en-el-firmware-y-en-la-planta).

**D44 · El microstepping es un solo parámetro, en `firmware/config.h`.**
- **Decisión:**
  - `SCARA_MICROSTEPS` (8 por defecto, D9) vive en `firmware/config.h`, junto con los pasos por vuelta de los motores. Lo incluyen el núcleo del firmware, la capa de hardware del Arduino UNO y la planta de Webots.
  - El firmware deriva de ahí, en tiempo de compilación, la fracción entera de pasos por unidad del protocolo (8/45 en J1–J3 y 2/1 en J4 con 1/8). La conversión y el acople están en `firmware/transmission.h`.
  - La mecánica (poleas 4:1, 60T–60T al codo, ACME de 8 mm) se escribe por separado en el firmware y en la planta: la planta es el robot y el firmware es lo que el robot cree.
  - Las pruebas compilan la conversión con los seis valores del TB6600 (1 a 32). Las conversaciones de conformidad están escritas para 1/8.
- **Por qué:** en el robot real, el microstepping es una llave DIP de los TB6600 que el firmware tiene que conocer. Si la planta tuviera su propio valor, cambiarlo en un solo lado haría que el robot simulado se moviera distinto de lo que el firmware cree, sin que falle ninguna prueba. La mecánica, en cambio, puede diferir a propósito para estudiar errores del modelo.
- **Descartado:** una constante en el controlador de Webots y otra en el firmware, como en la bala trazadora, y compartir también la mecánica.
- **Estado:** Aceptada. El valor 1/8 sigue siendo propuesta al profesor (D9).

**D45 · Límites de velocidad y aceleración por motor, derivados a las articulaciones por la transmisión.**
- **Decisión:**
  - Los límites se fijan por motor, en grados de su eje: M1 y M2 a 80 °/s y 136 °/s², M3 a 112 °/s y 204 °/s², M4 a 1350 °/s y 2700 °/s² (`firmware/config.h`).
  - Son un parámetro provisional, elegidos para que cada articulación quede dentro de los límites conservadores del modelo (J1 y J2 a 20 °/s, J3 a 28 °/s, J4 a 30 mm/s). Las curvas de par de N2 (#15) los reemplazan.
  - Los de las articulaciones se derivan con el acople: |ω_J1| ≤ ω_M1/4 y |ω_J1 + ω_J2| ≤ ω_M2/4. Mover J1 y J2 a la vez en el mismo sentido gasta el margen de M2.
  - El jog arranca y frena sin rampa, así que su velocidad máxima tiene que quedar dentro de la de cada motor. El firmware lo verifica al compilar.
- **Por qué:** la limitación física está en los motores, no en las articulaciones. Con el acople, J2 no tiene un límite propio: depende de cuánto se mueva J1. El planificador de la URC (#9, #10) necesita esa forma para validar los tramos PTP y LIN. Faltan los datos del fabricante («1000 rpm» sin carga, aceleraciones «??»): un valor provisional declarado es mejor que uno inventado como si fuera de placa.
- **Descartado:** límites por articulación independientes (ignoran que M2 sostiene J1 + J2) y «1000 rpm» del maestro (26,7 kHz por motor a 1/8: el UNO no los genera).
- **Estado:** Aceptada. Los valores los reemplaza D76; la forma (por motor, con el acople) sigue.

**D46 · Jog por motor como modo de prueba: `JOG Mm ± vel`.**
- **Decisión:**
  - `JOG M1 + 450` mueve solo el motor M1, sin compensar el acople. `m` va de 1 a 4. La velocidad usa las unidades de la articulación de ese motor (θM/4 en M1–M3, mm de J4 en M4), con el mismo rango que el jog articular. `JOG STOP`, `STOP` y `HALT` lo frenan igual.
  - La página lo ofrece con una casilla, «Modo de prueba: jog por motor». Las mismas teclas mueven M1–M4 en lugar de J1–J4.
- **Por qué:** muestra en la defensa lo que pidió el profesor: mover M1 gira el brazo, el antebrazo conserva su orientación, J2 cambia al revés que J1 y el rumbo de la herramienta queda igual. Una sola orden `JOG` con dos formas mantiene un solo camino en el firmware.
- **Descartado:** un comando aparte (`JOGM`) y medir la velocidad del motor en pasos por segundo (dependería del microstepping, y el protocolo no lo conoce, ADR 0003).
- **Estado:** Aceptada.

## Arduino UNO y socat (issue #16)

Decisiones tomadas al escribir la capa de hardware del UNO y ensayar el camino serie. El detalle está en [UCI en el Arduino UNO](ARDUINO_UNO.md).

**D47 · Pines del UNO compatibles con el shield Ethernet.**
- **Decisión:**
  - STEP de M1–M4 en D2, D3, D5 y D6 (PORTD); DIR en A0–A3 (PORTC); ENABLE común en D7; Hall de J1–J4 en D8, D9, A4 y A5.
  - Quedan libres D4 y D10–D13, los del shield Ethernet.
  - TB6600 con cátodo común: ENA+ en alto corta la corriente. Los KY-003 usan el pull-up interno; `LOW` es activo.
  - Un motor cableado al revés se corrige con `DIR_INVERT`, sin recablear.
- **Por qué:** con los STEP en un mismo puerto, la interrupción los escribe de una vez y los pulsos de M1 y M2 (J1) salen juntos. Los 13 pines entran en los 13 que no usa el shield, así que pasar a Ethernet (D18) no obliga a recablear.
- **Descartado:** repartir los pines sin mirar los puertos (los pulsos acoplados saldrían desfasados) y usar D10–D13 (cerraría la alternativa Ethernet).
- **Estado:** Aceptada.

**D48 · El núcleo cuenta los pasos y el Timer1 los convierte en pulsos.**
- **Decisión:**
  - `Hal::step` no saca el pulso: lo deja pendiente. La interrupción del Timer1, a 20 kHz, cambia DIR un tick antes del flanco y da un tick en alto y al menos uno en bajo: hasta 10 000 pasos/s por motor.
  - Con 255 pasos pendientes en un motor, `step` espera a que salgan. Nunca se descarta un paso contado.
  - El generador de pulsos es C++ sin dependencias de Arduino y se prueba en la PC.
  - Un `static_assert` en `hal_uno.h` comprueba al compilar que el tick alcance para la velocidad máxima de cada motor (D45) con el microstepping configurado (D44).
- **Por qué:** el ancho de pulso y el tiempo de preparación de DIR del TB6600 no dependen de cuánto tarde `poll()`, y la serie sigue atendida mientras salen los pasos. 20 kHz alcanza para J4 a 30 mm/s con 1/8 (6000 pasos/s); 10 kHz no. Descartar pasos haría que la posición estimada difiera de la real por culpa del firmware, y eso tiene que pasar solo con la pérdida de pasos que el firmware no advierte (ADR 0006).
- **Descartado:** pulsos con `digitalWrite` y `delayMicroseconds` dentro de `step` (frenan el lazo y el ancho depende de la carga) y mover la integración de la velocidad al timer (es lógica del núcleo, que tiene que ser la misma en Webots).
- **Estado:** Aceptada.

**D49 · Ensayo del camino serie: la UCI de PC hace de placa detrás de un PTY.**
- **Decisión:**
  - `firmware/pc/uci_serie` crea un puerto serie virtual (PTY) y espera; socat lo abre con la misma receta que el USB del UNO y se conecta a la URC.
  - Imita al UNO por USB: abrir el puerto reinicia el firmware (`BOOT`), y la línea que llega antes se pierde, como en el bootloader. Cerrarlo lo apaga.
  - En Windows se usa MSYS2 (socat y `g++` del mismo runtime). Al cerrarse el puerto, la UCI crea un PTY nuevo, porque en Cygwin un PTY cerrado no se reabre.
  - El UNO se compila con `arduino-cli` y el núcleo como biblioteca (`--library firmware`), sin copias.
- **Por qué:** así se prueba sin la placa justo lo que va a correr con ella: la receta de socat y la URC sin cambios. La prueba entra en `python -m unittest discover` y se omite si no hay socat.
- **Descartado:** que socat cree el PTY (`PTY,link=…`): en MSYS2 no espera a que lo abran (`wait-slave`) y se cierra con un error de E/S; además la receta dejaría de ser la del robot real. Un par de puertos COM virtuales (com0com): exige instalar un driver con permisos de administrador.
- **Estado:** Aceptada.

## Segmentos temporizados y tramo PTP (issue #9)

Decisiones tomadas al implementar la cola de segmentos del firmware y el planificador PTP de la URC. La forma de los mensajes está en [`PROTOCOLO_SCARA_1.md`](PROTOCOLO_SCARA_1.md#segmentos); cómo funciona y la evidencia, en la [validación de segmentos](../validation/segmentos/INFORME.md).

**D50 · Un `SEG` sin confirmar por vez; con la cola llena, el firmware retiene uno y demora su `OK`.**
- **Decisión:**
  - La cola tiene 16 lugares y el segmento en ejecución ocupa uno (`libres` en `S`). `OK n` sale cuando el segmento entró en la cola.
  - La URC envía un `SEG` y espera su `OK` para enviar el siguiente. Con la cola llena, el firmware guarda el segmento recibido aparte y envía su `OK` recién cuando termina el que se ejecuta. Un `SEG` más antes de ese `OK` es `ERR 9 cola`.
  - `SEG n ms q1 q2 q3 q4`: `n` de 1 a 999999999, que la URC no repite en la sesión; `ms` de 1 a 1000; `q` enteros de hasta ±99999. Cada segmento empieza cuando termina el anterior, en el reloj del firmware.
- **Por qué:** es el control de flujo de GRBL (*send-response*): simple de explicar y de probar, y la URC nunca puede desbordar la cola. Con 16 segmentos de 20 ms, la cola cubre 320 ms de demora del enlace sin que se note; por TCP local o 115200 baudios, una ida y vuelta tarda mucho menos que un segmento, así que la cola se mantiene llena. Guardar uno aparte permite que el `OK` se demore sin dejar de leer el enlace: `PING` y `STOP` siguen llegando. Hasta 1000 ms por segmento, la interpolación cabe en enteros de 32 bits aun con 1/32, y las esperas largas son varios segmentos.
- **Descartado:** contar caracteres pendientes como GRBL o créditos según `libres` (más rendimiento, que a 50 segmentos por segundo no hace falta, y un caso más para probar), y dejar de leer el enlace con la cola llena (el watchdog y `STOP` quedarían esperando).
- **Estado:** Aceptada.

**D51 · El firmware valida cada `SEG` contra la velocidad de los motores, en unidades articulares.**
- **Decisión:**
  - `SEG` exige corriente (`ERR 6`), los cuatro ejes referenciados (`ERR 7 referencia`) y ningún otro movimiento: con jog o frenando, `ERR 5`. Con segmentos en ejecución se rechazan `JOG` y `ZERO`.
  - El firmware calcula el recorrido de cada motor en el segmento con el acople (M2 sigue a J1 + J2) y lo compara con su velocidad de D45. Admite 2 centésimas de más: la URC redondea cada destino a la centésima y M2 suma dos articulaciones. Si no alcanza, `ERR 8 velocidad`.
  - No verifica aceleraciones, límites articulares ni choques: son del planificador (ADR 0005).
- **Por qué:** sin referencia, la URC no sabe dónde está el robot y ningún plan vale. La verificación de velocidad protege a los motores de un error de la URC (por ejemplo, unidades equivocadas) al costo de una cuenta por segmento. Medirla en unidades articulares, y no en pasos, la hace independiente del microstepping: el redondeo a pasos agregaría hasta un paso por segmento, el 14 % de M1 en 20 ms.
- **Descartado:** verificar en pasos con tolerancia de un paso (rechazaba planes válidos) y copiar al firmware los límites articulares (son provisionales y viven en `config/scara.json`).
- **Estado:** Aceptada.

**D52 · `STOP` frena con rampa en la dirección del segmento; todo `ERR` con segmentos frena igual.**
- **Decisión:**
  - `STOP` y el watchdog, con segmentos en ejecución: cada motor sigue en el sentido del segmento actual y baja su velocidad en línea recta hasta cero. Todos tardan lo mismo, lo que necesita el motor más exigido con su aceleración de D45, así el robot sigue en la misma dirección en articulaciones. La cola se vacía y la referencia se conserva. Mientras frena, `S` dice `RUN`.
  - `HALT` sigue parando en seco (D41). El jog sigue frenando en seco: a su velocidad baja no pierde pasos.
  - Con segmentos en ejecución, toda orden rechazada (`ERR`) frena con rampa. La URC, ante cualquier `ERR` con el tramo en marcha, deja de enviarlo y no envía `STOP`. Si `S` muestra el robot quieto antes del último segmento, con todo enviado, la URC también da el tramo por terminado: el firmware frenó por algo que no vio.
- **Por qué:** frenar de golpe desde 20 °/s pide una aceleración infinita y es justo lo que pierde pasos (ADR 0006). La velocidad del segmento actual ya está en la cola, así que el firmware frena sin cálculos de la URC; con 34 °/s² en J1, desde 20 °/s son 0,59 s y 5,9°. Si se rechaza un segmento a mitad de un tramo, lo encolado termina en un punto intermedio del plan, quizás a plena velocidad: frenar es lo seguro, y que los dos lados den el tramo por terminado evita un `STOP` duplicado.
- **Descartado:** rampa por motor con tiempos distintos (cada articulación frenaría en otro momento y el robot se desviaría del camino) y `STOP` automático de la URC ante un `ERR` (el firmware ya frena).
- **Estado:** Aceptada.

**D53 · Tramo PTP: un perfil trapezoidal común, limitado por articulaciones y motores.**
- **Decisión:**
  - Todas las articulaciones siguen el mismo perfil s(t), de 0 a 1: q(t) = inicio + s(t) · recorrido. Así empiezan, aceleran, frenan y llegan a la vez.
  - El perfil es trapezoidal, o triangular si no llega a la velocidad máxima. Sus máximos los fija la restricción más exigente entre las articulaciones del modelo (`config/scara.json`, que son también los `maxVelocity` de Webots) y los motores de D45 con el acople: M2 recorre J1 + J2.
  - La velocidad del tramo (porcentaje) reduce las velocidades máximas; la aceleración queda en su máximo.
  - El perfil se parte en segmentos de 20 ms; si la duración no es múltiplo de 20 ms, se estira hasta el siguiente, sin pasar ningún máximo. Las posiciones se redondean a la centésima y el último segmento es el destino exacto.
  - «Ir a una pose» acepta J1–J4 o X, Y, Z y rumbo (con el codo preferido, J2 negativo, D31, o el otro). Verifica límites articulares y choques en todo el camino, que en un PTP es la recta en articulaciones, muestra la duración y pide confirmación. El inicio puede estar fuera del recorrido (un jog lo llevó ahí): un PTP de vuelta se acepta, y el chequeo de choques arranca desde el punto más cercano dentro del recorrido.
- **Por qué:** es el PTP sincronizado de los robots industriales y la definición de tramo PTP del glosario. Limitar solo por motores dejaría a J2 a 40 °/s cuando J1 gira al revés, y Webots lo saturaría (D45). La URC conoce los límites de los motores en las unidades de cada articulación, no el microstepping (ADR 0003); una prueba verifica que coincidan con `firmware/config.h`. Bajar también la aceleración al reducir la velocidad alargaría las rampas sin hacer falta: la aceleración es lo que limita el par.
- **Descartado:** un perfil por articulación (cada una llegaría en otro momento), un perfil de quinto grado como el del banco viejo (más suave, pero llega a la aceleración máxima solo en un instante y alarga el tramo) y leer los límites del motor desde `config.h` en tiempo de ejecución.
- **Estado:** Aceptada.

## Tramo LIN y validación previa (issue #10)

Decisiones tomadas al implementar el tramo LIN y la validación de tramos en la URC: [`urc/planner.py`](../urc/planner.py) (`plan_lin`, `lin_tolerance`) y [`urc/validation.py`](../urc/validation.py) (`check_lin`, `check_ptp`, `check_tramo`). Pruebas en [`tests/test_lin.py`](../tests/test_lin.py).

**D54 · Tramo LIN: velocidad del punto de herramienta, perfil trapezoidal y tolerancia calculada.**
- **Decisión:**
  - El punto de herramienta recorre la recta entre los dos puntos y el rumbo (J1 + J2 + J3, sin envolver) va de uno al otro, con el mismo perfil trapezoidal s(t) de D53. En cada muestra de 20 ms la URC resuelve la cinemática inversa con la configuración del codo del tramo y mantiene J1 continuo.
  - La velocidad del tramo es una fracción de 30 mm/s sobre la recta y de 20 °/s de rumbo, con 60 mm/s² y 34 °/s² al 100 %. Son las de J4 y M1 (D45): una recta vertical o un giro en el lugar al 100 % nunca superan su articulación. A diferencia del PTP, la fracción baja también la aceleración: la rampa dura siempre 0,5 s.
  - Configuración del codo: la de los extremos. El brazo estirado (J2 = 0) admite las dos: toma la del otro extremo y, si los dos están estirados, la preferida (J2 negativo, D31). Se cuenta el signo exacto de J2: un J2 de +0,03° es el codo positivo.
  - **Tolerancia sobre la recta: 0,069 mm**, calculada por `lin_tolerance` con la geometría y los límites vigentes. Es lo más que se aparta de la recta el camino que ejecuta el firmware, interpolando lineal en articulaciones entre los destinos redondeados. Suma dos efectos:
    - Redondeo a la centésima: media centésima de grado en J1 y en J2, una entera en el antebrazo, media centésima de mm en J4. Da l1·e + l2·2e = 0,066 mm.
    - Cuerda: dentro de un segmento el extremo describe arcos. Con el brazo y el antebrazo girando Δ1 y Δφ, la flecha es a lo sumo (l1·Δ1² + l2·Δφ²)/8. Con M1 y M2 a 20 °/s, son 0,4° por segmento y 0,003 mm.
  - El plan informa el apartamiento medido (`deviation`), en cuatro puntos de cada segmento. En una recta típica al 50 % es de 0,02 mm.
- **Por qué:**
  - Así es el LIN de los robots industriales: el operador elige la velocidad del extremo y el robot la mantiene constante. Con la velocidad fija, una recta que pasa cerca del brazo estirado pide a J2 velocidades sin cota, y eso se puede rechazar con un motivo («velocidad excesiva») que se resuelve bajando la velocidad o con PTP.
  - Cerca del brazo estirado, la aceleración de J2 crece con la del punto de herramienta. Si la fracción no la bajara, bajar la velocidad no resolvería un rechazo por aceleración. Con la aceleración fija, una recta radial de 420 a 485 mm se rechazaba por la aceleración de J2 aun al 25 %. Así, se rechaza al 100 % por velocidad y pasa al 25 %.
  - La tolerancia es una cota y no un valor medido: vale para todo tramo que pasó la validación, porque esta acota Δ1 y Δφ.
  - **Qué no incluye:** el robot da pasos enteros. Con 1/8, medio paso de M1 y de M2 corre el extremo hasta 0,25 mm. La planta de Webots, además, va unas centésimas detrás de la posición estimada (D45). La URC no conoce el microstepping (ADR 0003): ese error es de la ejecución y se mide en el ensayo de Webots.
- **Descartado:**
  - Bajar la velocidad del tramo hasta que todas las articulaciones queden dentro de sus límites, como reduce ABB cerca de una singularidad. El tramo entero iría lento por un solo punto y nunca habría un rechazo por velocidad, pero la spec lo pide.
  - Una velocidad cartesiana más alta, por ejemplo 50 mm/s. Una recta vertical al 100 % superaría J4 y se rechazaría.
  - Una banda muerta alrededor de J2 = 0. Si el inicio está levemente del otro lado, la primera muestra salta de configuración y se rechaza igual por aceleración.
- **Estado:** Aceptada. La velocidad cartesiana es un parámetro provisional, como D45. D76 la separa de J4 (150 mm/s, con la componente vertical limitada por M4) y la tolerancia pasa a 0,127 mm.

**D55 · Validación previa: se verifica cada segmento que se va a enviar, y cada rechazo dice el tramo, el motivo y qué probar.**
- **Decisión:**
  - Antes de enviar nada, `check_lin` planifica el tramo y verifica, en este orden:
    1. Extremos dentro de su recorrido, y sin cambio de configuración del codo.
    2. Alcance: la recta queda en la corona que alcanza el brazo. Por dentro la limita J2: a ±135° el extremo no llega a menos de 191 mm del eje de J1. Por fuera no hace falta verificar: el círculo es convexo y los extremos son poses válidas.
    3. Límites articulares en cada segmento.
    4. Velocidad y aceleración de cada articulación y de cada motor, con el acople (M2 = J1 + J2), en cada segmento. Se usan las muestras sin redondear: el redondeo suma a lo sumo una centésima, dentro de lo que admite el firmware (D51).
    5. Choques: el chequeo de colisiones existente, en la recta en articulaciones de cada segmento, que es lo que ejecuta el firmware.
  - `check_ptp` verifica el destino y los choques del PTP como «Ir a una pose» (D53). `check_tramo` elige según el tipo; el gestor de trayectorias (#12) lo llama tramo por tramo.
  - Un rechazo es `Rejection`, subclase de `ValueError`. Lleva el número de tramo, el motivo (`alcance`, `codo`, `limite`, `velocidad`, `colision`) y un detalle con dónde ocurre (porcentaje del tramo, articulación o motor, valor pedido contra máximo; «brazo casi estirado» si |J2| < 30°). Un LIN sugiere PTP; por velocidad, primero bajar la velocidad.
  - Un LIN exige que el inicio esté dentro del recorrido. El PTP acepta un inicio levemente fuera (D53) y es la sugerencia.
- **Por qué:**
  - D14 exige que nunca arranque un tramo que no se puede terminar. Verificar los segmentos que se van a enviar, y no la recta ideal, cubre también el redondeo y las muestras.
  - El chequeo de colisiones acota el camino solo para una recta en articulaciones. Por eso se aplica a cada segmento y no al tramo entero.
  - Todo lo que el operador necesita para corregir está en el mensaje, como pide la historia 40 de la spec.
- **Costo:** unos 3 ms por segmento en el chequeo de colisiones, o 3 s para un LIN de 17 s. Si validar una trayectoria larga antes de cada play resulta lento, se pueden agrupar segmentos.
- **Descartado:**
  - Muestrear el camino en puntos sueltos: entre dos muestras podría haber un choque.
  - Verificar choques en la recta en articulaciones entre los extremos del tramo: no es el camino de un LIN.
- **Estado:** Aceptada.

## Sensores Hall y homing (issue #8)

Decisiones tomadas al implementar los Hall en la planta de Webots y el homing del firmware. La forma de `HOME` y `EV HOMED` está en [`PROTOCOLO_SCARA_1.md`](PROTOCOLO_SCARA_1.md#homing); la evidencia, en la [validación del homing](../validation/homing/INFORME.md).

**D56 · Homing por flanco, en cinco fases, y vuelta al reposo planificada por la URC.**
- **Decisión:**
  - Los imanes están centrados en los extremos del recorrido, con una zona activa de ±5° (±3 mm en J4). La referencia es el flanco del lado alcanzable: J1 y J2 en −130°, J3 en −145° y J4 a 3 mm de arriba (`HALL_EDGE` en `firmware/config.h`, parámetro provisional).
  - `HOME [j]` busca J4, J1 (M1 y M2 juntos), J2 (M2) y J3, o solo el eje `j`. En cada eje:
    1. Si el Hall está activo al empezar, sale del imán hacia la referencia, a 1 °/s (desde el reposo, J4 descansa sobre el de abajo). Si el eje tenía referencia y está en su flanco, retrocede directamente.
    2. Busca a 8 °/s (8 mm/s) hasta que el Hall se activa.
    3. Retrocede a 1 °/s hasta que se apaga, y 3° (3 mm) más a 8 °/s.
    4. Vuelve a 1 °/s (1 mm/s) al mismo flanco, que fija la referencia, y envía `EV HOMED j`.
  - La búsqueda está acotada en recorrido (todo el recorrido del eje y algo más) y en tiempo (60 s por eje). Si el Hall no aparece, `ERR 11 ausente`; si no se apaga dentro del ancho del imán más 1° (1 mm) de margen, `ERR 12 trabado`. Las fases que miden esa cota van lento: así no depende de la velocidad, ni del atraso con que Webots sigue a los pasos. Al abortar, y también con `STOP`, `HALT` o el watchdog, los ejes de ese `HOME` quedan sin referencia.
  - El firmware termina en los flancos. La vuelta a la pose de reposo es un tramo PTP de la URC al 50 %, con el chequeo de choques, que la URC envía sola al recibir los cuatro `EV HOMED`. «Estacionar» es el mismo tramo.
- **Por qué:**
  - El flanco al que se llega lento y siempre desde el mismo lado es repetible: no depende de la velocidad ni del lado de llegada. Centrar el imán en el extremo deja el flanco 5° antes del tope: el homing nunca empuja contra él.
  - Un solo sensor no distingue los dos imanes. Desde el reposo, el único Hall activo es el de J4, sobre su imán de fin; la referencia previa resuelve el caso de un segundo homing.
  - La vuelta al reposo mueve los cuatro ejes desde una pose plegada (J1 y J2 en −130°): planificarla en la URC, como cualquier PTP, verifica choques en todo el camino (ADR 0005) y no agrega un generador de trayectorias al UNO. Al 25 % tardaría 52 s, porque M2 recorre J1 + J2 = 260°.
- **Descartado:** referenciar con el centro del imán (exige recorrerlo entero, hasta el tope), que el firmware vuelva solo al reposo eje por eje (sin chequeo de choques y con más código en el UNO), y conservar las referencias de los ejes ya encontrados cuando el homing aborta (el operador no sabría qué quedó valiendo).
- **Estado:** Aceptada. Las posiciones de los imanes siguen siendo propuesta al profesor (D10). D72 cambia las velocidades de búsqueda, la vuelta al reposo y el arranque sobre un imán.

**D57 · En Webots, el Hall se activa por la distancia entre el imán y el sensor.**
- **Decisión:**
  - Cada KY-003 es un `Receiver` en la pieza fija y cada imán, un `Emitter` en la que se mueve, con su alcance en `range`. Los genera `tools/generate_world.py` en `SCARA.proto`.
  - La planta (`scara_uci.cpp`) activa el Hall cuando un imán de su articulación está a menos de su alcance, midiendo la distancia entre las posiciones de los dos nodos en el mundo. No lee la posición de las articulaciones.
  - `tests/test_hall.py` calcula los flancos desde la geometría del proto y verifica que coincidan con `HALL_EDGE` del firmware y con los imanes de la planta falsa de las conversaciones.
  - La simulación arranca con un desvío al azar de hasta ±10° en J1–J3 (`--desvio`, D11); los ensayos usan `--desvio 0`.
- **Por qué:** D10 preveía que el `Receiver` recibiera los paquetes del `Emitter`, pero Webots no entrega paquetes entre dispositivos de un mismo robot (verificado con un mundo de prueba: otro robot recibe y el propio no), y los imanes y los sensores son todos del SCARA. Medir la distancia entre los nodos es la misma regla que aplica el `Emitter` de radio y sigue saliendo de la geometría: si se mueve un imán en el modelo, el flanco se mueve.
- **Descartado:** un robot aparte para los imanes (no puede ir montado sobre los cuerpos del SCARA), un `DistanceSensor` apuntando a un imán sólido (le agrega volumen de choque al modelo) y calcular el Hall con la posición de las articulaciones (D10).
- **Estado:** Aceptada.

**D58 · Sin referencia, el firmware limita el jog y el Hall lo frena como fin de carrera.**
- **Decisión:**
  - Sin los cuatro ejes referenciados, el firmware baja todo `JOG` a 5 °/s (5 mm/s), aunque la URC pida más.
  - Con o sin referencia, un jog que activa el Hall de un eje que mueve frena en seco y avisa `ERR 10 fin`. En el jog por motor, M1 mueve J1 y J2 y frena con cualquiera de los dos.
  - Si el jog arranca sobre un imán, puede salir de él; si recorre más que el ancho del imán (5°, 3 mm en J4) y 1° (1 mm) de margen sin que se apague, iba hacia el tope y frena.
  - Mientras siga activo el Hall que frenó un jog, otro jog de los mismos motores en el mismo sentido no arranca (`ERR 10 fin`): solo se puede salir para el otro lado. Sin esto, cada toque de tecla avanzaría otro ancho de imán contra el tope.
- **Por qué:** es D21 llevado al firmware: sin referencia, nadie más protege el robot. El ancho del imán es justo lo que hay entre el flanco y el tope, así que salir siempre es posible y entrar no pasa del tope más que el margen, que cubre la tolerancia de montaje del imán.
- **Descartado:** rechazar el jog rápido con un `ERR` (la página usa una sola velocidad de jog y quedaría inutilizable sin referencia) y frenar el jog solo sin referencia (un fin de carrera protege siempre).
- **Estado:** Aceptada.

## Canal de instrumentación y banco de ensayo (issue #14)

Decisiones tomadas al implementar el canal que solo existe en la simulación (ADR 0004). Cómo funciona y la evidencia: [validación del canal de instrumentación](../validation/instrumentacion/INFORME.md).

**D59 · `scara-sim/1`: un protocolo de texto aparte, en el puerto 9001, que la URC solo muestra.**
- **Decisión:**
  - El controlador de Webots se conecta a la URC en el 9001 (`--sim-port`; 0 lo apaga) y envía, 20 veces por segundo, `SIM J1 J2 J3 J4 hall corriente f2 f3 f4 carga`: la posición física simulada en unidades de `scara/1`, leída de los `PositionSensor` de Webots, más los Hall que ve el firmware, los motores con corriente, el estado de las fallas y la carga.
  - La URC envía `F2 0|1`, `F3 j activo|inactivo|libre`, `F4 0|1`, `F5`, `CARGA gramos` y `RECARGA`.
  - En la URC, el canal es un módulo aparte (`urc/instrumentation.py`) y el panel, un script aparte (`urc/banco.js`). Sin canal, el panel no aparece.
  - La sesión con la UCI, el planificador y la validación no importan ese módulo, y una prueba lo verifica: capturar y planificar usan la posición estimada por pasos, como con el robot real.
- **Por qué:** es lo que pide ADR 0004 para que la URC no dependa sin querer de lo que el robot real no da. Separado en módulo y script, además, no se mezcla con el resto de la página. Un protocolo de texto, como `scara/1`, se lee a mano y no necesita una biblioteca de JSON en el controlador C++.
- **Descartado:** JSON por el canal (más pesado de escribir en C++ sin ganar nada) y la posición física medida por la orientación de los cuerpos, como el observador de los ensayos (los `PositionSensor` dan lo mismo y más simple).
- **Estado:** Aceptada.

**D60 · Sin corriente, el motor no hace fuerza y pierde los pasos; al volver la corriente, retiene el eje donde quedó.**
- **Decisión:**
  - La planta deja sin fuerza al motor sin corriente, el eje queda libre y J4 cae por su peso. Pasa con `DISABLE`, con la UCI recién arrancada y con la falla F2, que deja sin corriente solo el driver de M4.
  - Los pulsos que llegan a un motor sin corriente no lo mueven. Cuando vuelve la corriente, la planta toma la posición física como punto de partida: el motor retiene el eje donde quedó, y lo que se movió sin corriente el firmware no lo sabe.
- **Por qué:** es el comportamiento real de un paso a paso sin corriente (falla F2: «J4 cae; la posición estimada por pasos ya no vale»). Antes, la planta seguía sosteniendo los ejes sin corriente.
- **Descartado:** que J4 vuelva solo a la posición de los pasos al recuperar la corriente (un motor real no sabe dónde estaba).
- **Estado:** Aceptada.

**D61 · F4 corta el enlace sin cerrar la conexión; F5 reinicia solo el firmware; la carga es `toolMass`.**
- **Decisión:**
  - F4: el controlador descarta lo que llega por `scara/1` y no envía nada, con la conexión TCP abierta, como un cable desenchufado. El watchdog del firmware frena; su `ERR 4` se pierde con el enlace.
  - F5: el controlador crea el firmware de nuevo y este envía `BOOT`, sin corriente y sin referencia (D40). La planta no se reinicia: J1–J3 quedan donde estaban y J4, sin corriente, cae.
  - La carga cambia `toolMass` del `SCARA.proto` (de 0 a 5 kg). Hoy cambia la física de la herramienta; la pérdida de pasos por carga llega con N2 (#15).
  - `RECARGA` recarga el mundo: el controlador se vuelve a conectar a los dos canales y la UCI arranca de nuevo.
- **Por qué:** cerrar la conexión sería otra falla (la URC la vería como una desconexión de Webots). El reinicio tiene que ser del firmware, no del mundo, para que se vea que la URC detecta el `BOOT` con el robot en la misma pose.
- **Estado:** Aceptada.

## Captura de puntos y gestor de trayectorias (issue #12)

Decisiones tomadas al implementar el gestor de trayectorias en la URC: [`urc/trajectories.py`](../urc/trajectories.py) (modelo, archivo y validación de puntos) y [`urc/trajectories.js`](../urc/trajectories.js) (panel y teclas de la página). Pruebas por los endpoints HTTP en [`tests/test_trajectories.py`](../tests/test_trajectories.py).

**D62 · La trayectoria en edición vive en la URC, y cada una es un archivo `scara-trayectoria` versión 1 en el que mandan las articulaciones.**
- **Decisión:**
  - La URC guarda la trayectoria abierta, su nombre, su archivo y si tiene cambios sin guardar. La página la muestra y pide cada cambio por `/api/trayectoria/*`: capturar, punto, editar, sobrescribir, borrar, mover, ir, nueva, guardar y cargar.
  - Un pedido que descartaría trabajo devuelve 409 y se repite con permiso explícito: «nueva» y «cargar» con cambios sin guardar (`discard`), y «guardar como» sobre un archivo que ya existe (`overwrite`). La página pregunta en el medio.
  - Archivo: uno por trayectoria, en la carpeta `trayectorias/` de la URC (`--trayectorias` la cambia). El nombre del archivo sale del de la trayectoria, sin tildes ni signos: «Pick & place» → `pick-place.json`. Se rechazan los nombres de dispositivo de Windows (`con`, `nul`, `com1`…), que no pueden ser archivos. Se escribe en un temporal y se reemplaza, así un corte no deja un archivo a medias.
  - Contenido: `format` (`scara-trayectoria`), `version` (1), `name`, `saved` (fecha ISO 8601), `units` y `points`. Cada punto lleva `joints` (enteros en las unidades de `scara/1`: centésimas de grado en J1–J3 y de mm en J4), `tool` (X, Y, Z en mm y rumbo en grados, derivados), `kind`, `speed` (% entero) y `wait` (s).
  - Al cargar, mandan las articulaciones. `tool` es opcional, pero si está tiene que coincidir con ellas (±0,01): si alguien editó el XYZ a mano, se rechaza en vez de ignorarlo en silencio. Se rechazan una versión distinta de la 1, otras unidades, claves desconocidas o faltantes y una trayectoria sin puntos. El mensaje dice el archivo, el punto y por qué, y la trayectoria abierta no cambia.
- **Por qué:**
  - La reproducción (#13) necesita la trayectoria en la URC, que es la que planifica (ADR 0005). Con el estado en la URC, la página no puede perder la trayectoria al recargarse, y las pruebas del seam 2 cubren el gestor entero.
  - Las articulaciones guardan la configuración del codo y las vueltas de J1 y J3, que un XYZ con rumbo no determina (D13). En centésimas enteras, guardar y cargar no redondea nada: la trayectoria cargada es exactamente la guardada.
  - Un archivo con claves estrictas detecta los errores de una edición a mano, por ejemplo `velocidad` en lugar de `speed`, que con valores por defecto pasarían inadvertidos.
- **Descartado:** guardar solo XYZ y rumbo (pierde el codo y las vueltas), guardar las articulaciones en grados con decimales (redondeo al ir y volver), la trayectoria solo en la página (se pierde al recargar y la reproducción no la vería) y elegir cualquier archivo de la PC (la URC solo lee y escribe en su carpeta, sin rutas).
- **Estado:** Aceptada.

**D63 · Capturar exige el robot referenciado y quieto; un punto escrito o editado conserva su codo y se valida solo.**
- **Decisión:**
  - Capturar y sobrescribir usan la posición estimada por pasos del último estado `S`. Exigen robot referenciado (D21) y quieto: modo `IDLE`, sin jog y sin segmentos de un tramo por ejecutar (justo después de enviarlos, `S` todavía dice `IDLE`). El estado tiene que tener menos de 1 s: si la UCI dejó de informar, la posición no está al día.
  - Capturar inserta después del seleccionado y selecciona el punto nuevo. Retroceso borra el seleccionado: después de capturar es el último capturado, y varios Retroceso deshacen hacia atrás. Enter abre el diálogo del nombre y guarda.
  - Un punto escrito en XYZ y rumbo usa el codo preferido (J2 negativo, D31) o el que se elija. De las vueltas posibles de J1 y J3, toma la más cercana al punto anterior de la lista. Al editar en XYZ, el punto conserva su codo (un J2 = 0 cuenta como el preferido) y las vueltas más cercanas a las suyas. Para cambiar el codo se edita en J1–J4.
  - Cada punto se valida al capturarlo, escribirlo, editarlo, sobrescribirlo y cargarlo: alcance (si se escribió en XYZ), límites articulares y choque en reposo, con el chequeo de colisiones de los tramos. El rechazo dice el número de punto.
  - Los tramos (recta posible, velocidades, choques en el camino, cambio de codo) no se validan al editar: dependen del orden y del tipo, y los valida la reproducción antes de cada play (D29, D55).
  - «Ir al punto» es un PTP al 25 %, la velocidad del tramo de aproximación (D33). Primero planifica y muestra la duración; mueve recién con la confirmación, que trae el destino que vio el operador: si el punto cambió en el medio, no se mueve.
- **Por qué:**
  - Durante el jog, el estado `S` llega cada 50 ms y el robot sigue frenando con rampa después de soltar la tecla: el punto capturado no sería donde el robot se detiene.
  - Retroceso «borra el último» en el uso normal, que es capturar al final. Si se captura en el medio, borrar el último de la lista borraría otro punto: el que se acaba de capturar es el que el operador quiere corregir.
  - Las vueltas más cercanas evitan que un punto escrito haga girar J1 o J3 una vuelta entera respecto de sus vecinos, y que una edición chica cambie mucho la pose.
  - Validar los tramos en cada edición tardaría segundos (D55) y rechazaría estados intermedios legítimos mientras se arma la trayectoria.
  - «Ir al punto» arranca, igual que la aproximación, desde una pose que no está en la trayectoria.
- **Descartado:** capturar en movimiento, que Retroceso borre siempre el último de la lista, y validar la trayectoria entera en cada cambio.
- **Estado:** Aceptada.

## Pérdida de pasos N2 y falla F1 (issue #15)

Decisiones tomadas al modelar el par de los motores en la planta de Webots y la detección de pasos perdidos en el firmware ([ADR 0006](adr/0006-modelo-de-motores-pasos-y-perdida-de-pasos.md)). Cómo funciona, los parámetros y su fuente: [Transmisión, N2](TRANSMISION.md#par-de-los-motores-y-pérdida-de-pasos-n2). La forma de `EV LOST`: [protocolo](PROTOCOLO_SCARA_1.md#pérdida-de-pasos). La evidencia: [ensayo en Webots](../validation/perdida_pasos/INFORME.md).

**D64 · N2: el rotor sigue al campo con la curva par–ángulo y el par de su curva par–velocidad.**
- **Decisión:**
  - Cada motor es una inercia (rotor más carga reflejada) que sigue a los pulsos con `T = T(ω) · sen(π/2 · e / paso completo)`, más un amortiguamiento fijo (ζ = 0,6). `T(ω)` es plana hasta la velocidad de esquina, `V / (2 L I)`, y cae como `1/ω` arriba; a baja velocidad vale 0,7 del par de retención por los micropasos.
  - A dos pasos completos de atraso, el rotor cae al equilibrio siguiente: se pierden pasos de a cuatro. El firmware no se entera.
  - El modelo está en `webots/controllers/scara_uci/stepper.h`, sin Webots, con pruebas en la PC. Se integra en 10 subpasos de 0,2 ms dentro de cada paso de 2 ms de Webots.
  - La carga de cada motor sale de las masas del proto, con el brazo estirado, sin términos cruzados entre M1 y M2, y con `toolMass`. El peso de J4 pasa por el ACME con eficiencias distintas al subir y al bajar.
  - Webots lleva cada articulación hacia sus rotores con control de velocidad, sin su límite de aceleración y sin apoyarse en los topes. Al volver la corriente, la fuerza de la articulación sube en rampa durante 0,1 s: con J4 apoyado en su tope, ODE le aplica de más en el primer paso que el motor lo saca de ahí. En el mundo de la UCI, el par de las articulaciones de Webots se sube (campos `j1MaxTorque`… de `SCARA.proto`): quien limita es el modelo del motor.
  - Las hojas de datos exactas de los motores del maestro no aparecieron: M1 y M2 toman la familia Minebea 23KM-K3 (23KM-K349B), M3 el STP-42D201-37 y el resto son supuestos típicos declarados, con 24 V en los TB6600.
- **Por qué:** es lo que hace un paso a paso real cuando se le pide más par del que tiene: pierde pasos en múltiplos de cuatro, y con micropasos el atraso normal es una fracción de paso. La curva par–ángulo da el arranque sin rampa y la carga con la misma regla, sin una cota aparte por cada caso. La investigación del 29/10 proponía usar el control de posición de Webots con par limitado y medir el atraso; pero ese control se atrasa por su propia ganancia y por los límites de velocidad y aceleración del proto (con el jog sin rampa, J1 se atrasaría 1,5°, más que medio ciclo eléctrico), y no puede repartir el par de M1 y M2 entre J1 y J2 con el acople. Un modelo aparte, además, se prueba sin Webots.
- **Descartado:** el control de posición de Webots con par limitado (falsas pérdidas de pasos), un modelo cuasiestático que compara el par pedido con el disponible en cada paso de 2 ms (la aceleración, estimada de pulsos de a uno, es puro ruido), y N3 (ADR 0006).
- **Estado:** Aceptada. Los parámetros son provisionales hasta tener las hojas de datos.

**D65 · `EV LOST` al entrar en un imán, con 2 pasos completos de tolerancia, sin corregir la cuenta.**
- **Decisión:**
  - Con el eje referenciado y fuera del homing, al activarse su Hall el firmware compara los pasos contados con los del flanco del imán más cercano: `HALL_EDGE` o `HALL_FAR_EDGE` (nuevo en `config.h`, verificado contra la geometría del proto). J2 cuenta los pasos de M2 menos los de M1.
  - Si difieren en 2 pasos completos o más, envía `EV LOST j pasos`: los reales menos los contados, en pasos completos, con signo.
  - No corrige la cuenta ni frena. La URC marca la referencia de ese eje como dudosa (`doubtful` en su estado, un registro por eje) y lo avisa en el mensaje y en la lista de errores; la duda se limpia con el `EV HOMED` del eje, `BOOT` o al perder la referencia, no con `ZERO` (menos precisa y el firmware puede rechazarla).
  - Un Hall trabado activo (F3) a mitad de carrera también da `EV LOST`: sin encoders, el firmware no distingue un motor corrido de un sensor que miente.
  - De paso, la marca del Hall que frenó un jog (D58) se borra cuando ese Hall se apaga: si no, después de bajar con segmentos al imán del otro extremo, un jog para salir de él se rechazaba.
- **Por qué:** sin encoders, el Hall es la única medida absoluta: se activa siempre en el mismo lugar. Dos pasos completos son la mitad de lo mínimo que se pierde (cuatro), y quedan por encima de lo que yerra la lectura del Hall en movimiento. Informarlo en pasos completos no depende del microstepping (ADR 0003). Corregir la cuenta en movimiento escondería la falla con una medida menos precisa que la del homing, y frenar es una decisión de la URC, que es la que sabe qué está haciendo el robot.
- **Descartado:** comparar solo en el imán de la referencia (J4 nunca pasaría por él al estacionar), informarlo en pulsos (depende del microstepping), corregir la cuenta y que el firmware quite la referencia (cortaría la reproducción con `ERR 7` en medio de un tramo).
- **Estado:** Aceptada.

**D66 · N2 confirma los límites de D45.**
- **Decisión:** se conservan los valores de D45. Con la corriente nominal, el par que piden en su velocidad y aceleración máximas, con 5 kg, queda entre 1,4 veces (M4) y 22 veces por debajo del disponible, y las pruebas lo verifican también con el jog que arranca sin rampa.
- **Por qué:** dejan margen en todos los motores, y subir los de J1–J3 no se puede sin cambiar los límites articulares del modelo de Webots que también usa el planificador.
- **Descartado:** subirlos ahora (cambia el modelo y el planificador en paralelo con #11 y #13).
- **Estado:** Reemplazada por D76: con #11 y #13 cerrados, el margen de N2 se usó para subir los límites.

**D67 · F1 se provoca bajando la corriente de un driver: `F1 m porcentaje`.**
- **Decisión:**
  - El canal de instrumentación acepta `F1 m porcentaje` (10 a 100 % de la corriente nominal del driver de Mm) y `SIM` informa, además, la corriente de cada driver y los pasos completos que perdió cada motor según la planta.
  - El banco de ensayo lo ofrece junto a la carga, y muestra la referencia dudosa que informó el firmware.
- **Por qué:** con la corriente nominal el robot no pierde pasos dentro de D45 (D66), ni con los 5 kg que admite el banco. Un TB6600 regulado de menos es una falla real y común, y la pérdida aparece por las dos causas del enunciado: por carga (M4 al 50 % no sube 5 kg) y por aceleración (M1 al 20 % pierde pasos al arrancar el jog sin rampa).
- **Descartado:** forzar pasos perdidos desde el banco sin causa física (no muestra el modelo) y permitir más carga o más aceleración que lo que planifica la URC (cambia el planificador).
- **Estado:** Aceptada.

## Reproducción de trayectorias (issue #13)

Decisiones tomadas al implementar la reproducción desde el gestor de trayectorias: [`urc/playback.py`](../urc/playback.py) y el panel de [`urc/trajectories.js`](../urc/trajectories.js). Pruebas por los endpoints HTTP en [`tests/test_playback.py`](../tests/test_playback.py); la evidencia, en el [ensayo en Webots](../validation/reproduccion/INFORME.md).

**D68 · La reproducción valida todo antes de mover y encola un tramo detrás de otro, con sus esperas, en un solo movimiento.**
- **Decisión:**
  - Play desde el principio o desde el punto seleccionado, con velocidad global (% entero de 10 a 100, que multiplica la de cada tramo y no se guarda) y loop: N vueltas o sin fin.
  - Antes de enviar nada, la URC planifica y valida (D55) todo lo que se va a ejecutar: el tramo 0, cada tramo de la trayectoria y, con loop, la vuelta del último punto al primero y los tramos anteriores al punto de partida. El rechazo dice cuál: «Tramo 0», «Tramo 3» o «Tramo de vuelta».
  - Tramo 0: PTP desde la posición estimada hasta el punto de partida, al 25 % × la velocidad global (`--aproximacion` cambia el 25 %), con espera de 0 s. Se omite si el robot está a lo sumo a 6 centésimas de grado en J1–J3 y a 1 centésima de mm en J4: menos de un paso de 1/8, redondeado hacia arriba. Entonces el primer tramo parte del punto grabado, no de la pose del robot.
  - Exige el robot referenciado, quieto y sin referencia dudosa (D65). Si en plena reproducción llega un `EV LOST`, la URC la detiene con `STOP`.
  - La espera de un punto son segmentos sin movimiento en su destino, de hasta 1 s cada uno.
  - Toda la reproducción es un solo movimiento de la sesión, que crece: cuando quedan menos de 50 segmentos (1 s) por enviar, entra el tramo siguiente entero, con su espera. Cada vuelta del loop arranca con la vuelta al punto 1 (tipo, velocidad y espera del punto 1, D32) y sigue con los tramos 2…n; desde el seleccionado, solo la primera vuelta arranca ahí. El loop sin fin agrega vueltas hasta que llega Stop.
  - El tramo en ejecución sale de `último` en el estado `S`: el segmento siguiente dice a qué tramo y vuelta pertenece, y si es de la espera. La página resalta el punto al que va.
- **Por qué:**
  - D14 y D29: el robot nunca arranca un tramo que no puede terminar, y con loop la vuelta también se ejecuta. Validar al dar play cuesta unos segundos (D55), una sola vez.
  - Encolar el tramo siguiente antes de que se termine el anterior hace que el firmware los encadene con su reloj, sin huecos: los tiempos son los planificados (ADR 0005). Un segundo de margen es tres veces lo que cubre la cola del firmware (D50). Las esperas como segmentos van con el mismo reloj, sin depender de la red.
  - Un solo movimiento mantiene, mientras dura la reproducción, las protecciones de la sesión que ya existen: no hay jog, captura ni «Ir al punto» en el medio, y un `ERR`, un `BOOT` o una desconexión la cancelan (D52).
  - El umbral del tramo 0 está en centésimas porque la URC no conoce el microstepping (ADR 0003). Con 1/8 el robot llega a un punto escrito con un error de hasta medio paso por motor; J2, que es la diferencia de M2 y M1, suma los dos: hasta 5,6 centésimas. Con otro microstepping solo cambia si se omite o no un tramo 0 de una fracción de segundo.
  - Con la referencia dudosa, la posición estimada puede estar corrida pasos enteros y ningún plan vale: es la opción conservadora. Se limpia con un homing.
- **Descartado:**
  - Validar cada tramo recién antes de enviarlo: arrancaría tramos que no puede terminar.
  - Encolar la trayectoria entera de una vez: no sirve para el loop sin fin.
  - Medir las esperas en la URC: dependerían de la red.
  - Reproducir con la referencia dudosa avisando nada más.
- **Estado:** Aceptada.

**D69 · La pausa es el `STOP` con rampa del firmware; al reanudar, la URC recalcula el resto del tramo desde la pose de la pausa.**
- **Decisión:**
  - Pausa envía `STOP` (D52). La reproducción queda en pausa con el primer estado `IDLE` que llega después de la orden.
  - Con `último`, la URC sabe qué segmento se interrumpió. Si era del movimiento, al reanudar planifica y valida de nuevo ese tramo, con su tipo y su velocidad, desde la posición estimada hasta su destino. Si ya estaba en la espera, queda lo que faltaba de ella. Lo que seguía se encola como antes.
  - Reanudar exige el robot en la misma pose de la pausa y la trayectoria sin cambios. Si no, hay que frenar con Stop y reproducir de nuevo, con su tramo 0.
  - Stop (el botón del gestor, el general y Esc) frena con la misma rampa y descarta todo lo pendiente.
- **Por qué:**
  - La rampa sigue en la dirección del segmento en ejecución, en articulaciones. En un PTP, ese es exactamente su camino. En un LIN, el robot frena en menos de medio segundo y se aparta de la recta lo que se curva el camino en ese trecho: en el ensayo en Webots, 0,053 mm. El resto, desde ahí hasta el destino, es la misma recta: el tramo la conserva entera.
  - El firmware ya frena así, con la cola vaciada al instante. Una rampa planificada por la URC sobre la recta tendría que esperar que se ejecute lo ya encolado, hasta 320 ms a plena velocidad.
  - Si el robot se movió durante la pausa, el resto sería otra recta.
- **Descartado:** frenar con una rampa planificada por la URC, reanudar desde cualquier pose y repetir la espera completa.
- **Estado:** Aceptada.

## QA de la ronda 3

Decisiones tomadas al corregir lo que encontró la prueba manual de la URC con Webots el 31/10/2026: jog lento y sin límites, un PTP que no podía salir de cerca del pedestal, la «Parada inmediata» que no perdía la referencia durante el jog y un homing que no se podía repetir después de frenarlo.

**D70 · Con referencia, el jog va a 10 °/s y la URC lo frena antes del límite de recorrido y de un choque.**
- **Decisión:**
  - Con los cuatro ejes referenciados, la URC pide el jog a 10 °/s (10 mm/s en J4), el máximo del firmware sin rampa (`JOG_SPEED_MAX`). Sin referencia lo pide a 5 °/s, lo que de todos modos deja el firmware (D58).
  - Con referencia, en cada `S` y en cada pedido de la página, la URC mira adelante en el sentido del jog: si en 0,15 s una articulación que mueve pasaría su límite de recorrido, o si en 0,15 o 0,3 s el robot entraría en la zona de margen de un obstáculo, envía `JOG STOP` y rechaza el pedido con el motivo. Dentro de esa zona el jog puede salir: solo frena si la separación disminuye. El jog por motor cuenta lo que mueve cada motor: M1 mueve J1 y J2 al revés.
  - Stop, Parada inmediata y Deshabilitar no envían antes `JOG STOP` desde la página: la orden misma frena el jog. Un pedido de jog igual al frenado que llega dentro de los 0,3 s siguientes no lo reanuda.
  - La casilla del jog por motor se llama «Jog por motor (M1–M4)», sin «modo de prueba», y aclara que no afecta al PTP, que siempre mueve las articulaciones (D46).
  - «Copiar la pose actual» recorta cada articulación a su recorrido y avisa: la posición estimada puede quedar un poco afuera.
- **Por qué:**
  - A 5 °/s el jog no servía para mostrar. 10 °/s ya lo acepta el firmware y N2 verifica que arranca sin rampa sin perder pasos (D66). Ir más rápido exige una rampa en el firmware.
  - El jog no verificaba nada con referencia: en reposo, J4 bajó medio milímetro de más sobre su imán de fin (D58 deja entrar el ancho del imán) y la pose copiada quedó fuera del recorrido. Sin referencia sigue protegiendo el Hall (D21).
  - La página enviaba `JOG STOP` y después `HALT`: el `HALT` llegaba con el robot quieto y conservaba la referencia (D41).
- **Descartado:** los límites del jog en el firmware (no conoce el recorrido ni los choques, ADR 0005) y un jog que verifica choques con el camino continuo de `first_conflict` (más lento a 20 por segundo, sin ganar nada con lo que avanza en 0,3 s).
- **Estado:** Aceptada. Desde D75, con referencia, el freno de la URC rige solo para el jog por motor: el articular y el cartesiano son segmentos verificados.

**D71 · Un PTP puede salir de la zona de margen de un obstáculo si se aleja.**
- **Decisión:**
  - `CollisionChecker.first_conflict_leaving`, que usan el PTP de la página y la validación de los tramos PTP, admite un camino rechazado por `first_conflict` si: el inicio está a menos del margen más dos veces la resolución de un obstáculo, la separación crece en muestras cada vez más lejos del inicio (s = 2⁻²⁰ … 1) hasta salir de esa zona, en ese tramo las envolventes no se tocan (sin margen, con la cota continua) y el resto del camino respeta el margen.
  - `clearance` mide la separación quieta: por par de cajas, la mayor distancia en un eje, la misma regla con la que `first_conflict` declara conflicto.
  - El mensaje de un destino fuera del recorrido empieza con «El destino tiene…».
- **Por qué:** cerca del inicio, la cota continua no puede demostrar la separación si es menor que la resolución, así que todo camino desde ahí se rechazaba. Con pasos chicos el PTP llegó a J2 = 107,33° junto al pedestal y el robot quedó encerrado: solo salía con jog.
- **Descartado:** bajar la resolución en todo el chequeo (más lento en cada tramo) y prohibir los destinos dentro de esa zona (el robot igual llega con jog o con pasos perdidos).
- **Estado:** Aceptada.

**D72 · Homing más rápido, y repetible después de frenarlo.**
- **Decisión:**
  - La búsqueda va a 15 °/s en J1–J3 y a 10 mm/s en J4 (`HOME_FAST`, por eje). Las fases lentas siguen a 1 °/s (1 mm/s). La vuelta al reposo, y «Estacionar», es un PTP al 100 %.
  - El firmware recuerda qué ejes tienen una cuenta de pasos que sale de una referencia (`found_`), aunque un `STOP` o un homing abortado se la hayan quitado: solo la olvida con `HALT` en movimiento, `DISABLE` o un reinicio. Con el Hall activo al empezar, un eje así que está en su flanco retrocede directamente.
  - Si un eje sale hacia la referencia desde un imán (`LEAVE`) y recorre más que su ancho y el margen sin que el Hall se apague, era el imán de la referencia: retrocede lo que avanzó y busca el flanco. `ERR 12 trabado` queda para el Hall que no se apaga en ningún sentido.
- **Por qué:**
  - El homing tardaba ~80 s y la vuelta al reposo ~26 s; así, unos 55 s y 14 s. La aproximación lenta, que fija la referencia, no cambia.
  - N2 verifica que la búsqueda arranca y frena sin rampa sin perder pasos, con 5 kg. M4 a 15 mm/s pierde pasos subiendo 5 kg: por eso J4 va como el jog.
  - Frenar el homing después de J4 y repetirlo daba `ERR 12 trabado`: J4, sin referencia y sobre su imán de arriba, salía hacia el tope como si fuera el de abajo. Con `STOP` no se pierden pasos, así que la cuenta sigue diciendo dónde está.
  - El modo rápido de Webots no sirve para esto: los `PING` llegan en tiempo real y el watchdog cuenta tiempo simulado (D26).
- **Descartado:** conservar la referencia de los ejes encontrados al abortar (D56) y buscar a 15 mm/s también en J4.
- **Estado:** Aceptada.

## Campaña de validación (issue #18)

Decisiones tomadas al armar la campaña de validación en Webots del camino nuevo (seam 3 de la spec #2). Los escenarios, la versión ensayada y los resultados: [informe de la campaña](../validation/campana/INFORME.md).

**D73 · La campaña corre los ensayos de cada issue con un solo ejecutor, que registra la versión ensayada.**
- **Decisión:**
  - [`validation/campana/campana.py`](../validation/campana/campana.py) compila el controlador y corre, uno detrás de otro, los ocho ensayos en Webots: los siete de los issues #6 a #15 y uno nuevo, [`validation/campana/ensayo_webots.py`](../validation/campana/ensayo_webots.py), con lo que ninguno cubría: F3 con un Hall trabado inactivo, F5 en plena reproducción, teach & play con puntos capturados con jog y las trayectorias de demostración.
  - Escribe `validation/campana/campana.json`: el commit; el SHA-256 del controlador compilado, del mundo, del proto y de las trayectorias de demostración; Webots, Python y el sistema; y, por escenario, condición inicial, resultado esperado, tolerancia, ensayo, paso de su registro y resultado. Los registros van a `validation/campana/registros/`: los de cada issue quedan como estaban. Una corrida parcial (`campana.py homing`) deja los suyos en un temporal y no toca los de la última campaña.
  - Solo registra una campaña completa, con el árbol sin cambios sin commitear y si la versión no cambió mientras corría. Un escenario pasa si todos sus ensayos terminan con `ENSAYO OK`: cada ensayo verifica sus tolerancias con `assert` y se corta en la primera que no se cumple.
- **Por qué:**
  - Reusar los ensayos evita dos versiones de la misma prueba que después divergen. Cada uno ya mide lo que dice su informe, con su tolerancia.
  - El controlador se compila en cada máquina y no se versiona: el commit solo no dice qué binario se ensayó. Compilar antes de correr hace que salga de ese commit, y el SHA-256 lo identifica.
  - Los ensayos se corren de a uno porque Webots tiene que ir a tiempo real (D26): dos a la vez lo atrasan, y los que miden con el reloj de la PC (el watchdog de F4, por ejemplo) dejarían de valer.
- **Descartado:** copiar los ensayos en uno solo (duplica y diverge), correrlos en paralelo y volver a escribir los registros de cada issue (D25: la evidencia de cada issue no se altera).
- **Estado:** Aceptada.

**D74 · Las trayectorias de demostración se versionan en `trayectorias/`, la carpeta por defecto de la URC.**
- **Decisión:**
  - Tres archivos `scara-trayectoria` (D62), armados con el gestor de la URC: `demo-pick-and-place.json` (bajar y subir en LIN con esperas, cruzar en PTP), `demo-cuadrado-lin.json` (un cuadrado de 80 mm en LIN, a altura y rumbo fijos) y `demo-barrido-ptp.json` (de un lado al otro en PTP, con cambio de codo, que en LIN sería imposible).
  - Una prueba sin Webots ([`tests/test_demos.py`](../tests/test_demos.py)) carga cada una por HTTP y la reproduce en loop de 2 vueltas desde el reposo: así quedan validados sus tramos, la vuelta del último punto al primero y el tramo de aproximación. El ensayo de la campaña las reproduce en Webots.
- **Por qué:** con `python -m urc.app`, sin opciones, aparecen en «Cargar» para la defensa. Si alguien cambia los límites, el modelo o el planificador y una demo deja de valer, la suite lo dice antes de la defensa.
- **Descartado:** guardarlas en `validation/` (la URC no las vería sin `--trayectorias`) y capturarlas con jog (los puntos escritos se repiten exactos y se leen en el archivo).
- **Estado:** Aceptada.

## Jog cartesiano y jog verificado

**D75 · Con referencia, el jog es de segmentos de 20 ms que la URC planifica de a uno, con tres en cola contados en el reloj de la UCI.**
- **Decisión:**
  - Con los cuatro ejes referenciados, el jog articular y el cartesiano son `SEG` de 20 ms ([`urc/jog.py`](../urc/jog.py)). Cada uno sale de donde termina el anterior, sin redondear, y se verifica antes de enviarlo. La URC mantiene tres en la cola del firmware. Al soltar la tecla no envía nada: el robot frena al terminar lo encolado. Esc es el `STOP` con rampa (D52).
  - La cola se cuenta de dos maneras, y no pasa de tres en ninguna: por lo enviado desde que arrancó el jog, y por lo que el último `S` dice que terminó más lo que pasó desde que llegó, hasta dos períodos: sin un `S` nuevo, la UCI pudo trabarse. Las dos van en el reloj de la UCI, que la URC mide por el período de los `S` (cada 50 ms del firmware): Webots puede correr más lento que la PC.
  - **Velocidades.** Articular: 10 °/s (10 mm/s en J4); con Mayús, 2 °/s. Cartesiano: 20 mm/s en el plano y 4 mm/s con Mayús; el rumbo y la altura mueven J3 y J4 a la velocidad del articular. Ningún motor pasa de 10 °/s, en las unidades de su articulación: es la velocidad del jog sin rampa (D70). Cerca del brazo estirado o de la torre, el paso del cartesiano se acorta: el más largo que la respeta, por bisección.
  - **Teclas.** Las mismas en los dos modos (D12). En el cartesiano, A/D mueven el punto de herramienta en Y, W/S en X, Q/E giran el rumbo y R/F suben y bajan. En la pose de reposo, cada tecla mueve hacia el mismo lado que en el articular. Tab cambia de modo y la página muestra siempre el modo, el punto de herramienta y la configuración del codo.
  - **Verificación de cada segmento.**
    - Recorrido: frena antes de pasarlo; si la posición estimada quedó afuera, solo deja volver.
    - Codo (solo en el cartesiano): queda fijo, el signo de J2; desde el brazo estirado, el preferido (D31). El jog frena con |J2| por debajo de 2° o si lo que acorta el paso es el alcance: «borde del alcance».
    - Choques: dentro de la zona de margen de un obstáculo, solo deja alejarse (D70).
    - Como el robot frena en el último segmento enviado, que ya está verificado, no hace falta mirar adelante.
  - Un jog nuevo (otra tecla, o Mayús) arranca cuando el robot frenó el anterior, desde donde frenó.
  - Sin referencia, el cartesiano se rechaza y el articular es el `JOG` lento del firmware: 5 °/s, 2 °/s con Mayús (D58). El jog por motor sigue siendo el `JOG` del firmware, con el freno de D70.
  - Soltar la tecla solo frena el jog: si el jog se había rechazado, un tramo o un homing en curso siguen.
- **Por qué:**
  - Es D28: el jog no debe poder llevar el robot contra la torre, y el cartesiano necesita la cinemática inversa, que corre en la URC (ADR 0007).
  - El firmware frena en seco al vaciarse la cola. A 10 °/s no hace falta rampa (D66). Tres segmentos son 60 ms.
  - En Webots, a 0,82× del reloj de la PC, frenó en 80 ms simulados de mediana y 90 como mucho, contando hasta que la posición física queda a menos de un paso. Contando la cola con el reloj de la PC, crecía y frenaba en 110–150 ms; con otro Webots trabando la simulación, sin el tope de dos períodos, llegó a 320 ms.
  - Seguir del segmento anterior sin redondear evita que el punto de herramienta acumule el redondeo. En Webots, la posición estimada se apartó 0,06 mm de la recta como mucho.
  - Junto al brazo estirado, J2 cambia como la raíz del avance: a velocidad fija del punto de herramienta, se dispara, y al cruzar J2 = 0 el codo se da vuelta. Con 2° el cartesiano queda a 0,08 mm del alcance máximo.
  - Arrancar un jog al revés sin frenar sería el doble del salto de velocidad del jog sin rampa.
- **Descartado:**
  - El `JOG` del firmware con el freno de la URC (D70) también para el articular con referencia: no sirve para el cartesiano, y frena mirando adelante con la demora de los `S`.
  - `STOP` al soltar: frena con rampa y tarda más que lo encolado (73 ms a 10 °/s con la aceleración de M1), y con la cola corta pasaría del último segmento verificado.
  - Más velocidad en el cartesiano: necesita una rampa en el firmware.
- **Estado:** Aceptada.

## Límites más rápidos

**D76 · Los motores van más rápido, con el doble del par que piden; el LIN se separa de J4.**
- **Decisión:**
  - **Motores** (`firmware/config.h`): M1 y M2 a 360 °/s y 560 °/s², M3 a 720 °/s y 1440 °/s², M4 a 1800 °/s y 5400 °/s². En las articulaciones: J1 y el antebrazo (J1 + J2) hasta 90 °/s y 140 °/s²; J3, 180 °/s y 360 °/s²; J4, 40 mm/s y 120 mm/s².
  - **Criterio:** con la corriente nominal y 5 kg, el par que piden la velocidad y la aceleración máximas queda al menos 2 veces por debajo del disponible en M1–M3 ([tabla](TRANSMISION.md#los-límites-con-n2)). M4 conserva su 1,4: lo pone el peso que sube por el ACME, no la aceleración. Todas las velocidades quedan por debajo de la de esquina. M4 pide 8000 pulsos/s con 1/8, el 80 % de lo que da el Timer1 del UNO (D48).
  - **Modelo** (`config/scara.json`, de donde salen los `maxVelocity` del proto): algo por encima de lo que permiten los motores, para que limiten ellos. J1 a 1,75 rad/s y 2,7 rad/s²; J2 a 3,5 rad/s y 5,4 rad/s², el doble, porque con J1 al revés llega a 180 °/s; J3 a 3,5 rad/s y 7 rad/s²; J4 a 0,045 m/s y 0,135 m/s².
  - **LIN:** 150 mm/s sobre la recta con 300 mm/s² (la rampa sigue durando 0,5 s), y 90 °/s de rumbo con 140 °/s², las de M1. La componente vertical de la recta no pasa de la de M4, también escalada por la fracción: una recta vertical al 100 % va a 40 mm/s.
  - La velocidad global (D22) y la de cada tramo siguen siendo porcentajes de estos máximos. El jog, el homing y el tramo de aproximación no cambian.
- **Por qué:**
  - D66 dejaba entre 6,8 y 22 veces de margen con 5 kg: el robot usaba un 6 % de la velocidad de esquina de M1. Un PTP de 90° de J1 tardaba 5,1 s; ahora, 1,6 s.
  - 2 veces es un margen usual al dimensionar un paso a paso en lazo abierto: cubre lo que el modelo no tiene (resonancias, N3) y la dispersión de los supuestos de N2. Las pruebas de N2 lo verifican además simulando: ningún paso perdido y menos de un paso completo de atraso, también con 5 kg.
  - Con el modelo por debajo de los motores, Webots saturaba la articulación y la física se atrasaba del firmware (validación de segmentos). Por encima, el plan lo limitan los motores, como en el robot real.
  - Atado a J4, el LIN quedaba en 40 mm/s y casi no cambiaba. Limitar solo la componente vertical conserva lo que D54 quería (una recta vertical nunca supera J4) sin frenar las horizontales. No es bajar la velocidad por un punto: la componente vertical es la misma en toda la recta. Las rectas que piden más que un motor se siguen rechazando con su motivo (D55).
- **Consecuencias:**
  - Esc y `STOP` frenan con la misma rampa (D52): desde 90 °/s, J1 tarda 0,64 s y recorre 29°, unos 25 cm con la herramienta a 0,5 m del eje. Al 50 % de velocidad global, 0,32 s y 7°. Para probar algo nuevo, conviene empezar con la velocidad global baja.
  - La tolerancia del LIN pasa de 0,069 a 0,127 mm: la cuerda de cada segmento crece con la velocidad de M1 y M2 (1,8° en 20 ms).
  - F1 por aceleración: con el driver de M1 al 20 % y 5 kg, ahora también pierde pasos la rampa del planificador, no solo el jog sin rampa.
  - En el robot real los números siguen saliendo de los supuestos de N2: hay que confirmarlos con las hojas de datos o midiendo antes de usarlos al 100 %.
- **Descartado:**
  - Llegar al par disponible (margen 1): cualquier error de los supuestos pierde pasos.
  - J4 a 50 mm/s: son los 10 000 pulsos/s del Timer1, sin margen.
  - Subir el jog: arranca sin rampa y necesita una en el firmware (D70).
- **Estado:** Aceptada. Reemplaza los valores de D45 y la conclusión de D66.
