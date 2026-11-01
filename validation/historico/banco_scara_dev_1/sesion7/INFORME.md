# Sesión 7 · demo renderizada del paquete final

El 17/10/2026 se observó el guion autorizado completo en **Chrome y una ventana real de Webots**, sobre extracción limpia de `validation/sesion5/SCARA-ejecucion.zip`. Los ocho pasos pasaron; no se reprodujeron defectos de producto ni se modificaron fuentes. Estado final **STOPPED**, sin carga y con referencia de simulación válida. Candidato sujeto a revisión independiente de sesión 9.

## Identidad y entorno

- ZIP SHA-256 `eaea37ceab2c47340a0b02308df7c976cd2925b82bae6078ed55ccff665ab3ce`, 52 archivos. [Identidades](identidad.json): todos conservaron su hash después del uso; los 51 que existen también en el proyecto común coincidieron con sus fuentes (el restante es LEEME del paquete).
- Webots **R2025b Nightly Build 14/10/2026 `a459c02c7292d23ae437101c76111ec1668198c8`**, macOS 27.0.1 arm64, build 26A434. Cliente Python 3.15.0; controlador Python 3.9.6 del Command Line Tools. La versión Chrome está en [informe.json](informe.json).
- Ejecutable Webots SHA-256 `ffd0f55a57162289c4ee00049d824549572f1fa336f032d6a8a0d9c7e95f677f`.
- Había un Webots ajeno abierto en `/private/tmp/scara-transmision-native-20261017`, TCP 19051. CUA macOS elegía ese proceso por bundle ID y no exponía selector PID/ventana. Para preservar esa instancia se clonó el app instalado a la copia temporal de sesión 7 y se cambiaron **solamente** `CFBundleIdentifier=local.scara.sesion7.webots` y `CFBundleName=Webots Sesion7` de su Info.plist. Ejecutables original/copia idénticos; app instalado y producto intactos. El título nativo conserva el build real. Esta es una adaptación de observabilidad, no otra versión del simulador.

La ejecución propia usó un único cliente en HTTP 8765, un único controlador TCP 9000 y un único mundo propio, renderizado en tiempo real; puerto administrativo Webots 1237. El mundo ajeno 19051 no participó ni recibió acciones. El ensayo de movimiento y el de Hall comenzaron con recargas limpias distintas y carga 0 kg.

## Recorrido y resultado

| Paso observado | Resultado y relación con controlador/simulador | Evidencia |
| --- | --- | --- |
| Conectar; reiniciar; habilitar | «TCP conectado»/«Detenido» al conectar, sin habilitación automática. Tras reset `78812365`, habilitación `2bc048b0` dio `IDLE`/«En espera». Consola Webots: servidor 127.0.0.1:9000. | [Conectado](capturas/01_conectado.png), [Webots inicial](capturas/02_webots_inicial.png), [habilitado](capturas/03_habilitado.png) |
| Enviar X=240, Y=250, Z=35 mm, 30 %, rumbo vacío | Movimiento aceptado `a6ce9629`, estado `MOVING` muestreado y cambio de pose visible en Webots. Luego «Secuencia de consignas terminada: Finalizaron las consignas; comprobar llegada en instrumentacion». | [Movimiento](capturas/04_webots_movimiento.png), [llegada UI](capturas/05_llegada.png), [llegada Webots](capturas/05_webots_llegada.png) |
| Comprobar llegada aparte del fin de consignas | Dos segundos simulados después del primer `completed`, error XYZ por sensores articulares de **0,0014715 mm** y error del TCP geométrico del mundo de **0,0043774 mm**, ambos menores que 1 mm. Errores articulares inferiores a 0,005 rad/0,5 mm y rumbo inferior a 0,02 rad. Las columnas visibles mostraron 240,00 / 250,00 / 35,00. `completed` por sí solo no se usó como llegada. | Estado y cálculo numérico en [informe.json](informe.json), paso 2; [telemetría](telemetria.jsonl) |
| Desde la llegada, enviar 73,2233 / 176,7767 / 34,6669 mm, rumbo 0°, 30 % | Mensaje visible: «Recorrido rechazado: Z-SoporteEfector-1 puede tocar 0-Torre-1 (envolventes y margen 1 mm)». **Rechazo local del cliente antes de encolar TCP**, sin nuevo ID de movimiento. Entre la captura de llegada y el reinicio siguiente hubo 91 muestras conectadas `IDLE`, con delta de consigna exactamente 0. Webots conservó la pose. No se atribuye este rechazo al controlador TCP; el caso TCP directo anterior conserva su alcance propio. | [Rechazo UI](capturas/06_choque_rechazado.png), [Webots sin movimiento](capturas/06_webots_sin_movimiento.png) |
| Reiniciar, habilitar e inyectar Hall J1 fijo Activo | Reset `232a329e`, habilitación `ddc9359a`, falla `203a8fff`. UI «Falla activa», Hall J1 «Activo»; estado `FAULT`, Hall nominal inactivo y falla inyectada explícita. El robot permaneció en la pose inicial. | [Hall activo](capturas/07_Hall_activo.png) |
| Intentar habilitar con falla activa | `5e50faae` rechazado: «Primero quitar las fallas inyectadas». Continuó `FAULT`, sin iniciar movimiento. | [Rearme bloqueado](capturas/08_rearme_bloqueado.png), [Webots Hall](capturas/08_webots_Hall_sin_movimiento.png) |
| Limpiar sin rearmar | `f26097a3` aceptado con `STOPPED`; UI «Detenido», Hall J1 «Inactivo» y fallas vacías. La ventana de unos 8 segundos de pared antes del rearme explícito conservó solo `STOPPED`: limpiar no habilitó. | [Limpio sin rearme](capturas/09_limpio_sin_rearme.png) |
| Habilitar explícitamente y terminar detenido | `4023a1bf` dio `IDLE`/«En espera»; después **Detener movimiento**, `e2c24ad9`, dio `STOPPED`/«Detenido». Carga 0, Hall inactivos, fallas vacías, referencia válida. | [Rearme explícito](capturas/10_rearme_explicito.png), [STOPPED UI](capturas/11_STOPPED.png), [STOPPED Webots](capturas/11_webots_STOPPED.png) |

Los inputs del destino rechazado y el selector «Hall Activo» quedan como valores del formulario al reiniciar/limpiar. El estado observado procede de las tablas y de la telemetría: después de limpiar la señal Hall pasó a Inactivo. No se confundieron formularios con estado físico.

## Evidencia y límites

Se conservaron 15 PNG reales, snapshots AX, [12 eventos con IDs y primeras observaciones](eventos.json), [estados clave](estados_clave.json) y 2162 snapshots suplementarios de `GET /api/state` cada 0,1 s de pared. Todas las órdenes se efectuaron mediante controles renderizados, no por HTTP de prueba. El muestreador solo leyó HTTP: no abrió un segundo TCP. El bridge publica eventos que recibió del único controlador TCP; no se hizo captura pcap. La consola de Webots identifica el mismo servidor. [Informe estructurado](informe.json) declara pasos, tolerancias, identidades y recursos.

Las capturas nativas muestran el robot y sus cambios de pose, más la consola. No se pretende contar ni inspeccionar individualmente las 39 instancias a partir de esas imágenes: esa identidad se hereda de las fuentes intactas del paquete final. El [log](webots.log) incluye un aviso GL de textura; la geometría coloreada fue visible y el flujo respondió. La evidencia visual es una secuencia de estados, no video ni medición continua. El paso físico es el configurado en el paquete (2 ms); la telemetría no acredita máximos entre muestras.

No se repitieron suites de software, auditorías CAD ni otros escenarios nativos: no hubo cambios al producto. No hace falta reconstruir el ZIP por esta entrega de informes. Física, TCP, Hall y referencias siguen provisionales; no hay validación de hardware, homing, detección autónoma de Hall ni autocolisión general. No se ejecutó ronda B, Windows ni Webots Linux nativo.

## Cierre y recuperación

Después de registrar STOPPED se cerraron solo los procesos propios: cliente PID 17505, Webots final 17964, controlador final 18495 y muestreador 17718; también se cerró la pestaña creada para la demo. El Webots propio inicial PID 17546 fue cerrado durante la preparación antes de lanzar la copia observable; sus fuentes no cambiaron. Los puertos 8765, 9000 y 1237 quedaron libres; el controlador ajeno PID 983 siguió escuchando 19051. No se alteró el mundo ajeno.

Se conservan extracción, app temporal y scripts privados hasta que sesión 9 revise el candidato y el director integre. [Manifiesto de incorporación](manifest.json) identifica únicamente evidencia bajo `validation/sesion7/`; no incluye app, scripts ni productos nuevos. La revisión independiente y la integración corresponden a sesión 9.
