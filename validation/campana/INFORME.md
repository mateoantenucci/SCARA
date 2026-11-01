# Campaña de validación en Webots (issue #18)

Evidencia vigente del sistema `scara/1`: la URC, el firmware compartido dentro del controlador de Webots y la planta simulada. Es la seam 3 de la [spec #2](https://github.com/mateoantenucci/SCARA/issues/2): escenarios en Webots registrados como evidencia, cada uno con su condición inicial, el resultado esperado, la tolerancia y la ejecución registrada.

**Reemplaza** al índice de validación del banco provisional `scara-dev/1` ([`docs/VALIDACION_WEBOTS.md`](../../docs/VALIDACION_WEBOTS.md)) y a su especificación de fallas ([`docs/FALLAS_Y_VALIDACION.md`](../../docs/FALLAS_Y_VALIDACION.md)). Esos documentos, la evidencia de `validation/historico/`, la de `validation/sesion*/` y los JSON sueltos de `validation/` son del banco viejo: quedan como registro del proceso y no se citan como prueba del sistema nuevo (D25). Los mueve a histórico el issue #1. Siguen vigentes los documentos que no dependen del control: CAD, montaje, colisiones, propiedades y transmisión.

## Versión ensayada

Campaña del 01/11/2026, registrada en [`campana.json`](campana.json):

| Qué | Valor |
| --- | --- |
| Commit | `COMMIT` |
| Controlador compilado (`scara_uci.exe`, `g++` 14.2 de Webots) | SHA-256 `SHA_EXE` |
| Mundo `scara_uci.wbt` | SHA-256 `SHA_WBT` |
| `SCARA.proto` | SHA-256 `SHA_PROTO` |
| Trayectorias de demostración | SHA-256 de cada archivo en `campana.json` |
| Entorno | Windows 11 Pro, Webots R2025a, Python 3.12.7; Webots minimizado, sin vista, a tiempo real |
| Configuración | Microstepping 1/8 (D9), planta N2 (D64), los límites de D45 |

El ejecutor compila el controlador antes de correr, así que el binario ensayado sale del commit registrado, y solo registra una campaña completa con el árbol sin cambios (D73). El commit es el de la rama del PR, que se mergea sin rebase.

## Cómo repetirla

Desde la raíz del repo, con el árbol sin cambios sin commitear:

```sh
python validation/campana/campana.py
```

Dura unos 20 minutos. Corre, uno detrás de otro, los ocho ensayos en Webots, y deja `campana.json` y los registros en [`registros/`](registros/). Con nombres de ensayos (`python validation/campana/campana.py homing`) corre solo esos y deja sus registros en un temporal. Los puertos van del 9100 al 9121: puede correr con una URC y un Webots abiertos en 9000 y 9001.

## Escenarios

Cada ensayo verifica las tolerancias con `assert` y se corta en la primera que no se cumple. Un escenario pasa si todos sus ensayos terminan con `ENSAYO OK`. Los registros están en unidades de `scara/1`: centésimas de grado en J1–J3 y centésimas de mm en J4. Un paso de 1/8 es 0,05625° en J1–J3; un paso completo, 0,45°.

| Id | Escenario | Condición inicial | Resultado esperado | Tolerancia | Resultado | Evidencia |
| --- | --- | --- | --- | --- | --- | --- |
| H1 | Homing desde el reposo | Mundo en la pose de reposo, sin referencia | Sin referencia, el jog de J4 va a 5 mm/s y lo frena su Hall. El homing referencia J4, J1, J2 y J3 en el flanco de cada Hall y vuelve solo al reposo, sin choques | Flanco y reposo a ≤ 3 pasos; jog a 5 ± 0,25 mm/s | **OK** | [homing](registros/homing.log), corrida A |
| H2 | Homing con desvío | Desvío al azar de hasta ±10° en J1–J3 (el del mundo) | El homing termina igual en el reposo, también repetido después de uno abortado | Reposo a ≤ 3 pasos; física contra estimada a menos de un paso completo | **OK** | [homing](registros/homing.log), corrida B; [campaña](registros/campana.log), paso 2 |
| T1 | Teach & play | Referenciado en el reposo | Tres puntos capturados después de un jog se guardan, se cargan sin cambios y se reproducen: tramo 0 PTP, LIN, PTP con espera | Estimada en el último punto a < 1 paso; física a menos de un paso completo | **OK** | [campaña](registros/campana.log), paso 3 |
| T2 | Reproducción LIN y PTP con loop, pausa y stop | Referenciado; trayectoria mixta de 4 puntos | Cada tramo dura lo planificado y los LIN siguen la recta; la pausa conserva la recta; stop descarta lo pendiente | ± 0,12 s por tramo; recta ≤ 0,32 mm | **OK** | [reproducción](registros/reproduccion.log), pasos 1–3 |
| T3 | Trayectorias de demostración | Referenciado; cada `trayectorias/demo-*.json` | Se cargan y se reproducen sin errores ni `EV LOST`, y terminan en su último punto | Como T1 | **OK** | [campaña](registros/campana.log), paso 4; [`tests/test_demos.py`](../../tests/test_demos.py) |
| F1 | Pérdida de pasos | Referenciado, 5 kg; M4 al 50 % (carga) o M1 al 20 % (aceleración) | Sin falla no se pierden pasos; con falla, `EV LOST` al entrar en un imán, referencia dudosa y un homing la limpia | `EV LOST` = pasos perdidos ± 1 paso completo | **OK** | [pérdida de pasos](registros/perdida_pasos.log) |
| F2 | Driver de M4 sin corriente | Referenciado, J4 en 60 mm | J4 simulado cae y la estimada no cambia; al volver la corriente, retiene J4 donde quedó | J4 simulado > 118 mm; estimada ± 0,01 mm | **OK** | [instrumentación](registros/instrumentacion.log), paso 2 |
| F3a | Hall trabado activo | Sin referencia; Hall de J4 activo | El homing aborta con `ERR 12 trabado` | Sin referencia | **OK** | [instrumentación](registros/instrumentacion.log), paso 3 |
| F3b | Hall trabado inactivo | Desvío, sin referencia; Hall de J1 inactivo | El homing referencia J4 y aborta con `ERR 11 ausente`; con el Hall libre, se repite y termina | Solo J4 encontrado; sin referencia | **OK** | [campaña](registros/campana.log), pasos 1–2 |
| F4 | Enlace cortado | Jog de J1 en marcha | El estado deja de llegar y el watchdog frena; al volver, el robot está quieto; con la URC cortada, la UCI se reconecta sin `BOOT` | J1 quieto (≤ 1 paso) 2,5 s después del corte | **OK** | [instrumentación](registros/instrumentacion.log), paso 4; [protocolo](registros/protocolo.log), paso 5 |
| F5 | Reinicio de la UCI | Referenciado, quieto o en plena reproducción | `BOOT` inesperado: sin referencia ni corriente, J4 cae; la reproducción se detiene y no se puede volver a dar play | Un `BOOT` más; reproducción «detenida» | **OK** | [instrumentación](registros/instrumentacion.log), paso 5; [campaña](registros/campana.log), paso 5; [reproducción](registros/reproduccion.log), paso 4 |
| P1 | Protocolo `scara/1` | Reposo, sin corriente | Corriente, referencia manual, `STOP`, `HALT`, watchdog, `DISABLE` y reinicio, como dice el protocolo | Estados y mensajes exactos | **OK** | [protocolo](registros/protocolo.log) |
| P2 | Transmisión N1 | Referenciado en el reposo | Jog articular de a una articulación; M1 cambia J1 y J2 y no el rumbo; J3 en escalones de un paso | ≤ 1 paso; escalón de 0,05625° | **OK** | [transmisión](registros/transmision.log) |
| P3 | Segmentos y tramo PTP | Referenciado en el reposo | Llegada conjunta en el tiempo planificado; la cola absorbe 200 ms; `STOP` con rampa | Las del [informe de segmentos](../segmentos/INFORME.md) | **OK** | [segmentos](registros/segmentos.log) |

El detalle de cada ensayo reusado, lo que mide y por qué, está en el informe de su issue: [protocolo](../../docs/UCI_WEBOTS.md#ensayo-del-protocolo-completo-issue-6) (#6), [transmisión](../transmision/INFORME.md) (#7), [segmentos](../segmentos/INFORME.md) (#9), [homing](../homing/INFORME.md) (#8), [instrumentación y F2–F5](../instrumentacion/INFORME.md) (#14), [pérdida de pasos y F1](../perdida_pasos/INFORME.md) (#15) y [reproducción](../reproduccion/INFORME.md) (#13). Sus registros de entonces quedan como estaban; los de esta campaña son los de [`registros/`](registros/).

## Lo que agrega esta campaña

[`ensayo_webots.py`](ensayo_webots.py) cubre lo que ningún ensayo anterior probaba. Arranca como lo ve el operador: cerca del reposo, con el desvío al azar y sin referencia. Valores del [registro](registros/campana.log):

| Paso | Qué se hizo | Qué se midió |
| --- | --- | --- |
| 1 | F3: Hall de J1 trabado inactivo, homing | J4 se referenció; J1 recorrió su búsqueda sin ver el imán y el homing abortó con `ERR 11 ausente`. Máscara `1000`, sin referencia |
| 2 | Hall libre, homing de nuevo | J4, J1, J2 y J3; reposo con la física a PASO2 de la estimada |
| 3 | Jog, captura de tres puntos, guardar, cargar y reproducir | TEACH |
| 4 | Las tres demos al 100 % | DEMOS |
| 5 | F5 en plena reproducción sin fin de `demo-pick-and-place.json` | F5 |

Los tiempos de los pasos 3 y 4 son del reloj de la PC, con la validación previa incluida, y Webots fue a ~0,8× del tiempo real. La precisión de los tiempos la mide, con el reloj simulado, el ensayo de la reproducción (T2).

## Trayectorias de demostración

En [`trayectorias/`](../../trayectorias/), la carpeta por defecto de la URC: con `python -m urc.app`, aparecen en «Cargar» (D74).

| Archivo | Qué muestra | Tramos |
| --- | --- | --- |
| `demo-pick-and-place.json` | Tomar y dejar en dos estaciones: bajar y subir en recta, con 1 s de espera abajo, y cruzar en PTP | 6 puntos: PTP, LIN, LIN, PTP, LIN, LIN |
| `demo-cuadrado-lin.json` | Un cuadrado de 80 mm en el plano, a altura y rumbo fijos: el extremo sigue rectas | 5 puntos LIN (el último cierra en el primero) |
| `demo-barrido-ptp.json` | De −90° a +90° en J1 y un cambio de codo: el menor recorrido, donde una recta sería imposible | 4 puntos PTP |

[`tests/test_demos.py`](../../tests/test_demos.py) carga cada una por HTTP y la reproduce en loop de 2 vueltas desde el reposo con una UCI falsa: valida todos sus tramos, la vuelta y el tramo de aproximación. Si un cambio de límites, del modelo o del planificador invalida una demo, la suite lo dice antes de la defensa.

## Pruebas automáticas (seams 1 y 2)

Sin Webots, `python -m unittest discover` corre:

- **Firmware por su protocolo, en la PC:** las conversaciones de conformidad de [`firmware/test/conversaciones/`](../../firmware/test/conversaciones/) contra el núcleo C++ compilado con una capa de hardware falsa, y la compilación para el UNO (UNO_FLASH B de flash y UNO_RAM B de RAM).
- **URC por sus dos bordes:** las mismas conversaciones contra la URC con una UCI falsa por TCP, y los endpoints HTTP del jog, el gestor, la reproducción y el banco; el planificador como módulo puro.
- **La planta:** el modelo N2 de los motores y los flancos de los Hall contra la geometría del proto.
- **Esta campaña:** [`tests/test_campana.py`](../../tests/test_campana.py) verifica que cada escenario tiene condición inicial, resultado, tolerancia y un ensayo que existe, y que el último registro los trae a todos aprobados, con la versión identificada.

Resultado en el commit ensayado: SUITE.

## Límites

- **Solo Windows.** macOS queda pendiente de verificar (D19).
- **Sin mirar la ventana de Webots:** los ensayos corren minimizados, por la URC y el canal de instrumentación. Lo visual queda para la QA humana de la R6 (recorrido en el PR del issue #18).
- **Parámetros provisionales:** límites articulares, envolventes de colisión, ubicación de los Hall (D10) y los motores de N2, que son de la familia más cercana o supuestos declarados ([ADR 0001](../../docs/adr/0001-simulacion-del-diseno-sin-hardware.md)). La campaña prueba el diseño simulado, no un robot construido.
- **N2 sin términos cruzados ni modelo eléctrico** ([ADR 0006](../../docs/adr/0006-modelo-de-motores-pasos-y-perdida-de-pasos.md)).
- **El jog del teach (T1) va por órdenes `JOG` de `scara/1`**, no por el jog de la URC, que cambia con el jog cartesiano (#11). El jog de la URC lo prueban sus endpoints HTTP.
