# Checkpoint vigente del proyecto SCARA

**Continuación 16/10 — punto 3 completado:** se recuperaron las tres geometrías pendientes. El [consolidado vigente](../validation/cad_recovery.json) verifica 30 instancias con malla y cero referencias alámbricas, 47 STL aceptados/3 rechazos, propiedades de 49 tipos/51 sólidos y 30/30 instancias. Pasaron 30 pruebas Python, 15 comprobaciones de recuperación, auditoría de 22 BREP móviles y regresiones nativas CAD (330 comparaciones/seis llegadas) y colisiones (cinco comprobaciones). Configuración física y 152 originales intactos; las otras 47 entradas del lote son idénticas. El [diagnóstico](RECUPERACION_GEOMETRIAS.md) detalla reproducción y contraste alternativo opcional. El snapshot anterior está en `validation/historico/antes_geometrias_20261016/`.

Actualizado el **16/10/2026 al diagnosticar y reducir la oscilación del tope J4**, después de los puntos1–2 de propiedades y colisiones. Trabajo guardado en `/Users/mateoantenucci/Developer/SCARA`, sin Git inicializado, commits ni PR. Originales conservados; ningún CAD enviado a servicios externos.

Leer primero [Proceso y archivos](PROCESO_Y_ARCHIVOS.md) y [README](../README.md). No rehacer conversiones ni entrevista. **Ahora el CAD parcial sí está integrado en la cadena móvil.** El gemelo fiel completo sigue pendiente de revisión mecánica, geometrías y datos físicos/protocolo.

## Usuario y decisiones aceptadas

- Principiante absoluto. Explicar desde cero, resolver tareas técnicas rutinarias y pedir ayuda solo para información o acciones que realmente no podamos obtener.
- Todo desarrollo debe quedar documentado: propósito, método, archivos para explorar, reproducción, comprobaciones y datos/supuestos pendientes, de manera aprovechable para el informe de la materia. Preferencia reiterada el 15/10; no limitarse al mensaje final del chat.
- Entorno actual declarado el 15/10: **Webots R2025b nightly por problemas de R2025a en macOS 27**. No atribuir una build exacta a la instalación actual sin inspeccionarla; la sección de Webots conserva la evidencia histórica.
- No existe robot físico ni hardware. Se simula el diseño para docencia y construcción futura, sin prometer precisión experimental ni electrónica completa.
- Q1–Q5 aceptadas: CAD, cinemática, masas/inercias con procedencia, esfuerzo finito, TCP/IP, fallas e interfaz externa mínima. Sin fecha ni automatización solicitada.
- Movimiento suave articular punto a punto a XYZ; orientación opcional conserva rumbo sin vueltas completas accidentales. No garantiza línea cartesiana recta; primera versión sin pinza.
- Rechazo previo por alcance/límites; detener y exigir rearme tras falla/desconexión, sin repetir órdenes. No garantiza sostén si falta esfuerzo ni prevención general de colisiones.
- Protocolo del profesor NO entregado. `scara-dev/1` es JSON por línea sobre TCP local de desarrollo. Adaptar cuando llegue el contrato oficial.
- Pérdida de fuerza, atasco y desprendimiento son distintos. Los dos últimos no están implementados ni se fingen ocultando mallas.

## Resultado concreto y evidencia

1. **CAD articulado parcial: 30 instancias**, 30 con geometría aceptada y ninguna caja alámbrica magenta. Cinco grupos: base8, brazo6, antebrazo8, muñeca6, herramienta2; cuatro ejes R-R-R-P. Una instancia de torre usa sus tres cuerpos recuperados.
2. **30 pruebas Python aprobadas con OCP**, incluidas16 del banco, cinco de propiedades CAD y nueve de colisiones. Sin OCP se omiten tres y corren27. La integración incluye30 configuraciones aleatorias. El test TCP necesita permiso de loopback bajo sandbox; evidencia actual en `validation/cad_recovery.json`; `j4_tests.json` y `collision_tests.json` son anteriores.
3. **Once estados CAD en Webots nativo: 330 comparaciones de colocación y seis llegadas articulares aprobadas.** `validation/cad_motion.json`; `tools/check_cad_motion.py`. Comprueba pose guardada, regreso, cada eje por separado y cuerpos anteriores inmóviles. Error máximo de colocación ~0,0257 mm dentro del solver, no precisión física del robot.
4. **Nueve escenarios nativos de movimiento/fallas aprobados con CAD**, 137 eventos: `validation/simulation.json`; `tools/check_simulation.py`. Movimiento XYZ/rumbo, rechazo, Hall/rearme, carga e inercia efectiva, caída por pérdida de fuerza, sobrecarga, desconexión sin repetición y reinicio.
5. **Navegador → HTTP → Python/IK → TCP → Webots aprobado con CAD actual**: ida a (240,250,35) mm, vuelta a (250,250,34,67) mm, reinicio con nueva `trial_id`, STOPPED, carga0 y referencia válida. `validation/client_native.json`; ambos errores <0,025 mm dentro del simulador. Aviso final verificado en pantalla.
6. **Proceso, mapa de archivos y base del informe**: `docs/PROCESO_Y_ARCHIVOS.md`. Criterios geométricos: `docs/INTEGRACION_CAD_CRITERIOS.md`. Consultas concretas en `docs/DATOS_PARA_EL_PROFESOR.md`; no se enviaron.
7. Evidencia y fuentes del banco anterior de cajas conservadas en `validation/historico/banco_cajas/`, con estructura de rutas original. Los tres JSON de validación de la raíz corresponden al CAD actual.
8. **Punto 1 completado como precálculo, sin activar física nueva:** `tools/calcular_propiedades_cad.py` y `cad/propiedades/propiedades_geometricas.json`/`.csv`: 49 tipos, 51 sólidos, 30/30 instancias, cinco sumas por grupo de referencia. Solo B-ExtensorM3 excluido; torre y Z-BujeInterior tienen BREP válido aunque fallen sus STL. Método, unidades, transformaciones y transición física en `docs/PROPIEDADES_GEOMETRICAS_CAD.md`. Los 50 originales contienen la etiqueta de material sin especificar; no se asignó densidad. Los 217 archivos protegidos conservaron sus hashes en el cálculo.
9. **Cinco comprobaciones nuevas de propiedades CAD** en `tests/test_cad_properties.py`: caja analítica desplazada, integración Gauss independiente, compound OCCT transformado, rechazo de cara abierta y entradas sin volumen/no rígidas. Requieren OCP para tres de ellas; dos corren con el Python del banco. La suite completa aprobó 21/21 con OCP. Un contraste independiente sobre los BREP colocados de los cinco grupos reales concordó con error relativo máximo del tensor 7,30×10⁻¹⁵. Evidencia, hashes y log en `validation/cad_properties.json`. No se repitieron ensayos nativos de Webots ni se cambió su física.
10. **Punto 2, revisión inicial de pedestal/piso:** once poses y 19 BREP móviles válidos; cuatro invasiones CAD confirmadas, incluida una trayectoria con extremos libres y punto medio invasivo. `tools/check_collisions.py` → `validation/collisions.json`. Se centralizó el entorno en `config/scara.json`; se sustituyeron cinco cajas globales por 30 cajas de pieza en `Group`, conservando cajas de tres piezas pendientes. Masas e inercias exploratorias intactas.
11. **Rechazo continuo nominal:** `scara/collisions.py` acota todo q(s) del perfil común con cajas en el punto medio y cota de desplazamiento; margen1mm y resolución0,25mm. Rechaza si agota4096intervalos o precisión numérica, para evitar bloqueo con resolución impracticable. Runtime valida antes de mutar, Bridge antes de encolar; también valida cambio de carga de ensayo. No busca caminos alternativos ni cubre autocolisiones, seguimiento físico, cables/piezas omitidas u obstáculos sin configurar. Carga cúbica solo reserva geométrica del guard; no nueva caja física de carga.
12. **Cinco casos nativos de colisión aprobados** en `validation/collisions_native.json`: 30 cajas efectivas, rechazo de destino, rechazo de cruce intermedio, caída contra pedestal y reset. J4 en la caída≈94,677mm, TCP≈−0,0294mm y cuatro puntos de contacto Z≈0; esfuerzo0/referencia inválida. El caso intermedio nativo usa119mm para aislar la oscilación del tope; CAD offline conserva120mm.
13. **Problema registrado el15/10, diagnosticado el16/10:** la orden exacta J4=120mm producía oscilación persistente de≈11mm. La repetición en cada paso físico de16ms confirma error10,904553mm y amplitud10,997025mm. El código de la build y experimentos de una variable apuntan a la interacción motor energizado/tope ODE y paso temporal. Se conservan fallo y variantes; ver `docs/DIAGNOSTICO_TOPE_J4.md`.
14. **Regresiones nativas de la revisión del15/10 aprobadas:** `validation/simulation_collisions.json` nueve escenarios; `validation/cad_motion_collisions.json` once estados/330 comparaciones y seis llegadas. Sus hashes describen la revisión previa de16ms, conservada en el snapshot del16/10. `validation/collisions_before_after.json` confirma aceptación anterior/rechazo de dos casos al agregar el guard. `validation/collisions_execution.json` identifica esa copia y ejecutable históricos.
15. **Corrección numérica del16/10:** `simulation.basic_time_step_ms=2` en configuración y `WorldInfo` generado. Conserva carrera0–120mm, topes, geometría, masas, inercias, esfuerzo, aceleración, PID y amortiguación. No se adoptó el desplazamiento experimental del tope a121mm. El costo local aumentó; sonda documentada en `j4_timestep_cost.json`.
16. **Quince escenarios de sostén aprobados:** `j4_stops_after_initial.json`, `j4_stops_after_folded.json`, `j4_stops_after_payload025.json`, cadauno cinco destinos y1000 pasos físicos de2ms por ventana. Error máximo sin carga0,174002mm, amplitud0,174032mm; carga0,25kg:0,040870/0,040892mm. Todas las lecturas finitas, consigna fija y muestras de un único ensayo. La oscilación grande queda corregida dentro del criterio0,5mm; no se afirma residuo cero ni fidelidad real.
17. **Regresiones del16/10 aprobadas:** `collisions_native_j4.json` cinco casos (vuelve a120mm), `simulation_j4.json` nueve escenarios y `cad_motion_j4.json` once estados/330comparaciones/seis llegadas. `j4_diagnosis.json` verifica identidad y hashes finales. Snapshot `validation/historico/antes_tope_j4_20261016/` conserva29archivos del estado anterior. Los informes del15/10 son históricos y sus hashes de configuración/mundo ya no describen la revisión actual.

Captura nativa completa: [scara_cad_articulado.png](../validation/scara_cad_articulado.png). Se cerró la consola para aumentar la altura visible; no se modificó ni guardó la cámara/mundo mediante la UI. La vista estática anterior conserva su captura y mundo separados.

## Mundos y regeneración

| Archivo | Función |
| --- | --- |
| `webots/worlds/scara.wbt` | CAD parcial articulado, física provisional, controlador, interfaz y fallas. Abrir este para mover. |
| `webots/protos/SCARA.proto` | Robot reutilizable: mallas como visuales dentro de cuerpos, cuatro juntas/motores, cajas de colisión y Physics. Generado. |
| `webots/worlds/scara_cad_inspeccion.wbt` | Inspección estática de20 instancias:17congeometría+3referencias; sin motores/física. Pose guardada con torre arriba, no cero del robot. |

Fuentes de integración: `config/cad_integration.json` (agrupación y convenciones) y `cad/ensambles/informe.json`/`registro_subensambles.json` (colocaciones y procedencia). El manifiesto generado es `cad/ensambles/integracion_articulada.json`. No editar generados a mano.

```sh
python3 tools/integrate_cad.py --update-config
python3 tools/generate_world.py
```

El primer comando recalcula geometría/cajas y conserva masas, esfuerzos y límites. El segundo exige coherencia con el manifiesto. Si solo cambian parámetros físicos se ejecuta el segundo. Cerrar Webots antes, reiniciar cliente y repetir comprobaciones pertinentes después.

## CAD: procedimiento y decisiones resueltas

- Originales:50SLDPRT,10SLDASM,44SLDDRW,46PDF,3STL,1Gcode. Las 50piezas dieron50STEP enmm y47STL enmetros aceptados;3rechazos globales y21piezasaceptadasconadvertencias. La revisión 44+6 queda archivada y sus otras47entradas se conservaron idénticas.
- `sldprt2step` fijado a `fa954124f4f126e0c465c8f96454978ac80b812e`, con parches MiniFAT y precisión de intersecciones; OpenCascade/OCP sin VTK para teselar. No hicieron falta SolidWorks, CadQuery completo ni Blender. Versiones/licencias/reportes en `docs/EVALUACION_CONVERSION_CAD.md` y `tools/requirements-cad.txt`.
- Torre:3cuerpos exportados aparte, retirando solo8triángulos de área exactamente0 del cuerpo3. Cada malla cerrada individualmente, registros restantes/bbox/volumen sin cambios; no certifica unión global. `tools/exportar_torre_cuerpos.py`, `cad/derivados/torre_por_cuerpos/`.
- XML `COMPINSTANCETREE__ZLB` recuperó106instancias/47tipos de pieza de10ensambles. Las bbox guardadas se reproducen a precisión numérica. Es un caché de colocación, no restricciones reconstruidas ni garantía de revisión actual.
- Ejes cilíndricos cruzados entre piezas sustentan J1–J2=250mm y J2–J3=250mm. No pedir medir otra vez esas longitudes. Puntos sobre líneas no fijan ceros/anchors únicos/TCP.
- `tools/registrar_subensambles.py`:22candidatos registrados, usando piezas compartidas y verificaciones de múltiples anchors/revisión cuando existen. No asigna automáticamente cuerpos rígidos.
- Se seleccionaron explícitamente10montajes extra (6base,2brazo,2antebrazo). Otros12candidatos y5tipos ambiguos se retuvieron sin colocarlos ciegamente. NEMA23 se usa como carcasa visual completa; rotor/eje interno no animados.
- Carreteles: AInf→base/ASup→brazo; BSup→brazo/BInf→antebrazo; RInf→antebrazo/RSup→muñeca. Hay evidencia de caras/diámetros/coaxialidad, pero fase angular y fijación requieren confirmar. Asignación visual reversible; no demuestra transmisión completa ni relación motor→junta.
- Las tres referencias B-CarretelInf, B-CarretelSup y Z-SoporteEfector ya usan mallas cerradas validadas; no quedan referencias magenta en los mundos regenerados. NEMA17x2 y R-CarretelSup se ven ámbar por bbox/revisión discrepante. No estirar piezas para ocultar diferencias.
- Otras geometrías rechazadas del lote: B-ExtensorM3 y Z-BujeInterior. Torre tiene recuperación separada; la recuperación separada no acepta su malla global; el lote vigente es47+3.

## Marcos de coordenadas y física actual

`scara/frames.py` calcula transformaciones. `tools/integrate_cad.py` pone la torre vertical, alinea J1→J2 con+X y expresa cada pieza en el cuerpo móvil al que pertenece. En la pose de referencia se reconstruyen las colocaciones guardadas. Las mallas conservan origen y escala; se trasladan mediante Pose, sin hornear ni degradar otra vez los STL.

- L1=L2≈0,250m; shoulder_z=0,2913625m; elbow_z_offset=−0,078m; tool_z_offset≈−0,1186956411352m. Son marcos de simulación derivados del montaje seleccionado, no cotas maestras certificadas.
- Pose CAD guardada: `q ≈ [0, 0.0415858179222, 0.0722365244058, 0.06]` en radianes y metros. J4=60mm y rumbo de herramienta son convenciones reversibles.
- Pose inicial de uso: q=[0,π/2,−π/2,0.06]; TCP≈(250,250,34,6668589)mm, rumbo0. No es homing físico.
- Cada grupo móvil tiene una sola masa/Physics; las mallas visuales no duplican masa. Colisiones=Group de cajas por pieza (30totales), inercias=cajas equivalentes anteriores y masas provisionales0,30/0,50/0,35/0,15kg. Base fija sinPhysics. `selfCollision FALSE`.
- Motores genéricos con esfuerzo finito0,8/0,8/0,3Nm y8N. Velocidad/aceleración/transmisiones/materiales no certificados; no simulan automáticamente electrónica stepper ni pérdida de pasos.
- `scara/kinematics.py`: FK/IK, ambas ramas, solución cercana, perfil quintico y rumbo no envuelto cuando se omite yaw. `dynamics.py`: carga cúbica40mm y ejes paralelos. `runtime.py`: STOPPED/IDLE/MOVING/FAULT. `estimated` es referencia ideal, no modelo de conteo de pasos.
- `completed` termina consignas; solo instrumentación separada evalúa llegada. `tcp_world`, `tcp_world_yaw`, `tool_physics`, sensores internos e `inspect_cad` son instrumentación, no encoders físicos ocultos para control.
- `inspect_cad` obtiene matrices reales de30Pose en5mensajes del mismo paso; no fuerza colocaciones. `trial_id` cambia al arrancar el controlador y permite comprobar recarga incluso enFast.
- `transport.py` atiende TCP no bloqueante, máximo16KiB y descarta órdenes al perder sesión. La pausa de Webots detiene atenciónTCP. No hay heartbeat final.
- Pérdida de esfuerzo queda retenida e invalida referencia; limpiar no la recupera. Sobrecarga compara masa de ensayo conocida con8N, aplica masa sin quitar esfuerzo e invalida referencia; rechaza cambiar carga/rearmar hasta reset. No es diagnóstico con sensores inexistentes.
- Carga0,25kg→masa móvil0,40kg→sostén3,924N; quitar fuerza produce caída~60mm. Añadir1kg produce caída~60mm manteniendo8N. J1feedback=null con esta base fija.
- `reset_trial` recarga mundo, no hace homing. Physics de herramienta se expone mediante camposIS delPROTO para modificación/lectura real.
- Guard continuo contra pedestal/piso sobre las consignas ideales. Sin planner de desvíos, autocolisiones ni prueba exhaustiva del diseño. Los volúmenes son aproximados; no certificar seguridad física general. Hall aún lógicos provisionales.

## Webots en este Mac

**Uso actual declarado el 15/10/2026: R2025b nightly, por fallas de R2025a en macOS 27.** El cálculo geométrico no necesitó abrir Webots ni inspeccionar su build. La información siguiente es el registro histórico de la instalación y copia temporal ensayadas el 14/10; verificar rutas/build antes de otro ensayo.

Instalación detectada el 14/10: `/Applications/Webots.app` R2025a. macOS 27.0.1/Apple Silicon producía error falso de puertos ocupados incluso en --help. Bug oficial https://github.com/cyberbotics/webots/issues/6976 y corrección https://github.com/cyberbotics/webots/pull/7032 . No confundirlo con defecto del mundo.

Se usa copia oficial temporal sin reemplazar aplicación ni desactivar Gatekeeper:

- DMG: `/private/tmp/scara-webots-nightly-20261014/webots-R2025b.dmg`.
- URL: https://github.com/cyberbotics/webots/releases/download/nightly_13_10_2026/webots-R2025b.dmg
- 107171223 bytes; SHA-256 `37e40c7b2e456b56f161b54c846c425fa31fde145d8e165d09b12aff70c11ab6`.
- Tag repo: `303f6bc2af6b241098d2773cd3f9ae507187f2ef`; **build real en título de ventana**: `a459c02c7292d23ae437101c76111ec1668198c8`. No confundirlos.
- Montaje readonly: `/private/tmp/scara-webots-nightly-20261014/mount`. Codesign deep/strict pasó, --help y ejecución nativa pasaron. No reemplazar instalado sin necesidad.

Si está desmontado:

```sh
hdiutil attach -nobrowse -readonly \
  -mountpoint /private/tmp/scara-webots-nightly-20261014/mount \
  /private/tmp/scara-webots-nightly-20261014/webots-R2025b.dmg
```

Para iniciar el banco:

```sh
/private/tmp/scara-webots-nightly-20261014/mount/Webots.app/Contents/MacOS/webots \
  --batch --mode=realtime --stdout --stderr --port=19000 \
  /Users/mateoantenucci/Developer/SCARA/webots/worlds/scara.wbt
python3 -m client.app
```

Son dos procesos: usar dos terminales, no esperar ejecutar el segundo tras un proceso que sigue abierto. La interfaz está en http://127.0.0.1:8765 . Python/controller usan solo stdlib. No instalar un paquete pip llamado controller.

Los tests TCP y Webots nativo necesitaron escalación de herramientas por sandbox (bind local/Qt); las autorizaciones se aprobaron automáticamente. Un PermissionError en bind bajo sandbox no prueba un bug del proyecto. El renderer avisa de textura/efectos de GPU Apple; no se cambiaron preferencias globales para silenciarlo.

## Estado operativo al cerrar la integración anterior — 14/10

Este estado no se reinspeccionó durante el cálculo del 15/10; no se movió ni recargó el simulador. Las sesiones siguientes son históricas y pueden haber caducado.

- Webots dinámico: sesión de herramienta `26439`, `scara.wbt` en **Real-time**, controlador STOPPED, pose inicial, carga0, referencia válida. El ensayo corre para atender TCP, movimiento deshabilitado.
- Cliente HTTP actual: sesión `20315`, localhost:8765, conectado aTCP9000 y configuración CAD actual. Pestaña3 del navegador interno marcada entregable.
- Se cerró una instancia anterior de `client.app` que reconectaba y ocupaba el únicoTCP; se reinició con configuración nueva. Si se repiten pruebas, comprobar que no quede otro cliente reconectando.
- DMG sigue montado para esa copia deWebots. No desmontar mientras se use. No hay pruebas/agentes de fondo ni automatizaciones.
- Sesiones/pestañas pueden caducar. Verificar antes de iniciar otra instancia. Cerrar cliente conCtrl+C yWebots cuando se termine de usar.

## Reproducción y próximos pasos

**Estado al cerrar el16/10:** instalación actual `/Applications/WebotsB.app`, misma builda459c02… comprobada con `--version`. Había una copia abierta desde `/private/tmp/scara-colisiones-native-20261015`, controladorTCP19001; no se conectó ni movió. No se detectaron cliente8765 ni controlador9000. El diagnóstico usó una copia distinta `/private/tmp/scara-tope-j4-20261016`, controlador19011/aplicación19013; terminóSTOPPED, pose inicial, carga0 y referencia válida, y se cerró. El mundo raíz guardado usa2ms; la copia abierta anterior conserva su versión hasta recarga/regeneración. El resumen `validation/j4_diagnosis.json` guarda hashes, identidad y resultados. No quedaron ensayos nuevos en ejecución ni automatizaciones.

Estado histórico al cerrar el punto2 del15/10: se dejó la sesión original sin mover/recargar, entonces Webots2.app con mundo raízTCP9000 y clienteHTTP8765. Las pruebas se hicieron en `/private/tmp/scara-colisiones-native-20261015`, TCP19001/aplicación19003. Las sesiones pueden cambiar entre días; prevalece la inspección del16/10 anterior. La build comprobada es **R2025b Nightly Build14/10/2026 a459c02c7292d23ae437101c76111ec1668198c8**.

Los **puntos1–2 y el diagnóstico del tope J4 tienen resultados documentados**: [propiedades](PROPIEDADES_GEOMETRICAS_CAD.md), [colisiones/recorridos](COLISIONES_Y_RECORRIDOS.md) y [sostén J4](DIAGNOSTICO_TOPE_J4.md). El punto2 cubre pedestal/piso y referencia nominal; permanecen autocolisiones, CAD/materiales/transmisiones y protocolo incompletos. La oscilación del tope cumple ahora el criterio numérico declarado. No rehacer conversiones. El punto3 de las mallas pendientes no se inició.

- PythonCAD temporal: `/private/tmp/scara-cad-piloto-20261014/venv/bin/python`3.12; upstream `/private/tmp/scara-cad-piloto-20261014/sldprt2step-fa954124f4f126e0c465c8f96454978ac80b812e`. Si caduca, recrear según evaluación; no reconvertir artefactos innecesariamente. Python3.9 de sistema sirve para simulación/interfaz.
- Pruebas: `python3 -m unittest discover -v`. Para pruebas nativas cerrar el cliente de esa sesión, dejar Webots reproduciendo; Fast conserva el paso físico configurado, ahora2ms, y el reloj simulado para la dinámica. Para preservar trabajo usar otra copia y puertos, según diagnóstico J4.
- Precálculo: `/private/tmp/scara-cad-piloto-20261014/venv/bin/python tools/calcular_propiedades_cad.py --output /tmp/scara-propiedades-repeticion`. Pruebas completas con OCP: ese mismo Python con `-m unittest discover -v`. El Python sin OCP omite tres pruebas geométricas; no confundir omisión con validación CAD.

```sh
python3 tools/check_cad_motion.py --webots-version "compilación real" --output validation/cad-local.json
python3 tools/check_simulation.py --webots-version "compilación real" --output validation/simulation-local.json
```

Los scripts mueven, cargan/fallan y recargan mundo. No ejecutarlos contra hardware. EnFast la recarga se comprueba por nueva `trial_id` y estado, no por tiempo<10s. El registro de órdenes copia el JSON realmente serializado para no alterarlo al mutar listas de Python. Todos los hashes de los tres informes coincidían al cierre; repetir si cambia código,configuración oCAD.

Próximo trabajo autónomo: revisar interferencias internas y añadir componentes con colocación sustentada, según el orden acordado. El punto3 de geometrías visibles quedó completado. Reconstruir piezas solo con colocación/revisión sustentada. Al cambiar masas/esfuerzos/PID/topes/build repetir `tools/check_joint_stops.py` y regresiones pertinentes. Las propiedades geométricas están preparadas para materiales/modelos comerciales; no copiar sumas a densidad común como física multimaterial. No hace falta intervención externa para iniciar esos diagnósticos.

Intervención externa real: revisión oficial coherente; contraste independiente opcional de las tres geometrías recuperadas; transmisión/fijaciones/fases; materiales/piezas comerciales; curvas/configuración motor; Hall/homing y TCP oficial; protocolo y criterios docentes. Ver `DATOS_PARA_EL_PROFESOR.md`. No enviar mensajes sin autorización explícita.

Luego incorporar protocolo oficial cuando exista; definir alcance de homing, pasos/atasco/desprendimiento y repetir enWindows/Linux. No declarar completos esos puntos ni fidelidad física por haber importado mallas.
