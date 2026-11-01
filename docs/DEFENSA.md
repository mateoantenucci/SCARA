# Guion de la defensa

Guion de la defensa grupal del SCARA (issue #20): la demostración paso a paso desde un arranque limpio en Windows, quién explica qué, las preguntas probables del profesor con su respuesta y el material de estudio para que cualquier integrante pueda explicar la arquitectura, el acople M1/M2, el homing y la pérdida de pasos.

Usa el vocabulario del [glosario](../GLOSSARY.md). Cada respuesta cita su decisión del [registro](REGISTRO_DE_DECISIONES.md) y, si la tiene, su [ADR](adr/). El documento de referencia es el [maestro v2](maestro/SCARA-Master-v2.md); la evidencia, la [campaña de validación](../validation/campana/INFORME.md).

> **Pendiente para el grupo.** Los integrantes y la duración pactada con el profesor no están en el repo. Donde dice `[INTEGRANTE A]`…`[INTEGRANTE D]` y `[DURACIÓN PACTADA]` hay que completar. El reparto y los tiempos de la sección 3 son una propuesta para 4 integrantes y 25 minutos de demostración, más las preguntas.

## Contenido

1. Antes del día de la defensa
2. Demostración paso a paso
3. Quién explica qué y cuánto dura
4. Preguntas probables del profesor
5. Material de estudio
6. Si algo sale mal

## 1. Antes del día de la defensa

Una vez, en la máquina que se lleva a la defensa (Windows 11, Webots R2025a en `C:\Program Files\Webots`, Python 3 y Git). Los comandos van en PowerShell, desde la raíz del repo.

1. **Traer la versión final:**

   ```powershell
   git switch main
   git pull --ff-only
   ```

2. **Volver a correr la campaña de validación (pendiente).** La campaña registrada en [`campana.json`](../validation/campana/campana.json) es del commit `ba2b8ee`, anterior al jog cartesiano y verificado (issue #11, D75). Hay que repetirla sobre `main` y commitear `campana.json` y los registros, para que la evidencia que se muestra sea la de lo que se demuestra. Dura unos 18 minutos y exige el árbol sin cambios:

   ```powershell
   python validation/campana/campana.py
   ```

   Usa los puertos 9100–9121: no choca con una URC y un Webots abiertos en 9000 y 9001 (D73).

3. **Correr la suite** (unos 3 minutos; no necesita Webots). Tiene que terminar en `OK`; se omiten las pruebas de propiedades CAD si no está el Python con OCP. Incluye la carga y reproducción de las tres trayectorias de demostración (D74):

   ```powershell
   python -m unittest discover
   ```

4. **Compilar el controlador de Webots** con el firmware de `main`. Webots no compila solo los controladores C++, y el binario no se versiona: hay que hacerlo en cada máquina y cada vez que cambia el firmware ([UCI en Webots](UCI_WEBOTS.md#compilar-el-controlador)):

   ```powershell
   & "C:\Program Files\Webots\msys64\usr\bin\bash.exe" -lc "export PATH=/mingw64/bin:/mingw64/bin/cpp:/usr/bin WEBOTS_HOME='C:/Program Files/Webots'; make -C webots/controllers/scara_uci"
   ```

   Deja `scara_uci.exe` en `webots/controllers/scara_uci/`. Desde Git Bash no funciona: hay que llamar al `bash` de Webots (D19).

5. **Ensayar el guion completo una vez**, con el reloj, y anotar los tiempos reales en la tabla de la sección 3.

6. **El día de la defensa:** cerrar todo lo que use los puertos 8766, 9000 y 9001 (otra URC, otro Webots) y otros Webots abiertos: dos simulaciones a la vez atrasan el tiempo real (D26).

## 2. Demostración paso a paso

Arranque limpio: Webots cerrado, sin URC y con el árbol en `main`. Cada paso dice qué hacer, qué tiene que verse y qué decisión explica. Lo que dice la página está entre comillas latinas («»), tal como aparece en la URC.

Cada paso se validó contra el código y contra los ensayos de Webots que lo ejecutan por script, en puertos distintos de 9000 y 9001: [campaña](../validation/campana/ensayo_webots.py) (homing, F3, teach, demos, F5), [jog](../validation/jog/ensayo_webots.py), [instrumentación](../validation/instrumentacion/ensayo_webots.py) (F2–F5) y [pérdida de pasos](../validation/perdida_pasos/ensayo_webots.py) (F1). Se corrieron el 01/11/2026 sobre `main` (commit `79e2295`), en Windows 11 con Webots R2025a, y los cuatro terminaron con `ENSAYO OK`. El de la campaña se cortó una vez en el paso 3, con la UCI desconectada en pleno jog y Webots a ~0,66× del tiempo real, y pasó al repetirlo: si se repite en la campaña de la sección 1, hay que mirarlo. El rechazo del LIN de la sección 2.5 lo verifica la suite. Lo visual de la ventana de Webots no se pudo mirar desde un script: queda para el ensayo del punto 5 de la sección 1.

### 2.1 Arranque y conexión

1. **Levantar la URC** en una terminal que queda abierta:

   ```powershell
   python -m urc.app
   ```

   Imprime `URC scara/1: http://127.0.0.1:8766` y `Esperando a la UCI en TCP 127.0.0.1:9000`. Abrir <http://127.0.0.1:8766> en el navegador.

2. **Abrir Webots** con el mundo de la UCI, a tiempo real: **File → Open World** → `webots/worlds/scara_uci.wbt`, y play. O desde PowerShell:

   ```powershell
   & "C:\Program Files\Webots\msys64\mingw64\bin\webots.exe" --mode=realtime webots\worlds\scara_uci.wbt
   ```

   La consola de Webots dice `UCI: conectada a la URC en 127.0.0.1:9000`. El orden no importa: si Webots arranca primero, reintenta cada segundo.

3. **Qué se ve:** en «Tráfico scara/1», el `BOOT` del firmware, el `HELLO` de la URC y el `HI scara/1 1`; el estado `S` llega 20 veces por segundo con modo `OFF` (sin corriente) y sin referencia. Aparece el panel «Banco de ensayo (solo simulación)», porque el controlador se conectó también al 9001.

4. **Qué se explica:** la URC es servidor y la UCI se conecta (D1); el firmware arranca con la primera conexión, como el UNO cuando socat abre el puerto (D36); arranca sin corriente (D40); el banco de ensayo va por otro canal, que el robot real no tiene (D2, ADR 0004).

### 2.2 Habilitar y homing

1. **«Habilitar motores»**: el modo pasa de `OFF` a `IDLE`. El robot está cerca de la pose de reposo, con el desvío al azar de hasta ±10° en J1–J3 con el que arranca el mundo (D11, D57).
2. **«Homing…»**: la página dibuja la pose de reposo y pregunta «¿El robot está en la pose de reposo?». Responder **«Sí, está en reposo»**.
3. **Qué se ve:** J4 sube hasta su Hall, después J1 (M1 y M2 juntos), J2 (M2 solo) y J3. Cada eje busca rápido, retrocede y vuelve lento al flanco: `EV HOMED 4`, `EV HOMED 1`, `EV HOMED 2`, `EV HOMED 3`. Con los cuatro, la URC vuelve sola a la pose de reposo con un PTP. Unos 55 s de homing y 14 s de vuelta (D72).
4. **Qué se explica:** por qué ese orden y ese sentido (D11, D56), por qué el flanco y no el centro del imán (D56), cómo se activa el Hall en Webots (D57). Mientras el robot se mueve hay tiempo para el material de la sección 5.3.

Alternativa más corta si el homing falla o falta tiempo: **«Referencia manual…»** declara la pose de reposo sin homing. Es menos precisa (D30) y no sirve para la falla F1, que necesita el flanco del Hall.

### 2.3 Acople M1/M2

1. Con la página enfocada, mantener **D**: jog articular de J1 a 10 °/s. Gira el brazo y el antebrazo sigue alineado con él: el firmware mueve M1 y M2 la misma cantidad de pasos.
2. Marcar **«Jog por motor (M1–M4, sin compensar el acople; no afecta al PTP)»** y mantener **D**: solo gira M1. El brazo gira, el antebrazo conserva su orientación en el mundo, J2 cambia al revés que J1 y el rumbo de la herramienta no cambia (D46).
3. Desmarcar la casilla y volver con **«Estacionar…»**.
4. **Qué se explica:** J2 = (θM2 − θM1)/4 y el rumbo depende solo de M2 y M3 (sección 5.2). La URC habla en articulaciones y el firmware resuelve el acople (D5, ADR 0003). Evidencia en Webots: escenario P2 de la campaña.

### 2.4 Teach con jog

1. **«Nueva»** en el panel de la trayectoria.
2. **Tab** pasa a jog cartesiano: la página muestra el modo, el punto de herramienta y la configuración del codo. Mantener **S** (X −, hacia adentro): desde el brazo estirado el codo dobla al lado preferido, J2 negativo (D31). **R/F** suben y bajan, **A/D** mueven en Y, **Q/E** giran el rumbo, **Mayús** hace el jog lento (D12, D75).
3. Capturar tres puntos con **Espacio**, moviendo entre uno y otro. **Retroceso** borra el último capturado (D63). Mostrar que capturar exige el robot quieto: la posición capturada es la estimada por pasos del último `S`.
4. En la tabla, poner el punto 2 en LIN y el punto 3 en PTP con espera de 1 s (D22).
5. **Enter** pide el nombre: por ejemplo, `Teach defensa`. Se guarda en `trayectorias/` (D62).
6. Mostrar el jog verificado, como en su [ensayo](../validation/jog/INFORME.md): en «Ir a una pose (PTP)», J1 = 0°, J2 = 95°, J3 = 0° y J4 = 120 mm (abajo), y **«Ir a la pose…»**. Con jog articular (**Tab** si quedó en cartesiano), mantener **W** (J2 +, hacia la torre): el jog frena antes de la zona de margen del pedestal y avisa el motivo; **S** sale sin frenar (D28, D70, D75).
7. **Qué se explica:** el punto guarda la pose, no el camino (D13); el camino lo calcula la URC al reproducir; el jog con referencia son segmentos de 20 ms verificados de a uno, con tres en cola (D75).

Después de la defensa, borrar el archivo de la trayectoria grabada en `trayectorias/`: si queda, el árbol tiene cambios y `campana.py` no corre (D73).

### 2.5 Reproducción LIN y PTP

1. **«▶ Desde el principio»** con la trayectoria recién grabada. Primero se ve «Validando la trayectoria completa…»: la URC valida todo antes de mover (D68). El tramo 0 es un PTP lento desde donde esté el robot hasta el punto 1 (D32, D33). Después, el LIN, y el PTP con su espera. La página resalta el punto al que va.
2. **Pausa** a mitad de un tramo y **Reanudar**: frena con rampa y sigue sobre la misma recta (D69). **Stop** o **Esc** frenan y descartan lo pendiente.
3. **Cargar las demos** con el selector y **«Cargar»** (si hay cambios sin guardar, la URC pregunta):
   - `demo-cuadrado-lin.json`: cuadrado de 80 mm en LIN, a altura y rumbo fijos; ~54 s al 100 %.
   - `demo-barrido-ptp.json`: de −90° a +90° en J1 y cambio de configuración del codo, todo PTP; ~43 s.
   - `demo-pick-and-place.json` si sobra tiempo: bajar y subir en LIN con 1 s de espera, cruzar en PTP; ~30 s.

   Las duraciones son las planificadas que registró la campaña (T3). Con **Loop** en «N vueltas» o «Sin fin» se muestra la vuelta del último punto al primero.
4. **Un LIN imposible se rechaza antes de mover.** En el barrido PTP, cambiar el tramo del punto 3 a LIN y dar play: la URC responde «Tramo 3 (LIN), cambio de codo: J2 pasa de -60° a 60°; para cambiar de lado el brazo tendría que estirarse, que es una singularidad. Usá un tramo PTP.» y el robot no se mueve (D14, D55). Volver a PTP **sin guardar**, para no tocar la demo versionada.
5. **Qué se explica:** LIN contra PTP (D53, D54), la tolerancia de 0,127 mm del plan y la de la ejecución (D54; T2 de la campaña), los segmentos con el reloj del firmware (D6, D50, ADR 0005).

### 2.6 Fallas F1–F5

El orden importa: F1 y F2 necesitan referencia; F5 la borra; F3 y F4 se muestran sin referencia, como en los ensayos; el bloque termina con un homing que deja el robot como al principio. Todas se inyectan desde el banco de ensayo (D59). El robot arranca el bloque referenciado y en la pose de reposo.

1. **F1 · Pérdida de pasos por carga (D64–D67).**
   1. En «Ir a una pose (PTP)», J4 = 60 mm y J1–J3 en 0 → **«Ir a la pose…»** y confirmar.
   2. «Carga en la herramienta (g)»: 5000 → **«Aplicar»**. «F1 · Corriente del driver de» M4 al 50 % → **«Aplicar»**.
   3. «Ir a una pose» con J4 = 10 mm. La estimada sube; en la columna «Simulado» del banco, J4 no sube: la planta perdió pasos, en múltiplos de 4 pasos completos, y el firmware no se entera.
   4. M4 al 100 % y **«Estacionar…»**. Al bajar, J4 entra en el imán de abajo y el firmware envía `EV LOST 4` con los pasos perdidos. La página avisa «Referencia dudosa (EV LOST)», y reproducir queda bloqueado hasta un homing (D68).
   5. Carga de nuevo en 150 g (la herramienta sola).
2. **F2 · Driver de M4 sin corriente (D60).** «Ir a una pose» con J4 = 60 mm. Marcar **«F2 · Driver de M4 sin corriente (J4 cae)»**: en «Simulado», J4 cae hasta abajo; la estimada sigue en 60 mm. Desmarcarla: el motor retiene J4 donde quedó, y el firmware sigue creyendo que está en 60. Es la falla silenciosa que, sin encoders, se ve recién en un Hall.
3. **F5 · Reinicio de la UCI (D43, D61).** **«F5 · Reiniciar la UCI…»** y confirmar. La URC avisa «BOOT inesperado: la UCI se reinició y perdió la referencia (F5)». La UCI arranca sin corriente: J4 queda abajo y J1–J3 donde estaban. Esto también limpia lo que dejaron F1 y F2.
4. **F3 · Hall trabado inactivo.** **«Habilitar motores»**. En «F3 · Hall trabado», J1 → `inactivo`. **«Homing…»** y confirmar: J4 se referencia y J1 recorre toda su búsqueda sin ver el imán: `ERR 11 ausente`, y el homing aborta sin declarar referencia (D56). Con J4 en `activo`, el homing aborta con `ERR 12 trabado` (escenario F3a).
5. **F4 · Enlace cortado (watchdog, D37).** Sin referencia, el jog articular es el `JOG` lento del firmware. Mantener **D** y, sin soltarla, marcar con el mouse **«F4 · Cortar el enlace scara/1 (actúa el watchdog)»**: el estado deja de llegar y el brazo frena solo en menos de 1 s. Desmarcarla: el robot está quieto.
6. **Cierre.** F3 de J1 en `libre` y **«Homing…»**: termina en la pose de reposo y el robot queda referenciado.
7. **Qué se explica:** cómo se detecta cada falla sin encoders (tabla de la sección 5.4); el catálogo y por qué F6 no se hizo (D23).

## 3. Quién explica qué y cuánto dura

Propuesta para 4 integrantes y 25 minutos de demostración, más el tiempo de preguntas que fije el profesor. Duración pactada: **`[DURACIÓN PACTADA]`**. Si es más corta, se acortan los bloques marcados como recortables; con 3 integrantes, `[INTEGRANTE D]` se reparte entre B y C.

| Bloque | Contenido | Quién | Min | Recortable |
| --- | --- | --- | --- | --- |
| Introducción y arquitectura | Qué se pidió, qué se hizo, diagrama de la sección 5.1, firmware único y simulación sin hardware (D0, D3, D6, ADR 0001) | `[INTEGRANTE A]` | 3 | No |
| Arranque y conexión | Sección 2.1: URC, Webots, `BOOT`, canal de instrumentación | `[INTEGRANTE B]` | 2 | No |
| Habilitar y homing | Sección 2.2; durante la búsqueda, el porqué del homing | `[INTEGRANTE B]` | 3 | Usar referencia manual |
| Acople M1/M2 | Sección 2.3: jog articular contra jog por motor | `[INTEGRANTE C]` | 2 | No |
| Teach con jog | Sección 2.4: jog cartesiano, captura, guardar | `[INTEGRANTE C]` | 4 | Capturar dos puntos |
| Reproducción LIN y PTP | Sección 2.5: la trayectoria grabada, pausa, demos y el LIN rechazado | `[INTEGRANTE D]` | 4 | Una sola demo |
| Fallas F1–F5 | Sección 2.6 | `[INTEGRANTE D]` y `[INTEGRANTE A]` | 6 | Omitir F2 y el homing final |
| Cierre | Validación, límites y lo pendiente (sección 5.5) | `[INTEGRANTE A]` | 1 | No |
| **Total** | | | **25** | |

Cada integrante estudia la sección 5 entera: el profesor puede preguntarle a cualquiera.

## 4. Preguntas probables del profesor

Agrupadas por tema. Cada respuesta dice la decisión del registro, que tiene el detalle y lo descartado.

### Alcance y arquitectura

**¿Por qué no hay robot físico? ¿Qué vale entonces lo que muestran?**
El grupo no tiene hardware. Se simula el diseño y cada parámetro declara su procedencia: confirmado, calculado o provisional. La campaña prueba el diseño simulado, no un robot construido; si se construye, sus mediciones reemplazan los parámetros (ADR 0001).

**¿Copiaron AGSABOT?**
No. Es la referencia de la idea, no de la implementación. Leímos su código: reproduce a ciegas cada 1200 ms, el stop puede no enviarse y no tiene homing (D0).

**¿Por qué la URC es servidor y Webots cliente?**
Lo pidió el profesor, y con el robot real quien se conecta es socat, que abre el USB. La URC queda esperando y el robot puede reiniciarse o desconectarse sin tocarla (D1).

**¿Qué cambia el día que se construya el robot?**
Nada en la URC ni en el firmware. El mismo núcleo C++ compila para el UNO; solo cambia la capa de hardware: pines, serie y timer en lugar de socket TCP y planta simulada (D3, ADR 0002). Ya compila: 16 148 B de flash (50 %) y 1297 B de RAM (63 %), y se probó el camino serie con un puerto virtual y socat, sin la placa (D49).

**¿Por qué no un emulador en Python, que era más rápido?**
Porque después habría que escribir y depurar el firmware real desde cero, que es justo lo que el profesor quiere evitar (D3, ADR 0002).

**¿Quién calcula la cinemática? ¿Por qué no el Arduino?**
La URC: inversa, rectas y perfil de velocidad. Manda segmentos de 20 ms con su duración, y el firmware los encola y los ejecuta con su reloj. Un UNO no calcula la inversa a la frecuencia que pide una recta, y ejecutar con el reloj del firmware evita que las demoras de red se vuelvan tirones. Es la división de GRBL y Klipper (D6, ADR 0005).

**¿Cómo es el protocolo y por qué texto?**
Una línea ASCII por mensaje, de hasta 64 bytes, solo enteros (D4). Se procesa en 2 KB de RAM y se lee a mano con `nc` o el monitor serie. JSON es pesado para un UNO. Estado 20 veces por segundo, `PING` cada 250 ms, watchdog de 1 s, cola de 16 segmentos, 115200 baudios (D27).

**¿Cómo se ve un mensaje? ¿Qué puertos usa?**
`HI scara/1 1` saluda con el protocolo y la versión del firmware; `S` lleva nueve campos fijos, con el modo como palabra (`IDLE`, `JOG`, `OFF`) para leerlo a simple vista; `ERR` lleva un código estable y una palabra (D35). Puerto 9000 para `scara/1` y 9001 para instrumentación, configurables (D24).

**¿Por qué UCI y URC?**
Es el vocabulario de AGSABOT, que la cátedra ya conoce. No hay PPM porque no hay panel físico (D7).

**¿Por qué una página web?**
Ya existía, no agrega dependencias y la consigna admite «una página web». La sirve la URC en el 8766 (D15).

**¿Por qué el protocolo habla en centésimas de grado y no en pasos?**
Porque el microstepping, las poleas y el acople son hechos del robot. Cambiar un driver o una polea toca la configuración del firmware, no la URC; la telemetría se lee; y los enteros evitan flotantes en el AVR (D5, ADR 0003).

**¿Cómo saben que la URC y el firmware entienden el mismo protocolo?**
Las mismas conversaciones de conformidad corren contra el firmware compilado en la PC y contra la URC con una UCI falsa por TCP. Una prueba de mutación lo confirmó (D39, D42).

**¿Por qué un segundo canal para la simulación?**
Para que la URC no dependa sin querer de algo que el robot real no da. La posición física simulada, las fallas, la carga y la recarga van por el 9001, con `scara-sim/1`. La sesión, el planificador y la validación no importan ese módulo, y una prueba lo verifica (D2, D59, ADR 0004).

**¿El tiempo de la simulación es el real?**
Durante teach y play, Webots corre a 1× y el firmware usa el reloj simulado. Si la PC no llega, el robot va más lento sin romperse. Con tiempo acelerado, el watchdog saltaría: los `PING` llegan a ritmo real (D26).

**¿Por qué hay dos mundos de Webots?**
`scara_uci.wbt` usa el mismo `SCARA.proto` con el controlador nuevo y arranca en la pose de reposo; el mundo viejo quedó al lado mientras el camino nuevo no funcionaba (D16, D38).

### Mecánica, motores y electrónica

**¿Qué es el acople M1/M2 y cómo lo resuelven?**
M2 fija el ángulo absoluto del antebrazo, J1 + J2; por eso J2 = (θM2 − θM1)/4. Para mover solo J1, M1 y M2 dan los mismos pasos. Lo resuelve el firmware (`firmware/transmission.h`); la URC habla en articulaciones (D5, D44). Se demuestra con el jog por motor (D46). Sección 5.2.

**¿Por qué 1/8 de paso, si el maestro dice 400 pulsos?**
Con 400, un pulso de J1 mueve el extremo casi 2 mm con el brazo estirado y una recta se ve escalonada; con 1/8, medio milímetro. Los pulsos siguen al alcance del UNO: el que más pide es M4, 8000 pasos/s, contra 10 000 por motor del Timer1. Es un solo parámetro, `SCARA_MICROSTEPS`, que comparten el firmware y la planta. Es propuesta al profesor (D9, D44, D48).

**¿De dónde salen las velocidades máximas?**
Se fijan por motor, no por articulación, y se derivan con el acople: M1 limita a J1 y M2 limita a J1 + J2. El maestro dice «1000 rpm», que a 1/8 serían 26,7 kHz por motor, imposibles en el UNO. Se eligieron con las curvas de par de N2: con 5 kg, el par que piden queda al menos 2 veces por debajo del disponible en M1–M3, el margen usual de un paso a paso en lazo abierto. M4 queda en 1,4 por el peso que sube. J1 llega a 90 °/s, J3 a 180 °/s y J4 a 40 mm/s (D45, D76). Antes eran 4,5 veces más lentos en J1, elegidos sin N2 (D66).

**¿Por qué un Arduino UNO y no algo más grande? ¿Alcanzan los pines?**
Es la placa del maestro. Con un Hall por eje usa 15 de 20 pines por USB. Los pines elegidos dejan libres los del shield Ethernet, así que pasar a Ethernet no obliga a recablear (D18, D47).

**¿Cómo genera los pulsos el UNO?**
El núcleo cuenta los pasos y la interrupción del Timer1, a 20 kHz, los convierte en pulsos con los tiempos del TB6600. Nunca se descarta un paso contado: si se juntan, el firmware espera (D48).

**¿Cuántos motores hay? El ensamble tiene tres NEMA 23.**
Cuatro: dos NEMA 23 en la base (M1, M2) y dos NEMA 17 (M3 en el antebrazo, M4 en la columna Z). `NEMA23-2` no tiene ubicación ni aparece en los planos: es una instancia suprimida o residual (D20).

**¿Qué modelo de motor simulan?**
Dos niveles: N1, pasos, transmisión y acople; N2, par limitado según la velocidad, con pérdida de pasos que el firmware no advierte. No el modelo eléctrico: faltan datos y exigiría pasos de simulación mucho más chicos (D8, D64, ADR 0006). Sección 5.4.

### Homing y referencia

**¿Dónde van los sensores Hall y por qué uno solo por eje?**
Un KY-003 por articulación en la pieza fija y dos imanes en la que se mueve, en los extremos. Un sensor por eje entra en el UNO. J2 se mide relativo, en el codo, porque los topes que importan son los relativos. Es propuesta al profesor (D10).

**¿Por qué ese orden de homing, J4, J1, J2, J3?**
J4 sube primero para alejar la herramienta de la mesa. J1 mueve M1 y M2 juntos para que J2 no cambie. J2 con M2 solo. J1 y J2 se referencian en el mismo extremo, el negativo: con J2 en el positivo y J1 en −135°, el soporte Z choca con la torre (D11).

**¿Por qué el flanco y no el centro del imán?**
El flanco al que se llega lento y siempre desde el mismo lado es repetible. Centrar el imán en el extremo deja el flanco 5° antes del tope: el homing nunca empuja contra él (D56).

**¿Cómo simulan un Hall en Webots? ¿No es trampa leer la posición?**
Sería trampa, y es lo que hacía el banco viejo. El imán es un `Emitter` y el KY-003 un `Receiver`; la planta mide la distancia entre los dos nodos, porque Webots no entrega paquetes dentro de un mismo robot. La activación sale de la geometría: si se corre un imán, se corre el flanco, y una prueba lo verifica (D10, D57).

**¿Qué pasa si el Hall falla?**
La búsqueda está acotada en recorrido y en 60 s por eje. Un Hall que no aparece aborta con `ERR 11 ausente`; uno que no se apaga, con `ERR 12 trabado`. En los dos casos el homing no declara referencia (D56; F3 en la demo).

**¿Por qué la pose de reposo es el brazo estirado?**
Contraída, con J2 = ±135°, toca la torre incluso quieta. Estirada queda libre y J1 puede barrer hasta los dos extremos. J4 queda abajo porque sin corriente cae solo (D30).

**¿Qué se puede hacer sin referencia?**
Solo jog articular lento, a 5 °/s, protegido por los Hall como fin de carrera. Capturar y reproducir están bloqueados: `SEG` exige referencia. Sin referencia la URC no sabe dónde está el robot y no puede verificar nada (D21, D51, D58).

**¿Por qué tardaba tanto el homing y qué cambiaron?**
Tardaba unos 80 s. Ahora busca a 15 °/s en J1–J3 y a 10 mm/s en J4, y la aproximación lenta que fija la referencia no cambió: unos 55 s más 14 s de vuelta. J4 no va más rápido porque a 15 mm/s pierde pasos subiendo 5 kg (D72).

### Jog, trayectorias y reproducción

**¿Por qué el jog con el teclado de la URC y no en Webots, como sugirió?**
El robot real no tiene botonera, así que el jog desde la URC funciona igual con los dos. El jog cartesiano necesita la cinemática inversa, que corre en la URC, y la lista de puntos queda a la vista. Teclas en Webots se pueden agregar sin tocar el firmware (D12, ADR 0007).

**¿El jog puede llevar el robot contra la torre?**
Con referencia, no: el jog son segmentos de 20 ms que la URC verifica de a uno contra recorrido, configuración del codo y choques, con tres en la cola. Al soltar, el robot frena al terminar lo encolado, unos 60 ms; en Webots, 80 ms simulados de mediana (D28, D75). Sin referencia lo protegen solo los Hall (D58). El jog por motor, que no compensa el acople, sigue siendo el `JOG` del firmware, y la URC lo frena antes del límite o de un choque mirando adelante 0,15 y 0,3 s (D70).

**¿Qué pasa en la singularidad del brazo estirado?**
Desde J2 = 0 hay dos soluciones; el codo dobla hacia el lado preferido, J2 negativo. El jog cartesiano nunca cambia de configuración del codo y frena con |J2| de 2°; para cambiarla se usa PTP o jog articular (D31, D75).

**¿Qué guarda un punto de trayectoria?**
La pose en articulaciones, enteras en las unidades del protocolo, que incluye la configuración del codo y las vueltas de J1 y J3. No el camino: lo calcula la URC al reproducir, así que no hace falta «mover bien» con las teclas. Archivo JSON con formato y versión (D13, D62).

**¿Por qué capturar exige el robot quieto?**
Durante el jog, el estado llega cada 50 ms y el robot sigue frenando después de soltar la tecla: el punto capturado no sería donde se detiene (D63).

**¿Se pueden escribir puntos sin jog?**
Sí, en X, Y, Z y rumbo o en J1–J4. Se validan al agregarlos: alcance, límites y choque en reposo (D34, D63).

**¿Qué hace el gestor de trayectorias?**
Lista de puntos con XYZ, rumbo, tipo, velocidad y espera; reordenar, borrar, sobrescribir con la pose actual, «Ir al punto» con confirmación; guardar, cargar y nueva con aviso de cambios sin guardar; play desde el principio o desde el seleccionado, loop, pausa, stop, y validación completa antes de cada play. Es lo útil de AGSABOT más lo que le faltaba (D29).

**¿Con qué velocidad se reproduce cada tramo?**
Cada punto dice cómo se llega a él: tipo, velocidad y espera; nacen LIN, 50 % y 0 s, y se ajustan en el gestor. La velocidad global, de 10 % a 100 %, permite probar despacio. Como en los robots industriales: primero se enseñan posiciones y después se ajustan velocidades (D22).

**¿Cuál es la diferencia entre LIN y PTP?**
En LIN el punto de herramienta sigue una recta, a velocidad constante del extremo. En PTP todas las articulaciones siguen el mismo perfil trapezoidal y llegan a la vez: el camino es una recta en articulaciones (D14, D53, D54).

**¿Qué tan recta es la recta?**
El plan se aparta a lo sumo 0,069 mm: el redondeo a la centésima y la cuerda de cada segmento. La ejecución suma medio paso de M1 y M2, hasta 0,25 mm con 1/8. En Webots, los LIN quedaron dentro de 0,32 mm la estimada y 0,40 mm la física (D54; T2 de la campaña).

**¿Qué pasa si una recta es imposible?**
Se rechaza antes de arrancar, con el tramo, el motivo (alcance, codo, límite, velocidad o colisión), dónde ocurre y qué probar; casi siempre, PTP. El robot nunca arranca un tramo que no puede terminar (D14, D55). Se muestra en la demo.

**¿Y si el robot quedó pegado a la torre? ¿Puede salir?**
Sí. Un PTP que arranca dentro de la zona de margen de un obstáculo se acepta si la separación crece hasta salir de ella y el resto del camino la respeta. Antes, todo camino desde ahí se rechazaba y el robot quedaba encerrado (D71).

**¿Desde dónde arranca la reproducción?**
Desde donde esté el robot. La URC agrega el tramo 0, un PTP al 25 % hasta el punto 1, que no se guarda. Un PTP entre dos poses alcanzables siempre se puede hacer; una recta no (D32, D33).

**¿Cómo no hay huecos ni tirones entre tramos?**
La reproducción es un solo movimiento: el tramo siguiente se encola cuando queda menos de un segundo por enviar, y el firmware los encadena con su reloj. Las esperas son segmentos sin movimiento. En Webots, el loop duró 61,45 s contra 61,46 s planificados (D50, D68).

**¿Cómo funciona la pausa?**
Es el `STOP` con rampa del firmware. Al reanudar, la URC recalcula el resto del tramo desde donde frenó, con el mismo tipo: en un LIN, la misma recta (D52, D69).

**¿Qué diferencia hay entre Stop y Parada inmediata?**
`STOP` frena con rampa y conserva la referencia. `HALT` para en seco y, si había movimiento, borra la referencia, porque parar en seco puede perder pasos. Es la división de GRBL entre *feed hold* y *reset* (D41, D52).

### Fallas y pérdida de pasos

**¿Qué fallas simularon y por qué esas?**
F1 pérdida de pasos, F2 driver sin corriente, F3 Hall trabado, F4 desconexión (watchdog) y F5 reinicio de la UCI. Son fallas que el robot real puede sufrir y casi todas se detectan sin encoders. F6, correa que patina, quedó fuera (D23).

**¿Cómo detectan pasos perdidos sin encoders?**
Con el Hall, que es la única medida absoluta: con el eje referenciado, al entrar en un imán el firmware compara los pasos contados con los del flanco. Si difieren en 2 pasos completos o más, envía `EV LOST j pasos`. No corrige la cuenta: la URC marca la referencia como dudosa y bloquea la reproducción hasta un homing (D65, D68).

**¿Por qué con la corriente nominal no se pierden pasos? ¿Cómo provocan F1?**
Porque los límites dejan margen: el par que piden es al menos la mitad del disponible en M1–M3 (D76). F1 baja la corriente de un driver desde el banco, una falla real de un TB6600 mal regulado: con M4 al 50 %, 5 kg no suben; con M1 al 20 %, el jog que arranca sin rampa pierde pasos, y también la rampa del planificador (D67, D76).

**¿Qué pasa si se corta la comunicación?**
Tres frenos: la página renueva el jog cada 150 ms, la URC lo frena si no se renueva en 500 ms, y el firmware frena si pasa 1 s sin mensajes (D37). F4 corta el enlace sin cerrar la conexión, como un cable desenchufado (D61).

**¿Y si el Arduino se reinicia en medio de un trabajo?**
Arranca sin corriente y sin referencia, y no retoma nada solo (D40). En Webots, el firmware arranca con la primera conexión, como el UNO que se reinicia al abrir el puerto, y no se reinicia si después se corta la red: así un corte no hace perder una referencia válida (D36). La URC, al leer el `BOOT`, descarta todo y lo avisa como F5 si llega a mitad de una conexión (D43). La reproducción se detiene y no se puede dar play hasta referenciar.

**¿Por qué sin corriente se pierde la referencia?**
Un paso a paso sin corriente gira libre: J4 cae y cualquier eje se puede mover a mano sin que el firmware cuente. En la planta, al volver la corriente el motor retiene el eje donde quedó, y lo que se movió no lo sabe nadie (D40, D60).

### Proceso y validación

**¿Cómo validaron todo esto?**
En tres niveles: el firmware por su protocolo, en la PC; la URC por sus dos bordes, con una UCI falsa y por HTTP; y escenarios en Webots, corridos por un solo ejecutor que registra el commit y el SHA-256 del controlador, del mundo, del proto y de las demos (D39, D42, D73). La suite corre sin Webots en cada cambio, e incluye las tres demos (D74).

**¿Funciona en Windows? ¿En Mac?**
En Windows 11, compila con el `g++` que trae Webots R2025a, sin instalar nada (D19). macOS queda pendiente de verificar.

**¿Qué pasó con el banco viejo `scara-dev/1`?**
Se construyó el camino nuevo al lado y se retiró cuando funcionó (D16). Sus documentos y evidencia pasan a histórico, sin alterar bytes, y no se citan como prueba del sistema nuevo (D25).

**¿Por qué un maestro v2 y no corregir el v1?**
El v1 se conserva sin cambios; el v2 es Markdown en el repo, exportado a PDF, con enlaces a los ADR (D17).

## 5. Material de estudio

### 5.1 Arquitectura

```text
navegador ──HTTP 8766──► URC (urc/, Python, en la PC)
                           │  planifica: inversa, LIN, PTP, jog verificado, validación
                           │
                           ├──TCP 9000, scara/1──► UCI ─ firmware (firmware/, C++)
                           │                        │   cola de segmentos, pasos, homing, watchdog
                           │                        └─ capa de hardware
                           │                             Arduino UNO: pines, Timer1, serie (+ socat)
                           │                             Webots: socket, planta simulada (motores N1/N2, Hall)
                           │
                           └──TCP 9001, scara-sim/1──► banco de ensayo (solo simulación): verdad, fallas, carga
```

Ideas que hay que poder explicar sin mirar:

- **La URC planifica y el firmware ejecuta** (D6, ADR 0005). La URC envía `SEG n ms q1 q2 q3 q4`; el firmware responde `OK n` cuando el segmento entró en la cola de 16, y lo ejecuta con su reloj, interpolando lineal en articulaciones. Un `SEG` sin confirmar por vez: la URC nunca desborda la cola (D50).
- **Un único firmware** (D3, ADR 0002). El núcleo no usa memoria dinámica ni flotantes en la interrupción de pasos, y se prueba en la PC con conversaciones de conformidad (D39).
- **Lo que sabe el robot y lo que sabe el simulador.** La posición estimada por pasos es lo que cree el firmware; la posición física simulada es la verdad del simulador, que solo ve el banco de ensayo (ADR 0004). Capturar y planificar usan siempre la estimada, como con el robot real.
- **El firmware defiende a los motores, la URC al robot.** El firmware verifica corriente, referencia y velocidad de cada motor por segmento (D51); la URC verifica límites, alcance, codo y choques antes de enviar (D55).

### 5.2 Acople M1/M2

Transmisión (maestro v2, sección 4): M1 → 20T/80T → tubo exterior del brazo (J1). M2 → 20T/80T → eje interior → 60T/60T a lo largo del brazo → antebrazo. M3 → 20T/80T en la muñeca. M4 → varilla ACME de 8 mm por vuelta.

```text
J1 = θM1 / 4
J2 = (θM2 − θM1) / 4        porque J1 + J2 = θM2 / 4: M2 fija el ángulo absoluto del antebrazo
J3 = θM3 / 4
J4 = 8 mm · vueltas de M4
rumbo = J1 + J2 + J3 = (θM2 + θM3) / 4
```

Consecuencias que se demuestran:

1. **Mover solo J1:** M1 y M2 dan la misma cantidad de pasos. El jog articular lo hace el firmware (D5).
2. **Mover solo M1:** el brazo gira, el antebrazo conserva su orientación en el mundo, J2 cambia al revés que J1 y el rumbo no cambia (D46). En Webots: J1 +6,24° y J2 −6,24° (P2).
3. **M2 es el motor más exigido:** recorre J1 + J2. Con M1 y M2 a 360 °/s en su eje, J1 llega a 90 °/s, y si J1 gira a 90 °/s, J2 puede ir de 0 a −180 °/s. El planificador lo valida en cada segmento (D45, D53, D76).
4. **Con 1/8:** 17,78 pulsos por grado en J1–J3, 200 por mm en J4. En enteros: 8 pasos cada 45 centésimas de grado (D44).

### 5.3 Homing

```text
reposo ─► J4 arriba ─► J1 negativo (M1+M2) ─► J2 negativo (M2) ─► J3 negativo (M3) ─► PTP al reposo
```

En cada eje (D56, D72):

1. Si el Hall ya está activo, sale del imán a 1 °/s.
2. Busca rápido: 15 °/s en J1–J3, 10 mm/s en J4.
3. Retrocede a 1 °/s hasta que el Hall se apaga, y 3° (3 mm) más.
4. Vuelve a 1 °/s al mismo flanco: esa es la referencia. `EV HOMED j`.

Flancos (parámetro provisional, `HALL_EDGE` en `firmware/config.h`): J1 y J2 en −130°, J3 en −145°, J4 a 3 mm de arriba. El imán está centrado en el extremo con ±5° de zona activa: el flanco queda 5° antes del tope.

Qué tiene que poder responderse:

- **Por qué lento y desde el mismo lado:** repetibilidad; no depende de la velocidad ni del lado de llegada.
- **Por qué la URC vuelve al reposo y no el firmware:** es un PTP verificado contra choques desde una pose plegada; no se agrega un generador de trayectorias al UNO (D56).
- **Por qué el homing se puede repetir después de frenarlo:** con `STOP` no se pierden pasos, así que el firmware recuerda qué ejes tienen una cuenta que sale de una referencia (D72).
- **Referencia dudosa contra referencia perdida:** dudosa es después de un `EV LOST` (el robot sigue referenciado, pero conviene un homing); perdida es después de un `BOOT`, `DISABLE` o `HALT` en movimiento (glosario; D40, D41, D65).

### 5.4 Pérdida de pasos

**El modelo N2** (D64, ADR 0006). Cada motor es una inercia que sigue a los pulsos con la curva par–ángulo: T = T(ω) · sen(π/2 · e / paso completo), donde e es el atraso y T(ω) la curva par–velocidad (plana hasta la velocidad de esquina, después cae como 1/ω). Con un paso completo de atraso da su par máximo; con dos, medio ciclo eléctrico, cae al equilibrio siguiente y **pierde cuatro pasos completos**. El firmware sigue contando los pulsos que emitió: no se entera.

**La detección** (D65). El Hall es la única medida absoluta. Con el eje referenciado, al entrar en un imán el firmware compara la cuenta con el flanco esperado. Dos pasos completos de tolerancia: la mitad de lo mínimo que se pierde, y más que el error de leer el Hall en movimiento. `EV LOST j pasos`, en pasos completos para no depender del microstepping.

**Por qué no corrige la cuenta:** escondería la falla con una medida menos precisa que la del homing. Frenar es decisión de la URC: si llega en plena reproducción, la detiene (D65, D68).

**Cómo se detecta cada falla sin encoders** (maestro v2, sección 7):

| Falla | Se detecta por | En la demo |
| --- | --- | --- |
| F1 pérdida de pasos | `EV LOST` al cruzar un Hall | M4 al 50 % con 5 kg; `EV LOST 4` al estacionar |
| F2 driver sin corriente | Nada, hasta el próximo Hall: J4 cae y la estimada no cambia | Solo se ve en «Simulado» |
| F3 Hall trabado | El homing aborta: `ERR 11` o `ERR 12` | J1 `inactivo` |
| F4 enlace cortado | El watchdog del firmware, 1 s sin mensajes | Jog de J1 sin referencia |
| F5 reinicio de la UCI | `BOOT` a mitad de la conexión | Desde el banco |

### 5.5 Qué no prometemos

Para el cierre y para cualquier pregunta sobre precisión:

- Todo es el diseño simulado: los parámetros son provisionales y no hay mediciones (ADR 0001).
- Medio milímetro es la resolución ordenada con 1/8, no la precisión del robot: esa depende del par, la carga y las correas (D9).
- Las hojas de datos exactas de los motores no aparecieron: N2 usa la familia más cercana y supuestos declarados (D64).
- No se probó con la placa ni en macOS (D19, D49).
- La ubicación de los Hall y el microstepping son propuestas al profesor (D9, D10).

## 6. Si algo sale mal

| Síntoma | Qué hacer |
| --- | --- |
| No aparece el banco de ensayo | El controlador es anterior al canal: compilarlo de nuevo (sección 1) y **Reload World** en Webots |
| Webots no se conecta | ¿Está la URC levantada en el 9000? ¿Hay otra URC u otro Webots abierto? |
| Homing aborta sin falla inyectada | Revisar que F3 esté en `libre` en los cuatro ejes; repetir el homing (D72). Si no, **«Referencia manual…»** |
| «Para reproducir, el robot tiene que estar referenciado» | Hacer homing. Con referencia dudosa (F1), también |
| Un tramo se rechaza | Leer el motivo: lo dice el tramo y qué probar (D55) |
| El robot quedó en una pose rara | **«Estacionar…»**; si no hay referencia, jog articular lento hasta la pose de reposo y homing |
| Todo trabado | **«Recargar el mundo…»** en el banco: la UCI arranca de nuevo, sin referencia |
