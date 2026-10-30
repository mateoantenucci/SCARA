# Registro de decisiones: grabar y reproducir trayectorias

Por qué el SCARA quedó diseñado así. Sirve para responder al profesor. Cada entrada dice qué se decidió, por qué y qué se descartó. Las decisiones difíciles de revertir tienen además un ADR en [`docs/adr/`](adr/). El análisis completo está en la [investigación del 29/10/2026](INVESTIGACION_TEACH_AND_PLAY_2026-10-29.md). El documento maestro v2 incorporará este registro.

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
  - `S` tiene nueve campos fijos: `S modo ref J1 J2 J3 J4 hall libres último`. El modo es una palabra (`IDLE`, `JOG`); el resto, enteros.
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

